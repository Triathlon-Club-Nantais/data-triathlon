# Workflow IA — Spec Kit + Superpowers

Ce document s'adresse aux collaborateurs qui utilisent **Claude Code** (ou tout
agent IA compatible) sur ce projet. Deux outils d'assistance sont préconfigurés,
**Spec Kit** et **Superpowers**. Leurs périmètres se recouvrent largement : sans
règle claire, un agent lance les deux pour la même tâche et produit des artefacts
concurrents. Ce document fixe **qui fait quoi et quand**.

---

## Le principe

**Spec Kit et Superpowers sont deux voies complètes et parallèles. On ne les
croise jamais.**

> **Règle d'or** : l'exécution suit **l'outil qui a produit le plan**. Un
> `tasks.md` de Spec Kit s'exécute avec `/speckit-implement` ; un plan sous
> `docs/superpowers/plans/` s'exécute avec un exécuteur Superpowers.

| Outil | Ce qu'il apporte | Ce qu'il coûte |
|---|---|---|
| **Spec Kit** | Artefacts documentaires traçables (`spec.md`, `plan.md`, `tasks.md`, `checklists/` dans `specs/NNN-feature/`), gates explicites (`/speckit-clarify`, `/speckit-analyze`, gate checklists). Explicite et **déterministe** : on tape la commande. | Le cycle complet. Six fichiers plus un dossier `checklists/` pour une feature d'un écran. |
| **Superpowers** | Discipline d'artisanat : worktree, TDD red-green-refactor, revue de code, fin de branche. Ses skills se déclenchent **automatiquement** quand leur description correspond à la situation. | Le fan-out par sous-agents, si on choisit cet exécuteur (voir plus bas). |

**Le choix de la voie appartient à l'utilisateur.** L'agent ne le tranche pas
seul et ne bascule pas de l'une à l'autre en cours de route. Il n'existe **pas**
de critère mécanique par nature de travail : `002-runnerbreizh-scraper` est passé
par Spec Kit là où les 34 plans de `docs/superpowers/plans/` — scrapers, CLI,
refactos — sont passés par Superpowers. Les deux voies mènent au même résultat ;
la question est celle de la traçabilité souhaitée et du budget.

> **Notation** : sous Claude Code les commandes Spec Kit s'invoquent avec un tiret
> (`/speckit-specify`, `/speckit-plan`…). L'intégration `opencode` de ce repo
> utilise le point (`speckit.specify`). Même skill, séparateur différent.

---

## Les trois voies

La voie « sans plan » n'est pas un cas dégradé des deux autres : c'est l'absence
d'artefact de planification, et c'est le cas courant.

| Voie | Pour quoi | Artefacts | Exécution |
|---|---|---|---|
| **Sans plan** | bugfix, typo, ajustement de 1-2 fichiers, petit refacto | aucun | `systematic-debugging` ou `test-driven-development` directement |
| **Spec Kit** | vraie feature, quand on veut la traçabilité et les gates | `specs/NNN-feature/` | `/speckit-implement` |
| **Superpowers** | vraie feature, quand le design et le plan suffisent | `docs/superpowers/specs/…-design.md` + `docs/superpowers/plans/…` | l'exécuteur **nommé par l'utilisateur** |

### Voie « sans plan »

1. (facultatif) `brainstorming` si l'approche n'est pas évidente.
2. `systematic-debugging` (bug) **ou** `test-driven-development` (ajout de
   comportement).
3. `verification-before-completion`.
4. `finishing-a-development-branch` si ça mérite une PR.

Pas de dossier `specs/`, pas de plan. Les skills Superpowers ne s'activent que
sur le déclencheur de `brainstorming` : sauter la boucle ne demande donc **aucune
précaution particulière**, il suffit de ne pas l'ouvrir.

### Voie Spec Kit

1. **Cadrage flou** → laisser tourner `brainstorming` **avant** `/speckit-specify`.
2. `/speckit-specify` → `/speckit-plan` → `/speckit-tasks`.
3. `/speckit-analyze` **avant tout code** : il vérifie, en lecture seule, les
   incohérences, ambiguïtés et trous de couverture entre `spec.md`, `plan.md` et
   `tasks.md`.
4. `/speckit-implement` — en connaissant ses trois traits (§Garde-fous plus bas).

### Voie Superpowers

1. `brainstorming` → design sous `docs/superpowers/specs/…-design.md`.
2. `writing-plans` → plan sous `docs/superpowers/plans/…`.
3. Exécution. **L'exécuteur n'a pas de défaut** : au handoff, l'utilisateur
   nomme lequel des deux tourne.

