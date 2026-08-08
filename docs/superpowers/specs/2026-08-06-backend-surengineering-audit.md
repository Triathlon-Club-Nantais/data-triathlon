# Audit sur-ingénierie — `backend/` (2026-08-06)

> Relevé fait à froid sur l'arbre complet de `backend/` (18 998 lignes `app/`,
> 29 378 lignes `tests/`, 802 `scripts/`, 757 `alembic/`), branche
> `ponytail-analyse`. **Appliqué le 2026-08-08** — voir « État d'application »
> en fin de document : 13 entrées sur 14 sont dans le code, la 14ᵉ est refusée
> avec sa raison. Le relevé ci-dessous est conservé **tel qu'il a été écrit**,
> y compris une erreur de comptage relevée à l'application (entrée n° 3).
>
> Périmètre : sur-ingénierie et complexité seulement. Ni bugs, ni sécurité, ni
> performance — ces axes relèvent d'une revue normale.
>
> Pendant côté frontend : [`2026-08-06-frontend-surengineering-audit.md`](2026-08-06-frontend-surengineering-audit.md).

## Comment lire

Chaque ligne nomme ce qui peut être **supprimé** et ce qui le remplace. Les
étiquettes :

| Étiquette | Sens |
|---|---|
| `delete` | code mort, souplesse jamais utilisée, fonctionnalité spéculative. Remplacement : rien. |
| `stdlib` | réimplémentation de ce que la bibliothèque standard livre déjà. |
| `yagni` | abstraction à une seule implémentation, config que personne ne règle, couche à un seul appelant. |
| `shrink` | même logique, moins de lignes. |

Le classement va de la plus grosse coupe à la plus petite. Les estimations de
lignes sont mesurées (`wc -l`), pas devinées.

## Récapitulatif

| # | Étiquette | Objet | Lignes | Deps | Risque |
|---|---|---|---:|---:|---|
| 1 | `delete` | socle OpenTelemetry | −383 | −4 | aucun (éteint par défaut) |
| 2 | `stdlib` | scan de ports `dev_server` | −110 | — | faible (dev only) |
| 3 | `yagni` | 11 sous-classes `HostMatchedProvider` | −45 | — | moyen (cœur du routage) |
| 4 | `shrink` | 6 copies de `HH:MM:SS` → secondes | −40 | — | faible |
| 5 | `delete` | `PlaywrightProvider` + `_FALLBACK` + `_find_provider` | −40 | — | **change une valeur d'API** |
| 6 | `shrink` | recopie de `BatchTotals` × 2 | −25 | — | faible (forme `--json` à préserver) |
| 7 | `delete` | 5 `_detect_event_type` | −20 | — | aucun |
| 8 | `shrink` | 3 boucles de dédoublonnage ordonné | −15 | — | faible |
| 9 | `yagni` | `sheet_source.is_supported` | −7 | — | aucun |
| 10 | `delete` | repli fichier `VERSION` | −7 | — | aucun |
| 11 | `yagni` | `app/api/v1/version.py` | −6 | — | aucun |
| 12 | `delete` | 6 `CLAUDE.md` ne contenant que `@AGENTS.md` | −6 fichiers | — | aucun |
| 13 | `stdlib` | 4 × `d[k] = d.get(k, 0) + 1` | −4 | — | aucun |
| 14 | `delete` | `python-dotenv` en dépendance directe | −1 | −1 | aucun |

**Net : ≈ −690 lignes, −5 déclarations de dépendances.**

---

## 1. `delete` — socle OpenTelemetry entier

`app/core/tracing.py` (139 l.), `tests/test_core/test_tracing.py` (238 l.),
`app/main.py:99-103`, `app/core/config.py:57`, et 4 dépendances
`opentelemetry-*` dans `pyproject.toml`.

Sa propre docstring porte le constat : « Aucun collecteur n'est hébergé à ce
jour : ce module est posé pour que le branchement futur tienne en deux variables
d'environnement et zéro code. » Le flag `otel_enabled` est `False` par défaut et
aucun déploiement ne le lève. C'est de l'infrastructure posée pour un futur qui
n'existe pas encore, avec 377 lignes et 4 deps (≈ 8 paquets installés en
transitif) de coût permanent.

