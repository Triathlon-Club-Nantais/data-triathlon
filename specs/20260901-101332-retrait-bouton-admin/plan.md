# Implementation Plan: Retrait du bouton admin de déclaration de bénévolat

**Branch**: `780-retrait-bouton-admin` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260901-101332-retrait-bouton-admin/spec.md`

## Summary

Retire le geste admin en un clic de déclaration de bénévolat, redondant
depuis #778/#779. Retrait complet du chemin — bouton, route, service,
repository, permission — pas seulement de l'affichage, forcé par le test
de catalogue de pouvoirs existant (`test_chaque_pouvoir_du_catalogue_
garde_au_moins_une_ressource`). Aucune migration : les colonnes
`title`/`description` restent nullables pour les lignes historiques.

## Technical Context

**Language/Version**: Python 3.13 (backend) + TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2 ; TanStack Query

**Storage**: aucun changement de schéma

**Testing**: pytest (backend) ; vitest (frontend) — cette sous-issue est majoritairement une suppression, le TDD s'y applique à l'envers (retirer le test avant/avec le code qu'il couvrait, jamais après)

**Target Platform**: web

**Project Type**: web application (backend + frontend)

**Performance Goals**: aucun objectif dédié

**Constraints**: aucune migration ; ne pas casser la lecture des lignes historiques sans titre/description (#779, #781) ; `ValiderSaison`/`athletes:season_validate` inchangés

**Scale/Scope**: suppression de 1 route, 1 fonction service, 1 fonction repository, 2 schémas, 1 permission (backend), 1 bouton + 1 hook + 1 méthode client + potentiellement 1 type (frontend) ; adaptation de ~6 tests existants (#709/#778/#779/#781) qui appelaient la fonction retirée

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Suppression pure, aucun nouvel identifiant |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Suppression symétrique sur les trois couches, rien ne saute de niveau |
| III | TDD sans réseau (non-négociable) | ✅ | Tests adaptés/retirés en même temps que le code qu'ils couvraient, suite verte à chaque étape |
| IV | Contrats API et CLI stables | ⚠️ | Retrait d'une route `/api/v1` — justifié en Complexity Tracking |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`/`federal_only`/`seasons` concerné |
| VI | Simplicité / YAGNI | ✅ | Raison d'être de la sous-issue — retire un chemin mort plutôt que de le garder par prudence |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Retrait de `POST /admin/athletes/{athlete_id}/volunteer-actions` (Principe IV) | Le pouvoir qui la garde perdrait toute ressource, faisant échouer un test existant (`test_permissions_catalogue.py`) ; le geste qu'elle rendait est intégralement couvert par #778 (self-service) + #779 (validation) | Garder la route « au cas où » : c'est exactement le chemin mort que le Principe VI proscrit — jamais appelée après le retrait du bouton (seul appelant frontend), et jamais un contrat externe documenté (`app/api/AGENTS.md` la compte parmi les gestes d'administration internes, pas les contrats stables listés au Principe IV) |

## Project Structure

### Documentation (this feature)

```text
specs/20260901-101332-retrait-bouton-admin/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── removed-endpoint.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/admin_data.py                        # MODIFIED — route retirée
│   ├── services/admin_actions.py                    # MODIFIED — declare_volunteer_action() retirée
│   ├── repositories/volunteer_action_repository.py  # MODIFIED — create() retirée
│   ├── schemas/admin.py                             # MODIFIED — VolunteerActionCreate/Out retirés
│   └── core/permissions.py                          # MODIFIED — ATHLETES_VOLUNTEER_MANAGE retiré (P + ALL)
└── tests/
    ├── test_api/test_admin_data_api.py                    # MODIFIED — 5 tests retirés
    ├── test_services/test_admin_actions.py                 # MODIFIED — 3 tests retirés, 1 adapté
    ├── test_repositories/test_volunteer_action_repository.py  # MODIFIED — tests de create() retirés/adaptés
    ├── test_api/test_admin_volunteer_actions_api.py        # MODIFIED — 2 usages de create() adaptés
    ├── test_core/test_permissions.py                       # MODIFIED — code retiré de CODES_ATTENDUS
    └── test_permissions_catalogue.py                       # inchangé — paramétré sur ALL, se recale seul

frontend/
├── components/athletes/
│   ├── SeasonValidationPanel.tsx        # MODIFIED — DeclarerBenevolat retiré
│   └── SeasonValidationPanel.test.tsx   # MODIFIED — tests US2 retirés
├── lib/
│   ├── queries/admin.ts                 # MODIFIED — useDeclareVolunteerAction retiré
│   ├── queries/admin.test.ts            # MODIFIED — tests associés retirés
│   ├── api/client.ts                    # MODIFIED — declareVolunteerAction retiré
│   └── types.ts                         # MODIFIED — VolunteerAction retiré si orphelin
└── app/(public_restricted)/athletes/[id]/page.test.tsx  # MODIFIED — mock nettoyé si nécessaire
```

**Structure Decision**: Web application existante — suppression pure sur
backend et frontend, aucun nouveau fichier hors artefacts `specs/`.

## Verification (post-Phase 1)

Constitution Check re-vérifié : le seul écart (Principe IV) est justifié
en Complexity Tracking ci-dessus, conformément à la règle de gouvernance
(« une violation doit être justifiée [...] avec l'alternative rejetée et
la raison »).
