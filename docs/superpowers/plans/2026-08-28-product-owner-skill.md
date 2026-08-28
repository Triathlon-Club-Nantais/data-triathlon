# Skill `/product-owner` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/product-owner` skill that grooms the open GitHub backlog — Definition of Ready, epics via native sub-issues, board priority, and the epic git workflow — in dry-run-then-batch-approval mode.

**Architecture:** Three files — a durable convention doc (`docs/gestion-de-projet.md`), a heavy-reference file for the `gh api graphql`/`gh project` mechanics (`.claude/skills/product-owner/reference/graphql.md`), and the operational skill itself (`.claude/skills/product-owner/SKILL.md`) that reads the backlog, proposes a plan, waits for approval, then applies. One-time board setup configures the `Priority` field. A real dry-run against a small sample of the actual backlog closes the loop.

**Tech Stack:** Markdown (skill + docs), `gh` CLI v2.45.0, `gh api graphql` (GitHub GraphQL API), GitHub Projects v2 (board "Data TCN", `Triathlon-Club-Nantais`, project #1).

**Spec:** `docs/superpowers/specs/2026-08-28-product-owner-skill-design.md`

## Global Constraints

- Issue titles: `type(scope): description`, English, Conventional Commits (Principe I).
- Issue bodies: French, structured `## Constat de départ` / `## Demande` / `## Hors périmètre`.
- `gh` v2.45.0 has no CLI flags for sub-issue linking or adding options to an existing project field — every such mutation goes through `gh api graphql` (exact queries verified by schema introspection on 2026-08-28, see Task 2).
- Board "Data TCN": project node ID `PVT_kwDOEaPNkc4Bdwm2`, `Status` field ID `PVTSSF_lADOEaPNkc4Bdwm2zhYP1fg` (a real project field). `Priority` field ID `PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ` is a *mirror* of org-level Issue Field `IFSS_kgDOApchLg` (already has 4 options: Urgent/High/Medium/Low) — set it via `updateIssueFieldValue` on the issue, never via `gh project item-edit` or `updateProjectV2Field` (see Task 4).
- Never write to GitHub without the user's explicit batch approval of the presented plan.
- Never create a milestone automatically — always a separate, dedicated confirmation.

## RED baseline (already run — do not re-run before writing the skill)

Two pressure-scenario subagents were run 2026-08-28, before any product-owner file existed in this worktree, to establish whether these two rules need discipline-style bulletproofing (rationalization table, red flags) per `superpowers:writing-skills`:

1. **Dry-run gate** (time pressure + authority + sunk cost + social): agent chose **A — present the plan, wait for explicit approval** even under a club president's "go ahead, I trust you" at 18:50 before a 19:00 meeting.
2. **No auto-milestone** (apparent obviousness + exhaustion + convenience): agent chose **B — propose the milestone in the plan, apply nothing without a confirmation dedicated to that point**.

Both baseline runs already complied without any skill present — no failure to prevent. Per `superpowers:writing-skills` ("Don't test skills without rules to violate, skills agents have no incentive to bypass" / "If the control doesn't exhibit the failure, there is nothing to fix"), these two rules are written as plain ordered recipe steps below, not as a prohibition list with a rationalization table — that treatment is reserved for failures actually observed under pressure, and forcing it here would be authoring for a hypothetical.

---

### Task 1: `docs/gestion-de-projet.md` — Definition of Ready, epic model, priority, git workflow

**Files:**
- Create: `docs/gestion-de-projet.md`
- Modify: `AGENTS.md` (routing table)

**Interfaces:**
- Produces: the convention doc that Task 3's `SKILL.md` cross-references as `REQUIRED BACKGROUND`.

- [ ] **Step 1: Write `docs/gestion-de-projet.md`**

```markdown
# Gestion de projet — backlog, epics, priorité, workflow git

Convention appliquée par la skill `/product-owner` et par quiconque raffine
une issue ou planifie une release à la main. Le board GitHub Projects
utilisé est **Data TCN** (`Triathlon-Club-Nantais`, projet #1).

## Definition of Ready

Une issue est raffinée — elle peut passer `Backlog` → `Ready` sur le board —
quand elle a :

1. **Titre** `type(scope): description`, en anglais (Conventional Commits,
   jeton machine — Principe I de la constitution).
2. **Corps en français**, structuré :
   - `## Constat de départ` (ou `## Contexte`) — ce qui a été observé/mesuré ;
   - `## Demande` — le ou les critères d'acceptation, testables ;
   - `## Hors périmètre` — ce que l'issue ne couvre pas, pour éviter le
     scope creep.
3. **Une seule tâche.** Une issue qui décrit plusieurs livrables
   indépendants doit être scindée en issues enfants — 1 tâche = 1 issue.
4. **Labels** : au moins un label de domaine (`backend`, `frontend`,
   `scraper`, `auth`, `ops`, …) et un label de nature (`bug`,
   `enhancement`, …).
5. **Priorité** posée sur le champ `Priority` du board (voir plus bas).
6. **Rattachement** explicite : epic (label `epic`, sub-issue GitHub
   native) ou autonomie assumée.

Une issue qui ne peut pas être raffinée faute d'information reste en
`Backlog`, avec un commentaire listant ce qui manque.

## Epics

- Une epic se justifie quand ≥2 issues partagent un même objectif
  fonctionnel.
- **Issue-epic** : label `epic`, titre `epic(scope): objectif`.
- **Liaison** : relation *sub-issue* native de GitHub (champs `Parent
  issue` / `Sub-issues progress` du board), pas une checklist markdown.
- **Statut de l'epic**, toujours dérivé de ses sous-issues, jamais saisi à
  la main : `Backlog` tant qu'aucune sous-issue n'est `Ready`, `In
  progress` dès qu'une l'est, `Done` quand toutes sont fermées **et** la
  PR parapluie (voir plus bas) est mergée.

## Priorité

Champ `Priority` (single-select) du board « Data TCN ». Échelle standard
GitHub :

| Valeur | Quand |
| --- | --- |
| 🔴 Urgent | Sécurité, perte/corruption de données, prod cassée. |
| 🟠 High | Bloque d'autres tâches, ou demande répétée/impact large. |
| 🟡 Medium | Amélioration normale sans urgence. |
| 🟢 Low | Cosmétique, nice-to-have. |

## Milestone

Les milestones GitHub représentent des **versions/releases**, alignées sur
le déploiement par tag (`docs/ci-cd.md`) — jamais des sprints. Un milestone
ne se crée que sur décision humaine explicite ; ce n'est jamais une
conséquence automatique du raffinement d'une issue.

## Workflow git d'une epic multi-issues

- **Branche d'intégration** : `epic/<n°>-<slug>`, créée depuis `main`.
- **Sous-issues** : un worktree par issue comme d'habitude
  (`docs/dev-multi-worktree.md`), mais basé sur `epic/<n°>-<slug>` et non
  `main` ; leur PR cible cette branche, avec `Refs #<epic>` — pas `Closes`,
  l'epic ne se ferme qu'à la PR parapluie.
- **PR parapluie** : une fois toutes les sous-issues mergées dans la
  branche d'intégration, une PR `epic/<n°>-<slug>` → `main` avec
  `Closes #<epic>`.
- **Nettoyage** : suppression de la branche d'intégration après le merge de
  la PR parapluie.
```

- [ ] **Step 2: Add the routing line to `AGENTS.md`**

In the "Où lire quoi" table, insert a new row directly after the `RTK` row
(`| RTK : gains mesurés du préfixe \`rtk\`, et où il est interdit | \`docs/rtk.md\` |`):