**Remplacement : rien.** `setup_tracing` / `shutdown_tracing` se réécrivent en
~25 lignes le jour où un collecteur tourne réellement. `sql_observability.py`
(218 l.) reste : il alerte sur les requêtes lentes, ce qu'OTel ne fait pas — les
deux ne se recouvrent pas.

**Décision à prendre** : est-ce qu'un collecteur est prévu à court terme ? Si
oui, cette ligne se retire de l'audit et devient un ticket « brancher OTel ». Si
non, elle se supprime.

## 2. `stdlib` — le scan de ports de `dev_server`

`scripts/dev_server.py:67-101` et `:186-205`, plus la part correspondante de
`tests/test_scripts/test_dev_server.py` (200 l.).

À supprimer : `_is_free`, `find_free_port`, `DEFAULT_SPAN`,
`should_retry_after_exit`, `BIND_ATTEMPTS` et la boucle de reprise à 3 essais.

**Remplacement** — le noyau est déjà dans `socket` :

```python
def find_free_port(host: str = BIND_HOST) -> int:
    """Port libre attribué par l'OS (port 0)."""
    with socket.socket() as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]
```

La collision entre deux worktrees démarrés au même instant — ce qui justifiait
la boucle de reprise — vient du **point de départ déterministe à 8001** : deux
scans concurrents trouvent le même premier port libre. Un port éphémère tiré par
l'OS supprime la cause, donc le rattrapage. Le port reste publié dans
`.dev-backend.json`, `frontend/scripts/dev.mjs` continue de le lire sans
changement.

**Ceiling assumé** : `DEV_BACKEND_PORT` (port forcé) doit rester, c'est
l'échappatoire d'un dev qui veut un port stable. `DEV_BACKEND_PORT_BASE` perd son
sens et se supprime avec le scan.

## 3. `yagni` — 11 sous-classes `HostMatchedProvider` identiques

`app/scrapers/registry.py:233-333`.

`TimePulseProvider`, `ProLiveSportProvider`, `SportInnovationProvider`,
`RaceResultProvider`, `ChronoplaceProvider`, `OkTimeProvider`,
`CompetitorProvider`, `RunnerBreizhProvider`, `SporthiveProvider`,
`ChronoWebProvider` : chacune déclare `name`, `_HOSTS`, et un `scrape_event_all`
qui appelle `<module>.scrape_event_all(url)`. Rien d'autre. Ajouter un
chronométreur veut dire recopier ce squelette une douzième fois.

**Remplacement** : une classe générique et une table de données.

```python
class ModuleProvider(HostMatchedProvider):
    def __init__(self, name: str, hosts: tuple[str, ...], module) -> None:
        self.name, self._HOSTS, self._module = name, hosts, module

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return self._module.scrape_event_all(url)
```

Les 3 vrais cas particuliers restent des classes à part :
`KlikegoProvider` (fan-out, `last_trace`, `single_heat`), `BreizhChronoProvider`
(deux façades, deux moteurs), `WiclaxProvider` (`matches` composé sur le path),
`T2AreaProvider` (égalité stricte de host).

**Attention** : les commentaires par provider (pourquoi `ironman.com` chez
`competitor`, pourquoi `sporthive.com` sans `eventresults-api.speedhive.com`,
pourquoi les 3 façades RaceResult) sont de la connaissance mesurée — ils doivent
migrer dans la table, pas disparaître. C'est le point qui rend cette coupe moins
gratuite qu'elle n'en a l'air, et la raison de son risque « moyen ».

## 4. `shrink` — 6 implémentations de `HH:MM:SS` → secondes

| Fichier | Fonction | Comportement en cas d'échec |
|---|---|---|
| `app/scrapers/klikego.py:207` | `_secs` (locale) | `0` |
| `app/scrapers/timepulse.py:199` | `_secs` | `0` — **identique** à klikego |
| `app/scrapers/wiclax.py:334` | `_time_to_secs` | `0` |
| `app/scrapers/chronoweb.py:293` | `_seconds` | `0` |
| `app/scrapers/oktime.py:327` | `_secs` | `None` (distinction délibérée) |
| `app/services/stats_service.py:159` | `_seconds` | `None`, et tolère `MM:SS` |

Plus deux copies strictement identiques du sens inverse :
`timepulse.py:209` et `oktime.py:344` (`_fmt_secs`).

