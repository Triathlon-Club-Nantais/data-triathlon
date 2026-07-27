# Tasks: Skill Claude Code « onboard »

**Input** : design docs sous `/specs/001-onboard-skill/`

**Prerequisites** : `plan.md` ✅, `spec.md` ✅, `research.md` ✅, `data-model.md` ✅, `contracts/state-schema.json` ✅, `quickstart.md` ✅

**Tests** : la spec n'exige **pas** de tests unitaires au sens pytest (voir §Complexity Tracking du plan). La validation passe par le rejeu manuel de `quickstart.md` en fin de cycle.

## Format : `[ID] [P?] [Story?] Description`

- **[P]** : parallélisable (fichier distinct, pas de dépendance).
- **[Story]** : rattache à une user story (`US1`, `US2`, `US3`) — obligatoire sur les phases US.

## Path Conventions

- Skill : `.claude/skills/onboard/`
- References : `.claude/skills/onboard/references/`
- Racine : `.gitignore` (une ligne à ajouter)

---

## Phase 1 : Setup (infrastructure partagée)

**Purpose** : préparer l'accueil du skill et son état persistant.

- [X] T001 Créer le dossier `.claude/skills/onboard/` et son sous-dossier `.claude/skills/onboard/references/` (deux dossiers vides à ce stade).
- [X] T002 Ajouter la ligne `.claude/skills/onboard/state.json` au `.gitignore` racine, sans supprimer les entrées existantes.
- [X] T003 [P] Copier `specs/001-onboard-skill/contracts/state-schema.json` en `.claude/skills/onboard/state-schema.json` — sert de référence embarquée que le skill peut citer sans dépendre du dossier `specs/` (qui pourrait bouger).

---

## Phase 2 : Foundational (SKILL.md squelette)

**Purpose** : poser le SKILL.md avec son frontmatter et sa charpente. Toutes les user stories dépendent de cette base.

**⚠️ CRITICAL** : rien de US1/US2/US3 ne peut commencer avant.

- [X] T004 Créer `.claude/skills/onboard/SKILL.md` avec le frontmatter YAML complet :
  - `name: "onboard"`
  - `description: "Onboarding guidé du dépôt data-triathlon : vérification prérequis, installation, DB, tests, dev, tour de code adapté au profil, présentation outillage IA."`
  - `argument-hint: "Optionnel — profil à privilégier (fullstack / backend / frontend)"`
  - `compatibility: "data-triathlon uniquement — dépend de Taskfile.yml, AGENTS.md, .specify/memory/constitution.md"`
  - `user-invocable: true`
  - `disable-model-invocation: false`
  - Vérifier que le YAML parse (pas de tab, guillemets équilibrés).
- [X] T005 Ajouter dans `SKILL.md` la section `## Introduction` : 3-5 lignes en français qui expliquent au contributeur ce que le skill va faire, et rappelle qu'il peut poser des questions libres à tout moment (FR-010). Renvoi explicite à `AGENTS.md` pour le détail opérationnel (FR-011).
- [X] T006 Ajouter dans `SKILL.md` la section `## Détection de l'état initial` : liste des sondes shell à exécuter au démarrage (venv, node_modules, .env, DB, ports 8001/3000, gh installé/authentifié). Décrit précisément **quelle sonde donne quel signal** et comment la combiner avec `state.json` (voir `data-model.md` §Invariants).
- [X] T007 Ajouter dans `SKILL.md` la section `## Gestion de l'état persistant` : format du `state.json`, référence au `state-schema.json` embarqué, règle « détection factuelle prime sur state déclaré » (D3 de `research.md`), procédure d'invalidation si `schema_version` diverge.
- [X] T008 Ajouter dans `SKILL.md` la section `## Questions initiales` : la liste des 5 questions Q1-Q5 exactement formulées, avec les enum de réponses attendues (voir `data-model.md` Entité 1). Instruction explicite au LLM : utiliser `AskUserQuestion` pour Q1-Q5, jamais du prompt libre.

---

## Phase 3 : User Story 1 — Premier onboarding « from scratch » (Priority : P1) 🎯 MVP

**Goal** : un contributeur sur clone frais va de `git clone` à `task test` vert + `task dev` en < 15 min, guidé par 5 questions.

**Independent Test** : rejouer le §Scénario 1 de `quickstart.md`. Invariants attendus : `backend/.env` créé, `.venv` présent, DB > 100 Ko, `curl :8001/docs` = 200, `curl :3000` = 200/307, `state.json` complet et valide.

### Implementation for User Story 1