```markdown
| Gestion de projet : Definition of Ready, epics, priorité, workflow git des epics | `docs/gestion-de-projet.md` |
```

- [ ] **Step 3: Retrieval-scenario check**

Dispatch a fresh `general-purpose` subagent (no conversation context) with:

```
Lis uniquement le fichier docs/gestion-de-projet.md à la racine du dépôt
data-triathlon. Réponds à ces deux questions, une phrase chacune :
1. Une sous-issue d'epic ouvre sa PR vers quelle branche, et avec quel mot-clé
   (Closes ou Refs) ?
2. Un milestone peut-il être créé automatiquement par un outil qui suit
   cette convention ?
```

Expected answers: (1) vers la branche d'intégration `epic/<n°>-<slug>`, avec `Refs` (pas `Closes`) ; (2) non, jamais automatiquement, toujours une décision humaine explicite. If the subagent's answer is ambiguous or wrong, the doc is unclear — revise Step 1 and re-run this check.

- [ ] **Step 4: Commit**

```bash
git add docs/gestion-de-projet.md AGENTS.md
git commit -m "docs(gestion-de-projet): définir Definition of Ready, epics, priorité, workflow git"
```

---

### Task 2: `.claude/skills/product-owner/reference/graphql.md` — GraphQL/CLI mechanics