| Exécuteur | Mécanisme | Coût |
|---|---|---|
| `executing-plans` | Session courante, checkpoints de revue. | Une session, pas de fan-out. |
| `subagent-driven-development` | Un sous-agent **et** une revue en deux passes **par tâche**, tâches `[P]` en parallèle. | Élevé — voir le chiffre ci-dessous. |

**L'agent ne déclenche de lui-même ni le fan-out, ni les commits par tâche.** Si
l'exécuteur n'a pas été nommé, il demande.

---

## Fin de branche : commune aux trois voies

`requesting-code-review` → `verification-before-completion` →
`finishing-a-development-branch`.

Ces trois skills s'appliquent **quelle que soit la provenance du plan**, et c'est
délibéré : ce sont des **procédures**, pas des artefacts de planification. Elles
ne peuvent donc pas créer de doublon avec quoi que ce soit de Spec Kit. Et Spec
Kit n'offre aucun équivalent de revue de code : sans elles, une feature de la
voie Spec Kit se terminerait sans revue du tout.

La branche git et les commits-gate restent **manuels** — voir §Les hooks git dans
les garde-fous ci-dessous. Créer la branche soi-même.

---

## Le garant du TDD change d'endroit selon la voie

Le **Principe III** de la constitution (`.specify/memory/constitution.md`) est
**non-négociable** : toute nouvelle logique métier est précédée d'un test qui
échoue. Il tient dans les trois voies, mais pas par le même mécanisme — et c'est
le point qu'il faut avoir en tête depuis que l'exécution ne passe plus
systématiquement par Superpowers.

- **Voies Superpowers et « sans plan »** : c'est le skill
  `test-driven-development`, invoqué directement ou dans chaque tâche par
  l'exécuteur.
- **Voie Spec Kit** : c'est **`tasks.md` lui-même**. `/speckit-tasks` produit les
  tâches de test **avant** leurs tâches d'implémentation, et le dit explicitement.
  Cf. `specs/003-dashboard-rank-selector/tasks.md` : T002/T003 (tests) précèdent
  T004/T005 (implémentation), avec les mentions « le fichier ne compile pas
  encore, c'est attendu » et « ces tests doivent échouer avant T007 ».
  `/speckit-implement` s'instruit de respecter cet ordre (« Execute test tasks
  before their corresponding implementation tasks »).

> **Corollaire** : un `tasks.md` sans tâches de test viole le Principe III. Il se
> **régénère** (`/speckit-tasks`), il ne s'exécute pas. C'est le point de
> contrôle décisif de cette voie — le lire avant de lancer `/speckit-implement`.

Les quatre mentions « Tests are OPTIONAL » qui figuraient dans
`.specify/templates/tasks-template.md` — et qui faisaient de ce corollaire un
risque permanent — **ont été retirées**. Le follow-up TODO du Sync Impact Report
de la constitution est résorbé sur ce point.

---

## Garde-fous de `/speckit-implement`

Cette commande est devenue l'exécuteur nominal de la voie Spec Kit. Trois traits à
connaître avant de la lancer.

### 1. L'étape 4 « Project Setup Verification » : ne pas la dérouler

Elle vérifie les fichiers d'ignore d'après la stack détectée dans `plan.md`, et
son mode d'action sur un fichier existant est : « Verify it contains essential
patterns, **append missing critical patterns only** ». Le risque n'est donc pas
la création d'un fichier absent — ils sont tous là — mais **l'ajout silencieux de
motifs** dans des fichiers délibérés. Dans ce dépôt, concrètement :

| Fichier existant | Ce que l'étape 4 y ajouterait |
|---|---|
| `backend/.dockerignore` (8 motifs Python) | sa liste Docker générique : `node_modules/`, `.git/`, `Dockerfile*`, `.dockerignore`, `*.log*`, `coverage/` — dont `node_modules/` dans une image Python |
| `frontend/.dockerignore` | `Dockerfile*`, `.dockerignore`, `*.log*` (là où `npm-debug.log` suffisait) |
| `frontend/eslint.config.mjs` | « ensure the config's `ignores` entries cover required patterns » → `node_modules/`, `dist/`, `coverage/`, `*.min.js` dans un `globalIgnores` dont le commentaire dit qu'il **surcharge** volontairement les défauts d'`eslint-config-next` |
| les trois `.gitignore` (racine, `backend/`, `frontend/`) | les listes Node.js **et** Python **et** « Universal » (`.DS_Store`, `.vscode/`, `.idea/`…) |

