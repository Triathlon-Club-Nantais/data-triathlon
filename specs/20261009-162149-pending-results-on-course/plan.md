# Implementation Plan: Résultats en attente de validation visibles sur la page de l'épreuve

**Branch**: `feat/1273-pending-results-on-course` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20261009-162149-pending-results-on-course/spec.md`

## Summary

Une épreuve créée par une saisie manuelle paraît vide tant que son résultat n'est pas
validé (#270). On ajoute une **lecture d'affichage** distincte de tout comptage :

- `GET /courses/{id}` gagne un champ additif `pending_participations` : les résultats
  en attente non refusés de l'épreuve, aux mêmes filtres que le classement (`q`,
  `scope`, `club`, `category`), triés par nom, jamais paginés ni comptés dans `total`.
- `GET /courses/events` gagne `pending_count` par épreuve et liste aussi les épreuves
  qui n'ont que des résultats en attente ; `total`, `tcn_count` et
  `total_participations` restent des comptes de résultats validés.
- Le front rend les lignes en attente à la fin du classement (dernière page), avec
  `PendingBadge`, sans rang ni écart ; les listes d'épreuves disent « N résultat(s) en
  attente » quand le compte validé vaut zéro.

`validated_clause` reste le filtre de tout comptage. La nouvelle clause
`awaiting_validation_clause` (en attente **et** non refusé) ne sert qu'à lister.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 sync, Pydantic v2 ; React, Tailwind, `components/tcn`

**Storage**: PostgreSQL (prod) / SQLite (dev, tests). **Aucune migration** : les colonnes `is_pending_validation` et `is_rejected` existent.

**Testing**: pytest (`-m "not integration"`), Vitest + RTL

**Target Platform**: API Render, front Vercel

**Project Type**: web (backend + frontend)

**Performance Goals**: pas de régression du chemin rapide de `/courses/events` (#623) : la condition ajoutée est un `EXISTS` corrélé sur `participations.course_id` (indexé), évalué seulement quand `participation_count = 0`.

**Constraints**: contrat `/api/v1` additif (Principe IV) ; aucun compte existant ne change de valeur.

**Scale/Scope**: 17 résultats en attente en production, sur 16 épreuves ; ~1 200 épreuves.

## Constitution Check

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants nouveaux en anglais (`pending_participations`, `pending_count`, `awaiting_validation_clause`, `list_pending_for_course`), UI et docstrings métier en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Requêtes dans `participation_repository` ; la route appelle le repository comme le fait déjà `get_course` ; `stats_service._event_row` mappe le nouveau champ. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests repository et API écrits d'abord, dont un test par compte de FR-006 ; tests Vitest des rendus avant le code. Aucun réseau. |
| IV | Contrats API et CLI stables | ✅ | Deux champs ajoutés, à défaut neutre (`[]`, `0`). `participations`, `total`, `tcn_count`, `total_participations` gardent leur sens. Le seul changement observable : `/courses/events` liste en plus des épreuves sans résultat validé (`total = 0`), une ligne additionnelle dont aucun champ existant ne change de sens. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse ajouté. L'exclusion des comptes reste sans paramètre (invariant #270). |
| VI | Simplicité / YAGNI | ✅ | Pas de colonne dénormalisée `pending_count` (17 lignes en prod, un `EXISTS`/`COUNT` corrélé suffit), pas de pagination des lignes en attente, `PendingBadge` réutilisé. Les filtres inline existants (`list_pending`…) ne sont pas refactorés. |

## Project Structure

### Documentation (this feature)

```text
specs/20261009-162149-pending-results-on-course/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/core/validation.py                     # + awaiting_validation_clause
├── app/repositories/participation_repository.py  # + list_pending_for_course ; events_page inclut les épreuves en attente seule
├── app/services/stats_service.py              # _event_row : pending_count
├── app/schemas/course.py                      # EventOut.pending_count
├── app/schemas/participation.py               # CourseParticipationPage.pending_participations
├── app/api/v1/courses.py                      # get_course renvoie pending_participations
├── app/api/AGENTS.md                          # section #270 mise à jour
└── tests/
    ├── test_repositories/test_pending_on_course.py
    └── test_api/test_course_pending_rows.py

frontend/
├── lib/types.ts                               # EventOut.pending_count, CourseParticipationPage.pending_participations
├── lib/utils/event.ts                         # pendingResultsLabel
├── lib/utils/eventGroups.ts                   # pendingCount par groupe
├── components/results/RaceFinishers.tsx       # lignes en attente en fin de dernière page
├── components/results/EventList.tsx           # libellé « N résultat(s) en attente »
├── components/dashboard/RecentCourses.tsx     # idem
├── app/(public_restricted)/ajouter/page.tsx   # idem
└── app/(public_restricted)/courses/[id]/page.tsx  # passe les lignes en attente
```

**Structure Decision**: application web existante, backend + frontend ; aucun nouveau module.

## Complexity Tracking

Aucune violation à justifier.
