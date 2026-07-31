# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## Workflow IA

Deux outils d'assistance sont préconfigurés, **Spec Kit** et **Superpowers**.
Règle d'or : **ce sont deux voies complètes et parallèles, on ne les croise
jamais.** L'exécution suit l'outil qui a produit le plan — un `tasks.md` Spec Kit
s'exécute avec `/speckit-implement`, un plan sous `docs/superpowers/plans/`
s'exécute avec un exécuteur Superpowers. Détail, garde-fous et mise en place :
`docs/WORKFLOW-IA.md`.

**Le choix de la voie appartient à l'utilisateur** : l'agent ne le tranche pas
seul et ne bascule pas de l'une à l'autre en cours de route. Il n'existe pas de
critère mécanique par nature de travail — `002-runnerbreizh-scraper` est passé
par Spec Kit là où les 34 plans de `docs/superpowers/plans/` (scrapers, CLI,
refactos) sont passés par Superpowers.

- **Voie « sans plan »** — bugfix, typo, ajustement de 1-2 fichiers, petit
  refacto : `systematic-debugging` (bug) ou `test-driven-development` (ajout de
  comportement), puis `verification-before-completion`. Pas de dossier `specs/`,
  pas de plan. Les skills ne s'activant que sur le déclencheur de
  `brainstorming`, sauter la boucle ne demande aucune précaution.
- **Voie Spec Kit** — `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-analyze` **avant tout code** (lecture seule : incohérences,
  ambiguïtés, trous de couverture entre artefacts) → `/speckit-implement`.
  Cadrage flou : laisser tourner `brainstorming` **avant** `/speckit-specify`.
  Les artefacts vivent dans `specs/<id>-feature/` — `id` **horodaté**
  `YYYYMMDD-HHMMSS` depuis Spec Kit 0.15.0, séquentiel `NNN` sur les trois
  features déjà en place, qu'on ne renomme pas.
- **Voie Superpowers** — `brainstorming` → `writing-plans` → exécution.
  L'exécuteur **n'a pas de défaut** : l'utilisateur nomme `executing-plans`
  (session courante, checkpoints de revue, pas de fan-out) ou
  `subagent-driven-development` (un sous-agent **et** une revue en deux passes
  **par tâche**). L'agent ne déclenche de lui-même ni le fan-out ni les commits
  par tâche.
- **Fin de branche, commune aux trois voies** : `requesting-code-review` →
  `verification-before-completion` → `finishing-a-development-branch`. Ce sont
  des procédures, pas des artefacts : elles ne peuvent pas produire de doublon,
  et Spec Kit n'offre aucun équivalent de revue de code.
- **Le garant du TDD change d'endroit selon la voie**, le Principe III de la
  constitution restant non-négociable dans les deux cas. Voie Superpowers : le
  skill `test-driven-development`. Voie Spec Kit : `tasks.md` lui-même —
  `/speckit-tasks` produit les tâches de test **avant** leurs tâches
  d'implémentation (cf. `specs/003-dashboard-rank-selector/tasks.md`, T002/T003
  avant T004/T005, « ces tests doivent échouer avant T007 ») et
  `/speckit-implement` s'instruit de les exécuter dans cet ordre. Corollaire : un
  `tasks.md` sans tâches de test viole le Principe III et se **régénère**, il ne
  s'exécute pas.
- **Pourquoi le handoff `tasks.md` → `subagent-driven-development` a été retiré** :
  un sous-agent et deux passes de revue par tâche, soit de l'ordre de **117
  exécutions d'agent** pour les 39 tâches (dont 22 `[P]`) de
  `003-dashboard-rank-selector`. C'est une décision de coût, assumée. Elle
  referme au passage le **doublon de planification**, qui ne naissait que du
  croisement des deux voies : plus de handoff, donc plus de `writing-plans`
  régénérant un plan parallèle à `specs/<id>/plan.md`.
- **Le sur-outillage reste le seul piège** : pour un correctif d'une ligne, ne
  rien lancer. Compter **~20-40 % de tokens en plus** par feature dès qu'on ouvre
  un cycle complet, quelle que soit la voie.
- **`/speckit-implement` a trois traits à connaître** : son étape 4 « Project
  Setup Verification » est à **ne pas dérouler** (elle *ajoute* des motifs
  génériques aux fichiers d'ignore existants — les deux `.dockerignore`, les trois
  `.gitignore`, le `globalIgnores` délibéré de `frontend/eslint.config.mjs` — hors
  périmètre de toute feature, contraire au Principe VI, et toucher au `.gitignore`
  de la racine change ce que `.worktreeinclude` recopie), ses hooks git sont à
  ignorer, et son gate `checklists/` est à respecter. Détail :
  `docs/WORKFLOW-IA.md`, §Garde-fous de `/speckit-implement`.
- **Un sondage n'est ni une spec ni un plan** : il consigne ce qui a été mesuré sur
  le terrain. Il reste autorisé et attendu dans les deux workflows, sous
  `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md`, et il
  **prime** sur le design, la spec et le plan — toute divergence se tranche en
  re-sondant. Forme à reproduire et cas de référence : `docs/WORKFLOW-IA.md`,
  §La troisième catégorie : le sondage.
- Fin de branche : `requesting-code-review` → `verification-before-completion` →
  `finishing-a-development-branch`.
- **Les hooks git s'exécutent désormais** (Spec Kit 0.15.0, intégration active
  `claude` dans `.specify/integration.json`) : l'extension `git` enregistre ses
  cinq commandes **pour `claude`** — `registered_commands` et `registered_skills`
  dans `.specify/extensions/.registry` — et `auto_execute_hooks: true` dans
  `.specify/extensions.yml`. `/speckit-specify` déclenche donc réellement
  `before_specify` → `/speckit-git-feature`, qui crée la branche. C'est un
  renversement : en 0.9.2 l'extension ne s'enregistrait que pour `agy` et
  `codex`, et ces hooks ne partaient jamais. Les SKILL.md 0.15.0 l'écrivent
  noir sur blanc — annoncer le hook ne l'exécute pas, il faut l'invoquer.
- **La branche ne porte plus l'identité de la feature** : le
  `create-new-feature.sh` du core ne touche plus à git du tout (ni `fetch`, ni
  `checkout -b`) et numérote d'après `specs/` seul. La feature courante se lit
  dans `.specify/feature.json` (clé `feature_directory`, fichier **suivi**) ou
  dans `SPECIFY_FEATURE_DIRECTORY` ; `check-prerequisites.sh` ne valide plus le
  nom de branche. Conséquence utile ici : un worktree Superpowers dont la
  branche ne suit aucune convention Spec Kit ne bloque plus `/speckit-plan`.
  La création de branche, elle, vit dans l'extension (`/speckit-git-feature`).
- **Les commits-gate, eux, restent inertes** : dans
  `.specify/extensions/git/git-config.yml`, `auto_commit.default` vaut `false`
  et chaque événement est à `false`. Les hooks `speckit.git.commit` partent,
  lisent cette configuration et passent. Ne pas les activer à la légère : ils
  committent via `git add .`, donc tout le worktree, sans égard au périmètre.

## Pile applicative

Une seule génération, en deux briques :

- **Backend** (`backend/`) : FastAPI, archi en couches, modèle normalisé, Alembic.
- **Frontend** (`frontend/`) : Next.js 16 (App Router), TypeScript, Tailwind, shadcn/ui.

`docs/superpowers/specs/` mêle deux natures : des **designs de features livrées**
(valeur historique, dont les specs de refonte) et des **rapports de terrain encore
normatifs** — sondages et audits, cités nominativement plus bas là où ils
s'appliquent. Qui écrit quoi, et où : `docs/WORKFLOW-IA.md`, §Où atterrissent les
artefacts.

