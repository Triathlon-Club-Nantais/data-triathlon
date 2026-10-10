# Implementation Plan: Groupes d'entraînement, inscription d'office et séances récurrentes

**Branch**: `feat/1291-training-groups` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20261010-122023-groupes-seances-recurrentes/spec.md` (#1291)

## Summary

Ajouter des groupes de profils, viser des groupes depuis une séance pour y inscrire leurs membres d'office (avec resynchronisation des séances à venir non pointées), générer des séances depuis une récurrence hebdomadaire, et afficher la catégorie FFTri calculée. Backend : cinq tables génériques et deux colonnes, une règle de synchronisation unique dans un service. Frontend : un écran « Groupes », le choix des groupes dans la fenêtre de séance et l'appel du jour, un formulaire de récurrence au calendrier, la catégorie dans la liste, la fiche et l'appel.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 ; React 19, `@base-ui/react`, TanStack Query (patrons des écrans jeunes existants)

**Storage**: PostgreSQL (prod, preview), SQLite (dev, tests) ; une migration Alembic

**Testing**: pytest sans réseau ; Vitest + RTL

**Target Platform**: web, usage principal sur téléphone

**Project Type**: web-service + web app

**Performance Goals**: écrans instantanés à l'échelle du club (dizaines de jeunes, une centaine de séances par saison) ; synchronisation synchrone

**Constraints**: aucune présence déjà saisie ne doit changer (SC-003) ; contrats additifs (Principe IV)

**Scale/Scope**: ~50 profils, ~10 groupes, ≤ 53 séances par récurrence

## Constitution Check

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | identifiants et tables en anglais, copie UI et messages `DomainError` en français |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | requêtes dans `training_group_repository`, `training_recurrence_repository`, `training_session_repository` ; règle R3 dans `training_session_service` |
| III | TDD sans réseau (non-négociable) | ✅ | chaque tâche d'implémentation précédée de son test (tasks.md) ; aucune dépendance réseau |
| IV | Contrats API et CLI stables | ✅ | ajouts de routes et de champs seulement (contracts/api.md) |
| V | Neutralité par défaut des paramètres transverses | ✅ | `group_ids` absent = comportement d'aujourd'hui (séance vide, inscriptions manuelles) |
| VI | Simplicité / YAGNI | ✅ | récurrence hebdomadaire seule, pas de moteur RRULE, pas de tâche de fond, origine d'inscription réduite à un booléen (R2) |

## Project Structure

### Documentation (this feature)

```text
specs/20261010-122023-groupes-seances-recurrentes/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/<rev>_training_groups_and_recurrences.py
├── app/models/training_group.py              # TrainingGroup, TrainingGroupMember
├── app/models/training_recurrence.py         # TrainingRecurrence + tables d'association
├── app/models/training_session.py            # + recurrence_id, detached, groups
├── app/models/training_participant.py        # + added_manually
├── app/repositories/training_group_repository.py
├── app/repositories/training_recurrence_repository.py
├── app/repositories/training_session_repository.py   # requêtes de synchronisation
├── app/services/fftri_category.py            # catégorie d'âge (R1)
├── app/services/training_group_service.py
├── app/services/training_recurrence_service.py
├── app/services/training_session_service.py  # sync_group_enrolment (R3)
├── app/services/profile_service.py           # category, groups dans les vues ; purge (R6)
├── app/api/v1/admin_training_groups.py
├── app/api/v1/admin_training_recurrences.py
├── app/api/v1/admin_training_sessions.py     # group_ids
└── tests/                                    # un fichier de test par module ci-dessus

frontend/
├── app/admin/jeunes/groupes/page.tsx
├── components/admin/jeunes/GroupesList.tsx, GroupeDetail.tsx, GroupesPicker.tsx, RecurrenceForm.tsx
├── components/admin/jeunes/EntrainementForm.tsx, EntrainementDetailDialog.tsx, CalendrierEntrainements.tsx, AppelPresence.tsx
├── components/admin/ProfilesList.tsx, ProfileDetail.tsx
├── components/layout/nav.config.ts           # entrée « Groupes »
├── lib/api/client.ts, lib/types.ts
└── components/guide/…                        # section « jeunes » du guide admin
```

**Structure Decision**: on étend les modules jeunes existants plutôt que d'en créer un sous-paquet : mêmes couches, mêmes gardes, mêmes écrans.

## Ordonnancement

Implémentation **après fusion de #1290** (R7), branche rebasée sur `main`. Ordre : modèle et migration, catégorie, groupes, synchronisation, séances étendues, récurrences, puis front dans le même ordre.

## Complexity Tracking

Aucune violation.