Tout cela hors périmètre de la feature en cours, dans le même diff : frontalement
contraire au **Principe VI** (« un fix ne traîne pas de refacto »).

Le `.gitignore` de la racine est le plus sensible des quatre : `.worktreeinclude`
ne recopie un fichier dans un worktree que s'il est **à la fois** matché **et**
gitignoré. Y ajouter des motifs change donc ce qu'un worktree reçoit — un effet à
distance qu'aucun diff de feature ne laisse deviner. Sauter cette étape.

### 2. Les hooks git : du bruit, pas une action

`AGENTS.md` disait que les hooks de `.specify/extensions.yml` « ne s'exécutent
jamais ». La formulation exacte est **« échouent sans effet »**, et la nuance
compte.

L'extension `git` n'enregistre ses commandes que pour `agy` et `codex`
(`registered_commands` dans `.specify/extensions/.registry`) — ni pour `claude`,
ni pour `opencode`, l'intégration active. Mais le **corps** des skills
`speckit-*` lit `extensions.yml` de lui-même et, pour un hook `optional: false`,
s'instruit d'émettre `EXECUTE_COMMAND`. Or `before_specify` →
`speckit.git.feature` est précisément `optional: false` : `/speckit-specify`
**tentera** un `/speckit-git-feature` qui n'existe pas côté Claude. La branche
n'est pas créée pour autant — la commande est introuvable — mais l'agent ne doit
pas prendre ce `EXECUTE_COMMAND` pour une instruction à honorer autrement.

Les hooks de commit (`before_*` / `after_*` → `speckit.git.commit`) sont tous
`optional: true` : ils sont **affichés**, jamais exécutés. Donc pas d'auto-commit
par `/speckit-implement`, malgré `auto_execute_hooks: true` dans `settings`.

### 3. Le gate `checklists/` est réel, et gratuit

Les trois features ont un `specs/NNN/checklists/requirements.md`.
`/speckit-implement` scanne ce dossier, dresse un tableau de complétion et
**s'arrête en demandant confirmation** si un item est décoché. C'est un vrai
garde-fou : à connaître plutôt qu'à subir.

---

## Le piège qui reste : le sur-outillage

Pour un correctif d'une ligne, ne rien lancer. L'estimation historique de ce
document — **~20-40 % de tokens en plus** par feature quand on ouvre un cycle
complet — a été posée **avant** le retrait du handoff : elle vaut aujourd'hui
comme borne haute, et il n'y a pas de mesure plus récente. L'ordre de grandeur
suffit à la seule décision qu'elle sert : ouvrir un cycle, ou pas.

Le **doublon de planification** — `writing-plans` régénérant un plan parallèle à
`specs/<id>/plan.md`, `brainstorming` écrivant un `-design.md` concurrent de
`spec.md` — **n'est plus un piège** : il ne naissait que du handoff Spec Kit →
Superpowers, qui n'existe plus. Les deux voies ne coexistent plus sur une même
feature.

### Pourquoi le handoff a été retiré

Le handoff pointait `subagent-driven-development` sur le `tasks.md` de Spec Kit.
Mesuré sur `003-dashboard-rank-selector` : **39 tâches, dont 22 `[P]`**, avec un
sous-agent et une revue en deux passes par tâche — de l'ordre de **117 exécutions
d'agent** pour une feature front à quatre user stories.

C'est une décision de coût, assumée, pas une régression de qualité : les
garde-fous qui coûtaient peu sont tous conservés (TDD, vérification, revue de fin
de branche), seul le fan-out par tâche disparaît. `subagent-driven-development`
reste disponible sur la voie Superpowers, sur désignation explicite.

---

## Mise en place (une fois par repo)

1. Installer Superpowers : `/plugin marketplace add obra/superpowers-marketplace`
   puis `/plugin install superpowers@superpowers-marketplace`.
2. Initialiser Spec Kit : `specify init --integration claude-code` (Spec Kit v0.10+
   a remplacé les anciens flags `--ai` par `--integration`).
3. `/speckit-constitution`.
4. Committer `.specify/` ; `.claude/` selon la politique de l'équipe.

**Ne pas ajouter de « ligne-pont »** à la constitution du type « toute
implémentation d'une task list doit suivre le workflow Superpowers » : c'est
exactement le croisement que la règle d'or interdit. (Ce document l'a recommandé
par le passé ; la ligne n'est jamais entrée dans la constitution de ce repo.)

