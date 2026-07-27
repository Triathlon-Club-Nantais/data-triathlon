# Feature Specification: Skill Claude Code « onboard » pour nouveaux collaborateurs

**Feature Branch**: `001-onboard-skill`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Skill Claude Code nommé onboard à destination d'un nouveau collaborateur du projet data-triathlon (issue #82)"

## Clarifications

### Session 2026-07-27

- Q: Stratégie de persistance de l'état d'onboarding entre invocations (reprise après Ctrl-C) ? → A: **State JSON local** — `.claude/skills/onboard/state.json`, git-ignoré, stocke les étapes cochées ; permet une reprise exacte au relancement.
- Q: Comportement en cas de `backend/.env` préexistant ? → A: **Lecture + skip** — le skill lit le fichier, affiche la valeur `DATABASE_URL` pour information, et passe à l'étape suivante sans proposer d'écrasement.
- Q: Source de la « première feature suggérée » à la fin de l'onboarding ? → A: **Liste des `good first issue` GitHub** — le skill appelle `gh issue list --label "good first issue"` et propose les issues remontées ; fallback texte si `gh` absent ou non authentifié.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Premier onboarding « from scratch » (Priority: P1) 🎯 MVP

Un nouveau contributeur vient de cloner le dépôt. Rien n'est installé côté
projet (pas de `.env`, pas de DB, pas de dépendances). Il lance `/onboard`
dans Claude Code. Le skill lui pose 3 à 5 questions ciblées, vérifie ses
prérequis, guide l'installation complète, lance les tests pour valider, ouvre
les serveurs de dev, et lui fait faire un tour du dépôt adapté à son profil
(fullstack / backend-only / frontend-only). À la fin, il sait où trouver
l'info, quels outils IA sont à sa disposition, et quelle première feature il
peut attaquer.

**Why this priority** : c'est le cas nominal de l'issue #82. Sans ce chemin,
un nouveau contributeur passe 30 minutes à décoder `AGENTS.md` + `README.md`
+ `Taskfile.yml` + `docs/WORKFLOW-IA.md` pour reconstruire la séquence
d'install. Le skill remplace cette lecture croisée par un chemin balisé.

**Independent Test** : lancer `/onboard` sur un clone frais du dépôt, dans un
environnement sans `.env` et sans DB, et vérifier qu'à la fin (a) `task test`
est vert, (b) les serveurs de dev tournent sur `:8001` et `:3000`, (c) le
contributeur peut nommer les 6 principes de la constitution et le workflow
Speckit sans relire la doc.

**Acceptance Scenarios** :

1. **Given** un dépôt fraîchement cloné sans `.env` ni `.venv`, **When** le
   contributeur exécute `/onboard`, **Then** le skill détecte l'état vierge,
   propose la voie SQLite par défaut, exécute `task install`, crée
   `backend/.env` avec `DATABASE_URL=sqlite:///./triathlon.db`, lance
   `task b:reset-db`, `task test`, `task dev`, et signale les URLs à ouvrir.
2. **Given** un contributeur qui répond « je préfère Supabase », **When** il
   répond à la question DB, **Then** le skill lui explique comment récupérer
   l'URI Supabase (Direct pooler), attend qu'il colle la chaîne, l'écrit dans
   `backend/.env`, et adapte la suite (pas de `reset_db.py --no-seed` sur une
   base partagée sans confirmation supplémentaire).
3. **Given** un prérequis manquant (`uv` absent), **When** le skill vérifie
   les outils, **Then** il propose la commande d'install officielle
   (`curl -LsSf https://astral.sh/uv/install.sh | sh`) et vérifie après coup
   que la version installée est ≥ 0.11.
4. **Given** un test qui échoue au premier `task test`, **When** le skill
   détecte l'échec, **Then** il **ne poursuit pas** avec `task dev` : il
   affiche le résumé d'échec et propose au contributeur d'ouvrir un ticket ou
   de partager la sortie.

---

### User Story 2 — Retour après pause longue (Priority: P2)

Un contributeur revient sur le projet après plusieurs mois. Le dépôt est déjà
installé, mais la stack a peut-être bougé. Il lance `/onboard` et coche
« je connais déjà, résume-moi » pour sauter l'install et passer directement
au récap de la stack, du modèle normalisé et des dernières évolutions
(constitution v1.0.0, ajouts de scrapers récents).

