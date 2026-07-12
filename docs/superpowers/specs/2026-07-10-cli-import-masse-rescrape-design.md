# CLI Typer — import de masse depuis le Google Sheet & rescrape des events en DB

**Date** : 2026-07-10
**Cible** : `backend/`
**Statut** : spec validée, plan à rédiger
**Issue** : [#32](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/32)

## Contexte & problème

Deux besoins d'outillage en ligne de commande autour du scraping :

1. **Amorcer la base** à partir du Google Sheet rempli par les adhérents (une
   ligne = une compétition, avec un lien vers les résultats).
2. **Rafraîchir la data** existante en re-scrapant périodiquement tous les
   events déjà stockés en DB (nouveaux finishers, corrections, splits…).

Le moteur d'import existe déjà : `app/services/import_service.import_event(db,
url, settings)` (scrape → dédup par `(course, dossard)` → persiste → indice de
fiabilité). La CLI **n'orchestre** que des appels à ce service ; elle n'ajoute
aucune logique métier de scraping.

Deux frictions bloquent aujourd'hui cet outillage :

- Aucun **point d'entrée CLI** hors HTTP : les scripts existants
  (`scripts/audit_scrapers.py`, `scripts/reset_db.py`) sont en **argparse** et
  n'ouvrent pas de `Session` ORM. Il n'existe pas de précédent Typer ni de
  context manager de session hors requête FastAPI.
- Le **cache TTL** court-circuite le re-scraping. `import_event` appelle
  `_cached_result` (→ `cache.is_fresh`) juste après la validation d'URL et avant
  le scraping ; si la course est fraîche, il renvoie immédiatement sans
  re-scraper. Impossible de forcer un rafraîchissement sans vieillir
  artificiellement `course.scraped_at`.

## Objectifs

- Un module CLI **Typer** (`backend/app/cli.py`) exposant deux commandes,
  invocable depuis `backend/` : `python -m app.cli import-sheet`,
  `python -m app.cli rescrape-db`.
- `import-sheet` : lit le CSV public du Sheet, dédoublonne les liens, importe les
  liens **supportés**, produit un **rapport** des non supportés / sans lien.
- `rescrape-db` : re-scrape tous les events en DB avec **bypass effectif** du
  cache TTL.
- Robustesse : un échec unitaire n'interrompt pas le batch, bilan final correct.
- Tests unitaires **sans réseau**.

Hors périmètre :

- Développement des scrapers manquants → suivi dans
  [#33](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/33).
- Planification automatique (cron Render) de `rescrape-db` → décision ultérieure.

## Approche retenue

**CLI mince par-dessus les services existants.** Aucune logique de scraping ni
d'accès direct à la DB : la CLI ouvre une `Session` via la fabrique existante et
délègue aux services/repositories (règle d'archi en couches
`api/cli → services → repositories → DB`). Trois modifications **chirurgicales**
hors CLI rendent l'orchestration possible ; tout le reste vit dans `app/cli.py`.

### Dépendance Typer

`typer` n'est **pas** déclaré : il n'arrive qu'en transitif via
`fastapi[standard]` → `fastapi-cli`. On l'**ajoute explicitement** à
`requirements.txt` (ne pas se reposer sur la transitivité). Pattern standard :

```python
import typer

app = typer.Typer(help="Outillage d'import de masse et de rescrape.")

@app.command("import-sheet")
def import_sheet(...): ...

@app.command("rescrape-db")
def rescrape_db(...): ...

if __name__ == "__main__":
    app()
```

## Changements hors CLI (chirurgicaux)

### 1. Flag `force` sur l'import

`import_service.import_event` et `iter_import_event` reçoivent
`force: bool = False`. Quand `True`, on **saute** l'appel à `_cached_result`
(seul point qui consulte `cache.is_fresh`) → le scraping a toujours lieu. Défaut
`False` : comportement de l'API SSE / `/scrape/event` **inchangé**.
`rescrape-db` passe `force=True` ; `import-sheet` garde `force=False` (le cache
est un atout à l'amorçage).

### 2. Context manager de session

`app/core/database.py` n'expose qu'un générateur `get_db()` (dépendance
FastAPI). On ajoute un `@contextlib.contextmanager session_scope()` réutilisable
pour ouvrir/fermer une `Session` hors requête HTTP :

```python
@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 3. Parcours de toutes les courses