- [X] T009 [US1] Ajouter dans `SKILL.md` la section `## Étape 1 — Vérification des prérequis` : commandes `command -v uv/node/npm/git/task/gh`, contrôle des versions minimales (`uv >= 0.11`, `node >= 20`), messages d'install officiels si absent (`curl -LsSf https://astral.sh/uv/install.sh | sh`, install de `task` via `brew` ou apt, `gh` via dépôt officiel). FR-003, FR-004.
- [X] T010 [US1] Ajouter dans `SKILL.md` la section `## Étape 2 — Création de backend/.env` : si `.env` absent, écrire `DATABASE_URL=sqlite:///./triathlon.db` (branche `db_choice=sqlite`) ou demander l'URI Supabase (branche `db_choice=supabase`) ; si `.env` présent, lire et afficher la valeur `DATABASE_URL` puis passer (FR-005 clarifié).
- [X] T011 [US1] Ajouter dans `SKILL.md` la section `## Étape 3 — Installation` : lancer `task install` (avec fallback `uv sync` dans `backend/` + `npm install` dans `frontend/` si `task` absent). Vérification post-install : `[ -d backend/.venv ] && [ -d frontend/node_modules ]`. FR-006.
- [X] T012 [US1] Ajouter dans `SKILL.md` la section `## Étape 4 — Base de données` : `task b:reset-db` (SQLite). En cas de choix Supabase, ne PAS lancer reset — expliquer que la commande refuse toute DB non-SQLite (protection intégrée de `scripts/reset_db.py`). Vérification : `stat -c%s backend/triathlon.db` > 100 Ko pour SQLite. Marque `steps.db=done` ou `skipped`.
- [X] T013 [US1] Ajouter dans `SKILL.md` la section `## Étape 5 — Tests santé` : `task test` (avec fallback commandes brutes). En cas d'échec : afficher la sortie, marquer `steps.tests=failed`, **arrêter** et proposer de partager la sortie ou quitter (FR-007). Aucun passage à l'étape suivante.
- [X] T014 [US1] Ajouter dans `SKILL.md` la section `## Étape 6 — Serveurs de dev` : détecter si `:8001` ou `:3000` répondent déjà (FR-013), sinon lancer `task dev` en arrière-plan et vérifier `curl :8001/docs` = 200 et `curl :3000` = 200/307. Marque `steps.dev=done` ou `skipped`.
- [X] T015 [US1] Ajouter dans `SKILL.md` la section `## Étape 7 — Tour de code` : brancher sur `answers.profile` (`fullstack` → référencer `references/tour-fullstack.md`, `backend` → tour-backend, `frontend` → tour-frontend). Instruction au LLM : **charger** le fichier référence, **pas** recopier son contenu. Marque `steps.tour=done`.
- [X] T016 [US1] Ajouter dans `SKILL.md` la section `## Étape 8 — Outillage IA` : résumé Speckit vs Superpowers en 3-4 lignes, pointeurs vers `docs/WORKFLOW-IA.md`, `.specify/memory/constitution.md` (mentionner v1.0.0 + 6 principes sans les recopier). FR-009, FR-011.
- [X] T017 [US1] Ajouter dans `SKILL.md` la section `## Étape 9 — Première feature (gh)` : logique en 3 branches selon D4/`research.md` (`gh` absent → install + skip ; `gh` présent non-auth → `gh auth login` + skip ; `gh issue list --label "good first issue" --state open --json number,title,url,labels` → filtrer par profil si labels correspondants). Fallback texte manuel. FR-015. Marque `steps.first_feature=done|skipped`.
- [X] T018 [P] [US1] Créer `.claude/skills/onboard/references/tour-fullstack.md` : parcours pédagogique (stack §AGENTS.md, architecture en couches, modèle normalisé `docs/modele-donnees.md`, un scraper simple `app/scrapers/klikego.py`, `services/import_service.py`, un router `app/api/v1/`, puis frontend App Router + `lib/api/` + SSE). En français, avec des liens cliquables vers les fichiers et **pas** de recopie d'AGENTS.md.
- [X] T019 [P] [US1] Créer `.claude/skills/onboard/references/tour-backend.md` : parcours restreint backend (`app/core/`, `app/models/`, `app/services/`, un scraper `klikego.py`, un router `api/v1/`). Cite les endpoints exposés pour un contributeur backend qui livrera de nouveaux endpoints.
- [X] T020 [P] [US1] Créer `.claude/skills/onboard/references/tour-frontend.md` : parcours restreint frontend (App Router, `lib/api/client.ts`, `sse.ts`, `types.ts`, un composant `scrape/` + un composant `results/`). Cite les endpoints backend consommés **sans** ouvrir le backend (US3 acceptance scenario 1).

**Checkpoint US1** : après T009-T020, un contributeur sur clone frais peut faire tourner le skill de bout en bout en profil `fullstack`, `backend` ou `frontend`. Rejouer Scénario 1 de `quickstart.md`.

---

