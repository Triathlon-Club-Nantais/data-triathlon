# Workflow IA — Superpowers + Speckit

Ce document s'adresse aux collaborateurs qui utilisent **Claude Code** (ou tout
agent IA compatible) sur ce projet. Deux outils d'assistance sont préconfigurés
et leurs périmètres se chevauchent : sans règle claire, un agent peut lancer
les deux pour la même tâche, ce qui duplique le travail et crée des artefacts
concurrents. Ce document fixe **qui fait quoi et quand**.

---

## Les deux outils en une phrase

| Outil | Rôle |
|-------|------|
| **Speckit** | Produit les artefacts documentaires d'une feature : `spec.md`, `plan.md`, `tasks.md` dans `specs/NNN-feature/`. La branche git et les commits-gate, en revanche, restent **manuels** — voir le tableau anti-collision. |
| **Superpowers** | Applique la discipline d'artisanat pendant qu'on code : TDD, debug systématique, sous-agents parallèles, revue de code, vérification finale. Certains de ses skills **écrivent aussi des artefacts** — voir §Où atterrissent les artefacts. |

> **Règle d'or** : Speckit cadre et planifie (jusqu'à `tasks.md`). Superpowers
> exécute et garantit la qualité.

---

## Arbre de décision — par où commencer ?

```
Ma tâche, c'est quoi ?
│
├── Un bugfix, une typo, un ajustement de 1-2 fichiers, un petit refacto
│   └── → Workflow VIBE (superpowers seul) — voir §Workflow vibe
│
└── Une vraie feature (nouveau scraper, nouvel écran, changement de schéma,
    fonctionnalité avec plusieurs composants…)
    └── → Workflow FEATURE COMPLÈTE (speckit + superpowers) — voir §Workflow feature
```

---

## Où atterrissent les artefacts

Speckit n'est pas le seul à écrire des fichiers : `brainstorming` et
`writing-plans` en produisent aussi, et **au même endroit d'une fois sur l'autre**.
Savoir qui écrit quoi et où est ce qui distingue un artefact légitime d'un doublon.

| Emplacement | Écrit par | Statut |
|---|---|---|
| `specs/NNN-feature/` — `spec.md`, `plan.md`, `tasks.md`, plus `research.md`, `data-model.md`, `quickstart.md` | Speckit | **Canonique** sur le cadrage et la planification. Un seul de chaque, par feature. |
| `docs/superpowers/specs/YYYY-MM-DD-<sujet>-design.md` | `brainstorming`, qui l'écrit **et le commite** | Design Superpowers. **Interdit sur une feature en cycle Speckit** : ce serait le concurrent de `spec.md`. |
| `docs/superpowers/specs/YYYY-MM-DD-<sujet>-{sondage,audit,report}.md` | l'agent, à la main | **Rapport de terrain** : ce qui a été mesuré sur le site ou le code réels. Légitime dans les deux workflows, et **prime** sur le design, la spec et le plan. Toute divergence se tranche en re-sondant, pas en raisonnant. |
| `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` | `writing-plans` | Plan Superpowers. **Interdit sur une feature en cycle Speckit** : concurrent de `plan.md`. |
| `.superpowers/sdd/<nom-du-plan>/` | `subagent-driven-development` | Ledger d'exécution (`progress.md`, briefs, rapports). Jetable, jamais commité. |

Les deux chemins `docs/superpowers/` sont des **défauts amont du plugin**
(`brainstorming/SKILL.md`, section « After the Design » ; `writing-plans/SKILL.md`,
« Save plans to »), pas une convention de ce dépôt : le dossier porte le nom de
**l'outil**, pas celui du contenu. C'est ce qui fait lire un rapport de sondage
comme « une spec Superpowers » concurrente d'un `spec.md` Speckit. Les deux skills
prévoient la surcharge — « User preferences for spec/plan location override this
default » —, et ce projet l'exerce : voir la règle d'emplacement dans `AGENTS.md`.

