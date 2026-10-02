# Implementation Plan: Droit d'opposition effectif d'un athlète

**Branch**: `feat/334-athlete-opposition` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/20261001-181344-athlete-opposition/spec.md`

## Summary

Une table `athlete_oppositions` mémorise l'empreinte de l'identité normalisée d'une personne opposée. L'appliquer anonymise ses résultats existants (motif « Anonyme {épreuve}-{dossard} » déjà employé pour les noms masqués), retire la fiche et ses références, et journalise. Le même filtre, posé dans `_Persister.add` et `_resolve_pending`, anonymise tout résultat importé ensuite ; la saisie manuelle et la composition d'équipe refusent l'identité. Un écran `/admin/oppositions` liste les oppositions et en enregistre par nom ; la fiche athlète porte le geste ; le formulaire de signalement gagne le type « Retrait de mes données ».

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 / React 19 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 ; Next.js 16, React Query
**Storage**: PostgreSQL (prod, Azure) / SQLite (dev, tests) ; une table, aucune colonne modifiée
**Testing**: pytest (dont `db_session_fk` pour les FK), vitest + Testing Library
**Target Platform**: API Render, front Vercel
**Project Type**: web application (backend + frontend)
**Performance Goals**: application en une transaction ; filtre d'import en O(1) par ligne (empreintes chargées une fois par `_Persister`)
**Constraints**: rangs sources intacts ; aucun nom en clair stocké ; contrat v1 seulement étendu
**Scale/Scope**: quelques oppositions par an ; épreuves jusqu'à ~2 000 lignes

## Constitution Check

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants anglais (`AthleteOpposition`, `identity_hash`), messages et libellés en français. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Requêtes dans `opposition_repository` et les repositories existants ; logique dans `services/opposition_service.py` ; routes fines. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche d'implémentation suit son test ; imports testés avec des `ScrapedResult` construits, sans réseau. |
| IV | Contrats API et CLI stables | ✅ | Routes nouvelles ; `type: "retrait"` ajouté à `POST /feedback` (additif) ; deux 422 nouveaux sur une identité opposée, refus voulu par la loi, documentés. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse. |
| VI | Simplicité / YAGNI | ✅ | Réemploi du motif « Anonyme » et de `audit.record` ; pas de sel secret (research R3) ; pas d'annulation. |

## Project Structure

### Documentation (this feature)

```text
specs/20261001-181344-athlete-opposition/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/admin-oppositions.md
└── tasks.md
```

### Source Code

```text
backend/
├── alembic/versions/<rev>_athlete_oppositions.py
├── app/core/identity.py                     # opposition_key / identity_hash (pur)
├── app/core/permissions.py                  # + OPPOSITIONS_MANAGE
├── app/models/athlete_opposition.py
├── app/repositories/opposition_repository.py
├── app/services/opposition_service.py       # preview, apply, list, is_opposed
├── app/services/import_service.py           # filtre dans _Persister.add et _resolve_pending
├── app/services/scrape_service.py           # refus saisie manuelle
├── app/services/admin_actions.py            # refus set_teammates
├── app/schemas/opposition.py, app/api/v1/admin_oppositions.py (+ router.py)
├── app/models/user_feedback.py, app/schemas/feedback.py   # type "retrait"
└── tests/ (test_core/test_identity.py, test_services/test_opposition_service.py,
            test_services/test_opposition_on_import.py, test_auth/test_admin_oppositions_api.py, …)
frontend/
├── app/admin/oppositions/page.tsx + components/admin/OppositionsScreen.tsx
├── components/athletes/AthleteAdminPanel.tsx           # geste « Appliquer une opposition »
├── components/tcn/FeedbackButton.tsx, components/admin/FeedbackTable.tsx   # type retrait
├── components/layout/nav.config.ts, lib/api/client.ts, lib/queries/admin.ts, lib/types.ts
└── components/legal/content/confidentialite.tsx         # canal et anonymisation annoncés
```

**Structure Decision**: web application, les deux côtés. Le filtre d'import vit au point unique `_Persister` ; les deux chemins qui l'évitent refusent l'identité plutôt que de dupliquer l'anonymisation.

## Complexity Tracking

Aucune violation.
