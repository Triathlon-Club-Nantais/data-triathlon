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
| **Spec Kit** | Artefacts documentaires traçables (`spec.md`, `plan.md`, `tasks.md`, `checklists/` dans `specs/<id>-feature/`), gates explicites (`/speckit-clarify`, `/speckit-analyze`, gate checklists). Explicite et **déterministe** : on tape la commande. | Le cycle complet. Six fichiers plus un dossier `checklists/` pour une feature d'un écran. |
| **Superpowers** | Discipline d'artisanat : worktree, TDD red-green-refactor, revue de code, fin de branche. Ses skills se déclenchent **automatiquement** quand leur description correspond à la situation. | Le fan-out par sous-agents, si on choisit cet exécuteur (voir plus bas). |

**Le choix de la voie appartient à l'utilisateur.** L'agent ne le tranche pas
seul et ne bascule pas de l'une à l'autre en cours de route. Il n'existe **pas**
de critère mécanique par nature de travail : `002-runnerbreizh-scraper` est passé
par Spec Kit là où les 34 plans de `docs/superpowers/plans/` — scrapers, CLI,
refactos — sont passés par Superpowers. Les deux voies mènent au même résultat ;
la question est celle de la traçabilité souhaitée et du budget.

> **Notation** : sous Claude Code les commandes Spec Kit s'invoquent avec un tiret
> (`/speckit-specify`, `/speckit-plan`…) — c'est l'`invoke_separator` de
> l'intégration active, `claude` (`.specify/integration.json`). Les identifiants
> internes de Spec Kit, eux, gardent le point : le hook `speckit.git.commit` de
> `.specify/extensions.yml` désigne le skill `/speckit-git-commit`. Même skill,
> séparateur différent.

---

## Les trois voies

La voie « sans plan » n'est pas un cas dégradé des deux autres : c'est l'absence
d'artefact de planification, et c'est le cas courant.

| Voie | Pour quoi | Artefacts | Exécution |
|---|---|---|---|
| **Sans plan** | bugfix, typo, ajustement de 1-2 fichiers, petit refacto | aucun | `systematic-debugging` ou `test-driven-development` directement |
| **Spec Kit** | vraie feature, quand on veut la traçabilité et les gates | `specs/<id>-feature/` | `/speckit-implement` |
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

