# Skill `/product-owner` — design

Issue : #717

## Constat de départ

Aucun outil ne raffine systématiquement le backlog ouvert du dépôt. Mesuré au
28/08/2026 : 25 issues ouvertes, 18 sans aucun label, aucune epic. Le board
GitHub Projects « Data TCN » (org `Triathlon-Club-Nantais`, projet #1,
331 items) a :

- un champ `Status` single-select `Backlog → Ready → In progress → In
  review → Done` — inexploité comme gate de raffinement ;
- un champ `Priority` single-select, en fait le miroir d'un *Issue Field*
  au niveau organisation, déjà pourvu de 4 valeurs (Urgent/High/Medium/Low)
  — découvert en cours d'exécution (28/08/2026), corrige l'hypothèse
  initiale de cette spec qui le pensait vide ;
- des champs natifs `Parent issue` / `Sub-issues progress` (relation
  sub-issue GitHub, distincte d'une checklist markdown) — inexploités ;
- `Size`, `Estimate`, `Start date`, `Target date`, `Milestone`.

Deux outils voisins existent déjà et restent hors périmètre (voir
« Hors périmètre ») : `speckit-taskstoissues` (convertit le `tasks.md` d'une
feature Spec Kit en issues) et `claude-mem:oh-my-issues` (regroupe
rétroactivement un backlog déjà volumineux par cause racine).

## Objectif

Une skill invocable en commande slash (`/product-owner`) qui, à chaque appel,
balaie tout le backlog ouvert, le raffine, le structure en epics, pose une
priorité, et documente/applique le workflow git des epics multi-issues —
selon les pratiques agile standard (Definition of Ready, 1 tâche = 1 issue,
board Kanban), en dry-run validé par lot avant toute écriture GitHub.

## Mécanisme d'invocation

**Skill** (`.claude/skills/product-owner/SKILL.md`), invoquée via
`/product-owner`, sur le modèle des skills `speckit-*` déjà en place dans le
dépôt.

- Pas une **commande** simple (`.claude/commands/*.md`) : une commande est un
  prompt statique, sans emplacement naturel pour embarquer la Definition of
  Ready, le modèle epic/priorité/milestone et la spec du workflow git comme
  fichiers de référence rechargeables.
- Pas un **agent** (`.claude/agents/*.md`) : dans ce dépôt les agents sont
  réservés à des rôles délégués, en lecture seule, lancés à un point précis
  d'un workflow existant (`ui-ux-review`). Le PO est une procédure primaire
  invoquée directement par l'utilisateur, avec un gate d'approbation en
  plein milieu (dry-run → validation par lot) — mal adapté au modèle
  fire-and-forget d'un subagent.
- La skill peut dispatcher des agents `Explore`/`general-purpose` pour
  l'investigation approfondie d'une issue qui demande de lire le code
  (comme `claude-mem:oh-my-issues`), sans passer par l'outil `Workflow`
  (réservé à un opt-in explicite de l'utilisateur).

## Definition of Ready

Une issue est raffinée (passe `Backlog` → `Ready` sur le board) quand elle a :

- **Titre** `type(scope): description` en anglais (Conventional Commits,
  jeton machine — Principe I).
- **Corps en français**, structuré `## Constat de départ` / `## Demande`
  (critères d'acceptation testables) / `## Hors périmètre` — patron observé
  sur les issues #701-#712.
- **Une seule tâche.** Si le corps décrit plusieurs livrables indépendants,
  la skill **scinde** en issues enfants plutôt que de raffiner en l'état.
- **Labels** : au moins un label de domaine (`backend`/`frontend`/
  `scraper`/`auth`/`ops`/…) + un label de nature (`bug`/`enhancement`/…).
- **Priorité** posée sur le champ `Priority` du board — absente = pas prête.
- **Rattachement** explicite : epic (label `epic`, lien sub-issue natif) ou
  autonomie assumée.

Une issue qui ne peut pas être raffinée faute d'information reste en
`Backlog`, avec un commentaire de la skill listant ce qui manque — jamais
poussée en `Ready` par défaut.

## Epics

- **Création** : proposée quand la skill regroupe ≥2 issues (existantes ou
  issues d'un découpage 1-tâche-1-issue) autour d'un même objectif
  fonctionnel. En priorité, rattachement à une epic `label:epic` déjà
  existante avant d'en proposer une nouvelle.
- **Issue-epic** : label `epic`, titre `epic(scope): objectif`, corps =
  objectif + la spec du workflow git (section suivante) recopiée par
  référence.
- **Liaison native** : `gh` v2.45 n'expose pas la relation sub-issue côté
  CLI (`gh issue edit`/`gh issue develop` n'ont pas ces flags) — la skill
  passe par `gh api graphql` (mutation `addSubIssue`). Le champ
  `Sub-issues progress` du board reflète alors la progression
  automatiquement, sans checklist markdown à maintenir.
- **Statut dérivé**, jamais saisi à la main : `Backlog` tant qu'aucune
  sous-issue n'est `Ready`, `In progress` dès qu'une l'est, `Done` quand
  toutes les sous-issues sont fermées **et** la PR parapluie mergée —
  recalculé à chaque invocation.
- **Fermeture** : jamais automatique en dry-run — proposée dans le plan,
  validée comme le reste du lot.

## Priorité et Milestone

**Priorité** — le champ `Priority` du board est en réalité le miroir d'un
*Issue Field* au niveau de l'organisation (`Triathlon-Club-Nantais`), pas
un champ propre au projet (`isIssueField: true`, confirmé le 28/08/2026 par
introspection GraphQL — corrige une hypothèse initiale de cette spec, qui
le pensait vide et à configurer). Il a déjà 4 valeurs côté organisation
(Urgent/High/Medium/Low) — rien à créer, et surtout rien à recréer via
`updateProjectV2Field` (refuse explicitement les champs dérivés d'issues)
ni à renommer via `updateIssueField` (toucherait un champ potentiellement
partagé avec d'autres repos/projets du club). La skill pose une valeur sur
une issue via `updateIssueFieldValue`, pas via `gh project item-edit`
(détail : `.claude/skills/product-owner/reference/graphql.md`). Critère
d'attribution, volontairement simple :

- **Urgent** : sécurité, perte/corruption de données, prod cassée.
- **High** : bloque d'autres tâches, ou demande répétée/impact large.
- **Medium** : amélioration normale sans urgence.
- **Low** : cosmétique, nice-to-have.

**Milestone** — jamais créé spontanément. La skill repère les issues
`Ready`/`Done` qui semblent former une release cohérente et le **signale**
dans le plan ("ces N issues ressemblent à v0.7.0, je crée le milestone ?"),
sans jamais l'appliquer sans validation explicite dédiée sur ce point.

## Workflow git des epics (branche d'intégration + PR parapluie)

Documenté dans un nouveau `docs/gestion-de-projet.md` (routage ajouté à
`AGENTS.md`), convention réutilisable indépendamment de la skill :

- **Branche d'intégration** : `epic/<n°>-<slug>`, créée depuis `main`.
- **Sous-issues** : worktree par issue comme d'habitude
  (`docs/dev-multi-worktree.md`), mais basé sur `epic/<n°>-<slug>` et non
  `main` ; leur PR cible cette branche, avec `Refs #<epic>` (pas `Closes` —
  l'epic ne se ferme qu'à la PR parapluie).
- **PR parapluie** : une fois toutes les sous-issues mergées dans la branche
  d'intégration, PR `epic/<n°>-<slug>` → `main` avec `Closes #<epic>`.
- **Nettoyage** : suppression de la branche d'intégration après merge.

La skill s'appuie sur ce doc comme source de vérité pour rédiger le corps
des issues-epics — elle ne duplique pas la convention, elle y renvoie.

## Flux dry-run → validation → application

- **Collecte** : `gh issue list --state open` (backlog complet) +
  `gh project item-list`/`field-list` pour les items et IDs de champs du
  board (mis en cache pour la session).
- **Analyse** : pour chaque issue ne satisfaisant pas la Definition of
  Ready, la skill propose titre/corps/labels/priorité/scission/rattachement
  epic — dispatch d'agents `Explore`/`general-purpose` pour les issues qui
  demandent de lire le code.
- **Clustering epics** : priorité aux epics existantes avant d'en proposer
  une nouvelle.
- **Plan présenté en chat**, groupé par epic puis « sans epic », chaque
  ligne = état actuel → changement proposé. Ajustable en langage naturel
  avant validation ("saute la #123", "fusionne plutôt avec l'epic X") —
  l'approbation porte sur le lot ajusté, pas ligne par ligne.
- **Application, dans l'ordre** : création des epics → scission des issues
  bundlées → édition titre/corps/labels/priorité → liaison sub-issue
  (GraphQL `addSubIssue`) → champs board (`gh project item-edit`) →
  passage `Ready` si Definition of Ready atteinte. Les milestones ne sont
  jamais appliqués sans confirmation dédiée.
- **Idempotence** : une issue déjà conforme est absente du prochain plan —
  pas de ré-écriture inutile. Le statut d'une epic est recalculé, jamais
  incrémenté.
- **Échec partiel** : si un appel `gh`/GraphQL échoue en cours de lot, la
  skill rapporte précisément ce qui est passé vs. échoué et s'arrête —
  pas de retry silencieux ; les items déjà appliqués restent valides, une
  ré-invocation reprend le reste.

## Vérification

Pas de code applicatif testable par pytest/vitest — la skill est un
artefact de prompt engineering. Vérification par invocation réelle en
dry-run sur le backlog ouvert du dépôt (25 issues au moment de l'écriture),
relecture manuelle du plan produit (exactitude du raffinement, cohérence du
regroupement en epics, priorité posée), puis application sur un sous-lot
réduit avant un premier passage complet.

## Hors périmètre

- Remplacement de `speckit-taskstoissues` ou de `claude-mem:oh-my-issues` —
  la skill PO gère le raffinement continu du backlog courant, pas la
  conversion d'un `tasks.md` Spec Kit ni la déduplication rétroactive par
  cause racine d'un backlog déjà volumineux.
- Création automatique de milestones (toujours une décision humaine).
- Un board GitHub Projects à créer — le board « Data TCN » (#1) existe déjà
  et est réutilisé tel quel ; son champ `Priority` avait déjà ses 4 valeurs
  au niveau organisation, aucune configuration n'a été nécessaire.
