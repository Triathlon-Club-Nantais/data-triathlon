---
name: "onboard"
description: "Onboarding guidé du dépôt data-triathlon : vérification des prérequis, installation, base de données, tests, serveurs de dev, tour de code adapté au profil du contributeur (fullstack / backend / frontend), présentation de l'outillage IA embarqué (Speckit, Superpowers, constitution) et suggestion d'une première feature via GitHub."
argument-hint: "Optionnel — profil à privilégier (fullstack / backend / frontend)"
compatibility: "data-triathlon uniquement — dépend de Taskfile.yml, AGENTS.md, .specify/memory/constitution.md"
user-invocable: true
disable-model-invocation: false
metadata:
  issue: "https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/82"
  state_schema: ".claude/skills/onboard/state-schema.json"
---

## Introduction

Ce skill guide un nouveau contributeur (ou un contributeur qui revient
après une pause) sur le projet **data-triathlon**. Il vérifie les
prérequis, installe la stack, prépare une base de données de démo, lance
les tests, ouvre les serveurs de dev, puis fait un tour de code adapté à
la couche sur laquelle le contributeur va travailler.

Il s'appuie sur les fichiers déjà présents dans le dépôt (`AGENTS.md`,
`README.md`, `.specify/memory/constitution.md`, `docs/WORKFLOW-IA.md`,
`docs/modele-donnees.md`) et les **cite** sans les recopier.

Le contributeur peut poser une question libre à tout moment (« qu'est-ce
que `is_tcn` ? », « pourquoi les temps sont des strings ? ») — voir la
section « Questions libres du contributeur » en fin de fichier.

Le skill **gère la reprise** : si le contributeur ferme la session à
mi-parcours, une relance de `/onboard` reprend là où il en était (voir
« Gestion de l'état persistant »).

## Détection de l'état initial

Au démarrage, exécute (via l'outil `Bash`) ce bloc de sondes rapides pour
établir un instantané factuel de l'environnement. Timeout court (2s) sur
les sondes réseau pour ne pas bloquer.

```bash
# Prérequis système
command -v uv     && uv --version
command -v node   && node --version
command -v npm    && npm --version
command -v git    && git --version
command -v task   && task --version
command -v gh     && gh --version
command -v curl

# État d'installation
[ -f backend/.env ]              && echo "env_present=true"
[ -d backend/.venv ]             && echo "venv_present=true"
[ -d frontend/node_modules ]     && echo "node_modules_present=true"
[ -f backend/triathlon.db ] && [ "$(stat -c%s backend/triathlon.db 2>/dev/null || stat -f%z backend/triathlon.db)" -gt 100000 ] && echo "db_populated=true"

# Serveurs
curl -sSo /dev/null -w '%{http_code}' -m 2 http://localhost:8001/docs || echo "000"
curl -sSo /dev/null -w '%{http_code}' -m 2 http://localhost:3000        || echo "000"

# gh
gh auth status 2>&1 | head -1
```

**Règle d'or** : la détection factuelle **prime** sur ce que dit
`state.json`. Si `state.steps.install=done` mais `backend/.venv/` est
absent, considère `install` comme à refaire. Le state ne connaît que les
choix du contributeur ; la détection connaît la vérité du disque.

## Gestion de l'état persistant

Le skill maintient un fichier `.claude/skills/onboard/state.json` (déjà
ajouté au `.gitignore` racine). Son schéma est décrit dans
`.claude/skills/onboard/state-schema.json` (JSON Schema draft-07,
`schema_version = 1`).

**Structure attendue** :

```json
{
  "schema_version": 1,
  "last_updated": "2026-07-27T10:15:00Z",
  "answers": {
    "profile": "fullstack",
    "experience_level": "nouveau",
    "db_choice": "sqlite",
    "verbosity": "complete",
    "skip_ia_tooling": false
  },
  "steps": {
    "prerequisites":  "done",
    "install":        "done",
    "db":             "done",
    "tests":          "done",
    "dev":            "done",
    "tour":           "pending",
    "ia_tooling":     "pending",
    "first_feature":  "pending"
  }
}
```

**Chargement au démarrage** :

1. Si le fichier n'existe pas, initialise un state vide (tous les steps à
   `pending`, `answers = {}`) — sans l'écrire encore.
2. Si le fichier existe, lis-le et valide `schema_version == 1`. Toute
   valeur différente ou JSON mal formé → afficher au contributeur
   « ton état d'onboarding précédent n'est plus lisible » et proposer :
   (a) repartir de zéro (efface `state.json`), (b) quitter.
3. À chaque écriture, remets `last_updated` à l'ISO 8601 UTC courant.

**Sauvegarde** :

- Après chaque étape terminée ou skipée : écrire le state.
- Après chaque réponse à une question initiale (Q1-Q5) : écrire le state.
- Sur `SIGINT` (`Ctrl-C`) ou quand le contributeur demande à quitter :
  écrire le state avec l'étape courante marquée `failed` ou `pending`
  selon le contexte.

Un statut `failed` sur une étape **bloque** la progression : le skill
affiche un message et attend soit un retry, soit un skip explicite. Il
n'avance **jamais** silencieusement.

## Questions initiales

Au maximum **5 questions** posées via l'outil `AskUserQuestion` (jamais
en prompt libre). Chaque réponse est stockée sous `state.answers`.