## Phase 4 : User Story 2 — Retour après pause (Priority : P2)

**Goal** : un contributeur avec `.venv`, `node_modules` et `.env` déjà en place complète le parcours en < 3 min, sans réinstall inutile.

**Independent Test** : rejouer le §Scénario 2 de `quickstart.md`. Invariants : `uv sync`/`npm install` **non** exécutés inutilement, `task test` rejoué rapidement, `state.answers.experience_level=retour`.

### Implementation for User Story 2

- [ ] T021 [US2] Enrichir dans `SKILL.md` la section « ## Détection de l'état initial » (T006) avec la règle explicite : si `state.steps.install=done` **ET** `venv_present=true` **ET** `node_modules_present=true`, marquer `steps.install=skipped` et le signaler au contributeur (« deps déjà installées, on saute »). Ne PAS forcer un nouveau `uv sync`.
- [ ] T022 [US2] Ajouter dans `SKILL.md` la règle : Q3 (choix DB) **n'est pas posée** si `.env` préexistant contient un `DATABASE_URL` non vide. Le skill affiche la valeur détectée et considère `answers.db_choice` comme dérivée (`sqlite` si `DATABASE_URL` commence par `sqlite:`, `supabase` sinon).
- [ ] T023 [US2] Ajouter dans `SKILL.md` §Étape 5 (tests) l'exception : **même** en mode retour + `steps.tests=done` dans un state précédent, `task test` est **rejoué**. Il coûte ~5s et garantit qu'aucune régression locale ne passe silencieusement (SC-005).
- [ ] T024 [US2] Ajouter dans `SKILL.md` §Étape 7 (tour de code) : si `answers.verbosity=courte`, réduire le tour à un résumé de 5-7 lignes (stack, sens du flux `api → services → repositories`, `is_tcn` centralisé, TDD sans réseau, langue métier vs technique) + les liens vers les 3 documents clés. Le contributeur relit lui-même s'il veut.

**Checkpoint US2** : rejouer Scénario 2 de `quickstart.md`, chronomètre < 3 min.

---

## Phase 5 : User Story 3 — Contributeur mono-couche (Priority : P3)

**Goal** : un contributeur `frontend` ou `backend` seul reçoit un tour de code strictement filtré à sa couche + suggestion `good first issue` filtrée.

**Independent Test** : rejouer §Scénario 3 de `quickstart.md`. Invariants : le tour ne mentionne pas les scrapers si profil=frontend ; la suggestion `good first issue` est filtrée sur `label:frontend` ou `label:backend` quand disponibles.

### Implementation for User Story 3

- [ ] T025 [US3] Enrichir la section « ## Étape 9 — Première feature (gh) » (T017) avec la logique de filtrage : passer `--label frontend` / `--label backend` en supplément de `--label "good first issue"` selon `answers.profile`. Si aucune issue ne matche le double filtre, retomber sur `good first issue` seul et signaler « aucune issue filtrée pour ton profil, voici toutes les good first issues ».
- [ ] T026 [US3] Renforcer T018/T019/T020 : chaque `tour-*.md` doit **explicitement** commencer par un rappel de sa couche cible et une phrase « si tu veux voir l'autre couche, relance /onboard avec un autre profil ». Évite qu'un contributeur mono-couche pense que la doc lui manque.

**Checkpoint US3** : rejouer Scénario 3, vérifier que le tour front ne cite jamais `app/scrapers/` ni `services/import_service.py`.

---

## Phase 6 : Polish & Cross-Cutting Concerns

**Purpose** : robustesse, cas de bord, préparation à la revue.