**Files:**
- Create: `.claude/skills/product-owner/reference/graphql.md`

**Interfaces:**
- Produces: the reference `SKILL.md` (Task 3) cross-links as `REQUIRED REFERENCE`.

- [ ] **Step 1: Write `.claude/skills/product-owner/reference/graphql.md`**

```markdown
# Mécaniques GitHub GraphQL/CLI pour `/product-owner`

`gh` v2.45 (version installée sur les postes de dev) n'expose pas la
relation *sub-issue* ni l'ajout d'options à un champ de projet existant en
commande dédiée — ce fichier documente les appels `gh api graphql`
nécessaires. Confirmé le 28/08/2026 par introspection du schéma
(`gh api graphql -f query='{ __type(name: "...") { ... } }'`).

## IDs du projet « Data TCN »

| Élément | ID |
| --- | --- |
| Projet (owner `Triathlon-Club-Nantais`, #1) | `PVT_kwDOEaPNkc4Bdwm2` |
| Champ `Status` | `PVTSSF_lADOEaPNkc4Bdwm2zhYP1fg` |
| Champ `Priority` | `PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ` |

Si un appel échoue avec « field not found », ré-résoudre avec :
```bash
gh project field-list 1 --owner Triathlon-Club-Nantais
```

## Node ID d'une issue

Les mutations GraphQL utilisent l'ID de nœud (`node_id`), pas le numéro :
```bash
gh api repos/Triathlon-Club-Nantais/data-triathlon/issues/<numéro> -q .node_id
```

## Lier une sous-issue à une epic

```bash
gh api graphql -f query='
mutation($issueId: ID!, $subIssueId: ID!) {
  addSubIssue(input: { issueId: $issueId, subIssueId: $subIssueId }) {
    issue { number }
  }
}' -f issueId="<node_id de l'epic>" -f subIssueId="<node_id de la sous-issue>"
```

## Configurer le champ Priority (à faire une seule fois — voir Task 4)

```bash
gh api graphql -f query='
mutation($fieldId: ID!) {
  updateProjectV2Field(input: {
    fieldId: $fieldId
    singleSelectOptions: [
      { name: "🔴 Urgent", color: RED, description: "" }
      { name: "🟠 High", color: ORANGE, description: "" }
      { name: "🟡 Medium", color: YELLOW, description: "" }
      { name: "🟢 Low", color: GREEN, description: "" }
    ]
  }) {
    projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } }
  }
}' -f fieldId="PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ"
```

Récupérer les `option.id` retournés — nécessaires pour poser une valeur sur
un item (étape suivante).

## Poser Status/Priority sur un item du board

Il faut d'abord l'ID d'*item* de projet (pas le node_id de l'issue) :
```bash
gh project item-list 1 --owner Triathlon-Club-Nantais --format json \
  -q '.items[] | select(.content.number == <numéro>) | .id'
