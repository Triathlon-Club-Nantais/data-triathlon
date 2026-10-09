# Implementation Plan: Accès bénévoles sans mot de passe pour l'administrateur qui le gère

**Branch**: `feat/1272-benevole-access-sso-bypass` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20261009-161930-benevole-sso-bypass/spec.md`

## Summary

La garde `require_benevole_access` (`backend/app/api/deps.py`) admet en premier un utilisateur SSO valide qui détient `P.BENEVOLE_ACCESS_MANAGE` (via `authorization.has_permission`, superutilisateur compris), et sinon applique la garde actuelle à l'identique (cookie signé, fail closed, même 401). Elle rend désormais l'administrateur admis, ou `None` quand l'accès vient du cookie. Les six routes d'écriture de `benevoles.py` en déduisent l'acteur du journal par `benevole_access.actor_user_id(db, admin)` : l'administrateur, sinon le compte système. Côté front, la file se charge déjà sans formulaire dès que l'API répond 200 ; seul le bouton « Se déconnecter » est masqué à qui détient le pouvoir (`useSession`).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 sync, React Query (front). Aucune nouvelle dépendance.

**Storage**: aucune modification de schéma ni migration.

**Testing**: pytest (`-m "not integration"`), vitest + Testing Library.

**Target Platform**: API Render, front Vercel.

**Project Type**: web-service + web app.

**Performance Goals**: une résolution de session et une question de pouvoir de plus par requête bénévole quand un cookie SSO est présent ; rien pour un anonyme sans cookie SSO (`session_service.resolve` sort tôt sur jeton absent).

**Constraints**: contrat `/api/v1` inchangé (Principe IV) ; critère par pouvoir, jamais par rôle (FR-017 du socle) ; seuls les repositories requêtent la Session (Principe II).

**Scale/Scope**: une dépendance, un helper de service, onze routes (six écritures), un bouton front.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants et tests nouveaux en anglais (`actor_user_id`, `test_*`), docstrings de règle métier en français, aucun nouveau message utilisateur. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | La garde (api) délègue à `services/auth` (`session.resolve`, `authorization.has_permission`) ; l'acteur se calcule dans `services/benevole_access`, qui passe par `user_repository`. Aucune requête hors repository. |
| III | TDD sans réseau (non-négociable) | ✅ | Tests backend de la garde et de l'attribution écrits rouges avant la modification ; test front du bouton masqué avant le code. Aucun réseau. |
| IV | Contrats API et CLI stables | ✅ | Chemins, corps, codes inchangés ; l'ensemble des appelants admis s'élargit, le refus reste le même 401 (`contracts/api.md`). |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse (scope, filtre) touché. |
| VI | Simplicité / YAGNI | ✅ | Pas de nouvelle garde ni de nouveau cookie : la garde existante gagne une branche, la valeur de retour porte l'acteur. |

## Project Structure

### Documentation (this feature)

```text
specs/20261009-161930-benevole-sso-bypass/
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
├── app/api/deps.py                      # require_benevole_access : branche par pouvoir, rend User | None
├── app/api/v1/benevoles.py              # six écritures : acteur = actor_user_id(db, admin)
├── app/services/benevole_access.py      # actor_user_id
├── app/api/AGENTS.md                    # section « Page bénévoles » mise à jour
└── tests/test_auth/test_benevole_access_sso.py   # nouveaux tests (fixture ouvrir_session)

frontend/
├── app/benevoles/page.tsx               # bouton « Se déconnecter » masqué si pouvoir
└── app/benevoles/page.test.tsx          # test du masquage
```

**Structure Decision**: application web existante `backend/` + `frontend/` ; les nouveaux tests backend vivent sous `tests/test_auth/` pour réutiliser `ouvrir_session`, qui fabrique une session portant exactement les pouvoirs demandés.

## Complexity Tracking

Aucune violation.
