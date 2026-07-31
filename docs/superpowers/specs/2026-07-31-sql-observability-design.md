# Observabilité des requêtes SQL — design

**Issue** : [#89](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/89)
**Date** : 2026-07-31
**Statut** : design validé, à implémenter

## Le problème

Rien aujourd'hui ne permet de savoir ce qu'une requête coûte : pas de durée, pas
de compte, pas de trace. La seule instrumentation de `app/core/database.py` est
un listener `connect` qui corrige `lower()`/`upper()` sur les accents en SQLite —
rien sur les performances. On ne peut donc ni constater qu'une requête part en
balayage complet, ni voir une jointure devenir chère quand la base grossit, ni
repérer un N+1 dans la boucle d'import.

La base est encore petite : l'intérêt est de disposer de la mesure **avant** que
la latence se voie en production (Render + Supabase), pas après.

**Correction au libellé de l'issue** : la requête citée,
`participation_repository.existing_participations_for_course`, n'existe pas sous
ce nom. Le chargement visé est `participation_repository.list_for_course`
(`joinedload(Participation.athlete)`), appelé une fois par course par
`ParticipationIndexer._index_course` — puis **une seconde fois** par `finalize()`
pour `quality.analyze`.

## Décisions de cadrage

| Question | Décision |
| --- | --- |
| Usage visé | **Deux niveaux** : un seuil de lenteur toujours actif, plus un bilan verbeux activable |
| Périmètre | **API web *et* batches CLI** — les listeners vivent sur l'Engine, les deux en héritent |
| Forme du verbeux | **Bilan par unité de travail** (requête HTTP, épreuve importée), avec top-N des requêtes par occurrence |
| Seuil par défaut | **100 ms**, niveau **WARNING**, réglable |
| Contenu journalisé | **SQL paramétré seul** — jamais les paramètres liés |
| EXPLAIN / audit d'index | **Hors périmètre** — sondage séparé, mené *avec* l'outil livré ici |
| OpenTelemetry | **Dans le périmètre**, sans collecteur : SDK + instrumentations, exporter réglable, éteint par défaut |
| Articulation des deux étages | **Indépendants**, activables séparément, aucun lien de code |

### Pourquoi le bilan agrégé plutôt qu'un journal brut

Un journal ligne à ligne d'un import de 1 810 participants produit des milliers
d'enregistrements à dépouiller à la main. Le bilan agrégé rend le N+1 lisible
d'un coup d'œil :

```
import epreuve=La Baule M 2022 | 1812 requêtes | 4.2s SQL
  x1810  SELECT athletes.id, athletes.nom, … FROM athletes WHERE lower(nom) = ?
  x1     SELECT participations.… FROM participations JOIN athletes …
  x1     SELECT courses.… FROM courses WHERE source_url = ?
```

### Pourquoi le SQL paramétré seul

Les paramètres liés portent des noms d'athlètes et des libellés de club — des
données personnelles qui partiraient chez Render et dans toute ingestion en aval.
La forme paramétrée sert par ailleurs de **clé d'agrégation** du compteur : c'est
elle qui fait apparaître le `x1810`.

### Pourquoi OTel maintenant, sans collecteur

L'étage OTel n'apporte rien tant qu'aucun collecteur ne reçoit ses spans —
l'exporter `console` rend précisément le mur de lignes qu'on écarte plus haut.
Il est posé maintenant pour que le branchement futur soit **deux variables
d'environnement et zéro code**. Il ne remplace pas l'étage maison : OTel exporte,
il n'alerte pas ; le seuil à 100 ms reste l'affaire des listeners.

## Architecture

Deux modules nouveaux dans `app/core/`, sans dépendance l'un envers l'autre.

### `app/core/sql_observability.py` — étage maison

- **`install(engine)`** pose `before_cursor_execute` / `after_cursor_execute` sur
  l'engine **passé en argument**, jamais sur la classe `Engine`. Le listener
  SQLite existant est posé sur la classe et le reste : on ne le touche pas.
  L'argument explicite est ce qui rend le module testable sur un engine SQLite
  jetable sans instrumenter la suite entière.
- **Chronométrage** : `perf_counter()` au départ, empilé dans `conn.info` — le
  patron officiel de la documentation SQLAlchemy. Une **pile** et non une valeur
  simple, pour tenir la réentrance ; `conn.info` est propre à la `Connection`,
  donc au thread qui l'utilise. L'`ExecutionContext` passé aux listeners serait
  plus direct mais vaut `None` sur certaines exécutions.
- **`QueryStats`** : accumulateur (`count`, `total_ms`, `Counter` de requêtes
  normalisées), porté par un `ContextVar`.
- **`measure_queries(label)`** : context manager qui ouvre un accumulateur, le
  referme dans un `finally` et émet le bilan.
- **Normalisation** : espaces compressés sur une ligne, troncature à 200
  caractères. Cette forme est à la fois ce qui est journalisé et la clé
  d'agrégation.
- **Top-N** : 5 entrées, constante de module. Le rendre réglable serait du
  sur-outillage.

### `app/core/tracing.py` — étage OTel

Une fonction, `setup_tracing(app=None, engine=None)`, appelée par `create_app()`
et par le point d'entrée CLI. Elle **sort immédiatement** si `otel_enabled` est
faux, et les imports `opentelemetry.*` sont faits **à l'intérieur** : process
éteint, aucun paquet OTel n'est chargé.

Allumée, elle construit un `TracerProvider` (avec `Resource`), pose
`FastAPIInstrumentor` quand une app est fournie et `SQLAlchemyInstrumentor` quand
un engine l'est.

Le provider est passé **explicitement** aux deux instrumentations, et le module
l'expose par un accesseur. Les spans ne dépendent donc pas du provider global :
`trace.set_tracer_provider()` n'accepte qu'un seul appel par process — un second
est ignoré avec un simple avertissement — ce qui rendrait tout test allumant OTel
dépendant de son ordre d'exécution.

### Points d'accrochage dans l'existant

| Fichier | Ajout |
| --- | --- |
| `app/core/database.py` | `sql_observability.install(engine)` après `create_engine` |
| `app/main.py` | middleware ASGI ouvrant `measure_queries("<méthode> <chemin>")`, monté **seulement** si le bilan est activé ; appel à `setup_tracing(app, engine)` |
| `app/services/batch.py` | `_import_one` enveloppé dans `measure_queries(item.label)` — une épreuve = une unité |
| `app/cli/__init__.py` | `setup_tracing(engine=engine)` et fermeture du provider en fin de commande |
| `app/core/config.py` | trois réglages (ci-dessous) |
| `backend/pyproject.toml` | quatre dépendances OTel |

Rien d'autre ne bouge : ni les repositories, ni les services, ni les scrapers.

**Middleware ASGI pur, pas `BaseHTTPMiddleware`** : ce dernier exécute la suite
dans une tâche anyio séparée, ce qui rend la propagation du `ContextVar` subtile.
Une classe `__call__(scope, receive, send)` d'une quinzaine de lignes ne pose pas
la question.

## Réglages

```python
# ── Observabilité SQL ─────────────────────────────────────────────────────
sql_slow_query_ms: int = 100    # 0 → aucun log de lenteur
sql_query_stats: bool = False   # bilan par unité de travail
otel_enabled: bool = False      # étage OpenTelemetry
```

Lus **au démarrage du process**, pas par requête — `get_settings()` est déjà en
`lru_cache`. Corollaire assumé : allumer le bilan demande un redémarrage.

Si `sql_slow_query_ms <= 0` **et** `sql_query_stats` faux, `install()` ne pose
aucun listener : l'échappatoire pour un coût strictement nul.

**Rien de plus côté OTel** : la configuration passe par les variables **standard**
`OTEL_TRACES_EXPORTER`, `OTEL_EXPORTER_OTLP_ENDPOINT` et `OTEL_SERVICE_NAME`. Les
redéclarer dans `Settings` créerait deux sources de vérité.

Attention, elles ne sont pas toutes lues au même endroit. `OTEL_SERVICE_NAME` est
lu par `Resource.create()` et `OTEL_EXPORTER_OTLP_ENDPOINT` par l'exporter OTLP
lui-même : rien à écrire. `OTEL_TRACES_EXPORTER`, en revanche, n'est interprété
que par le lanceur `opentelemetry-instrument`, que nous n'utilisons pas — c'est
donc **`setup_tracing()` qui la lit** et choisit l'exporter (`none` par défaut,
`console`, `otlp`), en respectant la sémantique standard.