### Q1 — Sur quelle couche vas-tu contribuer ?

Choix : `fullstack` | `backend` | `frontend`. Détermine le fichier
`tour-*.md` chargé à l'étape 7. Si le contributeur a passé un argument à
l'invocation (`/onboard backend`), utilise-le et **saute** la question.

### Q2 — Nouveau contributeur ou retour après pause ?

Choix : `nouveau` | `retour`. Adapte le ton et permet de sauter certaines
vérifications si `retour` + artefacts d'install déjà en place.

### Q3 — SQLite (local) ou Supabase ?

Choix : `sqlite` | `supabase`. **Saute cette question** si
`backend/.env` existe déjà et contient un `DATABASE_URL` non vide — dans
ce cas, dérive `db_choice` de la valeur détectée (`sqlite` si commence
par `sqlite:`, sinon `supabase`) et affiche la valeur pour information.

### Q4 — Version courte ou complète ?

Choix : `courte` | `complete`. `courte` = tour de code résumé, présentation
IA condensée. `complete` = tour complet.

### Q5 — Sauter la présentation Speckit/Superpowers ?

Choix : `oui` | `non`. Si `oui`, l'étape 8 (outillage IA) et l'étape 9
(première feature) sont marquées `skipped`. Utile pour un contributeur
pressé qui veut juste installer et coder.

## Étape 1 — Vérification des prérequis

**But** : s'assurer que `uv`, `node`, `npm`, `git` sont installés à des
versions minimales, et signaler `task` et `gh` (recommandés).

**Contrat** :

| Outil | Version min | Statut |
|-------|-------------|--------|
| `uv` | 0.11 | Requis |
| `node` | 20 | Requis |
| `npm` | 10 | Requis (fourni avec node) |
| `git` | — | Requis |
| `task` | v3 | Recommandé (fallback commandes brutes sinon) |
| `gh` | 2.x | Recommandé pour l'étape 9 |
| `curl` | — | Requis pour les sondes |

**Actions selon l'état** :

- Chaque outil requis absent → afficher la commande d'installation
  officielle **et attendre** que le contributeur ait installé. Vérifier
  après coup en réexécutant la sonde. Ne pas skipper.
  - `uv` : `curl -LsSf https://astral.sh/uv/install.sh | sh` (Linux/macOS).
  - `node` : renvoyer vers https://nodejs.org (LTS 20+) ou `nvm install --lts`.
  - `git` : `sudo apt install git` (Debian/Ubuntu/WSL) ou `brew install git` (macOS).
- `task` absent : ne pas bloquer. Signaler que la suite du skill utilisera
  les commandes brutes en fallback.
- `gh` absent : ne pas bloquer. Signaler que l'étape 9 sera dégradée.

**Marquer** `state.steps.prerequisites = "done"` seulement quand **tous**
les outils requis sont OK.

## Étape 2 — Création de `backend/.env`

**But** : garantir que `backend/.env` contient un `DATABASE_URL` valide.

