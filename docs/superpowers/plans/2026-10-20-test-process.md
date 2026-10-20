# Processus de test : moins de tests par changement, plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** tests ciblés dans la boucle interne (règle écrite puis hooks), CI filtrée par application, boucle locale allégée (migrations, fixtures, vitest), outillage de mutation et consolidation prouvée de toute la suite ; la suite complète reste la porte de la merge queue.

**Architecture :** documentation de règle (`docs/tests-boucle.md`), deux hooks Claude Code projet en Python stdlib sous `.claude/hooks/`, un job `changes` et une décision `ci-ok` scriptée sous `.github/scripts/`, une option pytest `--migrations` dans `backend/tests/conftest.py`, puis outillage (testmon, pytest-split, mutmut, StrykerJS) et lots de consolidation.

**Tech Stack :** pytest 8 + xdist, vitest 5 (projets `jsdom`/`node`), GitHub Actions, hooks Claude Code (`PreToolUse`, `Stop`), mutmut, StrykerJS, pytest-testmon, pytest-split, `dorny/paths-filter`.

**Spec :** `docs/superpowers/specs/2026-10-20-test-process-design.md` (epic #1704 ; sous-issues #1705, #1706, #1707).

## Global Constraints

- La suite complète des deux applications tourne toujours en `merge_group` ; `ci-ok` reste le seul check requis.
- `AGENTS.md` racine ≤ 200 lignes (`wc -l AGENTS.md`).
- Actions GitHub épinglées par SHA, version en commentaire (`# vX.Y.Z`).
- Pistes rejetées par #508, à ne pas rouvrir : `isolate: false` sur jsdom, `pool: "threads"`, plafond `maxWorkers`.
- Mesures de temps : protocole de `docs/superpowers/specs/2026-08-20-suites-de-tests-sondage.md` (seuil de charge, répétitions, minimum retenu) ; hors seuil, la mesure est notée « non retenue », pas rapportée comme gain. Toutes les mesures vont dans `docs/superpowers/specs/2026-10-20-test-process-sondage.md`.
- Langue : Principe I (français visible/doc, anglais identifiants et tests). Aucun tiret cadratin ou demi-cadratin comme ponctuation dans les fichiers produits.
- Commits Conventional Commits avec `Refs #<sous-issue>`, directement sur `epic/1704-test-process`, via `/usr/bin/git -C <worktree>` (le `git` nu est bloqué par un hook dans ce worktree). Pas de trailer `Co-Authored-By`.
- Boucle interne de ce chantier lui-même : tests ciblés ; suite complète de l'application touchée à la fin de chaque sous-issue (tâches 3, 9, et dernière).

## Review Focus

1. Job `changes` en échec ou annulé : `ci-ok` doit être rouge, jamais vert par jobs sautés (tâche 3, test `changes_failure_fails`).
2. Commande de suite complète déguisée (`rtk uv run pytest`, `cd backend && uv run python -m pytest -q`, `FULL_SUITE=0 ...`) : le hook doit la reconnaître (tâche 5, tests paramétrés).
3. `-m "not integration"` passé en ligne de commande ne doit pas faire revenir les tests `migrations` (tâche 4, vérification de collecte).
4. Hook `Stop` relancé en boucle (`stop_hook_active: true`) ou tour sans fichier modifié : il ne doit rien lancer (tâche 9, tests `test_stop_hook_active_noop`, `test_unchanged_fingerprint_noop`).
5. Lot de consolidation dont le score de mutation baisse d'un mutant : le lot est annulé, pas « presque gardé » (tâche 12, procédure).

---

## Sous-issue #1705 (quick wins)

### Task 1 : les 3 tests frontend rouges

**Files :** à déterminer par l'enquête, parmi
- `frontend/components/athletes/AthleteDetachAction.test.tsx` (« sépare les résultats cochés après confirmation, puis ouvre la nouvelle fiche »)
- `frontend/components/athletes/TeammatesDialog.test.tsx` (« ne propose pas un coureur déjà dans l'équipe »)
- `frontend/components/admin/jeunes/CalendrierEntrainements.test.tsx` (« liste les séances à venir d'abord… », bloc « vu le 10/10/2026 »)
- et leurs composants si la cause est dans le code.

**Interfaces :** aucune.

- [ ] **Step 1 :** appliquer `superpowers:systematic-debugging`. Rejouer chaque fichier isolément : `cd frontend && npx vitest run <fichier>`, puis sous couverture : `npx vitest run <fichier> --coverage --coverage.provider=v8` (installer `@vitest/coverage-v8` à la version exacte de vitest avec `npm i --no-save`). Noter pour chacun : rouge isolé / rouge seulement sous couverture / rouge seulement sous charge.
- [ ] **Step 2 :** pour `CalendrierEntrainements`, vérifier d'abord l'horloge (date figée ou non par `vi.setSystemTime`, dépendance à « aujourd'hui »).
- [ ] **Step 3 :** corriger la cause (horloge figée, attente asynchrone `findBy*` au lieu de `getBy*`, ou correctif du composant si régression réelle). Interdits : augmenter `testTimeout`, ajouter des retries, supprimer l'assertion.
- [ ] **Step 4 :** vérifier : chaque fichier vert 5 fois de suite sans couverture, et 2 fois sous couverture. Expected : `Tests  N passed` à chaque exécution.
- [ ] **Step 5 :** consigner cause et preuve dans `docs/superpowers/specs/2026-10-20-test-process-sondage.md` (créer le fichier avec un titre et une section « Tests rouges du 20/10 »). Commit : `fix(frontend): <cause> in <tests> (#1705)`.

### Task 2 : règle de gradation des tests

**Files :**
- Create : `docs/tests-boucle.md`
- Modify : `AGENTS.md` (section « Commandes » et tableau « Où lire quoi »)
- Modify : `.claude/workflows/195-fanout-scrapers.mjs:162-166`

**Interfaces :**
- Produces : le passe-droit `FULL_SUITE=1` et l'option `--migrations`, nommés ici et utilisés par les tâches 4 et 5 ; le document `docs/tests-boucle.md` où les tâches 4, 5, 8, 9, 11, 12 ajoutent leur section.

- [ ] **Step 1 :** écrire `docs/tests-boucle.md` avec ces sections : « Pendant l'itération » (commandes : `uv run pytest tests/<chemin> -n 0`, `-k`, `--lf`, `--sw`, `npx vitest run <fichier>`, `npx vitest related --run <fichiers source>`, `npx vitest --changed origin/main`) ; « Une suite complète par branche » (avant `finishing-a-development-branch`, application touchée seulement ; déclencheurs des deux suites : contrat API consommé par le front, dépendances, configuration de test, workflows CI ; jamais relancée sans fichier modifié depuis le dernier vert) ; « Précédence » (texte ci-dessous, mot pour mot) ; « La porte » (CI et merge queue exécutent tout).
  Texte de précédence : « Cette règle du projet prime sur les consignes de suite complète des skills pour les étapes intermédiaires. `verification-before-completion` est satisfait par la commande ciblée pour une affirmation sur une tâche, et par la suite complète pour une affirmation sur la branche. »
- [ ] **Step 2 :** dans `AGENTS.md`, sous le bloc de commandes, 3 à 4 lignes : itérer sur les tests ciblés, une suite complète par branche sur l'application touchée, renvoi à `docs/tests-boucle.md`. Ajouter la ligne de tableau `| Boucle de tests : quoi lancer quand, hooks, mutation | docs/tests-boucle.md |`. Libérer les lignes nécessaires ailleurs dans le fichier en condensant sans perdre d'information.
- [ ] **Step 3 :** vérifier `wc -l AGENTS.md` ≤ 200.
- [ ] **Step 4 :** dans `195-fanout-scrapers.mjs`, remplacer la commande de suite complète du point 3 par `cd backend && uv run pytest ${sub.tests} tests/test_scrapers -n 0 -q` (vérifier que `tests/test_scrapers` existe ; sinon le dossier des tests de scrapers réel) suivi de `uv run ruff check .`. Vérifier : `node --check .claude/workflows/195-fanout-scrapers.mjs`.
- [ ] **Step 5 :** relire `.specify/memory/constitution.md` (lignes 165, 405, 500) et confirmer qu'aucune n'exige la suite complète à chaque étape ; si une ligne le fait, s'arrêter et le signaler au contrôleur (amender la constitution n'est pas dans le périmètre). Commit `docs(tests): targeted-test rule for agents and humans (#1705)`.

### Task 3 : filtre de chemins en CI

**Files :**
- Create : `.github/scripts/ci-ok.sh`, `.github/scripts/test-ci-ok.sh`
- Modify : `.github/workflows/ci.yml` (nouveau job `changes`, `needs`/`if` des jobs `backend`, `backend-audit`, `backend-postgres`, `frontend`, `frontend-test`, step de `ci-ok`)

**Interfaces :**
- Produces : `ci-ok.sh` lit `EVENT_NAME`, `CHANGES_RESULT`, `RESULTS` (paires `job=result` séparées par des espaces), `FILTERED_JOBS` (noms des jobs pouvant être `skipped`) ; sort 0 ou 1. La tâche 10 ajoute ses shards à `RESULTS` et `FILTERED_JOBS`.

- [ ] **Step 1 :** écrire `test-ci-ok.sh` (bash, sans dépendance) qui appelle `ci-ok.sh` et vérifie le code de sortie :
  - `pr_all_success_passes` : pull_request, changes=success, tout success → 0
  - `pr_filtered_skip_passes` : pull_request, backend=skipped (filtré) → 0
  - `pr_unfiltered_skip_fails` : pull_request, un job non listé dans `FILTERED_JOBS` en skipped → 1
  - `changes_failure_fails` : changes=failure, tout le reste skipped → 1
  - `changes_cancelled_fails` : changes=cancelled → 1
  - `merge_group_skip_fails` : merge_group, un job skipped → 1
  - `any_failure_fails` : pull_request, frontend-test=failure → 1
- [ ] **Step 2 :** `bash .github/scripts/test-ci-ok.sh` → échoue (script absent).
- [ ] **Step 3 :** implémenter `ci-ok.sh` selon ces règles (design, section B).
- [ ] **Step 4 :** `bash .github/scripts/test-ci-ok.sh` → tous OK.
- [ ] **Step 5 :** dans `ci.yml` : job `changes` avec `dorny/paths-filter` épinglé par SHA (dernière v4), filtres `backend: ['backend/**', '.github/**']`, `frontend: ['frontend/**', '.github/**']`, sorties forcées à `true` quand `github.event_name == 'merge_group'`. Chaque job backend/frontend : `needs: changes`, `if: needs.changes.outputs.<app> == 'true'`. `ci-ok` : `needs` inclut `changes`, un `actions/checkout` épinglé (même SHA que le reste), puis `run: bash .github/scripts/ci-ok.sh` avec les variables construites depuis `needs`.
- [ ] **Step 6 :** vérifier la syntaxe : `npx --yes actionlint` indisponible hors Go, donc `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` → aucune erreur ; la preuve réelle (PR frontend seule : jobs backend `skipped`, `ci-ok` vert ; run `merge_group` : tout exécuté) est notée comme vérification de la PR parapluie dans le sondage.
- [ ] **Step 7 :** suite complète frontend et backend (fin de sous-issue #1705) : `cd backend && uv run pytest -m "not integration"`, `cd frontend && npm test`. Commit `ci: run only the touched app's jobs on pull requests (#1705)`.

## Sous-issue #1706 (moyen terme)

### Task 4 : marqueur `migrations` hors boucle locale

**Files :**
- Create : `backend/tests/test_migrations_smoke.py`
- Modify : `backend/tests/test_migrations.py` (ajout `pytestmark = pytest.mark.migrations`, retrait de `test_upgrade_head_sur_base_vierge`)
- Modify : `backend/tests/conftest.py` (option et désélection)
- Modify : `backend/pyproject.toml` (marker `migrations` déclaré)
- Modify : `.github/workflows/ci.yml` (job `backend` : `uv run pytest -m "not integration" --migrations`)
- Modify : `docs/tests-boucle.md` (section « Migrations »)

**Interfaces :**
- Produces : option pytest `--migrations` (booléenne). Sans elle, les items portant `migrations` sont désélectionnés via `config.hook.pytest_deselected` dans `pytest_collection_modifyitems`, quel que soit `-m`.

- [ ] **Step 1 :** relever la référence : `cd backend && uv run pytest -m "not integration" --collect-only -q | tail -1` (noter N total).
- [ ] **Step 2 :** déplacer `test_upgrade_head_sur_base_vierge` dans `test_migrations_smoke.py` (il importe `_alembic_config` et la fixture `sqlite_url` depuis `tests.test_migrations`, ou les recopie si l'import crée une double collecte : vérifier par `--collect-only`). Ajouter `pytestmark` à `test_migrations.py`.
- [ ] **Step 3 :** implémenter `pytest_addoption` (`--migrations`, `action="store_true"`, aide en français) et la désélection.
- [ ] **Step 4 :** vérifier :
  - `uv run pytest -m "not integration" --collect-only -q | tail -1` → N − (M − 1) sélectionnés, où M est le nombre d'items collectés dans `test_migrations.py` à l'étape 1 (le test fumée reste sélectionné).
  - `uv run pytest -m "not integration" --migrations --collect-only -q | tail -1` → N.
  - `uv run pytest tests/test_migrations.py tests/test_migrations_smoke.py --migrations -n 0 -q` → tout vert.
- [ ] **Step 5 :** CI : ajouter `--migrations` au step « Tests (hors réseau) » du job `backend`. Section de doc : une branche qui touche `backend/alembic/` ou `backend/app/models/` lance la suite avec `--migrations`.
- [ ] **Step 6 :** commit `test(backend): keep migration tests out of the local loop, run them in CI (#1706)`.

### Task 5 : hook `PreToolUse` contre la suite complète

**Files :**
- Create : `.claude/hooks/test_gate.py`, `.claude/hooks/test_test_gate.py`
- Modify : `.claude/settings.json` (clé `hooks.PreToolUse`, matcher `Bash`, commande `python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/test_gate.py"`)
- Modify : `docs/tests-boucle.md` (section « Hooks »)

**Interfaces :**
- Produces : `is_full_suite(command: str) -> bool` dans `test_gate.py` ; le script lit le JSON du hook sur stdin (`tool_input.command`), et pour une suite complète sans `FULL_SUITE=1` sort le JSON `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": <message>}}` ; sinon sort 0 sans sortie. Message (français) : rappelle la commande ciblée, le passe-droit `FULL_SUITE=1`, et `docs/tests-boucle.md`.

- [ ] **Step 1 :** tests `unittest` paramétrés (`subTest`) dans `test_test_gate.py` :
  - vrai : `uv run pytest`, `uv run pytest -m "not integration"`, `uv run pytest tests`, `uv run pytest tests/ -q`, `rtk uv run pytest -m "not integration"`, `cd backend && uv run python -m pytest -q`, `npm test`, `npm test -- --reporter=dot`, `npx vitest run`, `rtk npx vitest run`, `FULL_SUITE=0 npm test`
  - faux : `FULL_SUITE=1 uv run pytest`, `uv run pytest tests/test_api -n 0`, `uv run pytest tests/test_x.py::test_y`, `uv run pytest -k raceresult`, `uv run pytest --lf`, `uv run pytest --sw`, `uv run pytest -m integration -n 0`, `npx vitest run components/AppNav.test.tsx`, `npm test -- components/x`, `npx vitest related --run lib/a.ts`, `npx vitest --changed origin/main`, `git status && ls`, `npm run build`
  - `test_main_denies_full_suite` : stdin JSON avec `npm test` → stdout JSON avec `permissionDecision == "deny"`
  - `test_main_silent_otherwise` : stdin JSON avec `ls` → stdout vide, code 0
- [ ] **Step 2 :** `python3 -m unittest .claude/hooks/test_test_gate.py` → échec (module absent).
- [ ] **Step 3 :** implémenter `is_full_suite` : découper en segments sur `&&`, `||`, `;`, `|` ; pour chaque segment, `shlex.split`, retirer les affectations `VAR=val` en tête (retenir `FULL_SUITE=1`) et les préfixes `rtk`, `uv run`, `python -m`, `npx` ; un segment pytest est complet s'il n'a aucun argument positionnel autre que `tests`/`tests/` et aucune des options `-k`, `--lf`, `--last-failed`, `--sw`, `--stepwise`, ni `-m` dont la valeur contient `integration` sans `not` ; un segment vitest/npm test est complet s'il n'a ni argument positionnel (après `--` pour npm), ni `related`, ni `--changed`.
- [ ] **Step 4 :** `python3 -m unittest .claude/hooks/test_test_gate.py` → OK.
- [ ] **Step 5 :** brancher dans `.claude/settings.json` ; vérifier le JSON (`python3 -m json.tool .claude/settings.json`). Vérification réelle notée pour la revue : une session où `uv run pytest -m "not integration"` est refusée, et passe avec `FULL_SUITE=1`.
- [ ] **Step 6 :** commit `chore(claude): deny full test-suite runs in the inner loop (#1706)`.

### Task 6 : coût des fixtures DB, puis fixture transactionnelle si > 10 %

**Files :**
- Modify : `docs/superpowers/specs/2026-10-20-test-process-sondage.md` (section « Coût de create_all »)
- Modify (conditionnel) : `backend/tests/conftest.py` (fixture `db_session`, branche SQLite)

**Interfaces :**
- Consumes : rien. Produces (conditionnel) : `db_session` garde son nom et son contrat (une `Session` vierge par test).

- [ ] **Step 1 :** mesurer en `-n 0`, sous le protocole : temps cumulé de la suite unitaire backend, et temps passé dans `create_all`/`drop_all` de la branche SQLite (instrumentation temporaire non commitée, par exemple `time.perf_counter` autour des deux appels, cumul écrit en fin de session). Consigner les deux chiffres et la charge machine.
- [ ] **Step 2 :** si la part ≤ 10 % ou si la mesure est hors seuil de charge : consigner la décision (« non retenu » ou « à remesurer au repos ») et clore la tâche ; commit `docs(tests): measure per-test schema cost (#1706)`.
- [ ] **Step 3 (si > 10 %) :** fixture de session par worker xdist (moteur SQLite mémoire, `create_all` une fois) ; `db_session` ouvre une connexion, une transaction, et une `Session(bind=connection, join_transaction_mode="create_savepoint")`, puis rollback. Appliquer le contournement pysqlite des SAVEPOINT de la documentation SQLAlchemy 2.0 (événements `connect` et `begin`).
- [ ] **Step 4 (si > 10 %) :** vérifier : `uv run pytest -m "not integration" -p no:randomly` puis avec un ordre aléatoire (`uv run --with pytest-randomly pytest -m "not integration"`), même nombre de tests passés que la référence de la tâche 4 ; remesurer sous protocole et consigner. Commit `perf(tests): share the SQLite schema per worker, roll back each test (#1706)`.

### Task 7 : profilage vitest

**Files :**
- Modify : `frontend/vitest.config.ts` (seulement si un essai est retenu)
- Modify : `docs/superpowers/specs/2026-10-20-test-process-sondage.md` (section « Vitest »)

- [ ] **Step 1 :** `cd frontend && npx vitest doctor` (si la commande n'existe pas dans la version installée, le noter) et `npx vitest run` ; consigner la ventilation `Duration`.
- [ ] **Step 2 :** essai `isolate: false` sur le projet `node` seulement : nombre de tests passés identique et temps sous protocole ; retenu seulement si plus rapide.
- [ ] **Step 3 :** essai happy-dom sur le projet `jsdom` (`npm i --no-save happy-dom`) : retenu seulement si plus rapide au repos et nombre de tests passés identique ; si retenu, ajouter la dépendance de dev et mettre à jour `frontend/test/environments.test.ts` si elle fige l'environnement.
- [ ] **Step 4 :** consigner chaque essai (retenu ou non, avec chiffres). Commit `perf(frontend): <essai retenu>` ou `docs(tests): vitest profiling results (#1706)`.

### Task 8 : pytest-testmon en local (opt-in)

**Files :**
- Modify : `backend/pyproject.toml` (groupe `dev` : `pytest-testmon`), `backend/uv.lock`, `.gitignore` (`.testmondata*`)
- Modify : `docs/tests-boucle.md` (section « testmon »)
- Modify : `docs/superpowers/specs/2026-10-20-test-process-sondage.md`

**Interfaces :**
- Produces : décision `testmon_retenu` (oui/non) consignée dans le sondage, lue par la tâche 9.

- [ ] **Step 1 :** `cd backend && uv add --dev pytest-testmon`. Première passe : `uv run pytest -m "not integration" --testmon` (avec `-n 4` par défaut) ; noter erreurs éventuelles de verrou.
- [ ] **Step 2 :** cas vérifiés : modifier une fonction de `app/services/` (sans la committer) et vérifier que `--testmon` relance ses tests et ceux d'un service appelant ; modifier une fixture HTML d'un scraper et constater qu'aucun test n'est relancé (limite connue, à documenter).
- [ ] **Step 3 :** retenu si la passe xdist fonctionne et que le premier cas relance les bons tests ; sinon retirer la dépendance. Documenter l'usage (`uv run pytest --testmon`) et la limite des fixtures dans `docs/tests-boucle.md`.
- [ ] **Step 4 :** commit `chore(backend): opt-in pytest-testmon for the local loop (#1706)` ou `docs(tests): testmon evaluated and not adopted (#1706)`.

### Task 9 : hook `Stop` sur les tests ciblés

**Files :**
- Create : `.claude/hooks/targeted_tests.py`, `.claude/hooks/test_targeted_tests.py`
- Modify : `.claude/settings.json` (clé `hooks.Stop`)
- Modify : `docs/tests-boucle.md` (section « Hooks »)

**Interfaces :**
- Consumes : décision `testmon_retenu` (tâche 8).
- Produces : `changed_files(repo: Path) -> list[str]` (diff de travail par rapport à `HEAD` plus fichiers non suivis, via `git -C`), `fingerprint(repo: Path, files: list[str]) -> str` (empreinte du contenu), `backend_targets(files: list[str], tests_root: Path) -> list[str]`, `frontend_targets(files: list[str]) -> list[str]`. Cache d'empreinte : `<git-dir>/claude-targeted-tests.sha` (`git rev-parse --git-dir`). Délai total : 180 s.

- [ ] **Step 1 :** tests `unittest` (dépôt git temporaire construit dans `setUp`) :
  - `test_stop_hook_active_noop` : stdin `{"stop_hook_active": true}` → code 0, aucune commande lancée (le lanceur de commandes est injecté et compté)
  - `test_unchanged_fingerprint_noop` : même empreinte que le cache → rien lancé
  - `test_no_source_change_noop` : seuls `docs/*.md` modifiés → rien lancé
  - `test_frontend_targets` : `["frontend/components/A.tsx", "frontend/lib/b.ts"]` → `["components/A.tsx", "lib/b.ts"]` (chemins relatifs à `frontend/`, passés à `npx vitest related --run`)
  - `test_backend_targets_direct_test` : `["backend/tests/test_x.py"]` → `["tests/test_x.py"]`
  - `test_backend_targets_import` : `["backend/app/services/foo.py"]` avec un test contenant `from app.services.foo import` et un autre `import app.services.foo` → les deux ; un test sans import → absent
  - `test_red_blocks` : lanceur renvoyant un code ≠ 0 → stdout `{"decision": "block", "reason": ...}` avec la sortie tronquée aux 40 dernières lignes
  - `test_timeout_warns` : lanceur qui dépasse le délai → code 0, avertissement sur stderr, pas de blocage
- [ ] **Step 2 :** `python3 -m unittest .claude/hooks/test_targeted_tests.py` → échec.
- [ ] **Step 3 :** implémenter. Backend : si `testmon_retenu`, `uv run pytest --testmon -n 0 -q` ; sinon `uv run pytest <cibles> -n 0 -q` (import direct seulement, volontairement). Frontend : `npx vitest related --run <cibles>`. L'empreinte est écrite après un passage vert.
- [ ] **Step 4 :** `python3 -m unittest .claude/hooks/test_targeted_tests.py .claude/hooks/test_test_gate.py` → OK.
- [ ] **Step 5 :** brancher dans `.claude/settings.json` ; `python3 -m json.tool .claude/settings.json`. Suite complète backend (`FULL_SUITE=1 uv run pytest -m "not integration" --migrations`) et frontend (`FULL_SUITE=1 npm test`) : fin de #1706.
- [ ] **Step 6 :** commit `chore(claude): run targeted tests when a turn ends with changed code (#1706)`.

## Sous-issue #1707 (à envisager)

### Task 10 : découpage du job backend en CI

**Files :**
- Modify : `backend/pyproject.toml` (dev : `pytest-split`), `backend/uv.lock`
- Create : `backend/.test_durations` (généré)
- Modify : `.github/workflows/ci.yml` (job `backend` en matrice `group: [1, 2]`), `.github/scripts/ci-ok.sh` et son test si les noms de jobs changent
- Modify : `docs/tests-boucle.md` (rafraîchir les durées)

- [ ] **Step 1 :** `uv add --dev pytest-split` ; `uv run pytest -m "not integration" --migrations --store-durations -n 0` (si `--store-durations` est compatible xdist dans la version installée, garder `-n 4`).
- [ ] **Step 2 :** vérifier la partition : pour `g` dans 1, 2 : `uv run pytest -m "not integration" --migrations --splits 2 --group g --splitting-algorithm least_duration --collect-only -q | tail -1` ; somme = collecte complète (même commande sans `--splits`).
- [ ] **Step 3 :** `ci.yml` : matrice sur le job `backend`, ruff dans un seul groupe ; `ci-ok` compte les deux instances (matrice : un seul `needs.backend.result` agrégé, vérifier dans le test `test-ci-ok.sh` qu'aucun cas ne change).
- [ ] **Step 4 :** `bash .github/scripts/test-ci-ok.sh` OK ; YAML valide. Documenter la commande de rafraîchissement des durées. Commit `ci(backend): split the unit suite across two runners (#1707)`.

### Task 11 : outillage de mutation

**Files :**
- Modify : `backend/pyproject.toml` (dev : `mutmut` ; section `[tool.mutmut]` : `paths_to_mutate = ["app/"]`, `tests_dir = ["tests/"]`, options pytest `-m "not integration" -n 0 -p no:cacheprovider`), `backend/uv.lock`, `.gitignore` (`mutants/`, `.mutmut-cache`)
- Modify : `frontend/package.json` (dev : `@stryker-mutator/core`, `@stryker-mutator/vitest-runner`), `frontend/package-lock.json`
- Create : `frontend/stryker.config.json` (`testRunner: "vitest"`, `incremental: true`, `incrementalFile` sous `reports/`, `reporters: ["clear-text", "json"]`), `.gitignore` (`frontend/reports/`, `frontend/.stryker-tmp/`)
- Modify : `docs/tests-boucle.md` (section « Mutation » : commandes par chemin et lecture du score)

**Interfaces :**
- Produces : commandes `cd backend && uv run mutmut run "<motif de mutants>"` puis `uv run mutmut results`, et `cd frontend && npx stryker run --mutate "<glob>"` ; score = tués / (tués + survivants), timeouts exclus.

- [ ] **Step 1 :** installer et configurer. Vérifier la syntaxe exacte de restriction par chemin dans la version installée de mutmut (motif de noms de mutants) et documenter celle qui marche.
- [ ] **Step 2 :** preuve backend : `mutmut` sur un petit module (`app/core/gender.py`) → score affiché ; supprimer à la main une assertion de son test (sans committer) → le score baisse ; restaurer.
- [ ] **Step 3 :** preuve frontend : Stryker sur un petit fichier `lib/` → score affiché ; même contre-épreuve.
- [ ] **Step 4 :** commit `chore(tests): mutation tooling for backend and frontend (#1707)`.

### Task 12 : procédure de consolidation, inventaire, lot 1 (`test_raceresult.py`)

**Files :**
- Modify : `docs/tests-boucle.md` (section « Consolider un lot », procédure ci-dessous)
- Create : `docs/superpowers/specs/2026-10-20-test-consolidation-inventaire.md` (liste ordonnée des lots, une ligne par lot : fichiers de test, code source couvert, nombre de tests, statut)
- Modify : `backend/tests/test_raceresult.py`

**Interfaces :**
- Consumes : commandes de mutation (tâche 11).
- Produces : la procédure suivie par les tâches 13 à 16 et l'inventaire qui définit les lots de la tâche 16.

Procédure d'un lot (à écrire dans la doc, puis appliquer) :
1. Référence : tests passés, couverture de lignes du code couvert (`uv run --with pytest-cov pytest <tests> --cov=<module> -n 0` ou `npx vitest run <tests> --coverage`), score de mutation sur ce code (budget 30 min ; au-delà, restreindre aux fonctions dont des tests seront supprimés ou fusionnés ; timeouts exclus des deux côtés).
2. Consolider : `parametrize` / `it.each` pour les cas répétés ; supprimer les tests d'interaction (vérification d'appels de mocks), de structure, et ceux de haut niveau déjà couverts plus bas. Aucune assertion de comportement observable ne disparaît sans qu'un autre test la porte.
3. Garder le lot seulement si score de mutation ≥ référence et couverture ≥ référence ; sinon annuler entièrement le lot.
4. Un commit par lot : `test(<zone>): consolidate <fichier> (#1707)`, corps : `tests: A -> B, mutation: X/Y -> X'/Y', coverage: P% -> P'%`.
5. Mettre à jour la ligne de l'inventaire.

- [ ] **Step 1 :** écrire la procédure et l'inventaire (tous les fichiers de test backend et frontend groupés par zone : un fournisseur de scraper, un service, un dossier de routes, un dossier de composants ; ordre par nombre de lignes décroissant ; les quatre premiers lots sont ceux des tâches 12 à 15).
- [ ] **Step 2 :** appliquer la procédure au lot `test_raceresult.py` (code couvert : `app/scrapers/raceresult*.py`).
- [ ] **Step 3 :** commit du lot (ou consignation de l'annulation dans l'inventaire).

### Task 13 : lot 2, `backend/tests/test_services/test_import_service.py`

- [ ] Procédure de la tâche 12, code couvert `app/services/import_service.py` ; commit ou annulation consignée.

### Task 14 : lot 3, `frontend/.../RaceFinishers.test.tsx`

- [ ] Procédure de la tâche 12 (Stryker sur le composant `RaceFinishers`) ; commit ou annulation consignée.

### Task 15 : lot 4, `frontend/.../AppNav.test.tsx`

- [ ] Procédure de la tâche 12 (Stryker sur `AppNav`) ; commit ou annulation consignée.

### Task 16 et suivantes : un lot de l'inventaire par tâche

- [ ] Pour chaque ligne restante de l'inventaire, dans l'ordre : procédure de la tâche 12, commit ou annulation consignée. Le contrôleur peut s'arrêter entre deux lots ; chaque lot commité est acquis.

### Task finale : remesure et clôture de l'epic

**Files :**
- Modify : `docs/superpowers/specs/2026-10-20-test-process-sondage.md` (section « Avant / après »)

- [ ] **Step 1 :** sous protocole : durée de la suite unitaire backend (sans et avec `--migrations`), durée `npm test`, nombre de tests des deux côtés, couverture des deux côtés ; comparaison avec les chiffres du 20/10 (backend 6 823 tests, 98 % ; frontend 3 224 tests, 92,37 % des lignes).
- [ ] **Step 2 :** suites complètes vertes (`FULL_SUITE=1`), `ruff check .`, `npm run lint`, `npm run build`.
- [ ] **Step 3 :** commit `docs(tests): before/after measurements for #1704`.