**Remplacement** : `to_seconds(t, *, strict=False)` et `fmt_seconds(s)` dans
`app/scrapers/utils.py`, qui héberge déjà `normalize_time` et
`derive_status_from_label`. Le `strict=True` rend `None` sur l'illisible — c'est
la distinction que `oktime` porte volontairement (« ce point ne porte pas de
durée » ≠ « ce point est illisible ») et qu'il ne faut pas écraser.

`stats_service` est le seul appelant hors `scrapers/` : soit il importe
`scrapers.utils` (couche basse, acceptable), soit la fonction remonte dans
`app/core/time.py`. À trancher au moment de le faire.

## 5. `delete` — `PlaywrightProvider`, `_FALLBACK`, `_find_provider`

`app/scrapers/registry.py:352-404` et `:440-449`.

`PlaywrightProvider` est une sentinelle de 26 lignes dont le seul rôle est de
capter tout (`matches` rend toujours `True`) puis de lever. Elle existe pour que
`_find_provider` rende toujours un objet — et `_find_provider` est un second
exemplaire de la boucle déjà écrite dans `get_provider`.

En prime, `is_supported` fait un détour :

```python
return detect_provider(url) in provider_names()   # reconstruit 14 noms pour un oui/non
```

**Remplacement** : `get_provider()` seul ; `scrape_event_all` lève sur `None` ;
`is_supported(url)` devient `get_provider(url) is not None`.

**⚠ Change une valeur d'API publique.** Sur une URL non reconnue,
`GET /api/v1/scrape/detect` rend aujourd'hui
`{"provider": "playwright", "supported": false}` et rendrait
`{"provider": "", "supported": false}`. À vérifier côté front avant de couper —
et c'est de toute façon un slug qui mentait : aucune dépendance `playwright`
n'existe plus dans le dépôt (supprimée en #102).

Le garde-fou verrouillé par
`test_host_non_reconnu_ne_declenche_aucune_requete` doit survivre à la coupe : il
teste qu'une URL inconnue ne déclenche aucune requête réseau, ce qui reste vrai
si `get_provider` rend `None`.

## 6. `shrink` — recopie champ par champ de `BatchTotals`

`app/services/bulk_import_service.py:25-34,105-111` et
`app/services/rescrape_service.py:84-94,178-186`.

`SheetOutcome` et `RescrapeOutcome` redéclarent chacune 7 champs de
`BatchTotals` (`imported`, `updated`, `skipped`, `errors`, `processed`,
`interrupted`, `failures`), puis les recopient un par un après l'appel à
`run_batch`. Soit 28 lignes qui ne font que transporter.

**Remplacement** : un champ `totals: BatchTotals` dans chaque `Outcome`, ou un
`_reporter(outcome, totals)` partagé. **Contrainte à respecter** : `asdict()`
alimente la sortie `--json` de la CLI, dont la forme est un contrat (le
pipeline `import-sheet --json | jq -r '.failures[].url' | rescrape-db --urls-from -`
documenté dans `rescrape_db`). Une imbrication change cette forme — il faut soit
aplatir à la sérialisation, soit garder les champs et ne factoriser que la
recopie.

## 7. `delete` — 5 `_detect_event_type`

`app/scrapers/klikego.py`, `timepulse.py`, `wiclax.py`, `sportinnovation.py`,
`prolivesport.py`.

Chacune est un wrapper de 2 lignes avec import différé :

```python
def _detect_event_type(name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(name)
```

