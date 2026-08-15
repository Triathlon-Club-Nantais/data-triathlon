# Feature Specification: Optimisation des fichiers AGENTS.md avec référence

**Feature Branch**: `20260815-114124-agents-md-optimisation`

**Created**: 2026-08-15

**Status**: Draft

**Input**: Issue GitHub #335 et ses commentaires (scope élargi à 4 volets : verbosité des
fichiers de contexte, workflow d'assignation GitHub, langue des titres d'issues,
concision des commentaires de code).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un agent lit un fichier d'API sans charger tout l'historique des epics (Priority: P1)

Un agent IA ouvre un fichier de `backend/app/api/` pour une tâche ciblée (ex. la
pagination du classement). Le mécanisme de chargement automatique (`CLAUDE.md`
→ `@AGENTS.md`) lui impose tout `backend/app/api/AGENTS.md`, qui aujourd'hui
mélange 13 sujets distincts (pagination, fusion d'épreuves, feedback,
statistiques...) sur ~494 lignes. Le même constat vaut pour
`backend/app/services/auth/AGENTS.md` (~486 lignes, 5 features SSO/RBAC
distinctes).

**Why this priority**: c'est le cœur de l'issue #335 (titre d'origine) et le
seul volet à coût token mesurable directement en lignes/tokens chargés à
chaque lecture d'un fichier du dossier.

**Independent Test**: mesurer la taille de `backend/app/api/AGENTS.md` et
`backend/app/services/auth/AGENTS.md` avant/après ; vérifier qu'aucune
information n'est perdue, seulement déplacée vers des fichiers de référence
chargés à la demande (non auto-chargés).

**Acceptance Scenarios**:

1. **Given** `backend/app/api/AGENTS.md` fait ~494 lignes avec 13 sections liées
   chacune à un ticket, **When** l'audit identifie les sections qui forment un
   sous-ensemble cohérent et détachable (une epic, un geste d'administration),
   **Then** ces sections sont déplacées vers `docs/api/<sujet>.md` et
   remplacées dans `AGENTS.md` par une ligne de renvoi, sur le patron déjà en
   place (`backend/app/scrapers/AGENTS.md` → `docs/scrapers/<fournisseur>.md`).
2. **Given** `backend/app/services/auth/AGENTS.md` fait ~486 lignes,
   **When** le même audit s'applique, **Then** le fichier redescend sous ~250
   lignes sans perte d'information.
3. **Given** un fichier `AGENTS.md` de dossier fait déjà moins de ~250 lignes
   ou expose déjà une table de renvoi par sujet (ex. `backend/app/scrapers/`,
   `backend/app/cli/`), **When** l'audit l'examine, **Then** il n'est pas
   retouché — le split ne s'applique qu'aux cas mesurés, pas en systématique.

---

### User Story 2 - Un agent qui commence une issue s'assigne, et sa PR est assignée + reviewée (Priority: P2)

Aujourd'hui rien ne consigne, dans les conventions du dépôt, qu'un agent doit
s'assigner une issue avant d'y travailler, assigner sa PR une fois créée, et
demander une review si elle passe "ready for review". Résultat observé sur
l'historique récent : des PR non assignées, pas de reviewer demandé.

**Why this priority**: comportement d'agent à corriger dès la prochaine
session — pas de mécanisme technique, un ajout de convention suffit.

**Independent Test**: relire `AGENTS.md` § Conventions générales et vérifier
que la règle y figure, en trois gestes distincts (assignation issue,
assignation PR, reviewer si ready).

**Acceptance Scenarios**:

1. **Given** un agent commence à travailler sur une issue GitHub, **When** il
   consulte `AGENTS.md`, **Then** il y trouve l'instruction de s'assigner
   l'issue avant de commencer.
2. **Given** une PR vient d'être créée, **When** l'agent consulte la même
   règle, **Then** il sait qu'il doit l'assigner.
3. **Given** cette PR n'est pas en brouillon ("ready for review"), **When**
   l'agent applique la règle, **Then** il demande une review.

---

### User Story 3 - Un agent nomme une issue GitHub en anglais (Priority: P3)

Le Principe I ne couvre aujourd'hui explicitement que le contenu (UI, docs,
identifiants) — pas le titre d'une issue GitHub, que l'utilisateur a rappelé
devoir être en anglais dans les commentaires de #335.

**Why this priority**: clarification courte d'une règle déjà écrite ailleurs,
sans ambiguïté ni risque.

**Independent Test**: relire la règle de langue dans `AGENTS.md` et vérifier
qu'elle couvre explicitement les titres d'issues.

**Acceptance Scenarios**:

1. **Given** un agent crée une issue GitHub, **When** il consulte la règle de
   langue, **Then** il sait que le titre suit la règle des identifiants
   techniques (anglais), au même titre que `Closes #123`.

---

### User Story 4 - Les commentaires de code restent minimaux (Priority: P3)

Consigner, si ce n'est pas déjà fait ailleurs dans `AGENTS.md`, que les
commentaires de code du dépôt doivent être minimaux/absents — économie de
token, même logique que les instructions déjà données à l'agent lui-même.

**Why this priority**: ligne courte, aucun risque, complète les Conventions
générales.

**Independent Test**: relire `AGENTS.md` § Conventions générales, vérifier la
présence de la règle et l'absence de duplication avec une règle existante.

**Acceptance Scenarios**:

1. **Given** un agent écrit du code, **When** il consulte les Conventions
   générales, **Then** il y trouve l'instruction de garder les commentaires de
   code minimaux, sans duplication d'une règle déjà présente.