`course_repository.list_all` est **paginé** uniquement. On ajoute un helper
`iter_all(db, *, provider=None, older_than_days=None)` (ou une variante non
paginée) renvoyant toutes les `Course`, filtrable par `provider` et par
ancienneté de `scraped_at`, pour alimenter `rescrape-db` sans fuite de requêtes
ORM hors repository.

## Commande 1 — `import-sheet`

Amorce la base depuis le Google Sheet des adhérents.

- **Source** : Sheet public, export CSV direct sans auth :
  `https://docs.google.com/spreadsheets/d/1rtiVRFOQUGcaWCTDPTR4xA9UL22UsWosKjsYMcRMsew/export?format=csv&gid=1961918487`.
  Téléchargement via **httpx** (déjà dépendance). URL par défaut configurable via
  option/env pour ne pas la figer.
- **Colonne des liens** : *« Donne-nous un lien pour accéder aux résultats. »*
  (10ᵉ colonne, ~1248 lignes). Parsing via le module standard `csv` ; sélection
  par **nom d'en-tête** (pas par index en dur) avec repli documenté.
- **Déduplication** : plusieurs adhérents renseignent le **même** lien. Dédup par
  **URL normalisée** avant de scraper. Normalisation **simple** : trim, host en
  minuscule, suppression du fragment `#…`, normalisation du slash final. Les
  liens **individuels** d'une même épreuve qui ne se dédupliquent pas trivialement
  sont couverts par le **cache TTL en filet de sécurité** (pas de dédup agressive
  « lien individuel → page d'épreuve »).
- **Détection** : `registry.detect_provider(url)`. `detect_provider` renvoie
  toujours un nom ; `"playwright"` = **non supporté pour l'import de masse**
  (son `scrape_event_all` lève, converti en `ProviderNotSupportedError`). Donc :
  supporté ⇔ `detect_provider(url) != "playwright"`. Si supporté → `import_event`
  (`force=False`). Sinon → **rapport**, jamais un échec.
- **Rapport de fin** : compteurs (importées / ignorées / en erreur) + table des
  liens **ignorés** groupés par **host** + volume, et lignes **sans lien**. Les
  providers non supportés sont suivis dans #33.

**Options** :

| Option | Effet |
| --- | --- |
| `--dry-run` | Détecte et dédoublonne, affiche ce qui serait importé, **ne persiste rien / ne scrape pas**. |
| `--limit N` | Borne le nombre d'épreuves (test). |
| `--only-provider <nom>` | Restreint à un provider (ex. `klikego`). |
| `--sheet-url <url>` | Override la source. |
| `--delay <s>` | Pause de politesse entre scrapes réels (défaut ~1 s). |
| `--json` | **stdout ne contient que le JSON** ; le rapport texte bascule sur stderr. |

## Commande 2 — `rescrape-db`

Parcourt toutes les `Course` en DB et relance l'import en **forçant** le
re-scraping.

- **Source des liens** : `course_repository` → `course.source_url` (clé de cache).
- **Bypass du cache TTL** : appel `import_event(db, course.source_url, settings,
  force=True)` → saute `_cached_result`. C'est le cœur de la commande.
- **Robustesse** : `try/except` par course, log + continue, bilan final.

**Options** :

| Option | Effet |
| --- | --- |
| `--dry-run` | Liste les épreuves qui seraient re-scrapées, sans écrire ni scraper. |
| `--older-than <jours>` | Ne re-scrape que les épreuves dont `scraped_at` dépasse N jours. |
| `--provider <nom>` | Restreint à un provider. |
| `--limit N` | Borne le nombre d'**épreuves** (arbitrage postérieur à ce design : les `Course` sont dédoublonnées par `source_url` avant le batch — une épreuve porte N courses en base, les heats — donc `--limit` et les compteurs comptent des épreuves, jamais des lignes de la table `course`). |
| `--delay <s>` | Pause de politesse entre scrapes (défaut ~1 s). |
| `--json` | **stdout ne contient que le JSON** ; le rapport texte bascule sur stderr. |

## Détails techniques & points d'attention

- **Session DB** : une `Session` par exécution via `session_scope()` ; DB touchée
  **uniquement** au travers des repositories/services (archi en couches).
- **Robustesse** : un lien qui échoue ne plante pas le batch → `try/except` par
  épreuve, log + continue, bilan final (importées / ignorées / en erreur).
- **Politesse / rate limiting** : `--delay` entre scrapes réels ; **jamais** de
  pause ni de scrape en `--dry-run`. Le cache TTL reste un second filet.
- **`force`** : `False` par défaut (API SSE inchangée) ; `rescrape-db` → `True`,
  `import-sheet` → `False`.
- **Sortie** : rapport texte lisible (compteurs + table des ignorés) sur **stdout**.
  `--json` est **exclusif** (arbitrage postérieur à ce design) : stdout ne porte
  alors **que** la ligne JSON, et le rapport texte bascule sur **stderr**, là où
  sort déjà la progression. Un humain voit toujours le rapport, et
  `… --json | jq` fonctionne sans découpage préalable — ce que le rendu « JSON
  **en plus** du texte » initialement prévu ici rendait impossible. En cas de
  Ctrl-C, la charge JSON est émise **avant** la sortie en code 130 : le bilan
  partiel n'est jamais perdu.
- **Codes de sortie** (arbitrage postérieur à ce design) :
  - `0` — succès, y compris **partiel** (quelques épreuves en échec sur N) et
    y compris « rien à faire » (zéro épreuve ciblée). Un dry-run sort toujours en 0.
  - `1` — **échec total** : aucune des épreuves ciblées n'a abouti
    (`batch.est_echec_total`). Sans lui, un cron dont les 53 épreuves échouent
    (site tiers down) sortait en 0 et n'alertait jamais. Le bilan reste émis
    **avant** la sortie.
  - `2` — **erreur d'usage** (convention Click) : option invalide, notamment un
    `--provider` / `--only-provider` inconnu (faute de frappe), rejeté par
    `cli/validators.valider_provider` **avant** tout travail. Auparavant, un
    `--provider kliego` filtrait 0 épreuve en silence et sortait en 0.
  - `130` — Ctrl-C (convention shell 128 + SIGINT). **Prioritaire sur 1** :
    l'interruption est une action de l'opérateur, pas une panne.
  Un tube fermé (`… | head -2`) ne modifie **aucun** de ces codes : le
  `BrokenPipeError` est rattrapé, le bilan bascule sur stderr.
- **Settings** : `settings = get_settings()` suffit (`import_event` ne consomme
  que les TTL de cache).

## Tests (sans réseau)

Pattern existant : **monkeypatch de `import_service.registry_scrape_event_all`**
(jamais le registry directement) et de `registry.detect_provider`. Fixture
`db_session` SQLite en mémoire (conftest).

Couverture minimale :

- **Parsing CSV** : depuis une string fixture (en-tête + lignes), extraction de la
  bonne colonne, lignes sans lien détectées.
- **Dédup** : liens identiques et variantes de normalisation (slash final,
  fragment, casse du host) collapsent en une seule entrée.
- **Détection / filtrage** : `"playwright"` classé non supporté → rapport ;
  providers supportés → import.
- **Orchestration & bilan** : compteurs corrects ; un échec unitaire (service qui
  lève) n'interrompt pas le batch.
- **`force`** : `import_event(..., force=True)` re-scrape même quand
  `cache.is_fresh` renverrait `True` (course fraîche) ; `force=False` conserve le
  court-circuit.
- **`--dry-run`** : aucune écriture DB, aucun scrape réel sur les deux commandes.

## Critères d'acceptation

- [ ] Module CLI Typer avec les deux commandes, invocable depuis `backend/`
      (`python -m app.cli import-sheet --dry-run`).
- [ ] `import-sheet` lit le CSV public, dédoublonne, importe les liens supportés,
      et produit un rapport des non supportés / sans lien.
- [ ] `rescrape-db` re-scrape tous les events en DB avec bypass effectif du cache
      TTL (flag `force`).
- [ ] `--dry-run` fonctionnel sur les deux commandes (aucune écriture DB, aucun
      scrape réel).
- [ ] Un échec unitaire n'interrompt pas le batch ; bilan final correct.
- [ ] Tests unitaires **sans réseau** (mock du registre / service) pour le parsing
      CSV, la dédup et l'orchestration.
- [ ] `typer` déclaré dans `requirements.txt`.
- [ ] `ruff check .` propre.
