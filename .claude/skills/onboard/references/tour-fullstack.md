# Tour guidé — contributeur fullstack

Bienvenue. Ce parcours te fait ouvrir dans l'ordre les fichiers qui donnent le sens du projet — pas un survol, une lecture. Compte 45 à 60 minutes, terminal à côté.

Si tu voulais un autre profil (backend seul, frontend seul, scraping, ops…), relance `/onboard` avec le profil correspondant : celui-ci suppose que tu vas toucher aux deux côtés.

## 1. La stack en 30 secondes

Backend FastAPI + SQLAlchemy 2.0 (sync) + Alembic sur Python 3.13, géré par `uv`. Frontend Next.js 16 App Router + TypeScript + Tailwind + shadcn/ui. Scrapers en `httpx` + BeautifulSoup, Playwright en dernier recours.

Le détail complet — commandes, variables, versions — est dans `AGENTS.md` §Stack et §Commandes. Garde ce fichier ouvert.

## 2. AGENTS.md est la référence, pas un résumé

Ouvre `AGENTS.md` à la racine. C'est la source de vérité opérationnelle du projet ; ce parcours pointe dedans plutôt que de dupliquer.

Sections à lire en priorité, dans l'ordre :

- **§Architecture backend** — le sens du flux `api → services → repositories → DB`, non négociable.
- **§Modèle normalisé** — les 4 entités et leurs contraintes d'unicité.
- **§Sorties de la CLI (stdout parsable)** — le contrat de sortie qui gouverne toute la CLI batch.
- **§Portée club et disciplines** — comment `scope=club` et `federal_only` traversent l'API.

Reviens-y à chaque doute pendant la suite du tour.

## 3. La constitution v1.1.0

Ouvre `.specify/memory/constitution.md`. Six principes non-négociables ; ils sont courts, lis-les tous.

Deux points structurants à ancrer :

- **Principe II** (architecture en couches, un seul propriétaire pour `is_tcn`) protège de la rechute #76 — trois définitions du club divergentes ont fait compter tout libellé « nantais » comme TCN.
- **Principe V** (défauts neutres des paramètres transverses) protège du même bug par un autre angle : un défaut « intelligent » côté API ampute silencieusement tout futur appelant.
- **Principe III** (TDD sans réseau) est la règle qui bloque une PR : `uv run pytest -m "not integration"` doit être vert.

## 4. Backend — le sens du flux

L'archi est en couches strictes. On descend une couche à la fois.

### 4.1 L'usine d'application

Ouvre `backend/app/main.py`. Tu y verras `create_app()` — CORS, handlers d'erreurs, montage du router `/api/v1`. C'est la porte d'entrée du process, tout part de là.

### 4.2 Un router (couche API)