### Edge Cases

- Un fichier candidat au split (`docs/*.md`, `.claude/agents/*.md`) n'est
  **pas** auto-chargé par le mécanisme `CLAUDE.md`/`AGENTS.md` de dossier — il
  se lit sur renvoi. Le split ne s'y applique donc que si sa taille gêne
  concrètement une lecture ciblée (ex. un fichier de 500+ lignes sans
  sous-sections repérables), pas par principe.
- Un fichier `AGENTS.md` de dossier au-dessus de 200 lignes mais déjà organisé
  en table de renvoi par sujet (le patron `scrapers/`) n'est pas un doublon à
  corriger : c'est l'aboutissement déjà en place du principe demandé par
  l'issue.
- Les 4 volets sont indépendants : livrer le volet 1 (split) sans les volets
  2-4 (conventions) reste une valeur livrable, et inversement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le dépôt DOIT identifier, par mesure de taille (lignes) et de
  structure (sections détachables), les fichiers `AGENTS.md` de dossier dont
  la verbosité dépasse mesurablement le patron déjà en place (root `AGENTS.md`
  sous 200 lignes ; `backend/app/scrapers/AGENTS.md` qui renvoie déjà à
  `docs/scrapers/<fournisseur>.md`).
- **FR-002**: Pour chaque fichier identifié, les sections détachables DOIVENT
  être déplacées vers un ou plusieurs fichiers de référence sous `docs/`,
  chargés à la demande, sans perte d'information.
- **FR-003**: Le fichier `AGENTS.md` de dossier ainsi allégé DOIT conserver une
  ligne de renvoi par sujet déplacé (patron table ou liste, comme
  `backend/app/scrapers/AGENTS.md`).
- **FR-004**: Les fichiers non identifiés comme mesurablement verbeux (déjà
  sous le seuil, ou déjà structurés en renvoi) NE DOIVENT PAS être réécrits.
- **FR-005**: `AGENTS.md` (racine) § Conventions générales DOIT documenter la
  règle d'assignation GitHub : s'assigner une issue en commençant à y
  travailler, assigner toute PR créée, demander une review si la PR n'est pas
  en brouillon.
- **FR-006**: Cette règle DOIT être consignée comme convention de
  comportement d'agent, pas comme mécanisme technique (aucune GitHub Action,
  aucun workflow CI à créer).
- **FR-007**: La règle de langue du Principe I, telle que reprise dans
  `AGENTS.md`, DOIT préciser explicitement que les titres d'issues GitHub
  suivent la règle anglaise des identifiants techniques.
- **FR-008**: `AGENTS.md` § Conventions générales DOIT documenter la
  concision/absence des commentaires de code, sauf si une règle équivalente
  existe déjà ailleurs dans le fichier — auquel cas elle n'est pas dupliquée.
- **FR-009**: Aucune des modifications ne DOIT dépasser la contrainte de
  sobriété explicitement demandée par le porteur produit dans les commentaires
  de #335 : pas de nouvelle section longue, formulations courtes.

### Key Entities

- **Fichier de contexte** : `AGENTS.md` (racine ou de dossier), `CLAUDE.md`
  (toujours `@AGENTS.md`), fichier `docs/*.md`, fichier `.claude/agents/*.md`.
  Deux régimes de chargement : automatique (dossier, à la lecture d'un
  fichier du dossier) ou sur renvoi (`docs/`).
- **Convention** : règle de comportement d'agent consignée dans `AGENTS.md`
  § Conventions générales — pas de code, pas de migration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `backend/app/api/AGENTS.md` et
  `backend/app/services/auth/AGENTS.md` perdent au moins 40 % de leurs lignes
  actuelles (494 et 486) sans perte d'information — le contenu déplacé reste
  entièrement lisible depuis les fichiers de référence renvoyés.
- **SC-002**: Un agent qui ouvre un seul fichier de `backend/app/api/` pour une
  tâche portant sur un seul sujet (ex. pagination) ne charge plus, via le
  mécanisme automatique, les sections sans rapport (fusion d'épreuves,
  feedback, stats) — elles sont désormais sous `docs/`, chargées seulement si
  citées.
- **SC-003**: `AGENTS.md` (racine) documente les 3 conventions (assignation
  GitHub, titres d'issues en anglais, commentaires de code minimaux) en moins
  de 15 lignes ajoutées au total.
- **SC-004**: Aucune information technique n'est perdue : chaque section
  déplacée reste retrouvable par un renvoi explicite depuis le fichier
  d'origine.

## Assumptions

- "Verbeux" se mesure ici par la taille en lignes rapportée au seuil déjà posé
  par le dépôt lui-même (200 lignes pour la racine) et par la présence de
  sections clairement détachables (un `##` par ticket/epic) — pas par une
  notation de style.
- Les fichiers `docs/*.md` et `.claude/agents/*.md` sont déjà hors du
  mécanisme de chargement automatique (chargés sur renvoi) : ils sont audités,
  mais seuls ceux dont la taille gênerait une lecture ciblée sont retouchés.
  Aucun n'a été trouvé mesurablement problématique lors du sondage initial de
  cette spec (voir plan.md pour le détail de l'audit).
- Le workflow d'assignation GitHub (volet 2) reste une convention documentée,
  pas une GitHub Action — le porteur produit l'a explicitement qualifié de
  règle de comportement, pas de mécanisme technique.
- La règle sur les commentaires de code (volet 4) est vérifiée avant ajout
  pour éviter un doublon avec une règle existante (ex. instructions système de
  l'agent, hors du périmètre d'`AGENTS.md`).