Les fichiers déjà présents dans `docs/superpowers/` **restent où ils sont**. Ils
mêlent deux natures : des designs de features livrées (valeur historique) et des
rapports de terrain **encore normatifs**, cités nominativement par `AGENTS.md` là
où ils s'appliquent — le sondage RaceResult (« elle prime sur le design et sur le
plan »), le sondage T2Area, l'audit d'architecture backend référencé par
`backend/README.md`.

### La troisième catégorie : le sondage

Un sondage n'est ni une spec ni un plan : il consigne des **observations**, pas des
intentions. Il a donc sa place dans les deux workflows, et il n'entre en collision
avec rien.

Le cas déjà en place est `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`
(15 épreuves, 3 façades) : `AGENTS.md` le donne pour primant « sur le design et sur
le plan », et deux tests de non-régression protègent ses conclusions. Il n'a pas de
contrepartie Speckit — il précède l'adoption du cycle.

La forme à reproduire, sondage **et** Speckit sur la même feature, est celle de
runnerbreizh : sondage du HTML réel écrit **avant** tout cadrage, puis déclaré
« source de vérité technique » par `specs/002-runnerbreizh-scraper/spec.md`,
`plan.md` et `tasks.md`, le `research.md` consignant les **décisions** que les
mesures ont permis de prendre sans les recopier. Deux fichiers, deux rôles, zéro
redondance.

---

## Tableau anti-collision

Les paires suivantes couvrent la **même étape** — ne jamais en lancer deux en
parallèle pour la même tâche :