**Why this priority** : cas fréquent dans un club (contributions bénévoles
saisonnières). Le skill doit gracefully accepter les « skip » sans obliger à
tout relancer.

**Independent Test** : sur une machine qui a déjà `.env` + `.venv` + `node_modules`,
lancer `/onboard`, répondre « je connais déjà » aux questions d'install, et
vérifier que le skill passe direct au tour de code + résumé constitution
sans exécuter `uv sync` ni `npm install` inutilement.

**Acceptance Scenarios** :

1. **Given** un `backend/.venv` existant et une DB SQLite peuplée, **When**
   le contributeur répond « skip install », **Then** le skill saute
   `task install` et `task b:reset-db`, mais **rejoue** `task test` (rapide,
   ~5s) pour confirmer que rien n'est cassé localement.
2. **Given** une constitution mise à jour depuis la dernière visite, **When**
   le skill présente les principes, **Then** il indique la version courante
   (v1.0.0) et pointe le fichier plutôt que de recopier son contenu.

---

### User Story 3 — Tour rapide adapté à un contributeur mono-couche (Priority: P3)

Un contributeur front-only (React/Next.js) veut comprendre juste ce qu'il faut
du backend pour appeler l'API correctement, sans se plonger dans les
scrapers. À l'inverse, un contributeur backend Python peut demander un tour
qui saute le tour frontend. Le skill adapte son parcours selon la réponse à
la question « sur quelle couche vas-tu contribuer ? ».

**Why this priority** : réduit la charge cognitive. Un dev front n'a pas
besoin de comprendre `RaceResultProvider._HOSTS` au premier jour.

**Independent Test** : lancer `/onboard`, répondre « front only » à la
question de couche, et vérifier que le tour de code ne montre pas les
scrapers et l'import service, mais insiste sur `lib/api/`, `sse.ts`, App
Router, et le contrat `/api/v1`.

**Acceptance Scenarios** :

1. **Given** un contributeur qui répond « front only », **When** le tour de
   code commence, **Then** il couvre uniquement `frontend/`, les types
   partagés (`lib/types.ts`), et le contrat API (endpoints consommés), en
   citant les fichiers backend correspondants **sans** les ouvrir.
2. **Given** un contributeur qui répond « backend only », **When** le tour
   de code commence, **Then** il couvre `app/core/`, `app/models/`,
   `app/services/`, `app/scrapers/klikego.py`, et saute `frontend/`.

---

### Edge Cases

- **Interruption au milieu (Ctrl-C)** : le skill persiste son état dans
  `.claude/skills/onboard/state.json` (fichier git-ignoré). Au relancement,
  il lit cet état pour reprendre exactement là où le contributeur s'est
  arrêté (étapes cochées, réponses aux questions déjà données, profil
  choisi). Un état invalide ou incomplet DOIT être détecté et proposer soit
  de reprendre depuis la dernière étape valide, soit de repartir de zéro.
- **Version d'outil trop ancienne** : `uv < 0.11`, `node < 20`, `task < v3`.
  Le skill signale la version détectée et propose la mise à jour, mais ne
  bloque pas — le contributeur peut passer outre sous sa responsabilité.
- **DB déjà peuplée avec des vraies données** (le contributeur travaille sur
  la DB Supabase de prod par erreur) : `task b:reset-db` refuse déjà pour
  toute DB non-SQLite ; le skill respecte ce refus et n'insiste pas.
- **`task` absent** : le skill retombe sur les commandes brutes (`uv sync`,
  `alembic upgrade head`, `npm install`, etc.) plutôt que d'exiger
  l'installation de go-task.
- **Contributeur qui ne veut pas parler à un LLM** : le skill affiche
  d'emblée l'option « affiche-moi juste la liste des commandes à exécuter »
  et sort proprement au bout de 30 secondes de conversation.
- **Constitution v1.0.0 non ratifiée en `main`** : le skill lit
  `.specify/memory/constitution.md` tel qu'il est, quelle que soit sa version.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** : Le skill DOIT être invocable via `/onboard` depuis Claude
  Code (frontmatter `name: onboard`).