**Branche A — `backend/.env` déjà présent** :

Lire le fichier, extraire la valeur `DATABASE_URL`, l'afficher au
contributeur pour information, marquer `state.steps` avancée. **Ne
jamais proposer d'écraser** — c'est au contributeur de supprimer le
fichier manuellement s'il veut le régénérer.

**Branche B — `backend/.env` absent, `db_choice = sqlite`** :

Créer `backend/.env` avec la ligne unique :

```
DATABASE_URL=sqlite:///./triathlon.db
```

**Branche C — `backend/.env` absent, `db_choice = supabase`** :

Rappeler au contributeur comment récupérer l'URI :
- Se connecter sur https://supabase.com, ouvrir le projet
- **Connect** → **Direct** → copier l'URI
- Format attendu : `postgresql://postgres.<ref>:<mdp>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres`

Attendre que le contributeur colle l'URI, valider un préfixe
`postgres://` ou `postgresql://` (préfixe `postgres://` sera converti en
`postgresql://` par la config, cf. `backend/app/core/config.py`), puis
créer `backend/.env` avec cette valeur.

Si la valeur collée est vide ou ne matche pas un URI Postgres, marquer
l'étape `failed` et redemander.

## Étape 3 — Installation

**But** : `backend/.venv/` créé, `frontend/node_modules/` créé.

**Si `task` disponible** :
```bash
task install
```

**Sinon (fallback)** :
```bash
cd backend  && uv sync && cd ..
cd frontend && npm install && cd ..
```

**Vérification post-install** :
```bash
[ -d backend/.venv ] && [ -d frontend/node_modules ] && echo "install OK"
```

Toute erreur → afficher la sortie brute, marquer `state.steps.install =
"failed"`, ne pas passer à l'étape suivante.

**Mode retour (`experience_level = retour`)** : si `.venv/` **et**
`node_modules/` sont déjà là, marquer `state.steps.install = "skipped"`
et le signaler explicitement (« deps déjà installées, on saute »). Ne
**pas** rejouer `uv sync` inutilement.

## Étape 4 — Base de données

**But** : DB SQLite peuplée avec le seed démo (12 épreuves, ~10 900
participations). Pour Supabase, la DB de prod n'est **pas** reset —
comportement documenté ci-dessous.

**Si `db_choice = sqlite`** :
```bash
task b:reset-db --yes   # ou: cd backend && uv run python scripts/reset_db.py --yes
```

Vérification : `[ -f backend/triathlon.db ] && [ $(stat -c%s
backend/triathlon.db) -gt 100000 ]` (empiriquement la DB seed pèse ~5 Mo).

**Si `db_choice = supabase`** :
- **Ne pas lancer `reset_db.py`**. Le script refuse déjà toute DB
  non-SQLite (protection intégrée), mais on ne le teste même pas.
- Appliquer uniquement les migrations : `task b:migrate` (ou
  `cd backend && uv run alembic upgrade head`).
- Marquer `state.steps.db = "skipped"` (pas de seed).
- Prévenir le contributeur : « ta DB Supabase peut être vide ; l'API
  répondra 200 mais les endpoints renverront des listes vides. Pour un
  onboarding riche, préfère SQLite. »

## Étape 5 — Tests santé

**But** : garantir qu'aucune régression locale ne passe silencieusement.

```bash
task test         # ou: cd backend && uv run pytest -m "not integration" -q
                  # puis: cd frontend && npm test
```

**Contrat attendu** : `1146 passed` (ou plus) côté backend, Vitest
frontend vert.

**En cas d'échec** :
- Marquer `state.steps.tests = "failed"`.
- Afficher la sortie brute (pas juste « des tests ont échoué »).
- **Stopper le skill.** Ne pas lancer `task dev`.
- Proposer : (a) partager la sortie en ouvrant un ticket, (b) quitter
  proprement, (c) retry après correction locale.

Aucun passage silencieux à l'étape suivante en cas d'échec (FR-007).

**Mode retour** : même en `experience_level = retour` et `steps.tests` à
`done` dans un state précédent, **rejouer** `task test`. Il coûte ~5s et
c'est la garantie SC-005 (retour propre en moins de 3 min).

