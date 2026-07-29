# Workflow IA — Spec Kit + Superpowers

Ce document s'adresse aux collaborateurs qui utilisent **Claude Code** (ou tout
agent IA compatible) sur ce projet. Deux outils d'assistance sont préconfigurés,
**Spec Kit** et **Superpowers**, et leurs périmètres se chevauchent sur la
planification. Sans règle claire, un agent lance les deux pour la même tâche et
produit des artefacts concurrents. Ce document fixe **qui fait quoi et quand**.

---

## Le principe

**Spec Kit possède les artefacts. Superpowers possède l'exécution.** Le point de
jonction est `tasks.md`.

| Outil | Rôle |
|---|---|
| **Spec Kit** | Produit les artefacts documentaires d'une feature : `spec.md`, `plan.md`, `tasks.md` dans `specs/NNN-feature/`. Explicite et **déterministe** : on tape `/speckit-plan`. |
| **Superpowers** | Applique la discipline d'artisanat pendant qu'on code : worktree, TDD red-green-refactor, sous-agents, revue de code, fin de branche. Ses skills se déclenchent **automatiquement** quand leur description correspond à la situation. |

Les deux se recouvrent sur la phase **planification** — c'est là que naissent les
conflits. La différence de nature aide à les répartir : Spec Kit est explicite et
déterministe (une commande `/speckit-*`), tandis que les skills Superpowers
s'activent seuls sur correspondance de description.

> **Règle d'or** : Spec Kit cadre et planifie jusqu'à `tasks.md` ; Superpowers
> exécute et garantit la qualité.

> **Notation** : sous Claude Code les commandes Spec Kit s'invoquent avec un tiret
> (`/speckit-specify`, `/speckit-plan`…). L'intégration `opencode` de ce repo
> utilise le point (`speckit.specify`). Même skill, séparateur différent.

---

## Mise en place (une fois par repo)

1. Installer Superpowers : `/plugin marketplace add obra/superpowers-marketplace`
   puis `/plugin install superpowers@superpowers-marketplace`.
2. Initialiser Spec Kit : `specify init --integration claude-code` (Spec Kit v0.10+
   a remplacé les anciens flags `--ai` par `--integration`).
3. `/speckit-constitution`, en y ajoutant une **ligne-pont** du type : « toute
   implémentation d'une task list doit suivre le workflow Superpowers : worktree →
   TDD red-green-refactor → sous-agents → code review → finish-branch ».
4. Committer `.specify/` ; `.claude/` selon la politique de l'équipe.

**État de ce repo** : la mise en place est déjà faite. La constitution est
**ratifiée en v1.0.0** (`.specify/memory/constitution.md`) — ne pas relancer
`/speckit-constitution` pour « la remplir ». L'intégration active est `opencode`
(`.specify/integration.json`) ; les neuf skills `speckit-*` sont présents pour
Claude.

---

## La boucle par feature

Une **vraie feature** = nouveau scraper, nouvel écran, changement de schéma,
fonctionnalité à plusieurs composants.

1. **Cadrage flou** → laisser tourner le skill `brainstorming` de Superpowers.
2. `/speckit-specify` → `/speckit-plan` → `/speckit-tasks`.
3. `/speckit-analyze` **avant tout code** : il vérifie, en lecture seule, les
   incohérences, ambiguïtés et trous de couverture entre `spec.md`, `plan.md` et
   `tasks.md`.
4. **Handoff** vers Superpowers : pointer `subagent-driven-development` sur le
   `plan.md` / `tasks.md` de Spec Kit. Les tâches marquées `[P]` sont distribuées
   sur des sous-agents en parallèle. Superpowers gère alors **TDD + revue en deux
   passes**, avec `test-driven-development` dans chaque tâche.
5. Fin de branche : `requesting-code-review` → `verification-before-completion` →
   `finishing-a-development-branch`.

La branche git et les commits-gate restent **manuels** : les hooks de
`.specify/extensions.yml` ne s'enregistrent que pour `agy` et `codex`, jamais pour
`claude` ni pour `opencode` (l'intégration active) — ils ne s'exécutent donc jamais.
Créer la branche soi-même.

---

## Deux pièges concrets

- **Le doublon de planification.** Dire explicitement à l'agent que le plan existe
  déjà dans `specs/<id>/plan.md` et qu'il **ne doit pas le réécrire** — sinon le
  skill `writing-plans` régénère un plan parallèle. Même principe pour la spec :
  `spec.md` est canonique, pas un `-design.md` concurrent.
- **Le sur-outillage.** Pour un correctif d'une ligne, **sauter la boucle
  entièrement** : les skills Superpowers ne s'activent que sur le déclencheur de
  `brainstorming`, donc un petit changement n'entraîne aucun cycle. Compter
  **~20-40 % de tokens en plus** par feature quand on lance la boucle complète.

---

## Quand sauter la boucle : le workflow vibe

Bugfix, typo, ajustement de 1-2 fichiers, petit refacto → **Superpowers seul**, pas
de cycle Spec Kit, pas de dossier `specs/` :

1. (facultatif) `brainstorming` si l'approche n'est pas évidente.
2. `systematic-debugging` (bug) **ou** `test-driven-development` (ajout de
   comportement).
3. `verification-before-completion`.
4. `finishing-a-development-branch` si ça mérite une PR.

---

## Où atterrissent les artefacts

Spec Kit n'est pas le seul à écrire des fichiers : `brainstorming` et
`writing-plans` en produisent aussi. Savoir qui écrit quoi distingue un artefact
légitime d'un doublon.

| Emplacement | Écrit par | Statut |
|---|---|---|
| `specs/NNN-feature/` — `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md` | Spec Kit | **Canonique** sur le cadrage et la planification. Un seul de chaque, par feature. |
| `docs/superpowers/specs/…-design.md` | `brainstorming` (l'écrit **et le commite**) | Design Superpowers. Sur une feature Spec Kit, `spec.md` reste canonique — ne pas laisser ce design en devenir le concurrent (voir le piège du doublon). |
| `docs/superpowers/plans/…` | `writing-plans` | Plan Superpowers. Sur une feature Spec Kit, `plan.md` reste canonique. |
| `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md` | l'agent, à la main | **Rapport de terrain** — voir ci-dessous. |
| `.superpowers/sdd/<nom-du-plan>/` | `subagent-driven-development` | Ledger d'exécution (`progress.md`, briefs, rapports). Jetable, jamais commité. |

Les chemins `docs/superpowers/` sont les **défauts amont du plugin**
(`brainstorming/SKILL.md`, `writing-plans/SKILL.md`), pas une convention de ce
dépôt : le dossier porte le nom de **l'outil**, pas celui du contenu. Les fichiers
déjà présents **restent où ils sont** ; ils mêlent des designs de features livrées
(valeur historique) et des rapports de terrain encore normatifs, cités nominativement
par `AGENTS.md` là où ils s'appliquent.

### La troisième catégorie : le sondage

Un sondage n'est ni une spec ni un plan : il consigne des **observations** (ce qui a
été mesuré sur le site ou le code réels), pas des intentions. Il a donc sa place dans
les deux workflows et n'entre en collision avec rien. Il est écrit sous
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

---

*Pour les détails d'architecture et les conventions de scraping, voir `AGENTS.md`.*