**Quand la branche touche `frontend/`, une quatrième étape s'insère après
`requesting-code-review` : le sous-agent `ui-ux-review`**
(`.claude/agents/ui-ux-review.md`, #276). `requesting-code-review` juge du code ;
lui juge du rendu — respect des tokens `--tcn-*` et de la frontière
`components/tcn/` vs `components/ui/`, accessibilité WCAG AA (contrastes
**calculés**, focus visible, `prefers-reduced-motion`, cibles tactiles,
sémantique), états d'écran, responsive jusqu'à 360 px, microcopie française. Il
est en **lecture seule** et **l'utilisateur le déclenche** : comme le fan-out et
les commits par tâche, il ne part pas de lui-même. Deux traits à connaître avant
de le lancer :

- **Il ne rouvre pas l'identité visuelle.** Ni palette, ni typo, ni « signature
  element » : c'est arbitré. Un rapport qui en propose est un rapport à jeter.
- **Il est statique.** Il lit le code et les tokens, il ne voit pas le rendu. Ce
  qu'il ne peut pas juger, il le dit en clôture de rapport — et c'est ce relevé,
  pas une intuition, qui décidera un jour d'ouvrir la review au navigateur
  (`webapp-testing`, ou Playwright en devDep du front).

La branche git, elle, n'est plus à créer soi-même sur la voie Spec Kit : depuis
0.15.0 le hook `before_specify` de `/speckit-specify` l'ouvre pour de vrai. Les
commits-gate, en revanche, restent inertes — voir §Les hooks git dans les
garde-fous ci-dessous.

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

### 2. Les hooks git : ils s'exécutent depuis 0.15.0

C'est un renversement par rapport à ce que ce document et `AGENTS.md` disaient en
0.9.2 (« échouent sans effet »). L'extension `git` enregistre désormais ses cinq
commandes **pour `claude`** — `registered_commands` et `registered_skills` dans
`.specify/extensions/.registry` — et `.specify/extensions.yml` porte
`auto_execute_hooks: true`. `/speckit-specify` déclenche donc réellement
`before_specify` → `/speckit-git-feature`, qui fait le `git checkout -b`. Les
SKILL.md 0.15.0 l'écrivent noir sur blanc : annoncer le hook ne l'exécute pas,
il faut l'invoquer.

Le core, lui, a **coupé le lien entre la feature et la branche** :
`create-new-feature.sh` ne fait plus aucun appel git (ni `fetch`, ni
`checkout -b`) et numérote d'après `specs/` seul ; la feature courante se lit
dans `.specify/feature.json` (clé `feature_directory`, fichier **suivi**) ou dans
`SPECIFY_FEATURE_DIRECTORY` ; `check-prerequisites.sh` ne valide plus le nom de
branche. Un worktree Superpowers dont la branche ne suit aucune convention Spec
Kit ne bloque donc plus `/speckit-plan` — c'était la friction nº1 entre les deux
outils.

Les **commits-gate** restent en revanche inertes, et c'est voulu :
`auto_commit.default: false` dans `.specify/extensions/git/git-config.yml`, tous
les événements à `false`. Les hooks `speckit.git.commit` partent, lisent la
config et passent — donc pas d'auto-commit par `/speckit-implement`. Ne pas les
activer à la légère : ils committent via `git add .`, donc tout le worktree, sans
égard au périmètre.

### 3. Le gate `checklists/` est réel, et gratuit

Les trois features ont un `specs/NNN/checklists/requirements.md`.
`/speckit-implement` scanne ce dossier, dresse un tableau de complétion et
**s'arrête en demandant confirmation** si un item est décoché. C'est un vrai
garde-fou : à connaître plutôt qu'à subir.

---

## Le pointeur `<!-- SPECKIT START -->` de `AGENTS.md` peut devenir périmé

`AGENTS.md` (racine) porte, tout en bas, un bloc géré par l'extension
`agent-context` (`.specify/extensions/agent-context/`) : « lire le plan actuel
à `specs/<id>-feature/plan.md` ». Ce bloc n'est réécrit que sur les hooks
`after_specify`/`after_plan` — donc quand une branche lance `/speckit-specify`
ou `/speckit-plan` — et son script (`update-agent-context.sh`) résout
`specs/<branche-courante>/plan.md` (repli sur « pas de plan » si ce fichier
n'existe pas — jamais sur le `plan.md` d'une autre feature).

Avant #374, le script choisissait le `plan.md` le plus récemment modifié sur
**tout** `specs/`, sans regard pour la branche courante : une branche qui ne
relançait jamais `/speckit-specify`/`/speckit-plan` (voie sans plan, voie
Superpowers) conservait le pointeur laissé par la dernière feature Spec Kit
mergée, potentiellement sans rapport avec son propre travail — constaté avec
le pointeur vers `specs/20260814-221102-athletes-par-saison/` (#274, déjà
mergé par `11d3527`) resté présent plusieurs branches plus tard. La résolution
par branche courante élimine cette dérive inter-feature.

Une fenêtre résiduelle plus courte subsiste : le commit qui met à jour ce bloc
fait partie du diff de la feature qui vient de lancer `/speckit-plan`, donc
`main` hérite temporairement, après fusion, d'un pointeur qui désigne cette
feature tout juste livrée — jusqu'à ce qu'une future branche relance
`/speckit-specify`/`/speckit-plan` et écrase le bloc à son tour. Comme
`AGENTS.md` se charge à **chaque** session quelle que soit la branche
(`CLAUDE.md` → `@AGENTS.md`), **vérifier avant de fusionner une branche qui a
touché ce bloc** : si `git diff main -- AGENTS.md` montre que le pointeur
désigne le plan de la branche en cours, le vider (revenir à la forme sans
ligne « at … », celle que le script émet lui-même quand aucun plan n'est
trouvé) avant de merger, plutôt que de laisser `main` porter une référence à
une feature déjà livrée.

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
2. Installer les skills officiels Anthropic :
   `/plugin marketplace add anthropics/skills` puis
   `/plugin install example-skills@anthropic-agent-skills`. Le paquet embarque
   `frontend-design`, sur lequel `ui-ux-review` s'appuie pour le fond, et
   `webapp-testing`, candidat du jour où la review passera au navigateur.
3. Initialiser Spec Kit : `specify init --integration claude-code` (Spec Kit v0.10+
   a remplacé les anciens flags `--ai` par `--integration`).
4. `/speckit-constitution`.
5. Committer `.specify/` ; `.claude/` selon la politique de l'équipe.

Les étapes 1 et 2 s'installent **par machine**, pas par dépôt : un plugin vit
dans la configuration utilisateur et ne se commite pas. Les artefacts du dépôt —
`.claude/agents/`, `.claude/skills/` — sont versionnés et arrivent donc avec le
clone ; les plugins sont à installer une fois par poste. `ui-ux-review` reste
utilisable sans le plugin : il en emprunte la doctrine, il n'en dépend pas.

**Ne pas ajouter de « ligne-pont »** à la constitution du type « toute
implémentation d'une task list doit suivre le workflow Superpowers » : c'est
exactement le croisement que la règle d'or interdit. (Ce document l'a recommandé
par le passé ; la ligne n'est jamais entrée dans la constitution de ce repo.)

**État de ce repo** : la mise en place est déjà faite, en **Spec Kit 0.15.0**
(`.specify/init-options.json`) — à l'étape 2 près, qui est par poste et reste
donc à faire sur une machine neuve. La constitution est **ratifiée le
2026-07-27, amendée en v1.1.0** (`.specify/memory/constitution.md`) — ne pas
relancer `/speckit-constitution`
pour « la remplir ». Elle ne nomme aucun exécuteur (sa section « Development
Workflow » dit `… → /speckit-analyze → exécution`), donc la règle de provenance
**ne demande aucun amendement**. L'intégration active est `claude`
(`.specify/integration.json`) : dix skills de cœur (`speckit-specify`,
`speckit-plan`, `speckit-tasks`, `speckit-analyze`, `speckit-clarify`,
`speckit-checklist`, `speckit-implement`, `speckit-converge`,
`speckit-constitution`, `speckit-taskstoissues`) et six skills d'extension
(`speckit-git-{feature,validate,remote,initialize,commit}`,
`speckit-agent-context-update`).

Deux personnalisations locales vivent dans `.specify/templates/` et sont
**réappliquées à chaque mise à jour de Spec Kit**, qui les écrase : la table de
passage des 6 principes dans `plan-template.md` (l'amont y remet
`[Gates determined based on constitution file]`) et l'exigence TDD du
`tasks-template.md` (l'amont y remet « Tests are OPTIONAL »). Vérifier ces deux
fichiers dans le diff d'une montée de version — le Principe III est
non-négociable, un template qui dit l'inverse contredit la constitution.

---

## Où atterrissent les artefacts

Spec Kit n'est pas le seul à écrire des fichiers : `brainstorming` et
`writing-plans` en produisent aussi. Savoir qui écrit quoi distingue un artefact
légitime d'un doublon.

| Emplacement | Écrit par | Statut |
|---|---|---|
| `specs/<id>-feature/` — `spec.md`, `plan.md`, `tasks.md`, `checklists/`, `research.md`, `data-model.md`, `quickstart.md` | Spec Kit | **Canonique** sur la voie Spec Kit. Un seul de chaque, par feature. `id` **horodaté** (`YYYYMMDD-HHMMSS`) depuis 0.15.0 : `feature_numbering: timestamp` dans `.specify/init-options.json`, doublé de `branch_numbering: timestamp` dans `.specify/extensions/git/git-config.yml` pour que la branche et le dossier portent le même préfixe. Les trois features déjà en place gardent leur `NNN` séquentiel. |
| `docs/superpowers/specs/…-design.md` | `brainstorming` (l'écrit **et le commite**) | **Canonique** sur la voie Superpowers. |
| `docs/superpowers/plans/…` | `writing-plans` | **Canonique** sur la voie Superpowers. |
| `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md` | l'agent, à la main | **Rapport de terrain** — voir ci-dessous. |
| `.superpowers/sdd/<nom-du-plan>/` | `subagent-driven-development` | Ledger d'exécution (`progress.md`, briefs, rapports). Jetable, jamais commité. |

Une feature relève d'une voie **ou** de l'autre : la ligne `specs/<id>-feature/` et
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
`/speckit-*`. Pour ce projet, elle est **ratifiée le 2026-07-27, amendée en
v1.1.0** — ne pas relancer `/speckit-constitution` pour la remplir.

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