Vestiges de la migration vers le classifieur unique (PR #10) : la logique a bien
été centralisée dans `app/scrapers/classify.py` — « seule source de vérité » dit
sa docstring — mais les points d'entrée par scraper sont restés.

**Remplacement** : appeler `classify.classify_event_type` sur les sites d'appel.
`klikego` passe un `contexte=slug`, les autres non — c'est le seul écart.

## 8. `shrink` — 3 boucles de dédoublonnage ordonné

`app/services/sheet_source.py:31` (`dedupe_links`),
`app/services/import_service.py:92` (`_merge_cached_courses`),
`app/services/rescrape_service.py:21` (`_dedupe_par_url`).

Trois fois le motif `seen: set` + `out: list` + `if key not in seen`. Les clés
diffèrent (URL normalisée, `course.id`, `source_url`), la boucle non.

**Remplacement** : un `dedupe_by(items, key)` partagé. `dict.fromkeys` ne suffit
pas ici : les trois conservent la **première** forme rencontrée et non la clé,
là où un dict garderait la dernière valeur.

## 9. `yagni` — `sheet_source.is_supported`

`app/services/sheet_source.py:70-76`. Sept lignes dont la docstring dit « simple
alias de `registry.is_supported` ». Un seul appelant : `bulk_import_service`, qui
importe déjà `registry` et l'appelle directement deux lignes plus bas.

**Remplacement** : `registry.is_supported` sur le site d'appel.

## 10. `delete` — le repli fichier `VERSION`

`app/version.py:36` et `:50-54`. La docstring porte elle-même le constat :
« **Rien dans ce dépôt ne l'écrit** : ni le Dockerfile, ni Render, dont le
`buildCommand` effectif est celui du dashboard et non celui de `render.yaml`.
C'est cette croyance qui a fait répondre "dev" en production pendant #134. »

**Remplacement** : `environ.get("APP_VERSION") or FALLBACK` — une ligne. Plus de
`Path`, plus de `try/except OSError`, `@lru_cache` devient superflu (lire une
variable d'environnement n'est pas un I/O).

## 11. `yagni` — `app/api/v1/version.py`

Un module de 18 lignes plus une entrée dans `router.py:17,27` pour une route qui
rend `{"version": …}`. **Remplacement** : la route dans `app/api/v1/health.py`
(24 l.), déjà le module des endpoints d'infra à une ligne.

## 12. `delete` — 6 `CLAUDE.md` ne contenant que `@AGENTS.md`

`app/api/`, `app/cli/`, `app/core/`, `app/models/`, `app/scrapers/`,
`app/services/auth/`. Six fichiers d'indirection pure.

**Remplacement** : rien — `AGENTS.md` est lu directement. À vérifier une fois sur
l'outillage réellement utilisé avant de couper (le `CLAUDE.md` racine fait la
même chose vers l'`AGENTS.md` racine et sert peut-être de garde-fou de
compatibilité).

## 13. `stdlib` — 4 × `d[k] = d.get(k, 0) + 1`

`app/services/bulk_import_service.py:83`, `app/services/stats_service.py:39,42`,
`app/services/import_service.py:424`.

**Remplacement** : `collections.Counter`, déjà importé dans `rescrape_service.py`
et `stats_service.py`.

## 14. `delete` — `python-dotenv` en dépendance directe

`pyproject.toml:8`. Jamais importé dans `app/`, `scripts/`, `tests/` ni
`alembic/` — vérifié par grep. C'est `pydantic-settings` qui l'utilise
(`env_file=".env"` dans `Settings.model_config`) et qui le tire en transitif.

**Remplacement** : rien, la ligne se retire.

---

## Hors périmètre, vu au passage

- Quatre bases SQLite résiduelles à la racine de `backend/` :
  `_alembic_tmp.db`, `_fresh_check.db`, `_smoke.db`, `_verify.db` (datées du
  2026-06-07/08). Ignorées par git, jamais suivies — mais elles traînent dans les
  worktrees.
- `triathlon.db` pèse 38 Mo en développement.

## Ce que l'audit n'a **pas** trouvé à couper

Pour éviter de rejuger ces points au prochain passage :

- **`app/core/http.py`** — le garde SSRF est dense mais chaque ligne porte une
  mesure (IDNA 2003 vs 2008, `raw_host`, mémo `getaddrinfo`). Rien à retirer.
- **`app/core/text.py`, `app/core/club.py`, `app/core/discipline.py`** — chacun
  existe pour tenir une définition **unique** de part et d'autre de la barrière
  Python/SQL. C'est l'inverse de la duplication.
- **Les repositories** (`identity`, `session`, `user`, `pending_provider`) — 3 à
  5 fonctions chacun, aucune indirection gratuite.
- **`app/services/progress.py`** (`ProgressReporter` + `NullReporter`) — un
  Protocol à 3 implémentations réelles (`Null`, `Plain`, `Rich`), pas une.
