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