- **FR-002** : Au démarrage, le skill DOIT poser **au maximum 5 questions**
  au contributeur (profil, DB souhaitée, couche de contribution, ce qu'il
  connaît déjà, s'il veut la version courte ou complète), via la primitive
  `AskUserQuestion` de Claude Code.
- **FR-003** : Le skill DOIT vérifier la présence des prérequis `uv`,
  `node`, `npm`, `git` (indispensables) et `task` (recommandé, optionnel).
- **FR-004** : Pour chaque prérequis manquant, le skill DOIT proposer la
  commande d'installation officielle et VÉRIFIER après coup que la
  commande est disponible et à la version minimale (`uv >= 0.11`,
  `node >= 20`).
- **FR-005** : Le skill DOIT créer `backend/.env` avec la valeur choisie
  (`sqlite:///./triathlon.db` par défaut, ou l'URI Supabase saisie).
  Si `backend/.env` existe déjà, le skill DOIT lire le fichier, afficher la
  valeur `DATABASE_URL` détectée pour information, et passer à l'étape
  suivante **sans** proposer d'écrasement. C'est au contributeur de
  supprimer manuellement le `.env` s'il souhaite le régénérer.
- **FR-006** : Le skill DOIT exécuter les étapes d'install et de vérif via
  les commandes Task documentées (`task install`, `task b:reset-db`,
  `task test`, `task dev`), et fallback sur les commandes brutes si `task`
  est absent.
- **FR-007** : Le skill DOIT stopper la séquence en cas d'échec de
  `task install`, `task b:reset-db` ou `task test`, afficher la sortie
  d'erreur pertinente, et proposer soit de partager la sortie, soit de
  quitter le skill proprement.
- **FR-008** : Le skill DOIT présenter la stack, l'architecture en couches
  backend, le modèle normalisé, et un chemin lecture de code adapté au
  profil déclaré (fullstack / backend / frontend), en **pointant** les
  fichiers plutôt qu'en recopiant leur contenu.
- **FR-009** : Le skill DOIT présenter l'outillage IA embarqué (Speckit,
  Superpowers, la constitution `.specify/memory/constitution.md`, le
  workflow vibe vs feature complète documenté dans `docs/WORKFLOW-IA.md`),
  et proposer une première feature à attaquer.
- **FR-015** : Pour proposer une première feature (FR-009), le skill DOIT
  interroger GitHub via `gh issue list --label "good first issue" --state
  open --json number,title,url,labels` et présenter au contributeur les
  issues remontées, filtrées le cas échéant selon son profil (labels
  `backend`, `frontend`, `scraper` si présents).
  - Si `gh` est **absent** de l'environnement, le skill DOIT afficher un
    message expliquant comment l'installer et lister par défaut l'issue
    parente d'onboarding (#82) comme repère, puis passer.
  - Si `gh` est **présent mais non authentifié**, le skill DOIT proposer
    la commande `gh auth login` et attendre que le contributeur choisisse
    entre s'authentifier maintenant ou passer.
  - Si `gh issue list` échoue pour toute autre raison (rate limit, réseau,
    label absent du repo), le skill DOIT afficher l'erreur et proposer un
    fallback texte manuel : « visite https://github.com/Triathlon-Club-
    Nantais/data-triathlon/issues et choisis une issue qui te parle ».
- **FR-010** : Le skill DOIT laisser le contributeur poser des questions
  libres à tout moment (« qu'est-ce que `is_tcn` ? »), et y répondre en
  s'appuyant sur `AGENTS.md` et le code, sans exiger de reprendre la
  séquence linéaire.
- **FR-011** : Le skill NE DOIT PAS dupliquer le contenu d'`AGENTS.md`,
  `README.md` ou de la constitution — il DOIT y renvoyer.
- **FR-012** : Le skill NE DOIT PAS modifier de code produit (backend/,
  frontend/, docs/), à l'exception de `backend/.env` (fichier ignoré par
  git) qu'il crée avec la valeur choisie.
- **FR-013** : Le skill DOIT rester silencieux sur `task dev` s'il détecte
  qu'un backend et/ou un frontend écoutent déjà sur `:8001` / `:3000`, et
  proposer de sauter cette étape.
- **FR-014** : Tout texte visible par l'utilisateur (invites, questions,
  résumés) DOIT être en français (principe I de la constitution v1.0.0).
  Les identifiants et frontmatter techniques du fichier `SKILL.md` peuvent
  être en anglais.