Ouvre `backend/app/api/v1/courses.py` (ou `stats.py` pour un cas d'agrégation). Un router **fin** : il valide les entrées, délègue à un service, formate la sortie. Il n'ouvre **jamais** de session SQLAlchemy — c'est la garde du principe II.

L'agrégateur des routers vit dans `backend/app/api/v1/router.py`.

### 4.3 Un service (couche métier)

Ouvre `backend/app/services/stats_service.py` (agrégation lisible) ou `backend/app/services/mapping.py` (transformations pures scraper → DTO, avec `build_splits` et `_SPLIT_KEYS_BY_SPORT`).

Un service orchestre la logique métier, ne construit **pas** de requête SQL et ne renvoie **pas** de DTO au router directement en touchant la Session — il passe par les repositories.

### 4.4 Un repository (couche persistance)

Ouvre `backend/app/repositories/course_repository.py`. **Seule couche autorisée à toucher `Session`** — cf. principe II. Un repository lit et écrit, il ne connaît ni HTTP ni règle métier au-delà des filtres qu'on lui passe.

Regarde aussi `athlete_repository.delete_orphans()` — voir §Rescrape-db dans AGENTS.md pour comprendre à quoi il sert.

### 4.5 Les modèles

Ouvre `backend/app/models/`. Quatre modèles centraux :

- `Athlete` — unique par `(nom, prenom, birth_date)`.
- `Course` — unique par `(name, event_date, event_type)` ; `source_url` sert de clé de cache.
- `Participation` — unique par `(course_id, bib_number)`. C'est cette contrainte qui a fait disparaître les doublons d'import.
- `PendingProvider` — file d'attente des URL soumises pour un provider pas encore supporté.

Détails et rationale dans `AGENTS.md` §Modèle normalisé (dont le déplafonnement des segments RaceResult et ses limites mesurées).

## 5. Le modèle de données visuel

Ouvre `docs/modele-donnees.md`. Diagramme Mermaid — les relations `Athlete ↔ Participation ↔ Course` en un coup d'œil, les colonnes JSON (`splits`, `raw_data`) situées.

Sers-toi en comme référence quand tu écriras une requête ou une migration.

## 6. Un scraper simple

Ouvre `backend/app/scrapers/klikego.py`. Note trois choses :

- La fonction publique unique : `scrape_event_all()`. C'est la **seule voie d'import** depuis la suppression du scraping athlète-unique.
- Les temps restent des strings (`"01:23:45"`), normalisées via `backend/app/scrapers/utils.py`.
- Breizh Chrono réutilise `_parse_detail` et `_detect_event_type` d'ici — cf. `AGENTS.md` §Conventions scrapers.

Puis ouvre `backend/app/scrapers/registry.py` — registre `Protocol`, fin des `if-else`. Provider inconnu → fallback Playwright.

Enfin `backend/app/services/cache.py` : `is_fresh(course)` court-circuite le re-scrape (10 min en cours, 30 j fini). Une commande qui veut passer outre le fait par `force=True`, jamais par contournement.

## 7. Le service d'import — le pipeline complet

Ouvre `backend/app/services/import_service.py`. Le générateur `iter_import_event()` émet des **phases** (fetch, parse, persist, done, error) consommées à la fois par :

- l'endpoint SSE (streaming au front pendant un import interactif),
- la boucle `batch` de la CLI (rescrape/import de masse).

C'est le point où le pipeline traverse **toutes** les couches : router SSE → service d'import → scraper → mapping → repositories. Un seul générateur, deux consommateurs. Si tu retiens un fichier de ce tour, c'est celui-là.

## 8. La CLI batch

Ouvre `backend/app/cli/`. Structure Typer, couche mince : `commands/` (un fichier par commande), `progress.py` (reporters Rich/Plain), `reports.py` (rendu bilan + `emit_outcome`).

Ouvre `backend/app/cli/commands/rescrape_db.py`. Note :

- **stdout parsable** — la progression sort sur **stderr**, avec `--json` seule la ligne JSON tombe sur stdout.
- **Codes de sortie normés** — `0` succès (même partiel), `1` échec total, `2` erreur d'usage, `130` Ctrl-C. Tout est dans `AGENTS.md` §Sorties de la CLI.
- **Deux modes exclusifs** : filtre base (`--provider`, `--older-than`) ou URL explicite (`--url`, `--urls-from`). Les combiner est une erreur d'usage.

Le rejeu d'échecs sans fichier intermédiaire est le cas d'usage à comprendre : `… import-sheet --json | jq -r '.failures[].url' | … rescrape-db --urls-from -`.

## 9. Frontend — la structure App Router

Ouvre `frontend/app/`. Une route = un dossier :

- `dashboard/` — vue d'accueil, StatsCards + RecentCourses.
- `resultats/` — liste filtrable.
- `athletes/[id]/` — fiche athlète.
- `courses/[id]/` — fiche course.
- `club/` — vue club (le toggle « Inclure les autres disciplines » vit ici).
- `carte/` — carte des épreuves.
- `ajouter/` — le formulaire de scrape.
- `admin/` — outils internes.

`layout.tsx` et `providers.tsx` chapeautent tout ça. `frontend/app/api/` porte les routes proxy Next → backend.

## 10. Frontend — la couche API

Trois fichiers à ouvrir dans l'ordre :

- `frontend/lib/api/client.ts` — appels `/api/v1`, typés. Toutes les requêtes passent par là.
- `frontend/lib/api/sse.ts` — consomme le streaming SSE de `import_service` (cf. étape 7). C'est le pont côté front vers le pipeline d'import.
- `frontend/lib/types.ts` — types TypeScript partagés (dont le champ `is_tcn` du DTO — cf. principe II, le front ne réimplémente pas la règle club, il lit ce booléen).

## 11. Un composant caractéristique

Ouvre `frontend/components/scrape/ScrapeForm.tsx` — orchestrateur du parcours utilisateur « coller une URL et voir arriver les participants ». Il appelle `sse.ts` et affiche la progression via `ImportProgress.tsx`.

Puis, pour un cas plus statique, `frontend/components/results/ResultCard.tsx` — comment un résultat est rendu (nom, chrono, splits).

## 12. Les tests

Ouvre `backend/tests/`. Structure qui **calque** l'archi en couches : `test_repositories/`, `test_services/`, `test_api/`, `test_cli/`. Un test unitaire par fichier concerné, pas de test transverse floue.

Les scrapers ont chacun leur fichier (`test_klikego.py`, `test_timepulse.py`…) avec des fixtures HTML/JSON figées dans `tests/fixtures/`. Le réseau réel est isolé derrière le marker `integration` (rappel principe III : jamais lancé par défaut).

Regarde `tests/conftest.py` pour les fixtures pytest de session/DB. Le front a ses propres tests Vitest + RTL côté `frontend/`.

## Pour attaquer une première feature

Trois voies coexistent, à choisir consciemment :

- **Speckit** (`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`) pour une vraie feature. Le cycle est décrit dans `.specify/memory/constitution.md` §Development Workflow.
- **Superpowers** (`brainstorming` → `writing-plans` → exécution) pour une vraie feature aussi — l'autre voie complète. On ne croise jamais les deux : l'exécution suit l'outil qui a produit le plan.
- **Sans plan** pour bugfix / typo / 1-2 fichiers, sans dossier `specs/`.

Le guide de choix est dans `docs/WORKFLOW-IA.md` — ouvre-le avant ton premier PR pour savoir dans quel mode tu es. Bonne route.