```

Puis, une seule valeur de champ par appel (limite de `gh project item-edit`) :
```bash
gh project item-edit \
  --project-id "PVT_kwDOEaPNkc4Bdwm2" \
  --id "<item id>" \
  --field-id "PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ" \
  --single-select-option-id "<option id>"
```

## Échec partiel

`gh project item-edit`/`gh api graphql` renvoient un code de sortie non nul
et un message d'erreur JSON en cas d'échec — capturer stdout/stderr, ne pas
masquer l'erreur, et lister explicitement à l'utilisateur les paires
(item, champ) qui n'ont pas pu être appliquées, sans retenter
automatiquement.
```

- [ ] **Step 2: Retrieval-scenario check**

Dispatch a fresh `general-purpose` subagent with:

```
Lis uniquement .claude/skills/product-owner/reference/graphql.md dans le
worktree courant. Écris (sans l'exécuter) la commande gh api graphql exacte
pour lier l'issue #123 (node_id "I_kwABC") comme sous-issue de l'epic #100
(node_id "I_kwXYZ").
```

Expected: a `gh api graphql` call using the `addSubIssue` mutation with
`issueId="I_kwXYZ"` (the epic) and `subIssueId="I_kwABC"` (the sub-issue),
matching the Task 2 Step 1 template. If the subagent swaps parent/child or
invents a different mutation name, the doc is ambiguous — revise and
re-check.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/product-owner/reference/graphql.md
git commit -m "docs(product-owner): documenter les mécaniques GraphQL/gh CLI"
```

---

### Task 3: `.claude/skills/product-owner/SKILL.md`

**Files:**
- Create: `.claude/skills/product-owner/SKILL.md`

**Interfaces:**
- Consumes: `docs/gestion-de-projet.md` (Task 1), `.claude/skills/product-owner/reference/graphql.md` (Task 2).

- [ ] **Step 1: Write `.claude/skills/product-owner/SKILL.md`**

```markdown
---
name: product-owner
description: Use when the user wants to groom, refine, triage, or prioritize the open GitHub issue backlog, wants issues clustered into epics or linked as GitHub sub-issues, or wants the "Data TCN" project board's Status/Priority fields updated.
---

# Product Owner

## Overview

Balaie tout le backlog GitHub ouvert, raffine les issues qui n'atteignent
pas la Definition of Ready, les regroupe en epics, pose une priorité sur le
board, et applique/documente le workflow git des epics multi-issues.
Fonctionne en dry-run : rien n'est écrit sur GitHub avant validation
explicite du plan par l'utilisateur.

**REQUIRED BACKGROUND:** `docs/gestion-de-projet.md` — Definition of
Ready, modèle d'epic, échelle de priorité, rôle des milestones, workflow
git. Cette skill applique cette convention, elle ne la redéfinit pas.

**REQUIRED REFERENCE:** `reference/graphql.md` — commandes `gh api
graphql`/`gh project` exactes (liaison sub-issue, champs du board, IDs).

## Quand l'utiliser

- "Raffine le backlog", "fais le tri dans les issues", "priorise le
  backlog".
- "Regroupe ces issues en epic", "crée une epic pour X".
- Avant une réunion/release, pour remettre le board à jour.

## Déroulé

1. **Collecter** : `gh issue list --state open` (backlog complet) +
   `gh project item-list 1 --owner Triathlon-Club-Nantais` pour les items
   du board. Résoudre une fois les IDs de champs (`reference/graphql.md`),
   les garder en mémoire pour le reste de l'invocation.
2. **Analyser** chaque issue contre la Definition of Ready
   (`docs/gestion-de-projet.md`). Une issue qui la satisfait déjà sort de
   la liste de travail. Pour les autres, dispatcher un agent
   `Explore`/`general-purpose` si le raffinement demande de lire du code,
   et proposer : titre, corps structuré, labels, priorité, scission (si
   plusieurs tâches sont bundlées), rattachement à une epic.
