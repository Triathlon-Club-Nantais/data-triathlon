# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## Workflow IA

Deux outils d'assistance sont préconfigurés, Speckit et Superpowers. **Ne jamais
lancer les deux sur la même étape** — détail et arbre de décision :
`docs/WORKFLOW-IA.md`.

- **Bugfix, typo, ajustement de 1-2 fichiers, petit refacto** → Superpowers
  seul : `systematic-debugging` (bug) ou `test-driven-development` (ajout de
  comportement), puis `verification-before-completion`. Pas de cycle Speckit,
  pas de dossier `specs/`.
- **Vraie feature** (nouveau scraper, nouvel écran, changement de schéma) →
  Speckit pour le cadrage : `/speckit-specify` → `/speckit-clarify` → GATE →
  `/speckit-plan` → GATE → `/speckit-tasks` → `/speckit-analyze`. Puis handoff
  vers Superpowers pour l'exécution (`subagent-driven-development`, les tâches
  `[P]` de `tasks.md` en parallèle), avec `test-driven-development` dans chaque
  tâche.
- **Speckit est canonique sur le cadrage et la planification** : un seul
  `spec.md`, un seul `plan.md`. Ne pas produire de plan Superpowers concurrent.
  `brainstorming` uniquement en amont si l'idée est encore floue — son résultat
  est injecté dans `/speckit-specify`.
- **Superpowers est canonique sur l'exécution** : ne pas lancer
  `/speckit-implement` **et** `subagent-driven-development`.
- Fin de branche : `requesting-code-review` → `verification-before-completion` →
  `finishing-a-development-branch`.
- Branche et commits-gate sont à gérer **manuellement** : les hooks de
  `.specify/extensions.yml` appellent `speckit.git.feature` et
  `speckit.git.commit` (qu'un agent Claude invoquerait en `/speckit-git-feature`
  / `/speckit-git-commit`), mais l'extension `git` n'enregistre ses commandes
  que pour `agy` et `codex` — voir `registered_commands` dans
  `.specify/extensions/.registry`. Ni pour `claude` (dont le manifest
  `.specify/integrations/claude.manifest.json` ne liste que les neuf skills
  `speckit-*`), ni pour `opencode`, l'intégration active
  (`.specify/integration.json`). Ces hooks ne s'exécutent donc jamais.

## Pile applicative

Une seule génération, en deux briques :

- **Backend** (`backend/`) : FastAPI, archi en couches, modèle normalisé, Alembic.
- **Frontend** (`frontend/`) : Next.js 16 (App Router), TypeScript, Tailwind, shadcn/ui.

Specs de refonte (historiques) : `docs/superpowers/specs/`.

## Stack
- **Backend** (`backend/`) : Python 3.13, **uv** (`pyproject.toml` + `uv.lock`), FastAPI,
  SQLAlchemy 2.0 (sync), Pydantic v2 + pydantic-settings, **Alembic** (migrations), PostgreSQL
  (Supabase) / SQLite en dev. Scraping httpx + BeautifulSoup/lxml, fallback
  Playwright. Tests pytest, ruff. API versionnée sous `/api/v1`.
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
  non pertinents. *Limite levée pour les scrapers qui renseignent `segments`*
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
- **Breizh Chrono réutilise la logique Klikego** (`klikego._parse_detail`,
  `_detect_event_type`) — ne pas dupliquer, factoriser dans `klikego.py`.
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

- **Langue** : UI, commentaires et messages en **français** (avec accents).
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- Schéma DB : migrations **Alembic** (`uv run alembic revision --autogenerate`
  après modif d'un modèle, puis `uv run alembic upgrade head`).
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (déclaré dans `backend/pyproject.toml`).

## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live, ProLiveSport, Sportinnovation,
RaceResult, Chronoplace, T2Area (FFTRI) — tous en **épreuve complète**.
Chronoplace (Laravel + Livewire) se lit en `GET ?perPage=all` — pas de POST
Livewire — et importe **toutes** les épreuves de l'événement pointé par l'URL.
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

Types : Triathlon XS/S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