Conséquence à ne pas manquer : `ConsoleSpanExporter` écrit sur **stdout** par
défaut, ce qui casserait `… --json | jq` sur la CLI. Il est donc construit avec
`out=sys.stderr`.

`OTEL_ENABLED` n'est **pas** une variable standard OTel — c'est notre
interrupteur, et lui seul décide si `setup_tracing()` fait quoi que ce soit. Le
standard `OTEL_SDK_DISABLED` n'est pas consulté par notre code : il ne prend
effet qu'une fois le SDK chargé, donc uniquement en aval de notre interrupteur.

Branchement futur d'un collecteur :

```bash
OTEL_ENABLED=true
OTEL_TRACES_EXPORTER=otlp
OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example/v1/traces
```

## Sorties

Logger dédié **`app.sql`**, donc filtrable en aval.

- **Requête lente** → WARNING, une ligne : durée + SQL normalisé.
- **Bilan** → INFO, émis en **plusieurs enregistrements** : une synthèse, puis
  jusqu'à 5 lignes de détail. **Jamais un message multi-ligne** : le formateur
  JSON de `app/core/logging.py` construit son objet à la main
  (`"message":"%(message)s"`), et un retour à la ligne brut dans le message
  casserait le JSON.
- **Jamais de paramètres liés**, ni dans la ligne de lenteur, ni dans le bilan.

