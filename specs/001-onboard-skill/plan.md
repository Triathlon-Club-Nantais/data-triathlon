# Implementation Plan: Skill Claude Code « onboard »

**Branch**: `001-onboard-skill` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-onboard-skill/spec.md`

## Summary

Livraison d'un **skill Claude Code** invocable via `/onboard`, qui guide un
nouveau contributeur (ou revenant) du `git clone` à sa première contribution.
Le skill est **conversationnel** (jusqu'à 5 questions via `AskUserQuestion`),
**adaptatif** (3 profils : fullstack / backend / frontend), **stateful**
(reprise via `.claude/skills/onboard/state.json` git-ignoré) et **intégré au
projet** (utilise `task`, `gh`, la constitution v1.0.0, `AGENTS.md`).

Approche technique : un **unique** `SKILL.md` qui contient l'intégralité du
script conversationnel en Markdown structuré (patron des skills `speckit-*`
déjà présents), assisté de **3 ressources auxiliaires** : un JSON schema
pour valider l'état persisté, une checklist de smoke-tests que le skill
exécute lui-même (« `curl :8001/docs` renvoie 200 »), et un lot d'issues
d'onboarding taguées `good first issue` **côté GitHub** (hors code, mais
prérequis pour que FR-015 soit utile en pratique).

## Technical Context

**Language/Version** : Markdown (SKILL.md) avec frontmatter YAML. Aucun code
Python/JS/TS écrit — le skill est **du texte** interprété par Claude Code, qui
appelle les outils du harnais (`Bash`, `Read`, `Write`, `AskUserQuestion`).

**Primary Dependencies** :
- Claude Code CLI (harnais qui charge `.claude/skills/*/SKILL.md`)
- Outils système : `uv >= 0.11`, `node >= 20`, `npm >= 10`, `git`, `task`
  (optionnel), `gh` (recommandé pour FR-015)
- Fichiers projet lus par le skill : `AGENTS.md`, `README.md`,
  `Taskfile.yml`, `.specify/memory/constitution.md`, `docs/WORKFLOW-IA.md`,
  `docs/modele-donnees.md`.

**Storage** : `.claude/skills/onboard/state.json` (git-ignoré, format JSON
minimal). Aucune DB, aucun cache.

**Testing** : le skill est du contenu Markdown ; il n'a **pas de test
unitaire au sens code**. Trois niveaux de validation :
1. **Manuel guidé** — un `quickstart.md` documente un scénario
   reproductible que le mainteneur exécute avant le merge.
2. **Auto-vérification par le skill lui-même** — à chaque étape « exécuter
   `task install` puis vérifier », le skill contrôle un artefact concret
   (`backend/.venv/` existe, `backend/triathlon.db` fait > 1 Mo,
   `curl :8001/docs` renvoie 200) et échoue explicitement sinon (FR-007).
3. **Lint YAML** du frontmatter — assurer qu'il parse et que `name:
   onboard` est unique dans `.claude/skills/`.

**Target Platform** : Linux / macOS / WSL avec shell POSIX. Le harnais
Claude Code s'exécute sur toutes ces plateformes.

**Project Type** : **artefact d'outillage IA** (aucune des catégories
« single project / web app / mobile » du template ne s'applique
exactement). Rangé sous `.claude/skills/onboard/` au même titre que les
skills `speckit-*` déjà en place.

**Performance Goals** :
- SC-001 : 15 min max pour l'onboarding complet
- SC-005 : 3 min max pour le mode « je connais déjà »
- Le skill lui-même est instantané (pas de calcul) ; le budget temps est
  dominé par `task install` (≈ 60-90s) et `task b:reset-db` (≈ 15s).

**Constraints** :
- Aucun texte visible par l'utilisateur en anglais (principe I).
- Aucune modification de code produit sauf `backend/.env` (FR-012).
- Ne duplique pas `AGENTS.md` — y renvoie (FR-011).
- L'unique fichier écrit hors `.claude/skills/onboard/` est `backend/.env`
  (créé si absent, sinon skip).

**Scale/Scope** : le skill cible **~5 à 10 contributeurs** sur la durée de
vie du projet (club amateur). Pas de scale horizontal, pas de concurrence.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage des 6 principes de la constitution v1.0.0 :

| # | Principe | Statut | Commentaire |
|---|----------|--------|-------------|
| I | Langue : français métier / English technique | ✅ OK | Frontmatter YAML en anglais (`name`, `description`), corps du SKILL en français, exemples de commandes en anglais (`gh`, `uv`). |
| II | Architecture en couches (api → services → repositories → DB) | ✅ **N/A** | Le skill ne touche pas le backend. Aucun risque de contournement de couche. |
| III | TDD sans réseau (non-négociable) | ⚠️ Justifié | Le skill est du Markdown, pas du code Python. Pas de test unitaire au sens strict — remplacé par un `quickstart.md` reproductible et auto-vérifications intégrées (voir §Testing). L'esprit du principe (« ne rien livrer sans validation ») est respecté. Documenté ci-dessous dans Complexity Tracking. |
| IV | Contrats API et CLI stables | ✅ OK | Le skill n'expose pas d'API. Il **consomme** trois contrats stables : les commandes `task` documentées, `gh issue list --json`, et le fichier `.specify/memory/constitution.md`. Ces contrats sont déjà stabilisés. |
| V | Neutralité par défaut des paramètres transverses | ✅ **N/A** | Le skill n'ajoute pas d'endpoint API ni de flag CLI transverse. |
| VI | Simplicité / YAGNI | ✅ OK | Un seul `SKILL.md`, un `state.json`, un `quickstart.md`, une checklist de smoke-tests. Pas de code Python, pas de dépendance externe ajoutée. |

**Gate result** : passe. Une seule violation partielle (principe III),
justifiée en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-onboard-skill/
├── plan.md              # Ce fichier
├── spec.md              # Spec fonctionnelle (déjà en place)
├── research.md          # Phase 0 (généré ci-dessous)
├── data-model.md        # Phase 1 (généré ci-dessous)
├── quickstart.md        # Phase 1 : scénario manuel de validation
├── contracts/
│   └── state-schema.json  # Schéma JSON du state.json persisté
└── checklists/
    └── requirements.md  # Checklist qualité de spec (déjà en place)
```

### Source Code (repository root)

Aucun code source produit. Un seul artefact livré, avec 2 fichiers de
support et 1 addition au `.gitignore` :

```text
.claude/skills/onboard/
├── SKILL.md                        # Le skill lui-même (frontmatter YAML + script Markdown)
├── references/
│   ├── tour-fullstack.md           # Chemin de lecture du code pour profil fullstack
│   ├── tour-backend.md             # Chemin de lecture du code pour profil backend
│   └── tour-frontend.md            # Chemin de lecture du code pour profil frontend
└── (à l'exécution, généré)
    └── state.json                  # État persistant, git-ignoré

.gitignore                          # + 1 ligne : .claude/skills/onboard/state.json
```

**Structure Decision** : le skill est **auto-contenu** dans
`.claude/skills/onboard/`. Les fichiers `references/tour-*.md` sont
extraits du `SKILL.md` pour trois raisons : (a) ils rendent le corps
principal du skill lisible, (b) ils peuvent être mis à jour indépendamment
si le code du projet bouge, (c) ils sont facilement diffables en revue.
Aucune modification de `backend/` ni `frontend/`.

## Complexity Tracking

*Rempli parce que la Constitution Check ci-dessus signale une violation
partielle du principe III.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Pas de test unitaire au sens du principe III** (`uv run pytest -m "not integration"`) | Le skill est **du texte Markdown** exécuté par un LLM à travers un harnais interactif. Il n'y a pas de fonction Python à tester — l'unité de « comportement » est la conversation, non déterministe par nature. | Écrire une pseudo-suite pytest qui parse le SKILL.md pour en extraire les invariants (frontmatter valide, commandes shell présentes, ≤ 5 questions) a été considéré et **rejeté** : ça teste la forme, pas le fond, pour un coût de maintenance qui dépasserait le fichier testé. **Alternative retenue** : (1) un `quickstart.md` reproductible qui documente une session complète à rejouer manuellement avant merge ; (2) le skill lui-même vérifie ses étapes (`.venv` créé, DB peuplée, `curl :8001` OK) — les smoke-tests sont dans le comportement du skill, pas à côté. |

## Phase 0 — Research & Design Decisions

### Décision 1 — Structure du SKILL.md

**Décision** : un unique `SKILL.md` avec frontmatter YAML, corps en
Markdown, imports de ressources annexes via mentions explicites (`Lis
.claude/skills/onboard/references/tour-backend.md`). Pas de scripts bash
séparés — le skill invoque directement les outils Claude Code (`Bash`,
`Read`).

**Rationale** : c'est le patron des skills `speckit-*` déjà en place. Un
contributeur qui ouvre `.claude/skills/onboard/` retrouve la même
structure que ce qu'il connaît des autres skills du repo.

**Alternatives considérées** :
- Skill + script bash externalisé (`scripts/onboard.sh`) : rejeté, ajoute
  une couche shell qui doit rester en synchro avec le Markdown.
- Skill mono-fichier sans références annexes : rejeté, le SKILL.md
  atteindrait ~800 lignes, illisible.

### Décision 2 — Format du `state.json`

**Décision** : JSON plat, minimal, versionné par un champ `schema_version`.
Une seule clé racine par étape (`step_prerequisites`, `step_install`,
`step_db`, etc.), valeur = `"pending" | "done" | "skipped" | "failed"`.
Timestamp `last_updated` en ISO 8601. Schéma formel dans
`contracts/state-schema.json`.

**Rationale** : simple, humainement lisible, permet la reprise granulaire.
Le schéma permet de faire évoluer le format sans casser les states
existants (`schema_version=2` invalide un state=1, on redemande).

**Alternatives considérées** :
- YAML : rejeté, plus de dépendances côté script si un jour on veut lire
  le state en dehors du skill (avec `jq` c'est trivial).
- Pas de `schema_version` : rejeté, ferme la porte à toute évolution.

### Décision 3 — Détection de l'état d'installation

**Décision** : le skill exécute une série de commandes de détection au
démarrage (indépendamment du `state.json`) :
- `[ -f backend/.env ]` — .env présent ?
- `[ -d backend/.venv ]` — venv Python ?
- `[ -d frontend/node_modules ]` — deps front ?
- `[ -f backend/triathlon.db ] && [ $(stat -c%s backend/triathlon.db) -gt 100000 ]` — DB peuplée ?
- `curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/docs` — backend up ?
- `curl -s -o /dev/null -w '%{http_code}' http://localhost:3000` — front up ?

Il **combine** cette détection avec le `state.json` : si `state.step_install=done`
mais `.venv` absent, on considère `state` obsolète et on rejoue.

**Rationale** : le state seul mentirait après un `rm -rf .venv`. La
détection seule ne dit pas si le contributeur a **répondu** à une question
(profil, DB choisie).

### Décision 4 — Stratégie pour `gh` absent / non authentifié (FR-015)

**Décision** : trois branches déterministes :
1. `command -v gh` échoue → afficher la commande d'install officielle,
   proposer de skipper cette étape, retomber sur le fallback texte.
2. `gh auth status` échoue → proposer `gh auth login` avec les 2 options
   (web browser interactif, ou skip).
3. `gh issue list ... --json` échoue pour toute autre raison → afficher
   l'erreur brute (utile pour le debug) et fallback texte.

**Rationale** : chaque branche est testable en `quickstart.md` (désinstaller
gh, révoquer le token, couper le réseau). Aucune branche cachée.

**Alternatives considérées** :
- Utiliser l'API GitHub directement en `curl` : rejeté, complexité inutile,
  gestion de token à réimplémenter.
- Ignorer FR-015 si `gh` absent : rejeté, l'utilisateur est laissé sans
  suggestion, ce qui va contre l'objectif du skill.

### Décision 5 — Emplacement du `state.json` dans le gitignore

**Décision** : ajouter la ligne `.claude/skills/onboard/state.json` au
`.gitignore` racine. Ne pas ajouter le répertoire entier — les fichiers
Markdown du skill DOIVENT être commités.

**Rationale** : granularité minimale. Un contributeur qui souhaite partager
son état d'onboarding (rare, mais légitime en support) peut le forcer avec
`git add -f`.

## Phase 1 — Design Artifacts

### Data Model

Voir `data-model.md`. Trois entités logiques :
1. **Profil contributeur** (en mémoire de session, non persisté par
   défaut mais reflété dans `state.json`).
2. **État de progression** (`state.json`, schéma dans `contracts/`).
3. **État d'installation** (calculé, non stocké).

### Contracts

Un seul contrat externe : le **schéma du `state.json`** (`contracts/state-schema.json`).
JSON Schema draft-07, validable par n'importe quel linter JSON. Sert de
référence pour toute future évolution du format.

Pas de contrat API à documenter — le skill n'expose pas d'endpoint.

### Quickstart

Voir `quickstart.md`. Scénario reproductible en 3 modes (fresh, retour,
mono-couche), avec les commandes de préparation (nuke `.env`, `.venv`,
DB), les réponses attendues aux 5 questions, et les invariants à vérifier
manuellement.

### Agent Context Update

Le fichier `CLAUDE.md` racine importe `AGENTS.md` sans balises
`<!-- SPECKIT START/END -->`. Pas de mise à jour ici — le plan reste
référencé via son chemin dans les branches Speckit standard
(`specs/001-onboard-skill/plan.md`).

## Post-Design Constitution Check

Re-passage après design (Phase 1) :

| # | Principe | Statut post-design |
|---|----------|--------------------|
| I | Langue française métier / English technique | ✅ Toujours OK. |
| II | Architecture en couches | ✅ N/A confirmé — aucun couplage introduit. |
| III | TDD sans réseau | ⚠️ Toujours justifié. `quickstart.md` prend le rôle du test manuel. |
| IV | Contrats stables | ✅ Un seul nouveau contrat (`state-schema.json`), interne au skill, versionné. Aucun impact sur `/api/v1` ni sur la CLI `app.cli`. |
| V | Neutralité paramètres | ✅ N/A. |
| VI | Simplicité | ✅ 4 fichiers livrés (SKILL.md + 3 references), pas de code Python, pas de dépendance ajoutée. |

**Gate result post-design** : passe. Prêt pour `/speckit-tasks`.
