# Research — Fan-out des heats Klikego

**Feature** : 005-klikego-fanout — [plan.md](./plan.md)

Résolution des points ouverts et validation des choix techniques avant génération des artefacts de design.

## Décision R1 — L'énumération des heats se lit dans `<el-select name="heat">`

**Décision** : parser le HTML de `GET /resultats/{event_id}` et extraire les couples `(slug, label)` depuis chaque `<el-option value="X"><span>Label</span></el-option>` du bloc `<el-select name="heat">…</el-select>`.

**Rationale** : constat direct du sondage 2026-07-31. Une première tentative avec `re.findall(r'heat=([^&<>\s"\']+)', html)` — le regex exact de `klikego._detect_heat` d'aujourd'hui — ne rend que **le heat courant** (répétitions du même slug dans les hrefs de la page affichée), pas les autres options. Sur Mesquer, la sonde initiale rendait `['swim-run-m-duo', 'swim-run-m-duo']` là où l'événement publie **8 heats**.

**Alternatives considérées** :
- Utiliser l'API `resultats-search.jsp?event=…` : elle attend déjà un `heat=X`, elle sert à la recherche de participants — pas de méta d'événement.
- Rechercher dans les `href="?heat=…"` : ils ne portent que la navigation vers d'autres pages Klikego (héro, partage), donc typiquement un seul heat.
- Playwright : rejeté (le HTML de la page événement porte le bon `<el-select>` en dur, aucun besoin de JavaScript pour l'énumérer).

**Implémentation prévue** :

```python
_RE_SELECT = re.compile(r'<el-select[^>]*name="heat"[^>]*>(.*?)</el-select>', re.DOTALL)
_RE_OPTION = re.compile(r'<el-option\s+value="([^"]+)"[^>]*>\s*<span>([^<]*)</span>')

def _enumerate_heats(html: str) -> list[tuple[str, str]]:
    """Retourne [(slug, label)] dans l'ordre du DOM. [] si <el-select> absent."""
    m = _RE_SELECT.search(html)
    if not m:
        return []
    return [(slug, label.strip()) for slug, label in _RE_OPTION.findall(m.group(1))]
```

**Cas absent de `<el-select>`** : 5 URLs du Sheet dans cette situation (URL d'inscription `/inscription/…`, page `resultats-challenge.jsp` du moteur T24, événement sans classement publié). Comportement : renvoyer une liste vide, laisser `import_service._require_event_name` produire l'erreur nominale (message : « nom d'épreuve introuvable »). Aucun changement.

## Décision R2 — Le fan-out s'implémente dans le scraper, pas dans `import_service`

**Décision** : `klikego.scrape_event_all(event_id, heat=None, event_name, slug)` boucle **en interne** sur les heats énumérés (si `heat` vide ou heat courant du site) et renvoie une liste plate de `ScrapedResult` couvrant plusieurs `event_type`. `KlikegoProvider.scrape_event_all(url)` supprime sa pré-résolution de heat (`_detect_heat`) et **ignore** `?heat=` de l'URL, sauf en mode `--single-heat`.

**Rationale** : symétrie totale avec Breizh Chrono (`breizhchrono.py:205-248` et `369-425`), qui fait déjà le fan-out au niveau du scraper depuis longtemps. `import_service` reçoit N `ScrapedResult` sur N `event_type` distincts et `_Persister.add()` construit N `Course` distinctes via `mapping.get_or_create_course` sans logique supplémentaire (cf. `courses_summary()` — déjà multi-courses). Le SSE `done` porte déjà `courses[]` (`import_service.py:395`), le hook front `useImportStream` porte déjà `state.courses` (`useImportStream.ts:69`).

**Alternative rejetée** — faire boucler `import_service` sur les heats : rejetée car (1) elle romprait la symétrie avec Breizh Chrono qui exposerait un contrat différent, (2) elle nécessiterait qu'`import_service` sache énumérer un heat au niveau du provider (fuite d'abstraction, viole le Principe II), (3) le SSE devrait émettre des sous-phases par heat, ce qui change son contrat (viole le Principe IV).

## Décision R3 — Un heat en échec n'annule pas les autres, **et est reporté**

**Décision** : la boucle de fan-out dans `klikego.scrape_event_all` **rattrape** les exceptions par heat, journalise (`logger.warning("Heat %s de %s en échec : %s", heat, event_id, exc)`), **et** collecte les échecs pour remontée en aval. Le canal de remontée est un dataclass `FanoutTrace` porté par le provider Klikego, lu par `import_service` pour peupler les compteurs SSE / CLI de FR-008.

**Structure retenue** — nouveau type au niveau du provider :

```python
@dataclass
class FanoutTrace:
    heats_enumerated: int      # rempli par le scraper
    heats_cached: int          # rempli par le scraper via cache_probe
    heats_imported: int        # dérivé : enumerated - cached - failed
    failures: list[dict]       # [{heat_slug: str, reason: str}], rempli par le scraper
```

Le scraper Klikego (fonction module `klikego.scrape_event_all`) retourne un `tuple[list[ScrapedResult], FanoutTrace]` — signature élargie, seul provider concerné. Le provider `KlikegoProvider.scrape_event_all(url, *, cache_probe=None)` conserve son contrat plat vis-à-vis du registre (`list[ScrapedResult]`) et **stocke la trace en attribut** `self.last_trace: FanoutTrace | None`. `import_service.iter_import_event` récupère la trace après `_scrape_all` et injecte les 5 clés dans la phase SSE `done`.

**Décompte `heats_cached` — le point clef** : le cache TTL vit dans `import_service._cached_result(db, event_url)` — mais il court-circuite l'import entier au niveau **URL globale**, pas au niveau heat. Pour compter par heat, on injecte un **callback `cache_probe`** :

```python
# Signature du provider
def scrape_event_all(self, url: str, *, cache_probe: Callable[[str], bool] | None = None) -> list[ScrapedResult]:
    ...

# Signature du scraper module
def scrape_event_all(event_id, heat, event_name, slug, *, cache_probe=None) -> tuple[list[ScrapedResult], FanoutTrace]:
    ...
```

Dans la boucle de fan-out, **avant** de scraper un heat, le scraper appelle `cache_probe(heat_url)` (URL de ce heat, `f"{BASE}/resultats/{slug}/{event_id}?heat={heat_slug}"`). Si le callback rend `True`, le scraper **saute** le heat et incrémente `trace.heats_cached`. Sinon il scrape normalement.

`import_service` construit `cache_probe = lambda heat_url: services.cache.is_fresh(course)` où `course` est trouvé par `course_repository.get_by_source_url(db, heat_url)` (nil → miss, sinon `is_fresh` juge). C'est **la même règle** que `_cached_result` mais au niveau heat, pas URL globale.

**Deux niveaux de cache complémentaires** :
- **Cache global URL** (existant) : si `_cached_result(db, event_url)` est frais, on court-circuite tout l'import — `iter_import_event` émet `done` avec les 4 compteurs à 0 et `courses=[]` d'origine (chemin cache TTL fresh, comportement inchangé — la vraie sémantique ici est « l'événement entier est frais »).
- **Cache par heat** (nouveau, via `cache_probe`) : au chemin non-cache global, on interroge le cache heat par heat. `heats_cached` compte donc **les heats individuellement frais** dans un import qui n'est pas globalement frais.

Les autres providers voient leur trace à vide (`heats_enumerated=1` si succès, `0` si échec global, `failures=[]`) — contrat SSE identique pour tous les providers, seule la valeur des compteurs change. **Ils ignorent `cache_probe`** : le signal est passé au provider via la signature élargie mais seul `KlikegoProvider` l'exploite en V1. Signature via `**kwargs` sur les autres providers pour préserver la compat.

**Fichiers touchés par `cache_probe`** :
- `backend/app/scrapers/registry.py::Provider.scrape_event_all(url, **kwargs)` — signature élargie côté Protocol.
- `backend/app/scrapers/registry.py::KlikegoProvider.scrape_event_all(url, *, cache_probe=None)` — utilise le kwarg.
- `backend/app/scrapers/klikego.py::scrape_event_all(..., *, cache_probe=None)` — la boucle interne.
- `backend/app/services/import_service.py::_scrape_all(url, *, cache_probe=None)` — passe le kwarg au provider.
- `backend/app/services/import_service.py::iter_import_event/import_event` — construit `cache_probe` avec la Session courante et le passe à `_scrape_all`.

**Rationale** : FR-004/FR-008/SC-004 exigent une remontée observable, pas juste un log Sentry. Un opérateur qui colle une URL dans `/ajouter` doit voir à l'écran quel heat a foiré. C'est aussi le Principe IV : le contrat SSE et le bilan CLI **doivent** porter cette information sans branche conditionnelle côté consommateur — d'où `failures=[]` sur un import sans échec plutôt qu'un champ absent.

**Alternatives rejetées** :
- **Singleton module (`klikego.LAST_FAILURES`)** : réentrance-hostile, deux imports concurrents s'écrasent.
- **Tuple `(results, trace)` sur tous les providers** : casse l'interface de tous les autres scrapers (BC, Wiclax, T2Area…) qui n'ont pas de trace à remonter.
- **Nouvelle phase SSE `warning`** : casse la compat descendante du contrat SSE.

**Contrepartie** : Breizh Chrono ne bénéficie pas de la remontée (son fan-out ne rattrape pas les échecs de heat aujourd'hui). Bénéfice indirect si un ticket futur adopte le même pattern. Hors scope V1.

## Décision R4 — `?heat=X` est ignoré dans le chemin nominal

**Décision** : `KlikegoProvider.scrape_event_all(url)` **ne lit plus** `parsed.query["heat"]` sur le chemin nominal. Le paramètre est ignoré. L'échappatoire `--single-heat` (voir R5) est le **seul** moyen de forcer un heat unique.

**Rationale** : A1. L'expérience utilisateur prime — coller une URL de heat depuis Klikego doit importer l'événement entier, comme A1 le décide. Corollaire : les 17 lignes `?heat=…` du Sheet (13 après dédup par événement) deviennent équivalentes à l'URL nue du même événement ; le cache TTL évite tout re-scraping.

**`Course.source_url` reste au niveau du heat** : dans la boucle interne, chaque heat construit son propre `ScrapedResult.source_url = f"{BASE}/resultats/{slug}/{event_id}?heat={heat}"` (contrat existant, cf. `klikego.scrape_event_all` actuel ligne 315-317). `_Persister` reçoit N scrapes avec N `source_url` distincts et écrit N `Course`, chacune avec sa propre clé de cache TTL. **Aucune migration**.

**Alternative rejetée — préserver la sémantique `?heat=X`** : cf. A1 dans la spec (option C d'origine). Rejetée : les 13 URLs `?heat=` du Sheet sont pour la plupart des liens copiés depuis Klikego, pas des ciblages délibérés ; forcer l'opérateur à retirer manuellement le paramètre est le friction que la feature veut supprimer.

## Décision R5 — Échappatoire CLI : `--single-heat` de `rescrape-db`

**Décision** : ajouter à `cli/commands/rescrape_db.py` une option `--single-heat` (nom retenu). Elle **doit** être combinée avec `--url` (une URL portant `?heat=X`), sinon erreur d'usage (code 2). Effet : le scraper Klikego lit `?heat=X` et n'importe **que** ce heat.

**Rationale** : A3. Voie d'échappement pour les cas de bord (heat cassé, embargo, curation manuelle post-fan-out). Distincte du chemin nominal — jamais activable par la seule forme d'URL, jamais exposée dans le Sheet ni dans l'UI.

**Contrat CLI** (à respecter pour rester conforme au Principe IV — CLI stable) :

| Combinaison | Comportement |
|-------------|--------------|
| `rescrape-db --url https://…?heat=X` | Fan-out complet (nominal). `?heat=` ignoré. |
| `rescrape-db --url https://…?heat=X --single-heat` | Heat unique X importé, pas de fan-out. |
| `rescrape-db --url https://…` (nue) + `--single-heat` | Erreur d'usage (code 2, message « `--single-heat` exige une URL avec `?heat=` »). |
| `rescrape-db --provider klikego --single-heat` | Erreur d'usage (code 2, `--single-heat` incompatible avec `--provider`/`--older-than` — pas de sens en mode filtre). |

**Alternative rejetée** — flag global sur la commande `import-sheet` : rejetée. `import-sheet` traite en masse depuis le Sheet ; un flag global tuerait le fan-out sur toutes les lignes. Le besoin est **par événement**, jamais par batch, ce qui pousse naturellement vers `rescrape-db --url --single-heat`.

## Décision R6 — Le récap `/ajouter` lit `state.courses`

**Décision** : `ImportProgress.tsx` rend, à la phase `done` et si `state.courses.length > 0`, une liste `[…, <Link href={`/courses/${c.id}`}>{c.name}</Link>, …]` — un lien par course créée. Le rendu s'applique à `N=1` aussi (pas de branche « singleton vs pluriel » qui perdrait l'info).

**Rationale** : A2. `useImportStream.ts:69` porte déjà `state.courses = ev.courses ?? []`. `_Persister.courses_summary()` construit déjà la liste depuis le SSE `done`. Aucune modification de contrat côté back — pur rendu front.

**Copywriting** : le récap dit combien de courses ont été créées (« N courses importées : ») et les liste avec leur `event_type` en petit chip. Frenchisation via clé `event_type` → libellé humain (utils déjà en place dans `frontend/lib/utils/format.ts`, cf. `formatToken` sur `/ajouter/page.tsx:39`).

**Alternative rejetée — redirection auto vers `/courses/<premier id>`** : rejetée (A2). L'opérateur perdrait l'info que N > 1 courses ont été créées.

## Décision R7 — Fixtures HTML pour les tests unitaires

**Décision** : capturer trois fichiers HTML statiques et les commiter dans `backend/tests/fixtures/klikego/` :

- `mesquer-2026-event.html` — page événement à 8 heats (Triathlon-et-Swimrun Mesquer, base du fix #153). Test de référence pour l'énumération.
- `nozeen-2025-no-select.html` — page sans `<el-select>` (Duathlon Nozéen). Test dégradation gracieuse.
- `mesquer-2026-heat-swimrun-m.html` — page **d'un** heat de Mesquer. Test que le heat existe et qu'un `_parse_detail` retourne du contenu.

**Rationale** : Principe III (TDD sans réseau, non-négociable). `pytest -m "not integration"` doit passer offline. Les HTML sont minimisés à ce que les regex et `_parse_detail` consomment (~15-25 Ko chacun, panel réel).

**Convention** : suffixe `.html`, chargement via `pathlib.Path(__file__).parent / "fixtures" / "klikego" / …`. Le test unitaire n'appelle pas `httpx` — il passe le HTML directement aux fonctions du scraper (`_enumerate_heats(html)`), qui doivent donc être exposables pour être testées.

## Décision R8 — Pas de migration Alembic, pas de nouvel endpoint

**Décision** : le schéma de la base est **inchangé**. Aucune nouvelle table, aucune colonne, aucun index. Aucun endpoint API ajouté ou modifié.

**Rationale** : le fan-out ré-utilise `Course.source_url = …?heat=X` comme clé, comportement identique à l'existant. `_Persister` gère déjà N courses par import (mapping.py:get_or_create_course, contrainte `UNIQUE(name, event_date, event_type)`). Aucun contrat API n'a besoin de bouger.

**Contre-vérification** : `git log --stat backend/alembic/versions/` sur la branche montre 0 nouveau fichier après implémentation. Un test contract implicite doit s'assurer qu'aucune nouvelle révision Alembic n'apparaît (tâche à créer par `/speckit-tasks`).

## Décision R9 — Le registre expose `get_provider(url) -> Provider | None`

**Décision** : ajouter à `backend/app/scrapers/registry.py` une fonction publique `get_provider(url: str) -> Provider | None` qui retourne l'**instance** de provider qui reconnaît l'URL (ou `None` si aucun ne matche). Cette fonction est distincte de `detect_provider(url) -> str | None` (existante) qui retourne le **slug** ; elle sert au chemin d'import qui a besoin de lire `provider.last_trace` après un scrape.

**Rationale** : `import_service.iter_import_event` doit lire `KlikegoProvider().last_trace` après `_scrape_all`. Avec l'API actuelle (`detect_provider` → slug + `scrape_event_all(url)` → results), la seule façon de récupérer l'instance est d'itérer sur `PROVIDERS` en appelant `matches(url)` — dupliquer la logique de dispatch. `get_provider` expose l'instance déjà nécessaire au dispatch interne.

**Implémentation** : `PROVIDERS` est déjà une liste globale d'instances (`registry.py:308` : `[…, KlikegoProvider(), …]`). `get_provider(url)` boucle sur `PROVIDERS` et retourne le premier dont `matches(url)` est vrai. Contrat identique à `detect_provider`, seule la valeur de retour change (instance vs slug).

**Alternative rejetée — dictionnaire `PROVIDERS_BY_SLUG`** : nécessite d'appeler `detect_provider(url)` puis d'accéder au dict, deux passes au lieu d'une. `get_provider` fait le vrai travail (matching) et rend directement l'instance utile.

**Test contract** : `tests/test_registry.py::test_get_provider_returns_instance` — pour chaque provider connu (klikego, breizhchrono, wiclax…), assert que `get_provider(url_exemple)` rend l'instance de la classe attendue ; pour une URL inconnue, rend `None`.

## Points laissés ouverts (pas de blocage)

- **Observabilité des heats en échec** : un canal SSE dédié (phase `warning`) pour signaler les heats sautés serait utile mais est **hors scope** V1. Un futur ticket peut l'ajouter sans casser le contrat existant.
- **Suppression du heat sur `Course.source_url`** : possibilité future d'utiliser l'URL nue de l'événement comme clé de cache pour l'énumération (une requête HTML de moins par re-import). Non priorisé — le coût actuel est marginal.