## Stack
- **Backend** (`backend/`) : Python 3.13, **uv** (`pyproject.toml` + `uv.lock`), FastAPI,
  SQLAlchemy 2.0 (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml — **aucun
  navigateur** : le fallback Playwright a été supprimé avec sa dépendance (#102),
  voir `registry.PlaywrightProvider`. Tests pytest, ruff. API versionnée sous
  `/api/v1`.
- **Frontend** (`frontend/`) : Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui.
- **Déploiement** : backend → Render (`render.yaml`), front → Vercel, DB → Supabase.

## Commandes

```bash
# Backend (depuis backend/ — aucun venv à activer, uv run s'en charge)
uv sync                                            # installe les dépendances (dev incluses)
uv run python scripts/dev_server.py                # API + /docs, port libre publié (voir « Dev multi-worktree »)
uv run alembic upgrade head                        # applique les migrations
uv run alembic revision --autogenerate -m "..."    # nouvelle migration après modif d'un modèle
uv run python scripts/reset_db.py                  # reset base dev SQLite (vide + migre + seed démo)
uv run python scripts/reset_db.py --no-seed --yes  # schéma vierge seul (refuse si DB non-SQLite)
uv run pytest -m "not integration"                 # tests unitaires (sans réseau) — défaut CI
uv run pytest -m integration                       # tests réseau réel (scrapers)
uv run ruff check .                                # lint

# CLI de batch (depuis backend/)
uv run python -m app.cli import-sheet --dry-run     # import de masse (Sheet) : ce qui serait importé
uv run python -m app.cli import-sheet --limit 5     # import réel — progression en direct
uv run python -m app.cli rescrape-db --limit 10     # re-scrape la DB (force=True) ; --plain, --no-progress
uv run python -m app.cli rescrape-db --json | jq    # bilan machine-lisible (stdout = JSON seul)
uv run python -m app.cli rescrape-db --url <url> --url <url2>   # cible des épreuves précises
uv run python -m app.cli rescrape-db --urls-from echecs.txt     # ou « - » pour lire stdin
# rejeu des échecs, sans fichier intermédiaire ni état persistant :
uv run python -m app.cli import-sheet --json | jq -r '.failures[].url' \
  | uv run python -m app.cli rescrape-db --urls-from -
uv run python -m app.cli club-labels --like nant   # libellés club vus en base, marqués TCN ou non

# Frontend (depuis frontend/)
npm run dev        # Next.js sur :3000 (ou suivant libre), branché sur le backend du worktree
npm run build      # build prod (strict TS + RSC)
npm test           # vitest run
npm run lint       # ESLint
```

Variable requise : `backend/.env` avec `DATABASE_URL` (voir `.env.example`). Le
schéma est géré par **Alembic** (`uv run alembic upgrade head`). Les dépendances et la
config des outils vivent dans `backend/pyproject.toml` (lock : `backend/uv.lock`).

### Dev multi-worktree

Plusieurs worktrees tournent en parallèle sans configuration. Le backend
(`backend/scripts/dev_server.py`) prend le **premier port libre à partir de 8001** —
un `--port 8001` figé faisait échouer le second worktree sur « Address already in
use » — et publie ce port dans `.dev-backend.json` à la racine du worktree
(gitignoré, un par worktree).

Deux adresses, deux rôles, à ne pas confondre (`BIND_HOST` / `CLIENT_HOST`) : on
**écoute** sur `0.0.0.0` — comme en prod (`--host 0.0.0.0` du Dockerfile et de
`render.yaml`), sans quoi l'API est injoignable depuis l'extérieur d'un conteneur —
et le scan de ports bind cette même adresse, sinon il déclarerait libre un port
qu'uvicorn ne pourrait pas prendre. Mais l'URL **publiée** (et celles du frontend)
reste en `127.0.0.1` : `0.0.0.0` désigne des interfaces d'écoute, pas une
destination, et seul Linux la tolère en connexion sortante. Le frontend ne bind
rien de son côté — `next dev` écoute déjà `0.0.0.0` par défaut.

`npm run dev` (`frontend/scripts/dev.mjs`) lit ce fichier, **vérifie que le port
répond** (un backend tué par `kill -9` laisse son fichier derrière lui), puis lance
`next dev` avec `BACKEND_URL` **et** `API_URL` renseignés. Les deux comptent : la
première alimente les rewrites `/api/*` de `next.config.ts`, la seconde les fetch RSC
de `lib/api/server.ts`. Sans elles, le front d'un worktree tapait `localhost:8001` en
dur, donc la base d'un autre worktree, **sans erreur visible**.

La découverte ne fait que **combler** : le lanceur n'injecte une variable que si
personne ne l'a définie, et les `.env*` comptent autant que le shell — c'est le
loader de Next lui-même (`@next/env`, épinglé sur la version de `next`) qui les lit
dans `dev.mjs`. Écraser les deux variables aurait rendu `.env.local` muet (Next ne
fait jamais primer un fichier `.env` sur l'environnement reçu) et supprimé la seule
façon de dissocier la cible SSR (`API_URL`) de celle des rewrites (`BACKEND_URL`),
qui diffèrent en prod.

Le code applicatif garde partout sa sémantique `process.env.X || défaut` : la
découverte vit dans les deux lanceurs de dev, jamais sur un chemin de production.
L'ordre de démarrage est libre — lancé en premier, le front attend le back (60 s,
puis repli signalé). Échappatoires : `DEV_BACKEND_PORT` (port imposé côté backend),
`BACKEND_URL` (cible imposée côté frontend, aucune attente), `API_URL` (cible SSR
seule) — au choix dans le shell ou dans `frontend/.env.local`.

Le lanceur rend le sort de `next` : code propagé tel quel, et **128+n** quand l'enfant
est tué (`pkill`, OOM-kill) — un « 1 » forfaitaire ferait passer un arrêt pour une
panne applicative (`scripts/exit-code.mjs`). Ctrl-C ne passe pas par là : SIGINT frappe
tout le groupe de processus, le lanceur meurt du signal et l'appelant voit déjà 130.

Côté backend, une sortie `SystemExit` d'uvicorn n'est retentée sur un autre port que
si le port est **effectivement occupé** (`should_retry_after_exit`) : uvicorn quitte
aussi par `sys.exit()` sur d'autres pannes de démarrage, et retenter à l'aveugle
masquerait la vraie cause derrière trois démarrages sur trois ports.

Un worktree reste une copie **neuve** : rien de gitignoré ne l'accompagne. Pour les
worktrees créés par Claude Code (`claude --worktree`, sous-agents
`isolation: worktree`), `.worktreeinclude` à la racine liste ce qui doit suivre —
syntaxe `.gitignore`, et un fichier n'est copié que s'il est à la fois matché **et**
gitignoré. Aujourd'hui : `.env` (donc `backend/.env`, porteur de `DATABASE_URL`),
`.env.local`, la base de dev `backend/triathlon.db` et `frontend/node_modules/`.

Ce dernier est là parce que **la copie bat la réinstallation** : 12,8 s contre
34,3 s de `npm ci` à cache npm chaud. `backend/.venv/` en est absent pour la raison
**inverse**, mesurée de même : 2,0 s de copie contre **0,21 s** d'`uv sync`, qui
reconstruit l'environnement par liens durs depuis `~/.cache/uv` — et un venv n'est
pas déplaçable, les shebangs de `.venv/bin/*` portant le chemin absolu du dépôt
principal. Ne pas l'ajouter « par symétrie ».

Deux fichiers en sont exclus pour une troisième raison, la même pour les deux : ils
désignent un worktree **en particulier**. `.dev-backend.json`, que chaque
`dev_server.py` republie, et tout `BACKEND_URL` / `API_URL` figé dans
`frontend/.env.local`, qui brancherait le front d'un worktree sur la base d'un
autre. Un worktree créé à la main (`git worktree add`) ne passe pas par ce
mécanisme : les fichiers sont à copier soi-même.

## Architecture backend (`backend/`)

Archi en couches, le flux ne traverse qu'une direction
(`api → services → repositories → DB`) :

- `app/main.py` — usine `create_app()` : CORS, handlers d'erreurs, montage routers.
- `app/core/` — `config.py` (pydantic-settings), `logging.py`, `database.py`,
  `exceptions.py`, `time.py`, `club.py` (appartenance au TCN : **liste blanche**
  de libellés, match à l'égalité — cf. #76), `discipline.py` (disciplines
  fédérales vs trail / course à pied / cyclisme).
- `app/models/` — SQLAlchemy **normalisé** : `Athlete`, `Course`, `Participation`,
  `PendingProvider` (voir « Modèle normalisé » plus bas).
- `app/schemas/` — DTO Pydantic v2 (entrée/sortie).
- `app/repositories/` — `*_repository.py` : **seule couche qui touche la Session**.
- `app/services/` — logique métier : `mapping`, `cache` (TTL), `scrape_service`,
  `import_service`, `stats_service`, `geocode_service`, plus les batches CLI :
  `sheet_source` (source Google Sheet), `batch` (la boucle : elle consomme
  `import_service.iter_import_event()` — le générateur de phases du SSE — et
  relaie la progression), `bulk_import_service`, `rescrape_service`, `progress`
  (Protocol `ProgressReporter` + `NullReporter`, le défaut muet).
- `app/cli/` — Typer, **couche mince** (zéro logique métier) : `commands/` (une
  commande par fichier), `progress.py` (reporters Rich/Plain, `select_reporter`),
  `reports.py` (rendu des bilans + émission).
- `app/api/` — `deps.py` + `v1/` (routers fins : validation + délégation au service),
  agrégés dans `v1/router.py`, montés sous `/api/v1`. Une future API v2 vivra dans `v1/`→`v2/`.
- `app/scrapers/` — `registry.py` (registre **Protocol**, fin des `if-else`) +
  un module par provider. `base.py` = `ScrapedResult`,
  `utils.py` = helpers de normalisation.
- `alembic/` — migrations (révision initiale = schéma complet).
- `tests/` — `test_repositories/`, `test_services/`, `test_api/`, `test_cli/`,
  `test_klikego.py`, `test_timepulse.py` (≈745 tests).

### Observabilité SQL

Deux étages **indépendants**, tous deux éteints ou presque par défaut (#89).

`core/sql_observability.py` — listeners posés sur l'engine par `database.py`.
Deux niveaux : un **seuil de lenteur** (`SQL_SLOW_QUERY_MS`, défaut 100 ms) qui
sort en WARNING sur le logger `app.sql`, et un **bilan agrégé par unité de
travail** (`SQL_QUERY_STATS`, défaut `false`) — une requête HTTP côté web, une
**épreuve** côté CLI. C'est le second qui rend un N+1 visible (« 1812 requêtes
pour 1810 participants ») ; le premier seul ne le montrerait pas.

Trois règles à ne pas relâcher. Le SQL est journalisé **paramétré**, jamais avec
ses valeurs liées : elles portent des noms d'athlètes et des libellés de club, et
partiraient dans les logs Render (test de non-régression dédié). Le bilan sort en
**plusieurs enregistrements**, jamais en message multi-ligne : le formateur JSON
de `core/logging.py` construit son objet à la main — et le **label** de l'unité
de travail subit le même écrasement d'espaces que le SQL, puisqu'il est lui aussi
construit depuis des données scrapées (`rescrape_service.py` le compose avec
`Course.name`) : un retour à la ligne y casserait le JSON tout autant. Et seuil à
`0` **plus** bilan éteint = aucun listener posé, coût strictement nul.

`core/tracing.py` — socle OpenTelemetry, `OTEL_ENABLED` à `false` par défaut,
imports paresseux : éteint, aucun paquet OTel n'est chargé. Aucun collecteur
n'est hébergé ; le socle est là pour que le branchement tienne en deux variables
(`OTEL_TRACES_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_ENDPOINT=…`). `OTEL_SERVICE_NAME`
et l'endpoint sont lus par le SDK, mais **`OTEL_TRACES_EXPORTER` est lu par notre
code** — elle n'est interprétée que par le lanceur `opentelemetry-instrument`,
qu'on n'utilise pas. L'exporter `console` écrit sur **stderr** : sur stdout il
casserait `… --json | jq`. La CLI doit appeler `shutdown_cli_tracing()` en fin de
process, faute de quoi le `BatchSpanProcessor` perd les spans du dernier import.
`shutdown_tracing()` ne fait d'ailleurs pas que vider ces spans : elle
**désinstrumente** aussi. Les instrumenteurs OTel sont des singletons par classe
(`BaseInstrumentor`) — sans cet appel symétrique, un second `setup_tracing()` dans
le même process est un no-op **silencieux** (un simple avertissement journalisé,
zéro span produit).

**EXPLAIN et audit d'index restent à faire** : c'est l'analyse à mener *avec* cet
outil, dont le livrable sera un sondage sous `docs/superpowers/specs/`.
Design : `docs/superpowers/specs/2026-07-31-sql-observability-design.md`.

### Modèle normalisé

- **Athlete** — `UNIQUE(nom, prenom, birth_date)`.
- **Course** — `UNIQUE(name, event_date, event_type)` ; `source_url` = clé de cache TTL.
- **Participation** — `UNIQUE(course_id, bib_number)` → plus de doublons à l'import.
- **splits** en **JSON** (remplace les colonnes figées swim/t1/bike/t2/run) →
  couvre tous les sports (duathlon course1/course2, swimrun…). Temps = strings.
  Les scrapers rangent les segments dans 5 slots positionnels triathlon
  (`swim/t1/bike/t2/run` de `ScrapedResult`) ; `services/mapping.build_splits`
  ré-étiquette ces slots selon `event_type` via le gabarit
  `_SPLIT_KEYS_BY_SPORT` (ex. duathlon → `course1`/`course2`) et omet les slots
  **vides**. Un slot sans discipline lisible pour le sport n'est pas absent du
  gabarit pour autant : il porte une clé positionnelle (`segment1` en bike & run,
  `segment2` en swimrun). L'omettre du gabarit jetait sans bruit le temps qui s'y
  trouvait, le filtre du gabarit ne distinguant pas « pas de clé » de « pas de
  valeur ». *Limite levée pour les scrapers qui renseignent `segments`*
  (RaceResult) : la liste ordonnée de segments étiquetés prime sur les 5 slots
  et n'a pas de plafond côté code. **Ce déplafonnement n'est pas mesuré** : sur
  le panel RaceResult, le maximum observé est de 5 segments, et les swimruns
  sondés n'ont **aucune liste publiée portant une colonne de split** — ils
  sortent donc à 0 segment, non par troncature. Ne pas en déduire qu'un swimrun
  multi-legs « garde toutes ses étapes » : rien ne l'établit à ce jour. Panel et
  chiffres : `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`. Les
  scrapers qui remplissent encore les 5 slots restent plafonnés à 5 segments.

### Cache TTL

`services/cache.py` : `is_fresh(course)` → 10 min si course en cours (une
participation sans `total_time`), sinon 30 j. `scrape_service` court-circuite le
re-scraping si frais. Réglable via `CACHE_TTL_IN_PROGRESS_SECONDS` /
`CACHE_TTL_FINISHED_SECONDS`.

### Portée club et disciplines

Deux paramètres traversent l'API de lecture, sur le même patron que `seasons` :

- `scope=club` — restreint aux membres du TCN. Remplace l'ancien `club`, un
  texte libre cherché en sous-chaîne : c'est lui qui laissait la définition du
  club chez l'appelant, et un `%nantais%` comptait les clubs d'athlétisme
  nantais (#76).
- `federal_only=true` — retire les disciplines hors fédération triathlon
  (`trail`, `course-a-pied*`, `cyclisme*`). **Défaut à `false` : l'API reste
  neutre.** Ce sont le dashboard et la page club qui l'activent, via le toggle
  « Inclure les autres disciplines ». Un défaut à `true` amputerait
  silencieusement tout futur appelant.

### Sorties de la CLI (stdout parsable)

Règle structurante, pas un détail : **stdout reste parsable**. La progression sort
donc toujours sur **stderr** (Rich en terminal, lignes simples sinon — cron, CI,
redirection), et avec `--json`, le rapport texte y bascule aussi : stdout ne
contient alors **que** la ligne JSON, d'où `… --json | jq` sans découpage. Sans
`--json`, le rapport texte sort sur stdout comme attendu.

Un batch interrompu (Ctrl-C) émet son **bilan partiel** — texte et, le cas
échéant, JSON — **avant** de sortir en code **130** : le travail déjà persisté
n'est jamais perdu de vue (chaque épreuve est commitée séparément). `--no-progress`
coupe la progression (le rapport final, lui, est toujours émis) ; `--plain` force
les lignes simples même en terminal.

**Codes de sortie** (`cli/reports.emit_outcome`) — le bilan est **toujours émis
avant** la sortie :

| Code | Sens |
| --- | --- |
| `0` | Succès, y compris **partiel** (quelques épreuves en échec sur N) ou « rien à faire » (zéro épreuve ciblée). Un dry-run sort toujours en 0. |
| `1` | **Échec total** : aucune des épreuves ciblées n'a abouti (`batch.est_echec_total` : `errors >= épreuves > 0`). Sinon un cron dont les 53 épreuves échouent n'alerterait jamais. |
| `2` | **Erreur d'usage** (convention Click) : option invalide — notamment `--provider` / `--only-provider` inconnu, rejeté avant tout travail par `cli/validators`. |
| `130` | Ctrl-C. **Prioritaire sur 1** : une interruption est une action de l'opérateur, pas une panne. |

Un tube fermé (`… | head -2`) ne fausse aucun de ces codes : le `BrokenPipeError`
est rattrapé, et le bilan bascule sur stderr plutôt que d'être perdu.

**Vocabulaire** : la CLI compte des **épreuves** (une `source_url` unique), jamais
des courses. Une épreuve porte N `Course` en base (heats Breizh Chrono, variantes
individuel/relais) : `rescrape-db` dédoublonne par `source_url` avant le batch,
donc « Épreuves ciblées : 12 » sur une table de 53 courses n'est pas une perte.

**Deux modes de sélection pour `rescrape-db`**, exclusifs l'un de l'autre :
par filtre sur la base (`--provider`, `--older-than`), ou par URL explicite
(`--url`, répétable, et `--urls-from <fichier|->`). Le second **court-circuite
la base** : une URL inconnue en table `course` est scrapée normalement, sans
avertissement — c'est le cas nominal du rejeu d'un échec d'import, dont
l'épreuve n'a rien persisté. Les combiner est une erreur d'usage (code 2) : ce
sont deux modes, pas des filtres à composer. `--limit` reste compatible avec les
deux : il borne la liste finale, il ne sélectionne rien.

**Deux unités dans un bilan**, et chaque libellé doit le dire : « Épreuves
ciblées / traitées / en erreur » comptent des **épreuves** ; « Participants
ajoutés / mis à jour / déjà en base » comptent des **participants** (ce
troisième compteur distingue l'upsert d'un simple `skipped` : une
participation déjà en base dont un champ a changé est mise à jour, pas
seulement conservée). Ne pas revenir à des libellés muets sur l'unité
(« Importées / Ignorées ») : lus sous « Épreuves ciblées : 42 », ils se
comprennent en épreuves, et « Ignorées : 5820 » devient un non-sens.
« Épreuves traitées » n'apparaît que sur un bilan interrompu, où elle situe le
Ctrl-C (7 des 42).

**Détail des épreuves en erreur** : le compteur « Épreuves en erreur : N » dit
*combien*, pas *lesquelles*. **Les deux commandes** listent donc les échecs
(URL + cause) sous « Épreuves en erreur (détail) : » — la boucle `batch`
collecte un `BatchFailure(url, label, message)` par épreuve fautive (phase
`error` ou exception rattrapée). Ce détail est aussi dans la charge `--json`
(`failures`), et borné aux seuls échecs : il reste léger, contrairement à la
liste de toutes les épreuves. C'est lui qui referme la boucle de rejeu
(`… --json | jq -r '.failures[].url' | … rescrape-db --urls-from -`), sans
fichier d'état. À distinguer des **liens non supportés** (`ignored_by_host`,
suivis dans #33) : ces derniers ne sont **jamais** soumis au batch, ils ne
comptent ni en succès ni en échec.

**Réconciliation de l'identité d'athlète** (issue #66) : `rescrape-db` n'est plus
purement additif. Sur un dossard déjà en base, il **résout l'athlète** et, si la
graphie stockée a divergé de la graphie corrigée, **réassigne
`participation.athlete_id`** — puis supprime en fin de batch les fiches d'athlète
ainsi vidées (`athlete_repository.delete_orphans`, no-op sur une base sans
orphelin). Le bilan compte, unités nommées : « Participations réconciliées »,
« Athlètes fusionnés », « Athlètes orphelins supprimés », avec le détail
`ancien -> nouveau (N participations)` — repris dans `--json`.

Il ne réconcilie **que** l'identité : temps, rangs, statuts et splits d'une
participation existante restent intouchés. Ce silence sur les valeurs est
délibéré (idempotence contre additivité : une autre question, une autre issue).
Garde structurante : une correction qui **viderait le prénom** n'est jamais
appliquée (cas « JP ROUX » / prénoms stockés en majuscules).

Le nettoyage des orphelins (`delete_orphans`) ne tourne **que** dans
`rescrape-db`, en fin de batch : le chemin web (`import_event`/SSE, une épreuve
à la fois) réassigne et commite mais **ne** balaie **pas** l'ancienne fiche
vidée — elle reste orpheline jusqu'au prochain `rescrape-db`, qui seul peut
constater qu'aucune autre épreuve du batch ne l'a entre-temps réutilisée.

`--dry-run` a changé de nature : il **scrape désormais** (le prix d'un aperçu
véritable) et **ne persiste rien** (rollback au lieu de commit). Il rend le détail
`avant -> après` sans écrire. `--limit` / `--url` le bornent. Un dry-run sort
toujours en code 0.

### Conventions scrapers

- Tout nouveau fournisseur : créer `scrapers/<nom>.py`, exposer
  `scrape_event_all()` — la **seule** voie d'import depuis la suppression du
  scraping athlète-unique —, puis l'enregistrer dans `scrapers/registry.py`
  (registre Protocol). Provider inconnu → `playwright`.
- **Détection par host, jamais par sous-chaîne d'URL.** Un provider déclare ses
  `_HOSTS` et hérite de `HostMatchedProvider` : il n'a pas de `matches` à
  écrire. La règle « host exact ou vrai sous-domaine » a une seule définition,
  `registry._host_match`. Un `"exemple.fr" in url` route n'importe quelle URL
  portant le jeton en query vers le scraper, qui la requête telle quelle —
  c'était le SSRF de #49. Un provider dont la condition ne se réduit pas à une
  liste de hosts (Wiclax : `wiclax.com` n'est une page de résultats que sur un
  chemin G-Live) surcharge `matches` et **compose** sur `_host_match`.
  Aucun `matches` n'appelle `urlparse` directement : le host se lit par
  `registry._url_host` (le path par `_url_path`), qui rendent `""` sur une URL
  illisible. `urlparse` lève sur un host IPv6 malformé (`https://[oops/x`), et
  `detect_provider` parcourt **tous** les providers : un seul `urlparse` nu —
  fût-il dans le dernier de la liste, T2Area — suffit à faire lever la
  détection entière, garde des autres comprise.
- **Toute sortie HTTP passe par `app/core/http.client()`**, jamais par
  `httpx.Client(...)` ni `httpx.get(...)` nus. La fabrique enveloppe le
  transport d'un garde qui refuse toute destination non publiquement routable
  (`not ip.is_global`), sur la requête initiale **et sur chaque saut de
  redirection** : #49 avait fermé le routage, un `302 → http://169.254.169.254/`
  restait ouvert (#101). Un méta-test refuse tout `httpx` nu dans `app/`. Deux
  conséquences à connaître : le refus lève `BlockedTargetError`, qui ne dérive
  pas de `ValueError` (sinon `import_service` la classerait en « fournisseur non
  supporté ») ; et une redirection vers un **autre domaine** reste autorisée —
  l'export CSV du Google Sheet en dépend. Design :
  `docs/superpowers/specs/2026-07-31-ssrf-redirection-design.md`.
- **Breizh Chrono réutilise la logique Klikego** (`klikego._parse_detail`,
  `_detect_event_type`) — ne pas dupliquer, factoriser dans `klikego.py`.
- « Supporté ou non » : **une seule définition**, `registry.is_supported` (dérivée
  de `PROVIDERS`), exposée par `GET /scrape/detect` (`{provider, supported}`). Le
  front ne liste **jamais** les providers : la liste en dur qu'il portait est
  restée figée à six noms et affichait « Non supporté (competitor) » sur une URL
  ironman.com pourtant importable — RaceResult et Chronoplace étaient logés à la
  même enseigne. `lib/constants.PROVIDER_LABELS` ne fait que traduire un slug en
  nom commercial ; un slug absent s'affiche tel quel, sans jamais valoir « non
  supporté ».
- Identification club : **une seule définition**, `app/core/club.py`
  (`is_tcn` / `tcn_clause`). Ne jamais la réimplémenter ailleurs — front et
  scraper l'avaient fait, les trois listes ont divergé et tout libellé contenant
  « nantais » a été compté comme TCN (#76). Le front lit le champ `is_tcn` du DTO.
- Les temps restent des **strings** (`"01:23:45"`), normalisés via `utils.py`.
  Splits adaptés au sport : dans `splits` (JSON) + `raw_data` (JSON).

## Architecture frontend (`frontend/`)

Next.js 16 (App Router), TypeScript strict, Tailwind CSS, shadcn/ui, consommant
`/api/v1` du backend. Tests Vitest + RTL verts. Build prod OK.

- `app/` — App Router : `dashboard`, `resultats`, `athletes/[id]`, `courses/[id]`,
  `club`, `carte`, `ajouter`, `admin`.
- `components/` — `scrape/` (ScrapeForm, ProviderDetector, ImportProgress),
  `results/` (ResultCard, ResultsList), `club/` (ClubView, AthleteDialog),
  `map/` (MapView), `dashboard/` (StatsCards, RecentCourses), `ui/` (shadcn).
- `lib/api/` — `client.ts` (appels `/api/v1`), `sse.ts` (streaming import SSE).
- `lib/types.ts` — types TypeScript partagés.
- Déploiement : Vercel, variables `BACKEND_URL` + `API_URL`.

## Conventions générales

- **Langue** : suit le Principe I de la constitution v1.1.0
  (`.specify/memory/constitution.md`) — **français** pour ce qui est
  visible utilisateur ou métier (UI, messages d'erreur affichés, docs
  produit, commentaires de règle métier, messages `DomainError`
  sérialisés vers le front) ; **English** pour la couche technique
  invisible (identifiants, tests, docstrings techniques, logs
  Sentry/Datadog, préfixes Conventional Commits). Un identifiant nomme
  ce qu'il porte : les noms d'une ou deux lettres sont réservés aux
  liaisons dont la portée tient sous les yeux (compréhension, boucle,
  lambda, `db`). Règle de transition : on ne réécrit pas l'existant, la
  règle s'applique aux nouveaux ajouts — **à une dérogation près**, la
  campagne de renommage de l'issue #88, bornée aux lots énumérés dans le
  Principe I (plan de découpage, pas définition de la fin : la dérogation
  s'éteint quand `backend/app` ne porte plus d'identifiant français hors de
  la clause « Pas d'exception de vocabulaire métier » du Principe I).
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- Schéma DB : migrations **Alembic** (`uv run alembic revision --autogenerate`
  après modif d'un modèle, puis `uv run alembic upgrade head`).
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (déclaré dans `backend/pyproject.toml`).

## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live, ProLiveSport, Sportinnovation,
RaceResult, Chronoplace, T2Area (FFTRI), Competitor, ok-time, runnerbreizh,
Sporthive (MYLAPS), chronoweb — tous
en **épreuve complète**. Chronoplace (Laravel + Livewire) se lit en
`GET ?perPage=all` — pas de POST Livewire — et importe **toutes** les épreuves de
l'événement pointé par l'URL.
ok-time.fr (issue #52) se lit sur une API JSON WordPress publique
(`/wp-json/gmcap/v1/evenements/{id}/results`) : **un seul appel** rend
l'événement entier, toutes épreuves comprises — ni Playwright ni parsing HTML
sur le chemin nominal. Les points de passage sont **cumulés** et différenciés en
durées de segment, rangées dans `segments` (chemin générique) avec les libellés
de la source : les `id` de points ne sont pas sémantiques (`12|2` vaut « T2 »
sur une épreuve, « VELO » sur une autre) et 55 des 99 courses du panel sortent
du motif triathlon. Ces libellés sont rendus **verbatim** par le front, via le
chemin générique de `lib/utils/splits.ts` (`splitColumns` / `splitSegments`) : à
défaut de clé canonique, les colonnes viennent des libellés publiés — sans lui, les
splits d'ok-time, RaceResult et Chronoplace étaient stockés mais invisibles.
Statuts : **DNS, puis DSQ, puis DNF** (la source cumule des drapeaux
contradictoires, et la disqualification prime sur l'abandon), et le repli
`finisher` d'une course non chronométrée se mesure **au seuil** — au plus
`max(1, 10 %)` de participants chronométrés — jamais à l'égalité stricte à zéro,
qu'un seul temps saisi à la main suffisait à désarmer, faisant classer toute une
course d'enfants DNF. Le type de course est classé sur `title_course`, le titre
d'événement servant d'**appoint** : `classify_event_type(texte, contexte=…)` ne
consulte le contexte que si l'épreuve ne nomme aucun sport (« Format M
individuel » d'un SwimRun), et la taille de l'épreuve prime toujours sur celle du
contexte. Ne pas revenir à la **concaténation** des deux titres : elle classait le
« Trail 12 km » d'un « Triathlon de X » en `triathlon`, qui s'affichait comme tel
et **survivait** à `federal_only=true`. Deux
formes d'URL sont supportées, `classement.ok-time.fr/<id>[/race/<raceId>]` et
`ok-time.fr/evenement/<slug>/` — cette dernière résolue par un GET HTML dont
`_resolve_event_id` **vérifie la page atterrie** (un slug retiré est redirigé vers
le listing générique, qui porte les liens de classement de tous les événements :
en retenir le premier importerait un événement étranger sous la `source_url`
demandée, sans erreur) ; les préfixes `/course/` et `/competition/` sont
**obsolètes** et rejetés avec un message qui le dit — trois URLs du Sheet en
relèvent et deviennent, ok-time étant désormais supporté, des épreuves en erreur
dans les bilans plutôt que des liens ignorés. Vérité d'API (panel de 21
événements / 99 courses / 12 644 participations) :
`docs/superpowers/specs/2026-07-26-oktime-scraper-design.md`.
Wiclax/G-Live couvre plusieurs déploiements : `wiclax-results.com`,
`chronosmetron.com` et `chronowest.fr` (WordPress + iframe G-Live). Un nouveau
déploiement tiers = un host dans `WiclaxProvider._HOSTS`.
RaceResult couvre de même trois façades d'un même produit (`raceresult.com`,
`espace-competition.com`, `chronoconsult.fr`, cf. `RaceResultProvider._HOSTS`),
toutes servies par la même API JSON publique — sans Playwright, et toutes
joignables via l'apex `my.raceresult.com` (aucune résolution de shard).
Particularités du moteur : les listes retenues sont celles dont `Mode` n'est pas
`"hidden"` dans `config["TabConfig"]["Lists"]` (qui porte le contest
explicitement) — critère **nécessaire mais non suffisant** : sur 406211 les
listes non-`hidden` sont des listes d'affichage et le seul vrai classement est
`hidden`. L'élargissement aux listes `hidden` est **réalisé** (#60) : elles ne créent ni
participant ni contest, elles **enrichissent** par **dossard** les participants
établis par les listes publiées (splits, scalaires vides). Coût : une requête
`list` par liste `hidden`. Le verrou C (410891, rang `(2)` sans point) reste
ouvert : `_RE_DUREE` rejette bien la cellule suffixée d'un finisher, mais un
non-finisher (DNF/DNS/DSQ), à qui RaceResult n'appose pas le suffixe, peut laisser
fuiter une durée intermédiaire nue comme split (élargissement renvoyé à un ticket
dédié). Design : `2026-07-23-raceresult-listes-hidden-design.md`.
Plusieurs listes peuvent couvrir un même contest et doivent être fusionnées.
La qualification de `Course` vient du **contest explicite** de `TabConfig.Lists` ;
le libellé de groupe de niveau 0 n'est consulté qu'en `Contest="0"`, et
seulement si tous ces libellés recoupent `contests` (ils sont sinon un axe
d'affichage : catégorie, sélecteur de split). Le `Name` de liste n'est **jamais**
un qualifiant — c'est un nom interne à pipe, et l'employer dupliquait
silencieusement des participations (cf. §3 du sondage).
La date d'épreuve n'existe que dans le JSON-LD schema.org de la page
`/{eventId}/results`.
Vérité d'API (15 épreuves au panel, 3 façades ; mesures détaillées sur 12/14/17) :
`docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` — elle prime sur le
design et sur le plan. Ne pas revenir à la route `/{id}/RRPublish/data/…` (alias
hérité, 404 sur les épreuves récentes) ni au filtre `Live` (qui vide certaines
épreuves) : les deux ont des tests de non-régression dédiés.
Design : `docs/superpowers/specs/2026-07-19-raceresult-scraper-design.md`.

`fftri.t2area.com` (T2Area) est la plateforme officielle de la FFTRI : Joomla
server-rendered, classement complet en **une** requête, **aucune pagination**.
L'URL accepte trois profondeurs — édition (`/calendrier/<événement>/<épreuve>/<année>.html`,
le cas nominal), fiche individuelle (**tronquée** vers son édition, la forme du
Sheet) et épreuve sans année (1 GET de plus, on prend la dernière édition
publiée). Une URL d'**événement** est refusée : ses épreuves ont des dernières
éditions d'années différentes, un fan-out n'aurait pas d'année lisible. Un appel
= une `Course`. **Préférer l'URL d'édition dans le Sheet** : une URL d'épreuve
sans année est stockée telle quelle en `Course.source_url` — après publication
d'une nouvelle édition, un `import-sheet` (`force=False`) retombe alors sur la
course de l'année précédente, la juge fraîche (TTL 30 j) et renvoie `cached` au
lieu d'importer la nouvelle édition. Pas un bug : la conséquence d'accepter
cette profondeur, à connaître avant de la choisir dans le Sheet.

Deux particularités structurantes. **Les splits ne sont pas dans le classement** :
ils vivent sur la fiche individuelle, soit une requête par participant — le
scraper ne charge donc que les fiches des membres du TCN (25 requêtes sur les 901
lignes de La Baule M 2022). C'est le seul scraper conscient du club ; il
**réutilise** `core/club.py`, il ne le réimplémente pas (#76). Et **la FFTRI
republie** : chaque page porte « Résultats produits par X ». Quand X est un
provider supporté, un avertissement est journalisé — mais la mention ne lie que
l'accueil du chronométreur, jamais l'épreuve, donc aucune URL source n'est
constructible : seul l'opérateur peut la fournir.

Détails de lecture : colonnes lues **par libellé d'en-tête** (l'en-tête réel en
porte 10, `id_league` et `league` s'intercalant avant `Détails`) ; `00:00:00` vaut
temps absent (un DNF sort avec cette valeur) ; `bib_number` n'est rempli que
lorsque la clé de fiche est un vrai dossard (`bib-566`), jamais avec une licence
(`A44719`) ni un identifiant interne (`id-1153352`) ; splits mappés **par
libellé** (`CàP 1`/`CàP 2` en duathlon), un libellé inconnu faisant basculer
toute la fiche sur `segments`. Design :
`docs/superpowers/specs/2026-07-26-t2area-scraper-design.md`, plan :
`docs/superpowers/plans/2026-07-26-t2area-scraper.md`.

**Competitor** (#54) est le moteur réel derrière `ironman.com` — d'où le nom du
provider — commun à toutes les épreuves IRONMAN / 70.3. La page « Results »
encastre une iframe `labs-v2.competitor.com` (Next.js, `__NEXT_DATA__`) : deux
sauts, page → uuid → JSON. Trois particularités structurantes :

- **une URL désigne une série, pas une édition** (21 éditions pour IRONMAN
  France) et le site n'expose aucune URL par année. On importe la dernière
  édition publiée — sauf si l'uuid de l'URL est lui-même celui d'une édition,
  auquel cas c'est celle-là. Cela donne un rattrapage par année que le site
  n'offre pas ;
- **`latestResults` de la page est amputé de l'Open Division** (62 athlètes sur
  1810 à IRONMAN France 2025) : on ne le réutilise jamais, le classement est
  redemandé au proxy `labs-v2.competitor.com/api/results-proxy?url=…` sans
  filtre de catégorie. `api.competitor.com` n'est **pas** joignable en direct
  (401, clé APIM) et le proxy n'accepte que `/web/results` ;
- **la source ne publie aucun club** : une participation Competitor sort avec
  `club = ""` et n'est donc jamais marquée TCN. Limite assumée, pas un bug.

Pièges à ne pas réintroduire : `wtc_swimtime_formatted` (secondes) n'est pas
`wtc_swimtimeformatted` (durée) ; `wtc_ContactId.gendercode` est faux (77 lignes
sur 1585 mesurées) — le genre se lit sur la catégorie d'âge ; `athlete`/`bib`
sont fabriqués côté navigateur et absents des réponses du proxy.
Sondage (source de vérité, 7 épreuves) :
`docs/superpowers/specs/2026-07-26-competitor-ironman-sondage.md`.
Design : `docs/superpowers/specs/2026-07-26-competitor-ironman-design.md`.

`runnerbreizh.fr` est du **HTML statique paginé** : 50 lignes par page,
`&page=N`, arrêt sur la première page dont `table.tableau-courses` n'a plus que
son en-tête. Ne **jamais** borner la pagination sur le total annoncé en colonne
« Classement » : en relais il compte des **équipes** (31) et non des lignes (62),
la boucle s'arrêterait à la moitié de l'épreuve.

Ce total sert en revanche de **garde de complétude après coup**
(`_require_complete_ranking`) — vérifier n'est pas borner. Le critère d'arrêt seul
confond la fin du classement avec une page intermédiaire servie vide : les rangs
lus restent contigus (1..150), `quality.analyze` ne voit alors aucune anomalie et
l'épreuve tronquée sort `is_reliable=true`. La garde ne juge donc que si la
dernière page lue était **pleine** (une page incomplète est la fin publiée) et
compare un **plancher**, jamais une égalité — sans quoi le décompte en équipes du
relais refuserait toute épreuve par équipes. Elle compte les **lignes vues**, pas
les résultats retenus : une ligne hors format est un autre sujet, déjà
journalisé. Même principe pour le plafond de pagination (`_MAX_PAGES`) : l'avoir
atteint signifie que l'invariant d'arrêt est faux, donc on **lève** au lieu de
rendre des lignes vraisemblablement dupliquées. Dans les deux cas un import
refusé se rejoue (`rescrape-db --urls-from -`), une épreuve tronquée et marquée
fiable ne se rattrape pas.

L'URL d'entrée est **canonicalisée** (`runnerbreizh.canonical_url`) : on ne garde
que `CourseFichierGpsNom` et on repart de la page 1. Ce n'est pas cosmétique —
8 des 10 liens du Sheet portent `&page=2` ou `&page=3`, et `&Sexe=F` renvoie un
**sous-ensemble** : partir de l'URL telle quelle amputerait silencieusement
l'import de ses premières pages, donc de ses meilleurs classés. La
canonicalisation est faite par **allowlist** (reconstruction depuis le seul
paramètre d'épreuve), pas par soustraction des vues connues. Portée exacte : elle
fixe le `source_url` des `ScrapedResult`, **pas** la clé du cache TTL —
`Course.source_url` reçoit l'URL brute passée par `import_service`, donc deux
graphies d'une même épreuve dans le Sheet la font re-scraper. Vérifié en base :
une seule `Course`, aucune participation dupliquée.

Trois manques structurants, tous assumés. **Aucun dossard** : rien à faire côté
scraper, le repli anti-doublon par athlète de `import_service` (commit `b49e295`)
est générique. **Aucun club** — ni dans le classement, ni sur la fiche coureur :
`Participation.club` reste `NULL`, donc ces participations sont **hors du
périmètre `scope=club`** (dashboard, page club, stats). C'est arbitré, pas un
oubli ; et sans danger, `athlete_repository.resolve` ne mettant à jour
`Athlete.club` que si un club est fourni. **Aucune date de naissance** : seule la
catégorie situe l'âge, d'où le genre lu sur son suffixe (`S3M` → M) — sauf
catégorie d'équipe (`M+F`), qui décrit la composition du duo et non la personne
de la ligne.

Les 8 colonnes sont **figées quelle que soit la discipline** et leurs libellés
mentent : en duathlon « 1ère épreuve » est une course à pied, en aquathlon la
cellule « Vélo » reste affichée mais vide. Elles se lisent donc **par position**
(2/3/5 → slots `swim`/`bike`/`run`), `services/mapping.build_splits` les
ré-étiquetant selon `event_type` — jamais par libellé d'en-tête, contrairement à
T2Area. Les transitions ne sont pas publiées (pas de T1/T2). Corollaire côté
gabarit : un sport dont un slot positionnel n'a pas de discipline lisible
(`swim_time` en bike & run, `bike_time` en swimrun) reçoit une clé
**positionnelle** — `segment1`, `segment2`. Omettre ce slot du gabarit, comme
avant, jetait silencieusement le temps qui s'y trouvait ; lui donner un nom de
sport mentirait. Métadonnées d'épreuve dans le `<title>`, seul porteur de la date
en format français ; le nom y est nettoyé de son suffixe de distances
(`Triathlon de Quiberon M`, pas `… M (1.5/38/10)`) faute de quoi l'extraction de
commune de la carte échoue. La commune, elle, **est** dans le titre et vaut mieux
que celle déduite du nom (`Pléneuf-Val-André` contre `Val-André`) : faute de champ
ville dans `ScrapedResult`, elle est conservée en `raw_data["city"]` — la brancher
sur le géocodage changerait un contrat partagé par tous les fournisseurs.

Le rang de catégorie ne se lit **pas** au premier enfant `<b>` de la cellule : sur
une ligne féminine, le site enveloppe toute la cellule dans un `<span>` de couleur
et supprime le `<b>` (`<span>29/SEF</span>`). Rang et qualifiant se lisent donc
tous deux depuis le **texte** ; l'oublier perdait `rank_category` pour toutes les
coureuses, et donnait deux rangs différents aux deux équipiers d'un même duo
mixte.

Deux profondeurs d'URL refusées, avec un message qui nomme la forme attendue :
la **fiche coureur** (`triathlons.php?CoureurNom=…`, présente dans le Sheet) —
un palmarès multi-épreuves dont le fan-out coûterait ~130 requêtes pour une URL —
et l'**identifiant d'épreuve inconnu**, que le site sert en 200 avec un `<title>`
vide et qui passerait sinon pour une épreuve sans classement publié. Un titre
**au format inattendu** est refusé de même, et distinctement : il est lu par
position depuis la droite, donc un champ manquant décale tout — nom vide, ville
promue en nom, taille perdue dans le type, date pourtant juste
(`_require_event_name` : aucune ligne → identifiant inconnu, des lignes → format
du titre changé). `import_service._require_event_name` rattrape bien le nom vide
en aval, mais après le scrape, sans nommer la cause, et le type dégradé
n'y serait rattrapé par personne. Comme la
FFTRI, le site **republie** (« Chronométrée par BREIZHCHRONO ») : un
avertissement est journalisé quand le chronométreur est un provider supporté —
sa page ne lie que son accueil, aucune URL d'épreuve n'est reconstructible.

Deux particularités de données à connaître : les lignes que le site n'a pas
appariées à un coureur portent le libellé `?DOSSARD #43637` (3 sur 322 à
Quiberon) et sont **importées telles quelles** en nom, sans prénom — les écarter
créerait autant de trous dans le classement, comptés en `rank_gap` par
`services/quality.py`, ce qui masquerait le ratio de place de toute l'épreuve. Et
un relais publie **une ligne par équipier**, temps et rang partagés : les deux
participations sont importées, mais les rangs en doublon font sortir l'épreuve
`is_reliable=false` — limite connue de `quality._rank_anomalies`, hors périmètre.

Sondage du HTML réel (fait autorité) :
`docs/superpowers/specs/2026-07-27-runnerbreizh-sondage.md`. Spec, plan et
tâches : `specs/002-runnerbreizh-scraper/`.

**Sporthive** (MYLAPS, issue #53) se lit sur une **API JSON publique** — aucune
clé, aucun cookie, ni Playwright ni parsing HTML. Elle vit sur
`eventresults-api.speedhive.com/sporthive`, MYLAPS ayant fondu Sporthive dans
Speedhive : l'hôte annoncé par l'issue est **mort** (son certificat ne couvre
plus le nom) et la route `classifications/search` n'existe plus. Si l'API
redéménage, l'adresse fait autorité dans `GET sporthive.com/api/clientSettings`,
pas dans le code. Le provider déclare le seul host `sporthive.com` — le
sous-domaine `results.` en découle — et **jamais** l'hôte d'API, qu'on appelle
sans le reconnaître.

Trois profondeurs d'URL désignent le même événement et sont toutes acceptées :
événement (`/events/{id}`), course (`/events/{id}/races/{n}`) et dossard
(`…/bib/{b}[/split]`), avec le préfixe de langue (`/en/events/…`) et le segment
`s/` vers lequel mène la redirection 307. Un import remonte toujours à
l'**événement entier** : le Sheet ne porte qu'un lien par épreuve, et un membre
inscrit sur un autre format y serait invisible.

**Deux familles d'identifiants** cohabitent sur ces mêmes routes : le
**snowflake** à 19 chiffres du fonds historique, et le **GUID** des événements
récents (`bdea2f10-1510-481c-b5ef-ef7f1926a06f`). L'API ne les distingue pas et
la page d'accueil publie les deux. Un motif `\d+` refusait donc tout le fonds
récent **avant tout appel**, en affirmant l'URL illisible alors que le site la
sert. La branche GUID reste **strictement** formée (8-4-4-4-12) : l'élargir à
`[^/]+` laisserait passer `/events/abc` et déclencherait une requête qui ne peut
que 400 — c'est le refus qui nomme la forme attendue.

Quatre pièges, tous mesurés, à ne jamais réintroduire :

- **`races/{n}` n'est pas un `raceId`** mais un ordinal *local* (`activeRaceId`).
  `GET /races/1` répond **200** et rend une épreuve de 2015 sans rapport : la
  prendre pour la course demandée importerait une épreuve étrangère sous la
  `source_url`, sans la moindre erreur. `_parse_url` rend donc l'identifiant
  d'événement **et rien d'autre** — un `str` nu, pas un couple : le piège est
  fermé par construction, pas par une garde à maintenir. Le vrai identifiant est
  le champ `id` (snowflake à 19 chiffres) de `/events/{id}/races` ; sur 32
  courses sondées, `id` égale le segment d'URL **0 fois**, `activeRaceId` **32
  fois**.
- **`size` est plafonné à 10** côté serveur (`size=50` → 400), et
  `count`/`offset` — les paramètres annoncés par l'issue — sont acceptés mais
  **silencieusement ignorés** : paginer avec eux relit les dix mêmes lignes
  indéfiniment. D'où ≈ 100 requêtes pour l'épreuve du Sheet (955 classés), et
  aucun export CSV pour y échapper. L'arrêt se fait sur `last` puis sur une page
  vide, jamais sur `totalPages` : borner sur un total annoncé est la faute que
  runnerbreizh a payée — le total sert à **vérifier** après coup
  (`classificationsCount`, égalité constatée 32 fois sur 32).
- **le statut vit dans `validity`** (`DNF`/`DNS`/`DQ` — noter `DQ`), et les
  booléens `dns`/`dsq` sont **morts** : `false` sur 10 360 lignes sur 10 360, y
  compris les 35 en `DNS`. S'y fier rate 100 % des statuts.
- **`legs[].sportName` ment** : saisi par le chronométreur, non normalisé
  (`SWIM`/`Swim`/`T1`) et `null` sur 23 % des legs. `legs[].type` prime donc
  (24 042/24 042) — d'où les libellés `natation`/`transition`/`vélo`/`course à
  pied`, rangés dans `segments` (chemin générique) et non dans les 5 slots
  positionnels : une course d'enfants publie **4** legs et un mapping positionnel
  ferait atterrir sa course à pied en `t2`. Mais `type` **peut valoir `Other`**,
  et il ne discrimine alors rien : sur les cinq legs de la course « Standard »
  de Jersey (177 classés), natation comprise, et sur les deux transitions
  d'Izvorani 2026. Rendu verbatim, cela publiait `Other`, `Other (2)` …
  `Other (5)` après désambiguïsation par `build_splits` — cinq fois le même
  non-mot là où `sportName` nomme correctement. D'où le **repli** : `type`
  d'abord, `sportName` quand `type` se tait, le `type` brut si les deux se
  taisent (mieux vaut un libellé pauvre qu'un temps perdu).

**Deux portées d'échec**, et c'est le choix structurant du module. Une course au
classement incomplet est **écartée** (`_IncompleteRankingError`, type privé rattrapé
par la boucle, journalisé avec intitulé, ordinal et les deux décomptes) : les
autres courses de l'événement s'importent. Refuser l'événement entier rendait
une course durablement tronquée côté source définitivement non importable,
membres du TCN des cinq autres courses compris. L'**événement** est refusé
(`ValueError`) sur URL illisible, événement inconnu (404), plafond de pagination
atteint, ou **aucune course importable** — ce dernier garde-fou parce que
`import_service._require_event_name` ne lève pas sur une liste vide et que
`batch` compte « aucun résultat » en succès : un import à zéro course passerait
sinon pour réussi. Contrepartie assumée de l'écart par course : le bilan CLI
comptant des épreuves, une épreuve ressort en succès à 5 courses sur 6, et seul
le `logger.warning` en garde la trace.

Deux règles de valeurs qui ne se devinent pas. Le **statut est tranché sur le
rang** quand `validity` se tait *et* qu'aucun temps n'est retenu : `finisher` si
classé, `DNF` sinon — sans quoi les 73 lignes sans `chipTime` ni `gunTime` mais
**classées** par la source s'afficheraient en abandon, le travers déjà payé sur
ok-time. Et une course annoncée à **zéro classé est sautée sans requête** : une
`Course` vide n'a aucune participation sans `total_time`, donc `cache` la déclare
terminée — et comme les six courses d'un événement partagent une `source_url`,
elle peut devenir celle qui répond pour tout l'événement et geler son re-scrape
30 jours.

Détails de lecture : temps en `HH:MM:SS`, `HH:MM:SS.fffffff` ou `HH:MM:SS.fff`
selon la course — la fraction se tronque **avant** `normalize_time`, dont le
motif est ancré en fin de chaîne et qui rendrait `00:57:33.2510000` tel quel ;
`00:00:00` vaut temps absent ; `overallPosition: 0` vaut rang absent ;
`gender: "U"` (41 % des lignes) sort vide. `eventType` de la source sert
d'**appoint** au classifieur (`classify_event_type(raceName, contexte=…)`) : sans
lui, `Senior Men` ne nommant aucun sport, les 2 852 lignes du cross UK entraient
en `triathlon` et **survivaient** à `federal_only=true`. Les relais publient
**une ligne par équipe** (l'inverse de runnerbreizh) au nom libre
(`LA COUSINADE`) : `is_relay` est décidé sur l'intitulé de **course**, et le nom
d'équipe n'est jamais passé à `split_athlete_name`. Les `tags`, qui semblent
offrir un découpage prénom/nom, sont un index de recherche tokenisé. `location`
et `countryCode` de l'événement sont conservés en `raw_data["city"]` /
`["country"]` (même clé que runnerbreizh), **non** branchés sur le géocodage ;
la nationalité du participant, que `country` écraserait, vit en
`raw_data["athlete_country"]`.

Trois limites assumées : les **sous-classements** dupliquent des participations
(le cross UK publie `Senior Men` *et* `Senior Men 9 to count`, dont les 90
dossards sont tous dans les 294) et rien dans le JSON ne les marque — tout est
importé, dans des `Course` distinctes ; `qualify_event_name` ne qualifie **pas**
« Triathlon S » de « Triathlon Sud Vendee Dimanche », son court-circuit testant
la sous-chaîne (sans conséquence #21 ici, les 6 noms restant distincts) ; et une
course de relais dont l'intitulé ne le dirait pas sortirait en individuel.

Sondage de l'API réelle (fait autorité — 7 événements, 32 courses, 10 360
participations, 1 063 requêtes) :
`docs/superpowers/specs/2026-07-29-sporthive-sondage.md`, **addendum du
30/07/2026** compris — re-sondage sur 11 événements / 6 pays d'où viennent les
deux corrections ci-dessus (familles d'identifiants, `type: "Other"`). Spec,
plan et tâches : `specs/004-sporthive-scraper/`.

`chronoweb.com` (issue #55) est du **HTML statique** dont une seule requête rend
l'**événement entier** — toutes les épreuves, classements complets, sans
pagination ni JavaScript : `epreuve`, `cat` et `point` ne sont que des paramètres
d'affichage que le navigateur traduit en bascule de classe CSS. Le fait
structurant n'est pas le markup, régulier sur les 89 épreuves du panel, mais sa
**sémantique** : une ligne du tableau est le **passage** d'un concurrent à un
point de chronométrage, pas un participant. Les compter pour des participants
triplerait l'effectif d'un triathlon (2 517 lignes pour 854 inscrits à Oléron
2024). Les lignes sont donc regroupées par `(épreuve, dossard)`.

Temps total et rangs (général **et** catégorie) viennent du **seul point final**
de l'épreuve, défini comme son `data-point` maximal — jamais du dernier point
franchi par le participant, sans quoi un abandon hériterait du temps et du rang
d'un point intermédiaire. Un concurrent absent du point final sort **sans aucun
rang** (1,42 % du panel) : promu en rang de classement, son rang intermédiaire
doublonnerait celui d'un finisher et ferait ressortir toute l'épreuve
`is_reliable=false`. Ces rangs restent lisibles dans `raw_data["points"]`, avec
vitesses et gains de place. **Le rang ne se lit pas au texte** de la cellule de
classement : elle superpose le rang général et un rang de catégorie `hidden`, et
`get_text()` y rend « 11 » pour un 1ᵉʳ/1ᵉʳ, « 11837 » pour un 118ᵉ/37ᵉ.

Les **transitions ne sont pas publiées** mais se calculent
(`cumul − intervalle − cumul précédent`, jamais négatif sur 17 497 écarts, égal
au caractère près au « Changement » de la fiche individuelle). Elles sont
renseignées partout où elles sont déductibles ; **une valeur nulle n'est pas
enregistrée**, et une transition dont un point encadrant manque ne s'invente pas.
Corollaire mesuré le 2026-07-30 : l'aquathlon relais à 8 points de la Verrerie
sort à **8 segments et non 15** — ses 14 équipes ont toutes des écarts nuls, ses
points de chronométrage étant contigus. Le remplissage suit le **motif** de
points (`_POINT_PATTERNS`, 5 motifs mesurés), jamais le type d'épreuve classé :
motif reconnu → les 5 slots positionnels, que `build_splits` ré-étiquette par
discipline ; motif inconnu → `segments` sous les libellés de la source, sans
plafond, transitions intercalées sous « Changement ».

Plafond de **2 requêtes** par import : le classement, puis le catalogue
`/resultats.php` (170 Ko) pour la commune — plus juste que celle déduite du nom
d'épreuve (« St Georges d'Oléron » contre « Oléron »), rangée en
`raw_data["city"]`, tout échec étant journalisé et ignoré. **Aucune mémoïsation**
de cette requête : `PROVIDERS` tient des singletons de module, un cache
d'instance serait un cache de processus. La **fiche individuelle** n'est jamais
requêtée (elle est cassée à la source sur les épreuves mono-point).

L'URL est canonicalisée par **allowlist** du seul paramètre `event` — la fiche
individuelle (2 des 5 URLs chronoweb du Sheet) est donc tronquée vers son
événement, et les 4 graphies d'Oléron 2024 se réduisent à une. Comme pour
runnerbreizh, cela fixe le `source_url` des `ScrapedResult`, **pas**
`Course.source_url`. Une URL sans `event` (l'archive ZIP du Sheet) est refusée
**avant tout appel réseau**, avec un message français nommant la forme attendue :
le scraper ne doit jamais tenter de parser un binaire. Deux échecs à ne pas
confondre : **pas de `h2.name` → événement introuvable, on lève** ; `h2.name`
présent mais zéro ligne → **événement sans classement publié**, import vide sans
erreur.

Trois absences, toutes de la source : **aucun club** (ces participations sont
donc hors du périmètre `scope=club`), **aucune date de naissance** — le genre se
lit sur la catégorie, dont les deux conventions cohabitent (`MSE` préfixé, `SEM`
suffixé, et `M0F` féminin malgré son `M` initial) et dont les codes d'équipe
(`MIXT`, `DUOX`, `DUOM`, `DUOF`) n'en donnent aucun —, et **aucune distinction
DNS / DSQ**. Une épreuve est marquée relais par son **libellé** (`relais`, `duo`,
`team`), jamais par la catégorie : `MASC`, `FEM` et `MIXT` servent aussi de
catégories « toutes classes » en individuel. Sur une épreuve relais, le libellé
de la colonne Nom est enregistré **entier** comme nom, sans prénom — le découpage
des individus mutile 52 des 707 équipes du panel. Les limites du classifieur
partagé mises en évidence par le sondage (« 53 km » d'un trail classé
`course-a-pied`, épreuve sans sport nommé repliée sur `triathlon`) sont **hors
périmètre** : elles affectent tous les fournisseurs.

Sondage du HTML réel (fait autorité) :
`docs/superpowers/specs/2026-07-29-chronoweb-sondage.md`. Spec, plan et tâches :
`specs/005-chronoweb-scraper/`.

Types : Triathlon XS/S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
