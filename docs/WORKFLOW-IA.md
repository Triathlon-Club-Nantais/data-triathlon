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
| **Speckit** | Produit les artefacts documentaires d'une feature : `spec.md`, `plan.md`, `tasks.md` dans `specs/NNN-feature/`. Gère aussi la branche git et les commits-gate entre chaque étape. |
| **Superpowers** | Applique la discipline d'artisanat pendant qu'on code : TDD, debug systématique, sous-agents parallèles, revue de code, vérification finale. |

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

## Tableau anti-collision

Les paires suivantes couvrent la **même étape** — ne jamais en lancer deux en
parallèle pour la même tâche :

| Étape | Skill speckit | Skill superpowers | Règle |
|-------|---------------|-------------------|-------|
| Cadrage du besoin | `/speckit-specify` + `/speckit-clarify` | `brainstorming` | **Speckit est canonique.** `brainstorming` uniquement en amont si l'idée est encore floue ; injecter le résultat dans `/speckit-specify`. |
| Planification | `/speckit-plan` | `writing-plans` | **Speckit est canonique.** Un seul `plan.md` dans `specs/`. Ne pas créer un plan superpowers concurrent. |
| Exécution | `/speckit-implement` | `subagent-driven-development` + `dispatching-parallel-agents` | **Superpowers par défaut** (voir §Exécution). Ne pas lancer les deux. |
| Branche / commits | Hooks `extensions.yml` (auto) | `using-git-worktrees` | Speckit crée et gère la branche feature. Ne pas ouvrir un worktree concurrent sur la même feature. |
| Fin de branche | — | `finishing-a-development-branch` | Superpowers pour le merge / PR. |

---

## Workflow feature complète (vraie feature)

```
[1] Idée floue ?
    └── brainstorming (superpowers) pour clarifier, puis continuer.

[2] /speckit-specify  ← crée la branche git + spec.md
    └── hook auto : git feature branch créée

[3] /speckit-clarify  ← affine spec.md avec des questions ciblées

[4] GATE — relire spec.md, approuver ou rejeter

[5] /speckit-plan     ← crée plan.md (commits-gate avant)

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
les principes du projet (stack, TDD, langue française, conventions) et est
injectée dans chaque commande speckit. Pour ce projet, elle est encore **vide
(template par défaut)**.

Pour la remplir, lancer une fois :

```
/speckit-constitution
```

Les principes à y reporter sont déjà documentés dans `AGENTS.md` :
conventions de code, TDD sans réseau (respx), Conventional Commits,
UI et commentaires en français, etc.

---

## Rappels projet (cohérence avec `AGENTS.md`)

- **Tests unitaires** : sans réseau, httpx mocké avec respx. Le réseau réel est
  derrière le marker `integration`. Lancer `pytest -m "not integration"` pour les
  tests rapides.
- **Commits** : Conventional Commits (`feat:`, `fix:`, `refactor:`…).
- **Langue** : UI, messages d'erreur et commentaires en **français** (avec accents).
- **Temps** : toujours des strings (`"01:23:45"`), normalisés via
  `backend/scrapers/utils.py`.

---

*Pour les détails d'architecture et les conventions de scraping, voir `AGENTS.md`.*