**État de ce repo** : la mise en place est déjà faite. La constitution est
**ratifiée en v1.0.0** — ne pas relancer `/speckit-constitution` pour « la
remplir ». Elle ne nomme aucun exécuteur (sa section « Development Workflow » dit
`… → /speckit-analyze → exécution`), donc la règle de provenance **ne demande
aucun amendement**. L'intégration active est `opencode`
(`.specify/integration.json`) ; les neuf skills `speckit-*` sont présents pour
Claude.

---

## Où atterrissent les artefacts

Spec Kit n'est pas le seul à écrire des fichiers : `brainstorming` et
`writing-plans` en produisent aussi. Savoir qui écrit quoi distingue un artefact
légitime d'un doublon.

| Emplacement | Écrit par | Statut |
|---|---|---|
| `specs/NNN-feature/` — `spec.md`, `plan.md`, `tasks.md`, `checklists/`, `research.md`, `data-model.md`, `quickstart.md` | Spec Kit | **Canonique** sur la voie Spec Kit. Un seul de chaque, par feature. |
| `docs/superpowers/specs/…-design.md` | `brainstorming` (l'écrit **et le commite**) | **Canonique** sur la voie Superpowers. |
| `docs/superpowers/plans/…` | `writing-plans` | **Canonique** sur la voie Superpowers. |
| `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md` | l'agent, à la main | **Rapport de terrain** — voir ci-dessous. |
| `.superpowers/sdd/<nom-du-plan>/` | `subagent-driven-development` | Ledger d'exécution (`progress.md`, briefs, rapports). Jetable, jamais commité. |

Une feature relève d'une voie **ou** de l'autre : la ligne `specs/NNN-feature/` et
les deux lignes `docs/superpowers/` qui la suivent ne se remplissent **jamais**
ensemble. Les deux dernières lignes du tableau, elles, sont transverses.

Les chemins `docs/superpowers/` sont les **défauts amont du plugin**
(`brainstorming/SKILL.md`, `writing-plans/SKILL.md`), pas une convention de ce
dépôt : le dossier porte le nom de **l'outil**, pas celui du contenu. Les fichiers
déjà présents **restent où ils sont** ; ils mêlent des designs de features livrées
(valeur historique) et des rapports de terrain encore normatifs, cités nominativement
par `AGENTS.md` là où ils s'appliquent.

### La troisième catégorie : le sondage

Un sondage n'est ni une spec ni un plan : il consigne des **observations** (ce qui a
été mesuré sur le site ou le code réels), pas des intentions. Il a donc sa place dans
les deux voies et n'entre en collision avec rien. Il est écrit sous
`docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md`, et il **prime**
sur le design, la spec et le plan — toute divergence se tranche en re-sondant, pas en
raisonnant.

Deux cas de référence :

- `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` (15 épreuves, 3
  façades) — donné pour primant « sur le design et sur le plan » par `AGENTS.md`, avec
  deux tests de non-régression qui protègent ses conclusions. Il n'a pas de contrepartie
  Spec Kit : il précède l'adoption du cycle.
- Le couple sondage + Spec Kit de runnerbreizh (`specs/002-runnerbreizh-scraper/`) :
  sondage du HTML réel écrit **avant** tout cadrage, puis déclaré source de vérité
  technique par la spec, le plan et les tâches. Deux fichiers, deux rôles, zéro
  redondance.

---

## La constitution Spec Kit (`.specify/memory/constitution.md`)

La constitution est le document de référence de Spec Kit : elle cadre les principes du
projet (stack, TDD, langue, conventions) et est injectée dans chaque commande
`/speckit-*`. Pour ce projet, elle est **ratifiée en v1.0.0** — ne pas relancer
`/speckit-constitution` pour la remplir.

Attention à sa portée réelle : la constitution n'est chargée que par les commandes
`/speckit-*`, alors qu'`AGENTS.md` l'est **à chaque session** via `CLAUDE.md`. En cas
de divergence entre les deux, c'est la règle d'`AGENTS.md` qui sera lue le plus
souvent — donc c'est là que les garde-fous doivent vivre, la constitution ne suffit
pas à les faire respecter.

Conséquence directe pour la voie Superpowers : elle ne charge **jamais** la
constitution, puisqu'elle ne passe par aucune commande `/speckit-*`. Les
invariants sur lesquels elle doit s'aligner (Principes I à VI) sont donc à
retrouver dans `AGENTS.md`, qui en porte le détail opérationnel.

---

*Pour les détails d'architecture et les conventions de scraping, voir `AGENTS.md`.*