3. **Regrouper en epics** : rattacher en priorité aux epics `label:epic`
   déjà existantes ; n'en proposer une nouvelle que si aucune epic
   existante ne correspond à l'objectif partagé par ≥2 issues. Le corps
   d'une epic proposée ne duplique pas le workflow git — il y renvoie :
   `Workflow : voir docs/gestion-de-projet.md#workflow-git-dune-epic-multi-issues`.
4. **Présenter le plan en chat**, groupé par epic puis « sans epic »,
   chaque ligne = état actuel → changement proposé. Une issue Ready/Done
   qui semble former une release cohérente est signalée séparément
   ("ces N issues ressemblent à v0.7.0, je crée le milestone ?") — jamais
   appliqué sans confirmation dédiée à ce point précis.
5. **Attendre l'approbation explicite du lot** (ajustable en langage
   naturel : "saute la #123", "fusionne avec l'epic X") avant d'écrire quoi
   que ce soit sur GitHub.
6. **Appliquer**, dans l'ordre : créer les epics → scinder les issues
   bundlées → éditer titre/corps/labels/priorité → lier les sub-issues
   (`reference/graphql.md`) → poser les champs du board → passer `Ready`
   si la Definition of Ready est atteinte. Ne jamais créer de milestone
   sans confirmation dédiée.
7. **Rapporter** : ce qui a été appliqué, ce qui a échoué (le cas échéant,
   sans retry automatique — voir `reference/graphql.md`), ce qui reste en
   `Backlog` faute d'information.

## Ré-invocation

Une issue déjà conforme à la Definition of Ready n'apparaît plus dans le
plan suivant — pas de ré-écriture inutile. Le statut d'une epic est
recalculé à chaque passe, jamais incrémenté.

## Erreurs courantes

| Situation | À faire |
| --- | --- |
| Une seule sous-issue prête, l'epic n'a pas encore de branche d'intégration | Le rappeler dans le plan, ne pas créer la branche avant qu'au moins une sous-issue soit prête à démarrer. |
| Une issue déjà bien écrite (Definition of Ready presque atteinte) | Ne proposer que ce qui manque réellement (souvent : juste labels + priorité) — ne pas réécrire un corps déjà conforme. |
| Board et labels en désaccord (ex. `Priority` posé sur le board mais pas de label de domaine) | Traiter chaque critère de la Definition of Ready indépendamment — un critère manquant suffit à garder l'issue hors de `Ready`. |
```

- [ ] **Step 2: VERIFY GREEN — re-run the two RED baseline scenarios with the skill present**

Dispatch two fresh `general-purpose` subagents (not forks) with the exact
same prompts used for the RED baseline (see "RED baseline" section above),
but prepend to each: `Tu as accès à la skill product-owner
(.claude/skills/product-owner/SKILL.md et docs/gestion-de-projet.md dans ce
dépôt) — lis-la si utile avant de répondre.`

Expected: both agents still choose the compliant option (A for the
dry-run-gate scenario, B for the milestone scenario), and at least one
response cites the skill or the doc by name. If either agent now picks a
non-compliant option, `SKILL.md` introduced guidance that undermines
already-good baseline behavior — find the contradicting sentence and fix
it before proceeding (this is a real regression, not a hypothetical to
pre-empt).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/product-owner/SKILL.md
git commit -m "feat(product-owner): add /product-owner skill for backlog grooming"
```

---

### Task 4: One-time board setup — configure the `Priority` field