Côté CLI, `setup_logging(sys.stderr)` est déjà en place : l'invariant « stdout
reste parsable » tient sans rien ajouter.

## Dépendances

Quatre paquets aux dépendances **principales** de `backend/pyproject.toml` :
`opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`,
`opentelemetry-instrumentation-sqlalchemy`,
`opentelemetry-exporter-otlp-proto-http` (plus leurs transitifs).

Pas un extra optionnel : sinon allumer OTel en production supposerait de changer
l'installation. L'import paresseux dans `setup_tracing()` fait qu'éteint, ils ne
sont pas chargés.

Les paquets `instrumentation-*` s'épinglent sur des plages de versions de FastAPI
et SQLAlchemy : la compatibilité se vérifie au moment du plan, avec `uv sync`.

## Cas limites et choix assumés

- **Une requête qui lève** n'est ni chronométrée ni comptée : SQLAlchemy
  n'appelle pas `after_cursor_execute`. Sans conséquence — l'échec remonte déjà
  en exception, et le chrono vit sur le contexte d'exécution, jeté avec lui.
- **Imbrication** de deux `measure_queries` : la plus proche gagne, sans
  sommation vers l'englobante. Rien dans le code actuel ne les imbrique ; la
  règle est écrite plutôt que découverte.
- **Pas de `try`/`except` autour des listeners** : un `except` silencieux à cet
  endroit masquerait ses propres bugs, et une exception dans un listener
  SQLAlchemy remonte dans la requête applicative. C'est précisément pourquoi le
  corps doit rester trivial et sans I/O.
- **`measure_queries` referme dans un `finally`** : une épreuve qui plante rend
  quand même son bilan. C'est celle-là qu'on veut mesurer.
- **Concurrence** : un `ContextVar` est propre à la tâche ou au thread, donc deux
  requêtes HTTP simultanées ont deux accumulateurs distincts.
- **Batches CLI et spans OTel** : un batch est un process court et le
  `BatchSpanProcessor` exporte de façon différée. Sans `shutdown()` du provider
  en fin de commande, les spans du dernier import sont perdus.

## Tests

Nouveau fichier `tests/test_core/test_sql_observability.py`, engine SQLite en
mémoire, sans réseau. Les tests s'écrivent **avant** l'implémentation
(constitution, Principe III).

**Étage maison** :

1. Seuil franchi → un WARNING sur `app.sql`.
2. Seuil non franchi → aucun enregistrement.
3. `sql_slow_query_ms=0` et bilan éteint → aucun listener posé.
4. Trois SELECT identiques sous `measure_queries` → une entrée `x3`. **C'est le
   test qui prouve qu'un N+1 se voit** ; il vaut à lui seul la feature.
5. **Garde anti-fuite** : une requête liée à une valeur reconnaissable (`LEMÉE`)
   — cette valeur n'apparaît dans aucun enregistrement. Seul garant de la
   décision « SQL paramétré seul », donc test de non-régression à part entière.
6. Aucun message ne contient de retour à la ligne (garant du format JSON).
7. Bilan émis même quand le bloc enveloppé lève.
8. `TestClient` sur un endpoint réel, bilan activé → compte non nul. C'est ce qui
   vérifie que le `ContextVar` traverse le middleware ASGI, seul point du design
   qui ne se tranche pas au raisonnement.

**Étage OTel** :

9. Éteint, `setup_tracing()` ne pose aucune instrumentation **et ne charge aucun
    paquet OTel** — vérifié en rendant l'import fatal (`monkeypatch` sur
    `builtins.__import__` ou une entrée `None` dans `sys.modules`), et non par
    une inspection de `sys.modules` qu'un autre test aurait déjà peuplée.
10. Allumé avec un `InMemorySpanExporter`, une requête produit au moins un span
    SQL.

**Point de vigilance** : les instrumentations OTel sont globales et rémanentes.
Le test 10 doit désinstrumenter en teardown, sinon il contamine le reste de la
suite.

## Hors périmètre

- **EXPLAIN sur les requêtes chaudes et audit des index**
  (`participation.course_id`, `participation.bib_number`) : analyse à mener
  **avec** l'outil livré ici, dont le livrable est un sondage sous
  `docs/superpowers/specs/`. Les faire d'abord reviendrait à conclure sans
  mesure.
- **Collecteur OTel hébergé** : le jour venu, deux variables d'environnement.
- **Métriques et logs OTel** : seules les traces sont posées.
