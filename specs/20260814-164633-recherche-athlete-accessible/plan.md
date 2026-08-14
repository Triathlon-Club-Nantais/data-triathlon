# Implementation Plan: Recherche d'athlète toujours accessible et sélection explicite

**Branch**: `feat-ui-garder-la-recherche-dathl-te-accessible` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260814-164633-recherche-athlete-accessible/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

L'entrée "Rechercher un athlète" de la navigation ne doit plus jamais
disparaître, y compris quand un athlète est déjà retenu et que le rail est
replié ; la sélection retenue doit s'afficher en complément, pas en
remplacement. Approche technique : dans `AppNav.tsx`, remplacer le rendu
exclusif (tuile *ou* bouton recherche) par un rendu qui affiche toujours
l'entrée recherche et, en plus, la tuile si un athlète est retenu (D1). Un
`CustomEvent` DOM natif synchronise la sélection entre `AppNav` et un nouveau
bouton "Sélectionner/Relâcher" sur la page profil (D2), porté par un
sous-composant client minimal puisque la page reste un Server Component (D4).

## Technical Context

**Language/Version**: TypeScript strict (Next.js 16, App Router)

**Primary Dependencies**: React (client components), lucide-react (icônes),
`components/tcn` (Modal, Input, Avatar) — aucune nouvelle dépendance.

**Storage**: `localStorage["tcn-athlete"]`, forme `PickedAthlete` inchangée — pas de DB/API.

**Testing**: Vitest + React Testing Library (`frontend/**/*.test.tsx`), sans réseau réel (`apiClient` mocké).

**Target Platform**: Web — rail desktop (déplié/replié), barre + tiroir mobile.

**Project Type**: Application web (frontend seul concerné ; aucun endpoint backend touché).

**Performance Goals**: N/A — pas de changement de volumétrie ni d'appel réseau supplémentaire.

**Constraints**: Aucun changement de contrat API/CLI (Principe IV) ; forme et
clé du `localStorage` inchangées ; raccourci clavier existant préservé.

**Scale/Scope**: Un composant de navigation partagé par toute l'app + une page
profil ; ~3 fichiers modifiés, 1 fichier nouveau (sous-composant client).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Tous les libellés visibles (boutons, aria-label) restent en français ; les nouveaux identifiants (`clearAthlete`, `SelectAthleteButton`, `tcn-athlete-changed`) suivent la convention déjà en place dans `AthletePicker.tsx` (fonctions en anglais, domaine `athlete`/`nomComplet` déjà mêlé — fichier existant, pas de réécriture substantielle). |
| II | Architecture en couches (api → services → repositories → DB) | N/A | Feature 100 % front, aucun endpoint ni couche backend touché. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests Vitest/RTL étendus (`AppNav.test.tsx`, `athletes/[id]/page.test.tsx`), sans appel réseau réel — pattern déjà en place (mock `apiClient`, `localStorage` mocké). |
| IV | Contrats API et CLI stables | N/A | Aucun endpoint HTTP ni commande CLI modifiés. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre de lecture (`scope`, `federal_only`, `seasons`) concerné. |
| VI | Simplicité / YAGNI | ✅ | `CustomEvent` natif plutôt qu'un store/contexte global (D2) ; `clearAthlete` rejoint le module existant plutôt qu'un nouveau fichier (D3) ; aucune nouvelle dépendance. |

Aucune violation à consigner : la section « Complexity Tracking » reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260814-164633-recherche-athlete-accessible/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── athlete-selection.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/
├── components/
│   └── layout/
│       ├── AppNav.tsx              # modifié : rendu simultané recherche + tuile, abonnement à l'event de sync
│       ├── AppNav.test.tsx         # étendu : nouveaux cas état×format, event de sync
│       └── AthletePicker.tsx       # modifié : + clearAthlete(), émission de l'event de sync
├── app/
│   └── athletes/
│       └── [id]/
│           ├── page.tsx                  # modifié : monte SelectAthleteButton
│           ├── page.test.tsx             # étendu : présence/bascule du bouton
│           └── SelectAthleteButton.tsx   # nouveau : sous-composant client (sélectionner/relâcher)
```

**Structure Decision**: Application web existante, frontend seul (Next.js App
Router). Pas de nouveau dossier de premier niveau — la feature s'insère dans
`components/layout/` (navigation) et `app/athletes/[id]/` (page profil),
conformément à l'arborescence documentée dans `frontend/AGENTS.md`.

## Complexity Tracking

*(vide — aucune violation de la Constitution Check à justifier)*