**Superseded during execution (2026-08-28).** The field-update mutation
below was run and rejected: `updateProjectV2Field` returned "Only custom
fields can be updated. Fields derived from issues or pull requests must be
updated through their respective APIs." Introspection showed why:
`Priority` (`PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ`) has `isIssueField: true` — it
mirrors an organization-level Issue Field (`IFSS_kgDOApchLg`), not a
project-owned field, and that Issue Field **already has 4 options**
(Urgent/High/Medium/Low — no emoji, unlike this task's original plan).

No configuration is needed or possible from the project side; recreating
or renaming those options via `updateIssueField` would touch a field
potentially shared with other repos/projects in the organization — an
effect outside this worktree and outside this single board, so it was not
attempted. `docs/gestion-de-projet.md` and
`.claude/skills/product-owner/reference/graphql.md` were corrected to
reflect this (see their "Priorité"/"Priority est un Issue Field partagé"
sections) — those corrections are this task's actual deliverable.

No file changes beyond the corrections above. No commit beyond the one
covering those doc corrections. Task 4 is complete as a documentation
correction, not a board mutation.

~~Step 1: Run the field-update mutation~~ — do not run; fails as described
above.

~~Step 2: Verify~~ — superseded; the four values already exist at
`gh api graphql -f query='{ node(id: "PVTSSF_lADOEaPNkc4Bdwm2zhYP1qQ") { ... on ProjectV2SingleSelectField { issueField { ... on IssueFieldSingleSelect { options { id name } } } } } }'`.

---

### Task 5: Real dry-run — application test against a live sample

No file changes, no commit. **Dry-run only — do not apply anything to
GitHub in this task**, per the skill's own rule (Task 3, Step 5).

**Sample** (chosen 2026-08-28 for diversity of starting quality):
- **#658** `fix(batch): ci action failed` — body is just a link, no
  structure. Expected: flagged as insufficient information, stays
  `Backlog`, with a comment listing what's missing (repro steps, which
  step of the CI failed, since when).
- **#700** `fix(resultats): CoverageTimeline n'affiche jamais l'année sur
  l'axe des mois` — body already has `## Contexte` / `## Cause probable` /
  `## Comportement attendu` / `## Fichiers concernés`. Expected: only
  labels (`frontend`, `bug`) + priority proposed, no body rewrite — this
  issue is already Definition-of-Ready-compliant in substance.
- **#718** `feat(admin): recherche d'epreuve par id` and **#719**
  `feat(admin): accéder à la course` — both one-line asks about `/admin`
  navigation. Expected: proposed as two sub-issues of a new epic (shared
  objective: ergonomie de navigation `/admin`), each rewritten into
  `## Constat de départ` / `## Demande` / `## Hors périmètre`, with
  `admin` + `enhancement` labels and a priority. The new epic's body links
  to `docs/gestion-de-projet.md#workflow-git-dune-epic-multi-issues`
  instead of restating the git workflow.

- [ ] **Step 1: Invoke the skill in dry-run against exactly these four issues**

Load `.claude/skills/product-owner/SKILL.md` and run its "Déroulé" against
issues #658, #700, #718, #719 only (not the full backlog — scoping to this
sample keeps the check fast and reviewable). Stop after step 4 ("Présenter
le plan en chat") — do not proceed to step 5/6.

- [ ] **Step 2: Compare the produced plan against the expected outcomes above**

For each of the four issues, check the plan's proposal matches the
expected outcome's *shape* (not exact wording): #658 flagged incomplete
and kept in `Backlog`; #700 gets only labels+priority, no rewritten body;
#718/#719 clustered into one new epic with restructured bodies. If any
issue's proposal diverges in shape (e.g. #700's already-good body gets
rewritten anyway, or #718/#719 aren't clustered), that's a real gap in
`SKILL.md`'s "Déroulé" or "Erreurs courantes" section — fix it and re-run
Step 1 against the same four issues before moving on.

- [ ] **Step 3: Report to the user**

Summarize the four proposals and the comparison result. Do not apply
anything — actual application to the live backlog is a separate,
explicitly user-invoked run of `/product-owner`, after this plan's PR is
reviewed and merged.