## Étape 6 — Serveurs de dev

**But** : backend écoute sur `:8001`, frontend sur `:3000`.

**Sonde préalable** :
```bash
curl -sSo /dev/null -w '%{http_code}' -m 2 http://localhost:8001/docs
curl -sSo /dev/null -w '%{http_code}' -m 2 http://localhost:3000
```

**Si déjà `200` / `200|307`** : marquer `state.steps.dev = "skipped"`,
signaler « serveurs déjà lancés, rien à faire ». (FR-013)

**Sinon** :
```bash
task dev    # lance backend :8001 + frontend :3000 en parallèle
```

`task dev` est bloquant au premier plan par défaut ; le skill doit le
lancer en arrière-plan (via `run_in_background: true` de l'outil `Bash`)
puis re-sonder après ~5-8s pour confirmer que les deux serveurs
répondent. Si `curl :8001/docs` ne renvoie pas `200` au bout de 20s,
afficher les logs et marquer `failed`.

**Guider vers l'UI** :
- API Docs : http://localhost:8001/docs
- Endpoint santé : http://localhost:8001/api/v1/stats?scope=club&federal_only=true
- Frontend : http://localhost:3000

## Étape 7 — Tour de code

**But** : présenter les zones structurantes du dépôt selon le profil
déclaré. **Le skill charge le bon fichier** au lieu de recopier son
contenu.

Selon `answers.profile` :

- `fullstack` → charge et déroule
  `.claude/skills/onboard/references/tour-fullstack.md`.
- `backend`  → charge et déroule
  `.claude/skills/onboard/references/tour-backend.md`.
- `frontend` → charge et déroule
  `.claude/skills/onboard/references/tour-frontend.md`.

Instruction au LLM : lire le fichier avec `Read`, puis afficher au
contributeur son contenu **en le commentant** (invite à ouvrir chaque
fichier cité, laisser le temps de digérer, accepter les questions à
chaque étape). Ne pas paraphraser massivement — le fichier est déjà
rédigé pour être lu tel quel.

**Mode `verbosity = courte`** : résumer le tour en 5-7 lignes plutôt que
de dérouler le fichier complet :

- La stack : Python 3.13 + FastAPI + SQLAlchemy 2.0 sync côté backend,
  Next.js 16 App Router + TypeScript côté frontend, SQLite en dev.
- Le sens du flux : `api → services → repositories → DB` (jamais en
  arrière).
- L'invariant club : `is_tcn` est **une seule et unique** définition
  dans `backend/app/core/club.py`.
- La règle temps : toujours des strings (`"01:23:45"`), normalisées via
  `scrapers/utils.py`.
- TDD sans réseau (respx). Tests réels derrière le marker `integration`.
- Métier en français, technique en anglais (Principe I).
- Pointer 3 fichiers de référence : `AGENTS.md`, `docs/modele-donnees.md`,
  `docs/WORKFLOW-IA.md`.

Marquer `state.steps.tour = "done"` à la fin.

## Étape 8 — Outillage IA embarqué

**But** : le contributeur sait quels skills IA existent, quand les
utiliser, où trouver le workflow.

**Si `skip_ia_tooling = true`** : marquer `state.steps.ia_tooling =
"skipped"` et passer directement à l'étape 9.

**Sinon**, présenter en trois blocs courts :

1. **Speckit** (skills `speckit-*` dans `.claude/skills/`) — **une voie
   complète** pour une vraie feature, du cadrage à l'exécution :
   `/speckit-specify` → `/speckit-clarify` → gate → `/speckit-plan` →
   gate → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`.
   Produit `specs/<horodatage>-.../` avec `spec.md`, `plan.md`,
   `tasks.md`, `checklists/`. La branche git est créée par le hook
   `before_specify` → `/speckit-git-feature` (Spec Kit 0.15.0).

2. **Superpowers** — **l'autre voie complète** (`brainstorming` →
   `writing-plans` → `executing-plans` ou `subagent-driven-development`),
   plus la discipline transverse : `test-driven-development`,
   `systematic-debugging`, `requesting-code-review`,
   `verification-before-completion`, `finishing-a-development-branch`.
   Le harness Claude Code livre aussi `/code-review`,
   `/security-review`, `/simplify`, `/review` (pour un PR GitHub).

   **On ne croise jamais les deux voies** : l'exécution suit l'outil qui a
   produit le plan. Pas de `subagent-driven-development` sur un `tasks.md`
   Speckit — c'est un handoff retiré pour son coût (~117 exécutions
   d'agent sur les 39 tâches de `003-dashboard-rank-selector`).

3. **La constitution v1.1.0** — `.specify/memory/constitution.md`, 6
   principes non-négociables (langue métier vs technique, architecture
   en couches, TDD sans réseau, contrats API/CLI stables, neutralité des
   paramètres transverses, YAGNI). Injectée automatiquement dans chaque
   `/speckit-*`.

**Où lire la règle « quel outil quand »** : `docs/WORKFLOW-IA.md` (les
trois voies, la fin de branche commune, les garde-fous de
`/speckit-implement`, où atterrissent les artefacts).

**Résumer en 3 phrases** :
- **Bugfix / typo / 1-2 fichiers** → voie « sans plan » : test rouge →
  correctif → `verification-before-completion` → PR.
- **Vraie feature** → voie Speckit **ou** voie Superpowers, au choix du
  contributeur : les deux mènent au même résultat, la question est celle
  de la traçabilité souhaitée. Aucun critère mécanique par nature de
  travail (`002-runnerbreizh-scraper` est passé par Speckit, les 34 autres
  plans de scraper par Superpowers).
- **Fin de branche identique dans les trois cas** :
  `requesting-code-review` → `verification-before-completion` →
  `finishing-a-development-branch`.

Marquer `state.steps.ia_tooling = "done"`.

## Étape 9 — Première feature (via `gh`)

**But** : proposer au contributeur une issue concrète à attaquer pour
sa première contribution, en filtrant sur son profil quand possible.

**Si `skip_ia_tooling = true`** : marquer `state.steps.first_feature =
"skipped"` et sauter cette étape (le contributeur explore lui-même).

**Sinon**, brancher selon l'état de `gh` :

### Branche 1 — `gh` absent

Afficher :

> `gh` (GitHub CLI) n'est pas installé. Tu peux l'installer depuis le
> dépôt officiel : voir https://github.com/cli/cli#installation. Une
> fois installé, relance `gh auth login`.
>
> **Voie de secours** : va sur https://github.com/Triathlon-Club-Nantais/data-triathlon/issues
> et cherche le label `good first issue`. L'issue parente d'onboarding
> est #82 (« Feat: onboarding ») — bon repère pour comprendre l'esprit.

Marquer `state.steps.first_feature = "skipped"`.

### Branche 2 — `gh` présent mais non authentifié

Sonde : `gh auth status` retourne code ≠ 0.

Afficher :

> `gh` est installé mais tu n'es pas authentifié. Lance dans ton
> terminal : `gh auth login` (choisir GitHub.com, HTTPS ou SSH, via le
> navigateur ou un token PAT). Une fois fait, relance `/onboard`.

Marquer `state.steps.first_feature = "pending"` (repris au prochain
lancement).

### Branche 3 — `gh` opérationnel

Requête filtrée par profil :

```bash
# Base
gh issue list \
  --repo Triathlon-Club-Nantais/data-triathlon \
  --label "good first issue" \
  --state open \
  --json number,title,url,labels

# Filtrage additionnel selon answers.profile (si labels correspondants existent) :
#   profile=backend  → --label backend
#   profile=frontend → --label frontend
#   profile=fullstack → pas de filtre supplémentaire
```

**Traitement du résultat** :

- Si la liste est **non vide**, l'afficher (numéro, titre, URL) et
  proposer au contributeur d'en choisir une. Lui rappeler qu'il peut
  ouvrir l'issue avec `gh issue view <numéro> --web`.
- Si la liste est vide **avec** filtre profil, retomber sur `good first
  issue` seul et signaler « aucune issue filtrée pour ton profil, voici
  toutes les good first issues ».
- Si la liste est **totalement vide** (aucune issue avec `good first
  issue`), afficher :

  > Aucune issue étiquetée `good first issue` pour l'instant.
  > Deux pistes :
  > - `gh issue list --state open` pour voir toutes les issues ouvertes.
  > - Poser la question dans l'issue #82 ou ouvrir une conversation avec
  >   un mainteneur pour identifier une bonne première tâche.

- Si `gh issue list` échoue pour toute autre raison (rate limit, réseau,
  label absent du repo), afficher l'erreur brute et retomber sur le
  fallback manuel de la Branche 1.

Marquer `state.steps.first_feature = "done"` (ou `skipped` si non
concluant).

**Enchainer** : proposer au contributeur, une fois l'issue choisie, de
lancer `/speckit-specify "<description courte de la feature>"` pour
démarrer le cycle Speckit sur cette issue.

## Questions libres du contributeur

À tout moment de la séquence, le contributeur peut poser une question
libre qui n'est pas dans la liste Q1-Q5 (« qu'est-ce que `is_tcn` ? »,
« pourquoi les temps sont des strings ? », « c'est quoi le cache TTL ? »,
« comment fonctionne le SSE ? »).

**Comportement attendu du LLM** :

1. Détecter que le message du contributeur n'est **pas** une réponse à
   une question du skill mais une **question libre**.
2. Répondre en s'appuyant en priorité sur `AGENTS.md`, la constitution,
   `docs/modele-donnees.md` et le code source. **Ouvrir** les fichiers
   pour citer les lignes précises, ne pas inventer.
3. Après la réponse, proposer explicitement de reprendre l'étape en
   cours : « on reprend à l'étape 5 — tests, ou tu veux d'abord... ? »
4. **Ne pas** perdre l'état d'avancement : le skill reste sur son
   étape courante, aucune régression de `state.json`.

## Gestion des erreurs et abandon

**Le contributeur tape `stop`, `quit`, `abandon`** :

1. Écrire `state.json` avec l'étape courante à son statut réel (`pending`
   si pas commencée, `failed` si commencée sans réussir).
2. Afficher : « À bientôt. Relance `/onboard` quand tu veux reprendre —
   on reprendra à l'étape en cours. »
3. Sortir proprement.

**Une commande shell échoue** (`task install` code ≠ 0, `task test`
échoue, `alembic upgrade head` refuse) :

1. **Ne pas masquer** la sortie. La reproduire brute, dans un bloc
   `stderr` clairement identifié.
2. Marquer `state.steps.<étape> = "failed"`.
3. **Ne pas avancer** à l'étape suivante.
4. Proposer trois options :
   - **Retry** : rejouer la commande (utile après une correction manuelle).
   - **Skip** : marquer explicitement `skipped` et continuer (le
     contributeur assume). Le skill signale que la suite peut être
     dégradée.
   - **Abandon** : voir « le contributeur tape stop » ci-dessus.

**Ctrl-C mid-étape** :

Le harness Claude Code capture `SIGINT`. Le skill ne peut pas toujours
sauver l'état de manière garantie, mais il tente : à chaque **début**
d'étape, il écrit `state.steps.<étape> = "pending"` (au cas où il serait
interrompu), et à la **fin** il passe à `done` ou `skipped`. Comme ça,
une interruption laisse toujours un state cohérent (soit l'étape n'a
pas commencé, soit elle est officiellement finie — jamais dans un
demi-état incompréhensible).

**Schéma incompatible** : si `state.schema_version ≠ 1`, ne pas tenter
de migrer. Afficher : « format d'état d'onboarding obsolète, on repart
de zéro » et supprimer `state.json` après confirmation du contributeur.

## Références externes

- `AGENTS.md` — architecture détaillée, commandes, conventions scrapers.
- `README.md` — installation et déploiement.
- `.specify/memory/constitution.md` — 6 principes non-négociables.
- `docs/WORKFLOW-IA.md` — quel outil IA pour quoi.
- `docs/modele-donnees.md` — MCD (Mermaid) du modèle normalisé.
- `Taskfile.yml` — liste des commandes `task` disponibles.
- `.claude/skills/onboard/state-schema.json` — schéma JSON de `state.json`.
- Issue GitHub d'origine : https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/82
