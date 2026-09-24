# Implementation Plan: Rattacher un résultat de relais à plusieurs athlètes

**Branch**: `894-relay-multi-athletes` (base `epic/889-relais`) | **Date**: 2026-09-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260924-171341-relay-multi-athletes/spec.md`

## Summary

Un résultat de relais n'appartient aujourd'hui qu'à un athlète, souvent fictif
(nom de l'équipe). On ajoute une table de liaison `participation_teammates`
qui porte les 2 à 8 équipiers d'un résultat, sans toucher à la ligne
`participations` : classements, compteurs du club et qualité restent justes
sans dédoublonnage. `athlete_id` reste renseigné (équipier porteur), ce qui
garde `ParticipationOut.athlete` valide ; les équipiers arrivent dans un champ
additif `teammates`. Un endpoint `PUT .../teammates` pose la composition en un
geste atomique, crée au besoin les équipiers saisis par nom, purge la fiche
d'équipe orpheline et journalise. Le rescrape ne défait plus une composition
posée. Les compteurs individuels excluent désormais tous les relais (Q1 : B).
Détail des arbitrages : [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend) ; TypeScript 5, Next.js 16 App Router (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 sync, Pydantic v2, Alembic ; React Query, `@base-ui/react` (dialog), composants `components/admin/`

**Storage**: PostgreSQL (prod, Azure) / SQLite (dev) ; une table ajoutée par migration Alembic, aucune donnée migrée

**Testing**: pytest (unitaires, sans réseau) ; Vitest + RTL

**Target Platform**: API Render, front Vercel

**Project Type**: application web (backend + frontend)

**Performance Goals**: la fiche athlète garde son coût actuel (une sous-requête indexée de plus) ; l'attribution répond en moins d'une seconde

**Constraints**: API `/api/v1` modifiée seulement par ajouts ; geste atomique ; rescrape idempotent sur un résultat attribué

**Scale/Scope**: quelques dizaines de relais attribués par saison ; 2 à 8 équipiers par résultat

## Constitution Check

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants anglais (`participation_teammates`, `set_teammates`, `teammates`) ; messages `DomainError` et UI en français. Champs d'entrée en anglais (`athlete_name`/`athlete_firstname`, précédent `ParticipationCreate`) ; `nom`/`prenom` restent seulement dans la sortie `AthleteBrief`, gelée par le contrat. |
| II | Architecture en couches | ✅ | Requêtes sur la liaison dans `participation_repository`/`athlete_repository` ; orchestration et transaction dans `services/admin_actions.py` ; route fine dans `api/v1/admin_data.py`. |
| III | TDD sans réseau | ✅ | Chaque tâche commence par un test rouge ; rescrape testé sur fixtures existantes, sans réseau. |
| IV | Contrats API et CLI stables | ✅ | Ajouts seulement (`teammates`, `teammate_names`, nouvel endpoint). La baisse des compteurs individuels est une règle métier voulue (spec FR-011/FR-012), pas un champ modifié. |
| V | Neutralité des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` ajouté ni modifié. |
| VI | Simplicité / YAGNI | ✅ | Pas de drapeau « verrouillé » : la présence de la liaison suffit (research R3). Pas de nouvel endpoint de création d'athlète : réutilisation de `get_or_create_athlete`. Pas de compteur « relais » séparé. |

Re-check post-design : inchangé.

## Project Structure

### Documentation (this feature)

```text
specs/20260924-171341-relay-multi-athletes/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/<rev>_participation_teammates.py   # nouvelle table
├── app/models/participation.py                         # modèle ParticipationTeammate + relation
├── app/schemas/participation.py                        # teammates (out)
├── app/schemas/admin.py                                # TeammateRef, TeammatesUpdate (in)
├── app/schemas/club.py                                 # ClubPodiumEntry.teammate_names
├── app/repositories/participation_repository.py        # liaison : lecture/écriture, list_for_athlete, exists_for_athlete_on_course, stats_rank_rows (is_relay)
├── app/repositories/athlete_repository.py              # orphelins, roster/rang/composition
├── app/services/admin_actions.py                       # set_teammates ; reassign vide la liaison
├── app/services/import_service.py                      # _Persister : garde de réconciliation, appariement par team_name
├── app/api/v1/admin_data.py                            # PUT /admin/participations/{id}/teammates
└── tests/                                              # test_repositories/, test_services/, test_api/, rescrape

frontend/
├── lib/types.ts, lib/api/client.ts, lib/queries/admin.ts
├── components/athletes/TeammatesDialog.tsx             # sélecteur multiple + saisie par nom (primitives tcn)
├── components/results/EquipeRelais.tsx                # équipiers d un relais, fiche athlète + classement
├── components/athletes/ParticipationAdminActions.tsx   # commande « Attribuer aux équipiers »
├── app/(public_restricted)/athletes/[id]/page.tsx      # compteurs sans relais
└── lib/utils/ma-saison.ts                              # compteurs sans relais
```

**Structure Decision**: application web existante, `backend/` et `frontend/`.
Aucun nouveau module de premier niveau.

## Complexity Tracking

Aucune violation à justifier.

## Points laissés à /speckit-tasks

- Ordre : migration et modèle, puis lectures par athlète (R5), puis
  `set_teammates`, puis garde du rescrape (R3), puis compteurs (R4), puis front.
- Issue séparée à ouvrir : la réattribution simple est défaite par le rescrape
  (research R3, hors périmètre).