### Key Entities

- **Profil contributeur** : ce que le skill retient pour adapter le
  parcours — profil (fullstack / backend / frontend), niveau (nouveau /
  retour après pause), DB souhaitée (SQLite / Supabase), version courte ou
  complète.
- **État d'installation** : présence de `.env`, `.venv`, `node_modules`, DB
  peuplée. Détecté par scan à chaque invocation ; complète l'état persistant
  pour trancher « étape déjà faite manuellement hors du skill ».
- **État de progression du skill** : fichier `.claude/skills/onboard/state.json`
  (git-ignoré), qui stocke les étapes déjà cochées, les réponses aux
  questions initiales (profil, DB souhaitée, couche), et un timestamp.
  Permet de reprendre après une interruption. Doit être supprimable
  manuellement pour repartir de zéro.
- **Fichier SKILL** : `.claude/skills/onboard/SKILL.md` avec frontmatter
  YAML (name, description). Peut inclure des ressources annexes
  (`references/`, `scripts/`) si le pattern des skills speckit-* le permet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** : Un nouveau contributeur sans expérience préalable du dépôt
  peut passer d'un `git clone` à `task test` vert + serveurs de dev qui
  répondent, en **moins de 15 minutes**, guidé uniquement par `/onboard`.
- **SC-002** : Après l'onboarding, le contributeur peut citer sans relire
  la doc : les 6 principes de la constitution, la différence entre workflow
  vibe et feature complète, et le sens du flux `api → services →
  repositories`.
- **SC-003** : Le skill traite au moins **3 profils distincts** (fullstack,
  backend-only, frontend-only) avec un tour de code différent pour chaque,
  et la suggestion de première feature est **filtrée sur le profil**
  lorsque les labels GitHub le permettent.
- **SC-004** : En cas d'échec de la séquence (test rouge, install cassée),
  le skill le signale et s'arrête ; **il ne poursuit jamais silencieusement**
  après un échec.
- **SC-005** : Sur un dépôt déjà installé, le skill en mode « je connais
  déjà » complète le parcours en moins de **3 minutes** (skip install,
  rejeu `task test` uniquement, tour de code + résumé constitution).
- **SC-006** : Aucun texte visible par l'utilisateur n'est en anglais ; le
  skill respecte le principe I de la constitution v1.0.0.

## Assumptions

- Le contributeur travaille sous Linux / macOS / WSL avec un shell POSIX
  (bash ou zsh). Windows natif est hors périmètre du skill (le projet lui-
  même est indifférent, mais les commandes d'install `curl … | sh` ne
  fonctionnent pas telles quelles sur PowerShell).
- Le contributeur a Claude Code installé et une session ouverte à la racine
  du dépôt.
- La constitution `.specify/memory/constitution.md` est en v1.0.0 ou
  supérieure (le skill peut lire la version en tête et adapter).
- L'issue #82 reste ouverte pendant la durée de développement — la PR
  associée y sera liée.
- La commande `task` est recommandée mais non obligatoire ; le skill doit
  fonctionner sans elle.
- Une seule invocation `/onboard` par contributeur suffit pour un
  onboarding complet ; le contributeur relance manuellement s'il veut
  refaire un tour.
- La `gh` CLI est **fortement recommandée** pour bénéficier de la
  suggestion de première feature via `good first issue` (FR-015). Le
  skill fonctionne sans, mais la dernière étape est dégradée.
- **Dépendance projet** : au 2026-07-27, le label `good first issue`
  existe sur le repo mais aucune issue ne le porte. Pour que FR-015
  produise des résultats, quelqu'un du projet doit tagger un lot d'issues
  d'onboarding — c'est une action **hors périmètre de ce skill**, à
  planifier en parallèle (piste : issues #33 sur les liens non
  supportés, ou petites features d'affichage front). Sans cela, le skill
  retombe sur le fallback texte manuel prévu par FR-015.
