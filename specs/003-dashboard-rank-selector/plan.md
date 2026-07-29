# Implementation Plan: Sélecteur de type de rang sur les cartes de stats

**Branch**: `feat/104-dashboard-rank-selector` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-dashboard-rank-selector/spec.md`

## Summary

Feature 100 % frontend : ajouter un paramètre URL `?rank=scratch|category|gender|all` sur `/dashboard` et `/club`, matérialisé par un toggle 4-boutons calqué sur `DisciplineToggle`. Ce paramètre pilote la sémantique des compteurs `rankCounters` / `isPodium` / `isTopN` / `listPodiums` de `frontend/lib/utils/club-aggregate.ts` :

- `scratch` → compte sur `rank_overall` seul
- `category` → compte sur `rank_category` seul
- `gender` → double comptage F/H (chaque carte se dédouble en deux compteurs)
- `all` → `min(rank_overall, rank_category, rank_gender)` (comportement actuel, préserve l'emboîtement #77)

Le défaut en absence de paramètre est `scratch` (aligné cas d'usage AG). Aucun changement backend : les trois rangs et le genre athlète sont déjà exposés dans le DTO `Participation`.

## Technical Context

**Language/Version**: TypeScript strict, Next.js 16 (App Router).

**Primary Dependencies**: React 19 (server components + client toggle), Vitest + RTL pour tests, Tailwind + shadcn/ui pour rendu.

**Storage**: Aucun — feature calculatoire côté client.

**Testing**: Vitest (unit + composant). Suite frontend actuelle : 199/199 verts sur main.

**Target Platform**: Web (SSR + hydrat). Pages ciblées : `/dashboard`, `/club`.

**Project Type**: Web application (frontend Next.js consommant `/api/v1`).

**Performance Goals**: Rendu en un seul cycle (pas de re-fetch réseau au changement de rank — le toggle bascule uniquement l'URL + re-render RSC). Les participations sont déjà chargées par la page. Cible : changement de rank imperceptible (< 100 ms côté client).

**Constraints**: Pas de nouveau endpoint backend. Pas de nouveau champ DB. Le paramètre URL doit se composer avec `?scope=`, `?seasons=`, `?sports=` déjà en place, sans les remplacer.

**Scale/Scope**: 3 fichiers à modifier (`club-aggregate.ts`, `dashboard/page.tsx`, `club/ClubDashboard.tsx`), 1 fichier à créer (`RankTypeToggle.tsx`), 1 fichier utilitaire optionnel (`lib/rank.ts` — enum + parse). Volume test : ~20 nouveaux cas Vitest (couvrant les 4 modes × 3 fonctions × edge cases).

## Constitution Check

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.0.0).

| # | Principe | Statut | Justification |
|---|----------|--------|----------------|
| I | Langue métier français / technique English | ✅ conforme | UI et libellés en français (« Scratch », « Catégorie », « Genre », « Tous »). Identifiants TS et noms de tests en anglais (`RankType`, `rankCounters`, `describe("rankCounters with rank=category")`). Aucun message utilisateur nouveau côté backend. |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Feature purement frontend, aucune couche backend touchée. Le principe vise le backend. |
| III | TDD sans réseau (non-négociable) | ✅ conforme | Test rouge écrit avant chaque changement de fonction utilitaire (`bestRank`, `rankCounters`, `isPodium`, `isTopN`, `listPodiums`). Aucune requête réseau réelle. Vitest utilise déjà des mocks de `apiServer`. |
| IV | Contrats API et CLI stables | ✅ conforme | Aucune modification d'API. Le paramètre `?rank=` est purement frontend, il n'atteint pas l'endpoint. Ajout côté front d'un nouveau paramètre URL — extension additive, pas de rupture. |
| V | Neutralité par défaut des paramètres transverses | ⚠️ justifié | Le principe vise les paramètres backend (défaut neutre côté API). Le défaut choisi ici (`scratch`) n'est pas neutre : il filtre sur un seul des trois rangs. Justification : (a) c'est un paramètre **front** qui ne remonte pas à l'API ; (b) l'ancien défaut (`all` implicite) empêchait le cas d'usage AG cité dans #104 ; (c) l'option « Tous » est offerte explicitement en trappe. Voir Complexity Tracking. |
| VI | Simplicité / YAGNI | ✅ conforme | Une seule signature ajoutée aux fonctions utilitaires (paramètre `rankType?`). Pas de nouvelle abstraction (pas de « strategy pattern », pas de map<RankType, comparator>). Un `switch` local dans `bestRank`. Un nouveau composant `RankTypeToggle` qui reproduit exactement le pattern `DisciplineToggle`. Aucune refacto préventive de `listPodiums`. |

## Project Structure

### Documentation (this feature)

```text
specs/003-dashboard-rank-selector/
├── plan.md                     # Ce fichier
├── research.md                 # Phase 0 : décisions techniques
├── data-model.md               # Phase 1 : types TS et signatures
├── quickstart.md               # Phase 1 : parcours utilisateur observable
├── contracts/
│   └── rank-url-param.md       # Contrat URL (?rank=) et rétro-compat
├── checklists/
│   └── requirements.md         # Écrit par /speckit-specify
└── tasks.md                    # Phase 2 : écrit par /speckit-tasks
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── dashboard/
│   │   ├── page.tsx                     # MODIFIED — lecture de ?rank, wiring dans les cartes
│   │   └── page.test.tsx                # NEW — tests intégration (4 modes)
│   └── club/
│       ├── page.tsx                     # MODIFIED — lecture de ?rank, passage à ClubDashboard
│       └── page.test.tsx                # optionnel si couverture ClubDashboard suffit
├── components/
│   ├── club/
│   │   ├── ClubDashboard.tsx            # MODIFIED — reçoit rankType, propage à podiums/summary/roster
│   │   └── ClubDashboard.test.tsx       # NEW — tests des 4 modes sur la page club
│   └── layout/
│       ├── RankTypeToggle.tsx           # NEW — composant client toggle 4 boutons
│       └── RankTypeToggle.test.tsx      # NEW — tests du toggle (URL, transition, actif)
└── lib/
    ├── rank.ts                          # NEW — enum RankType, RANK_PARAM, parse strict
    ├── rank.test.ts                     # NEW — parse, défaut, valeur inconnue
    └── utils/
        ├── club-aggregate.ts            # MODIFIED — nouvelle signature `rankType?: RankType`
        └── club-aggregate.test.ts       # MODIFIED — nouveaux cas (4 modes × chaque fonction)
```

**Structure Decision**: pas de nouveau dossier de plus haut niveau. Les 3 fichiers utilitaires (`lib/rank.ts`) et les 2 composants (`RankTypeToggle`) suivent l'organisation existante (`lib/scope.ts` sert de patron pour `lib/rank.ts` ; `DisciplineToggle.tsx` sert de patron pour `RankTypeToggle.tsx`).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Principe V — défaut `scratch` non neutre | Le cas d'usage produit central (comparer avec les stats AG) exige que le défaut soit le scratch. Un défaut neutre (`all` maintenu) revient à ne rien changer et laisse l'issue non résolue. | Défaut `all` (préservation historique) rejeté : reconduit exactement le problème signalé dans #104. Défaut « inféré du contexte » rejeté : ajoute un mode implicite, viole aussi le principe VI (YAGNI). Le principe V vise l'API, pas les paramètres front : cette exception est jugée acceptable et documentée dans les Assumptions de la spec (rétro-compat assumée via `?rank=all`). |