- **`app/services/auth/idp/`** (`base.py`, `registry.py`) — un seul fournisseur
  aujourd'hui (GitHub), donc formellement un candidat `yagni`. Épargné : le
  contrat opaque (`round_trip`) est justifié ligne à ligne par ce qu'il évite à
  l'arrivée d'un second fournisseur, et le registre est ce qui garantit
  qu'aucune doublure de test n'est atteignable en production (FR-034). Coût
  réel : ~110 lignes. À rejuger seulement si aucun second fournisseur n'arrive.
- **`app/core/time.py`** (7 lignes pour `utcnow()`) — point d'injection unique
  des tests et garde contre `datetime.utcnow()` déprécié.

## État d'application (2026-08-08)

Appliqué en quatre commits, dans l'ordre suggéré ci-dessus.

| # | Objet | État |
|---|---|---|
| 1 | socle OpenTelemetry | ✅ supprimé — `7eea9ed` |
| 2 | scan de ports `dev_server` | ✅ port éphémère — `829447b` |
| 3 | sous-classes `HostMatchedProvider` | ⚠️ appliqué sur **5**, pas 11 — `42afcfd` |
| 4 | 6 copies de `HH:MM:SS` → secondes | ✅ `utils.to_seconds` / `fmt_seconds` — `829447b` |
| 5 | `PlaywrightProvider` + `_FALLBACK` + `_find_provider` | ✅ supprimés — `42afcfd` |
| 6 | recopie de `BatchTotals` | ✅ `batch.reporter_totals` — `829447b` |
| 7 | 5 `_detect_event_type` | ✅ `dbd73b8` |
| 8 | dédoublonnage ordonné | ⚠️ partiel — `829447b` |
| 9 | `sheet_source.is_supported` | ✅ `dbd73b8` |
| 10 | repli fichier `VERSION` | ✅ `dbd73b8` |
| 11 | `app/api/v1/version.py` | ✅ fusionné dans `health.py` — `dbd73b8` |
| 12 | 6 `CLAUDE.md` d'une ligne | ❌ **refusé** (voir ci-dessous) |
| 13 | 4 × `d[k] = d.get(k, 0) + 1` | ✅ `collections.Counter` — `dbd73b8` |
| 14 | `python-dotenv` | ✅ `dbd73b8` |

**Trois écarts, et leurs raisons.**

- **n° 3 — l'audit a compté onze classes triviales, il y en avait cinq.** Il a
  rangé parmi elles `RaceResultProvider`, `ChronoplaceProvider`,
  `OkTimeProvider`, `SporthiveProvider` et `ChronoWebProvider`, qui portent tous
  un fan-out et une `last_trace` : leur `scrape_event_all` n'est pas une
  délégation d'une ligne. Seules `TimePulse`, `ProLiveSport`, `SportInnovation`,
  `Competitor` et `RunnerBreizh` sont devenues des entrées `ModuleProvider`.
  Le quintette fan-out partage bien, lui aussi, un motif (`__init__` posant
  `last_trace`, puis la bascule `single_heat` / `scrape_event_fanout`) : c'est
  une factorisation **distincte**, à instruire à part, sur le code le plus
  sensible du dépôt.
- **n° 8 — pas de `dedupe_by` partagé.** Le troisième site,
  `import_service._merge_cached_courses`, n'est pas un dédoublonnage mais une
  fusion à `seen` pré-amorcé, qui transforme ses éléments au passage. Restaient
  deux appelants, et `dict.setdefault` — que `_dedupe_par_url` employait déjà —
  répond au besoin sans nouvel helper. `dedupe_links` s'y aligne.
- **n° 12 — les `CLAUDE.md` d'une ligne ne sont pas de l'indirection, ils sont
  le mécanisme.** L'`AGENTS.md` racine le documente : « Claude Code ne lit que
  `CLAUDE.md`, les autres agents ne lisent qu'`AGENTS.md` ». Supprimer les six
  rendrait invisible à Claude Code tout le contexte de dossier — conventions
  scrapers, sorties CLI, API de lecture, modèle, observabilité, SSO. C'est
  l'entrée où l'audit s'est trompé de cible.

Reste **hors** de cet audit, et le demeure : les quatre bases SQLite
résiduelles à la racine de `backend/` (gitignorées) et les 38 Mo de
`triathlon.db` en développement.
