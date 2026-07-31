# AGENTS.md — data-triathlon

App web centralisant les résultats de compétition des membres d'un club de
triathlon (TCN). On colle une URL de chronométrage → le backend scrape, stocke,
et importe en arrière-plan tous les participants de l'épreuve.

Détails install/déploiement : voir `README.md`. Ce fichier cible les agents IA.

## Workflow IA

Deux outils d'assistance sont préconfigurés, **Spec Kit** et **Superpowers**. Le
principe : **Spec Kit possède les artefacts** (`spec.md`, `plan.md`, `tasks.md`
dans `specs/NNN-feature/`), **Superpowers possède l'exécution** (worktree, TDD
red-green-refactor, sous-agents, revue, fin de branche). Le point de jonction est
`tasks.md`. Détail, mise en place et pièges : `docs/WORKFLOW-IA.md`.

Les deux se chevauchent sur la **planification** — c'est là que naissent les
conflits. Spec Kit est explicite et déterministe (on tape `/speckit-plan`) ; les
skills Superpowers se déclenchent **automatiquement** quand leur description
correspond à la situation. D'où la règle d'or : **Spec Kit cadre et planifie
jusqu'à `tasks.md`, Superpowers exécute.**

- **Bugfix, typo, ajustement de 1-2 fichiers, petit refacto** → Superpowers seul :
  `systematic-debugging` (bug) ou `test-driven-development` (ajout de comportement),
  puis `verification-before-completion`. Pas de cycle Spec Kit, pas de dossier
  `specs/`. Sauter la boucle entièrement : les skills ne s'activent que sur le
  déclencheur de `brainstorming`.
- **Vraie feature** (nouveau scraper, nouvel écran, changement de schéma) :
  - Cadrage flou → laisser tourner le skill `brainstorming` de Superpowers.
  - `/speckit-specify` → `/speckit-plan` → `/speckit-tasks`.
  - `/speckit-analyze` **avant tout code** : il vérifie, en lecture seule, les
    incohérences, ambiguïtés et trous de couverture entre les artefacts.
  - Handoff : pointer `subagent-driven-development` sur `plan.md` / `tasks.md` de
    Spec Kit (tâches `[P]` en parallèle) ; Superpowers gère TDD + revue en deux
    passes, `test-driven-development` dans chaque tâche.
- **Piège nº1, le doublon de planification** : dire explicitement à l'agent que le
  plan existe déjà dans `specs/<id>/plan.md` et qu'il **ne doit pas le réécrire**,
  sinon `writing-plans` régénère un plan parallèle. Idem pour la spec : `spec.md`
  est canonique, pas un `-design.md` concurrent.
- **Piège nº2, le sur-outillage** : pour un correctif d'une ligne, sauter la boucle
  entièrement. Compter **~20-40 % de tokens en plus** par feature quand on lance la
  boucle complète.
- **Superpowers est canonique sur l'exécution** : ne pas lancer
  `/speckit-implement` **et** `subagent-driven-development`.
- **Un sondage n'est ni une spec ni un plan** : il consigne ce qui a été mesuré sur
  le terrain. Il reste autorisé et attendu dans les deux workflows, sous
  `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md`, et il
  **prime** sur le design, la spec et le plan — toute divergence se tranche en
  re-sondant. Forme à reproduire et cas de référence : `docs/WORKFLOW-IA.md`,
  §La troisième catégorie : le sondage.
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

- **Langue** : suit le Principe I de la constitution v1.0.0
  (`.specify/memory/constitution.md`) — **français** pour ce qui est
  visible utilisateur ou métier (UI, messages d'erreur affichés, docs
  produit, commentaires de règle métier, messages `DomainError`
  sérialisés vers le front) ; **English** pour la couche technique
  invisible (identifiants, tests, docstrings techniques, logs
  Sentry/Datadog, préfixes Conventional Commits). Règle de transition :
  on ne réécrit pas l'existant, la règle s'applique aux nouveaux ajouts.
- Commits : Conventional Commits (`feat:`, `fix:`…), déjà en place dans l'historique.
- Schéma DB : migrations **Alembic** (`uv run alembic revision --autogenerate`
  après modif d'un modèle, puis `uv run alembic upgrade head`).
- Tests unitaires **sans réseau** ; le réseau réel est isolé derrière le marker
  `integration` (déclaré dans `backend/pyproject.toml`).

## Fournisseurs supportés

Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live, ProLiveSport, Sportinnovation,
RaceResult, Chronoplace, T2Area (FFTRI), Competitor, ok-time, runnerbreizh — tous
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

Types : Triathlon XS/S/M/L/XL, Duathlon XS/S/M/L, SwimRun S/M/L, Aquathlon,
Aquarun, Bike & Run.