| Étape | Skill speckit | Skill superpowers | Règle |
|-------|---------------|-------------------|-------|
| Cadrage du besoin | `/speckit-specify` + `/speckit-clarify` | `brainstorming` | **Speckit est canonique.** Ne pas lancer `brainstorming` sur une feature déjà en cycle Speckit — voir ci-dessous, la raison n'est pas une question de discipline. |
| Planification | `/speckit-plan` | `writing-plans` | **Speckit est canonique.** Un seul `plan.md` dans `specs/`. Ne pas créer un plan superpowers concurrent. |
| Exécution | `/speckit-implement` | `subagent-driven-development` + `dispatching-parallel-agents` | **Superpowers par défaut** (voir §Exécution). Ne pas lancer les deux. |
| Branche / commits | — (les hooks `extensions.yml` ne s'exécutent jamais pour Claude) | `using-git-worktrees` | **Manuel.** Créer la branche soi-même. Détail de la cause : `AGENTS.md`, §Workflow IA. Ne pas ouvrir un worktree concurrent sur la même feature. |
| Fin de branche | — | `finishing-a-development-branch` | Superpowers pour le merge / PR. |

### Pourquoi `brainstorming` ne se « combine » pas avec Speckit

La consigne longtemps affichée ici — « `brainstorming` en amont, puis injecter le
résultat dans `/speckit-specify` » — **n'est pas exécutable**. Le skill ne rend pas
un résultat à réutiliser : il écrit **et commite** son
`docs/superpowers/specs/…-design.md`, puis enchaîne sur `writing-plans`, seule
transition qu'il s'autorise (« The terminal state is invoking writing-plans »,
« Do NOT invoke any other skill »). Lancé sur une feature Speckit, il produit donc
mécaniquement **un design et un plan concurrents** de `spec.md` et `plan.md`.

Deux voies propres, à choisir **avant** de commencer :

1. **Sondage puis Speckit** — la voie du cycle feature complète. On mesure le
   terrain, on écrit le sondage, et `/speckit-specify` le déclare source de vérité.
   Pas de `brainstorming`.
2. **`brainstorming` assumé, sans Speckit** — le workflow vibe. Son `-design.md`
   *remplace* `/speckit-specify` ; la chaîne `brainstorming` → `writing-plans` va
   jusqu'au bout et il n'y a pas de dossier `specs/`.

---

## Workflow feature complète (vraie feature)

```
[0] Créer la branche à la main (aucun hook ne le fera)

[1] Terrain inconnu ? (nouveau moteur de chrono, HTML jamais lu, API non documentée)
    └── SONDER : lire le site / le code réels, écrire
        docs/superpowers/specs/YYYY-MM-DD-<sujet>-sondage.md
        → ce sondage devient la source de vérité de la spec.
        Pas de brainstorming ici — voir §Pourquoi brainstorming ne se combine pas.

[2] /speckit-specify  ← crée spec.md
    └── y déclarer le sondage « source de vérité technique », s'il y en a un

[3] /speckit-clarify  ← affine spec.md avec des questions ciblées

[4] GATE — relire spec.md, approuver ou rejeter

[5] /speckit-plan     ← crée plan.md, research.md, data-model.md, quickstart.md
    └── research.md consigne les DÉCISIONS, il ne recopie pas les mesures
        du sondage

[6] GATE — relire plan.md, approuver ou rejeter

[7] /speckit-tasks    ← génère tasks.md (tâches [P] = parallélisables)

[8] /speckit-analyze  ← vérifie cohérence spec / plan / tasks

[9] HANDOFF vers superpowers — exécution
    ├── Par défaut : subagent-driven-development
    │   (les tâches [P] sont distribuées sur des sous-agents en parallèle)
    ├── Repli linéaire : /speckit-implement
    │   (convenable pour les features simples ; il coche tasks.md et gère les gates)
    └── Dans chaque tâche : test-driven-development + systematic-debugging

[10] requesting-code-review (superpowers)

[11] verification-before-completion (superpowers)

[12] finishing-a-development-branch (superpowers) → PR / merge
```

> **Note sous-agents** : les tâches marquées `[P]` dans `tasks.md` sont pensées
> pour être exécutées en parallèle. `dispatching-parallel-agents` en tire parti.
> C'est l'agent principal qui coche les cases dans `tasks.md` au fil de
> l'avancement.

---

## Workflow vibe (bugfix / petit changement)

Pas de cycle speckit, pas de dossier `specs/`. Superpowers seul :

```
[1] (facultatif) brainstorming si l'approche n'est pas évidente

[2] systematic-debugging  ← si c'est un bug
    OU
    test-driven-development  ← si c'est un ajout de comportement

[3] verification-before-completion

[4] finishing-a-development-branch  ← si ça mérite une PR
```

---

## La constitution Speckit (`.specify/memory/constitution.md`)

La constitution est le **document de référence absolu** de Speckit : elle cadre
les principes du projet (stack, TDD, langue, conventions) et est injectée dans
chaque commande speckit. Pour ce projet, elle est **ratifiée en v1.0.0** — ne pas
relancer `/speckit-constitution` pour « la remplir ».

Attention à sa portée réelle : la constitution n'est chargée que par les commandes
`/speckit-*`, alors qu'`AGENTS.md` l'est **à chaque session** via `CLAUDE.md`. En
cas de divergence entre les deux, c'est la règle d'`AGENTS.md` qui sera lue le plus
souvent — donc c'est là que les garde-fous doivent vivre, la constitution ne suffit
pas à les faire respecter.

---

## Rappels projet (cohérence avec `AGENTS.md`)

- **Tests unitaires** : sans réseau, httpx mocké avec respx. Le réseau réel est
  derrière le marker `integration`. Lancer `pytest -m "not integration"` pour les
  tests rapides.
- **Commits** : Conventional Commits (`feat:`, `fix:`, `refactor:`…).
- **Langue** (Principe I de la constitution) : **français** pour ce qui est visible
  utilisateur ou métier — UI, messages d'erreur affichés, docs produit, commentaires
  de règle métier ; **anglais** pour la couche technique invisible — identifiants,
  tests, docstrings techniques, logs, préfixes Conventional Commits. On ne réécrit
  pas l'existant : la règle vaut pour les nouveaux ajouts.
- **Temps** : toujours des strings (`"01:23:45"`), normalisés via
  `backend/scrapers/utils.py`.

---

*Pour les détails d'architecture et les conventions de scraping, voir `AGENTS.md`.*
