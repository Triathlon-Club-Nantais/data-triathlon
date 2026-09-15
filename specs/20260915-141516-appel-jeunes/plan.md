# Implementation Plan: Appel de présence jeunes

**Branch**: `869-appel-jeunes` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260915-141516-appel-jeunes/spec.md`

## Summary

Poser l'appel de présence par-dessus le calendrier (#868) et les profils
(#867) déjà en place sur `epic/863-jeunes` : un statut présent/absent
persistant par inscription (`EntrainementParticipant.present`), une note de
séance persistante (`Entrainement.note`), un écran mobile-first qui pointe
l'appel de début, recompte en pur frontend l'appel de fin sans rien écrire, et
réutilise tel quel le journal de bord (#867) pour les notes sur un jeune.
Unifie au passage les deux entrées de navigation « Jeunes » existantes en une
seule section à trois sous-liens (profils, calendrier, appel).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ; côté front, Tailwind, shadcn/ui, TanStack Query (`lib/queries/admin.ts`), `lib/api/client.ts`

**Storage**: PostgreSQL (Supabase) en production, SQLite en dev — via Alembic ; deux colonnes ajoutées à des tables existantes (`entrainement_participants.present`, `entrainements_jeunes.note`), aucune nouvelle table

**Testing**: pytest (backend, sans réseau), Vitest + RTL (frontend)

**Target Platform**: API web `/api/v1` (Render) consommée par le front Vercel

**Project Type**: web (backend + frontend, patron déjà en place par #867/#868)

**Performance Goals**: aucun objectif spécifique — même volume que #868
(quelques dizaines de séances, quelques dizaines de jeunes par saison).

**Constraints**: écran mobile-first (375 px sans défilement horizontal),
garde RBAC route par route (jamais un `dependencies=` de router), aucune
écriture réseau pour l'état de l'appel de fin (FR-007).

**Scale/Scope**: un club (TCN), une poignée d'encadrants, quelques dizaines de
jeunes et de séances par saison — identique à #867/#868.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants Python/TS en anglais (`present`, `note`), `appel` restant le terme métier français dans tous les libellés visibles et les noms de composants (cf. research.md D6) ; libellés UI, messages d'erreur et docstrings de règle métier en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Nouvelle fonction `set_presence` ajoutée à `admin_jeunes_entrainements.py` → `services/jeunes/entrainements.py` → `entrainement_repository.py` → modèles existants. L'appel de fin ne touche à aucune couche serveur (aucune requête, aucune route). |
| III | TDD sans réseau (non-négociable) | ✅ | `tasks.md` pose un test rouge avant chaque capacité (repository, service, route, composant frontend) ; aucun appel réseau réel dans ce lot. |
| IV | Contrats API et CLI stables | ✅ | Extension additive de trois contrats existants (`ParticipantRead`, `ParticipantAdd`, `EntrainementUpdate`/`Create`) — nouveaux champs optionnels, rien de retiré ni de renommé ; une route nouvelle (`PATCH .../presence`), aucune existante modifiée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (`scope`, `federal_only`, `seasons`) ne s'applique à une ressource jeunes — même statut N/A que #867/#868. |
| VI | Simplicité / YAGNI | ✅ | Colonne unique plutôt que table de présence séparée (research.md D1) ; appel de fin sans persistance ni route dédiée (research.md D2) ; aucun nouveau mécanisme de notes (research.md D3) ; navigation fusionnée plutôt que dupliquée une troisième fois. |

## Project Structure

### Documentation (this feature)

```text
specs/20260915-141516-appel-jeunes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── entrainement.py             # MODIFIÉ — + colonne `note`
│   │   └── entrainement_participant.py # MODIFIÉ — + colonne `present`
│   ├── schemas/
│   │   └── entrainement.py             # MODIFIÉ — ParticipantRead.present, ParticipantAdd.present,
│   │                                    #           EntrainementCreate/Update.note, nouveau PresenceUpdate
│   ├── repositories/
│   │   └── entrainement_repository.py  # MODIFIÉ — add_participant(present=), set_presence(), update(note=)
│   ├── services/jeunes/
│   │   └── entrainements.py            # MODIFIÉ — add_participant(present=), set_presence(),
│   │                                    #           create/update_entrainement(note=)
│   └── api/v1/
│       └── admin_jeunes_entrainements.py # MODIFIÉ — nouvelle route PATCH .../presence
├── alembic/versions/
│   └── <rev>_appel_presence_jeunes.py  # NOUVEAU — migration des deux colonnes
└── tests/
    ├── test_repositories/test_entrainement_repository.py  # MODIFIÉ
    ├── test_services/test_entrainements_jeunes.py          # MODIFIÉ
    └── test_api/test_admin_jeunes_entrainements.py          # MODIFIÉ

frontend/
├── app/admin/jeunes/appel/
│   ├── page.tsx                        # NOUVEAU — résout/crée la séance du jour
│   └── [id]/page.tsx                   # NOUVEAU — écran d'appel d'une séance
├── components/admin/jeunes/
│   ├── AppelPresence.tsx               # NOUVEAU — appel de début + bascule appel de fin
│   ├── AppelFin.tsx                    # NOUVEAU — recompte frontend, sans écriture
│   ├── NoteSeanceForm.tsx              # NOUVEAU — note de séance (PATCH note)
│   ├── AjouterNoteJeuneDialog.tsx      # NOUVEAU — délègue à POST .../log-entries existant
│   └── EntrainementDetailDialog.tsx    # MODIFIÉ — lien « Ouvrir l'appel »
├── lib/api/client.ts                   # MODIFIÉ — setEntrainementParticipantPresence, addEntrainementParticipant(present?)
├── lib/queries/admin.ts                # MODIFIÉ — useSetPresence, useCreateEntrainementParticipant(present?)
├── lib/types.ts                        # MODIFIÉ — EntrainementParticipant.present, Entrainement.note
└── components/layout/nav.config.ts     # MODIFIÉ — fusion des deux entrées « Jeunes » en une section à 3 sous-liens
```

**Structure Decision**: patron web existant, aucune nouvelle couche ni nouveau
router. Toute l'écriture backend passe par le router `admin_jeunes_entrainements.py`
et le service `services/jeunes/entrainements.py` déjà en place (#868) ; les
notes sur un jeune passent par `admin_profiles.py`/`profile_service.py` déjà
en place (#867), sans aucune modification de ces deux fichiers. Le nouveau
code frontend vit sous `app/admin/jeunes/appel/` (même famille RBAC que
`app/admin/jeunes/calendrier`), pas le groupe `(public_restricted)`.

## Complexity Tracking

*Aucune ligne : aucune violation de principe à justifier.*