- [X] T027 Ajouter dans `SKILL.md` une section `## Questions libres du contributeur` : instruction au LLM pour accepter à tout moment une question hors séquence (« qu'est-ce que `is_tcn` ? », « pourquoi les temps en strings ? »), y répondre depuis `AGENTS.md` et le code, puis proposer de reprendre l'étape en cours. FR-010.
- [X] T028 Ajouter dans `SKILL.md` une section `## Gestion des erreurs et abandon` : comportement précis si le contributeur tape `stop`/`quit` (fermer proprement, sauver `state.json`, message « à bientôt, relance /onboard pour reprendre ») ; comportement sur `steps.<X>=failed` (afficher la sortie brute, proposer retry ou skip explicite, ne jamais avancer silencieusement).
- [X] T029 [P] Vérifier la conformité française du texte du SKILL.md et des 3 `tour-*.md` : passe manuelle pour repérer tout anglicisme visible par l'utilisateur (SC-006, principe I). Traduire tout ce qui doit l'être ; laisser les identifiants techniques (`state.json`, `venv`, `uv sync`) en l'état.
- [ ] T030 [P] Rejouer manuellement les 3 scénarios + 4 cas de bord de `quickstart.md`. Chronométrer Scénario 1 (< 15 min) et Scénario 2 (< 3 min). Documenter chaque run dans un commentaire de la PR (SC-001, SC-005, signature de validation).
- [ ] T031 Créer 2-3 issues GitHub étiquetées `good first issue` (dépendance externe hors code, mais nécessaire pour que FR-015 produise un résultat utile en pratique). Piste : issues #33 (liens non supportés), ou petites features front/back qui traînent. **Cette tâche peut être déléguée** à un mainteneur du projet — la noter comme prérequis pour que le skill soit vraiment complet.
- [ ] T032 Mettre à jour la description de la PR de livraison avec la signature de validation `quickstart.md` (voir §Signature de validation de `quickstart.md`) + un lien vers l'issue #82 (Closes #82).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** — T001, T002, T003 : peuvent se faire en parallèle, seule T003 dépend du chemin créé par T001.
- **Phase 2 (Foundational)** — T004-T008 : SÉRIE stricte (même fichier `SKILL.md` en construction). Bloque Phase 3+.
- **Phase 3 (US1)** — T009-T017 en série (même fichier `SKILL.md`), T018/T019/T020 en parallèle avec T009-T017 (fichiers `references/*.md` distincts).
- **Phase 4 (US2)** — T021-T024 : dépendent de T006, T007, T013, T015 respectivement. Série stricte.
- **Phase 5 (US3)** — T025-T026 : T025 dépend de T017, T026 dépend de T018/T019/T020.
- **Phase 6 (Polish)** — T027, T028 en série ; T029, T030 en parallèle ; T031 hors code (délégable) ; T032 dernière (post-validation).

### Within Each Story

- Toutes les tâches qui écrivent dans `SKILL.md` sont **sérielles** (même fichier).
- Les tâches `tour-*.md` sont **parallèles** entre elles (fichiers distincts).
- La validation quickstart (T030) est la dernière porte avant PR.

### Parallel Opportunities

- **Setup (Phase 1)** : T001 puis T002 || T003.
- **US1 (Phase 3)** : T018, T019, T020 peuvent tourner **en parallèle** avec les tâches T009-T017 (autres fichiers).
- **Polish (Phase 6)** : T029 et T030 en parallèle. T031 hors ligne critique.

---

## Parallel Example : User Story 1

```bash
# Trois tour-*.md peuvent être rédigés en parallèle par 3 sous-agents :
Task: "Rédiger .claude/skills/onboard/references/tour-fullstack.md (parcours pédagogique complet)"
Task: "Rédiger .claude/skills/onboard/references/tour-backend.md (parcours backend seul)"
Task: "Rédiger .claude/skills/onboard/references/tour-frontend.md (parcours frontend seul)"
```

Pendant ce temps, l'agent principal enchaîne T009 → T017 dans `SKILL.md` (fichier unique, sérialisation obligatoire).

---

## Implementation Strategy

### MVP First (US1 uniquement)

1. Phase 1 (Setup) : T001-T003.
2. Phase 2 (Foundational) : T004-T008.
3. Phase 3 (US1) : T009-T020.
4. **STOP & VALIDATE** : rejouer §Scénario 1 de `quickstart.md`. Si OK, on tient l'MVP.
5. Ouvrir une PR (ou continuer sur la même branche selon la stratégie de livraison choisie).

### Incremental Delivery

- MVP US1 : premier onboarding fonctionne → PR mergeable, valeur immédiate.
- US2 ajoutée : mode « retour après pause » → PR incrémentale.
- US3 ajoutée : filtrage par profil raffiné → PR incrémentale.
- Polish : robustesse + validation quickstart complète.

### Livraison recommandée sur ce projet

Compte tenu de la taille du skill (< 500 lignes de Markdown total) et de l'unité conceptuelle de l'onboarding, **une seule PR** pour US1+US2+US3+Polish est plus logique qu'une série d'incréments. La colonne « MVP » du plan sert de garde-fou (si Phase 3 ne rentre pas dans le temps prévu, US2/US3 partent en suivi).

---

## Notes

- Les tâches T018-T020 sont des `[P]` mais **au sein de la même PR** : ne pas les mettre dans des branches séparées.
- La tâche T031 (issues `good first issue`) est **hors code** — elle peut être faite avant, pendant ou après le développement du skill, mais elle DOIT être faite avant que la fonctionnalité soit annoncée aux contributeurs (sinon FR-015 tombe systématiquement sur le fallback texte).
- Aucun test pytest / vitest : voir §Complexity Tracking du `plan.md`. La validation passe par `quickstart.md` (T030).
- Commits : Conventional Commits en français, un commit par étape logique (ex : `feat(skill): squelette SKILL.md avec frontmatter (T004-T008)`).
