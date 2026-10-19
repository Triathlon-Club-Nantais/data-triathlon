# Implementation Plan: Revendiquer sa fiche athlète

**Branch**: `feat/1325-claim-athlete` (empilée sur `epic/1312-member-accounts`) | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20261017-133422-rattachement-fiche-athlete/spec.md`.

## Summary

Une table `athlete_claims` (une demande au plus par compte, `pending` ou `rejected`) et un service `services/athlete_claims.py` : demander, annuler, se détacher côté utilisateur (`/auth/me/athlete-claim`, `/auth/me/athlete`), lister, valider, refuser côté back-office (`/admin/athlete-claims`, pouvoir `athlete_claims:review`). Valider écrit `users.athlete_id` (colonne existante, jamais écrite jusqu'ici) et supprime la demande. `membership.is_member` ajoute « ou rattaché ». `/auth/me` expose `athlete` et `athlete_claim` (additifs). Côté interface : bouton « C'est moi » sur la fiche, état et détachement dans le menu du compte, écran `/admin/rattachements` avec sa pastille ; pour un compte rattaché, la fiche du compte est écrite dans le stock local existant (`tcn-athlete`), ce qui fait suivre toutes les surfaces sans les toucher, et les gestes de changement d'athlète sont masqués.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript / Next.js 16 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic ; React Query, composants `tcn` ; aucune dépendance nouvelle

**Storage**: PostgreSQL (prod), SQLite (dev/tests) ; une table nouvelle `athlete_claims`, une migration Alembic

**Testing**: pytest sans réseau (`db_session`, `db_session_fk` pour les cascades), vitest + RTL

**Target Platform**: Render (backend), Vercel (frontend)

**Project Type**: application web (backend + frontend)

**Performance Goals**: `/auth/me` gagne au plus deux lectures par clé primaire ou index unique (fiche rattachée, demande du compte) ; la file se lit en une requête plus une par indice groupé (licenciés, adresses, comptes rattachés), quelques dizaines de demandes au plus

**Constraints**: routes `def` ; écritures protégées par `core/origin_guard` ; journal d'administration écrit dans le service (#935) ; toute table pointant vers `athletes.id` rejoint `athlete_merge` et la suppression de fiche (`app/models/AGENTS.md`) ; toute table pointant vers `users.id` est soit possédée par le compte, soit une référence de `user_repository` (#1326)

**Scale/Scope**: ~300 adhérents, quelques dizaines de demandes par saison

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants anglais (`athlete_claims`, `request_claim`, `approve`), messages `DomainError` et UI en français, tests en anglais. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Requêtes dans `athlete_claim_repository` (et lectures d'indices dans les repositories existants), décisions dans `services/athlete_claims.py`, routes fines. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque tâche de code a sa tâche de test écrite et vue échouer avant ; migration éprouvée par `test_migrations.py`. |
| IV | Contrats API et CLI stables | ✅ | Ajouts seulement : routes nouvelles, deux champs additifs sur `/auth/me`, une clé de pastille additive sur `/admin/badge-counts`. `is_member` garde sa forme, sa dérivation s'élargit comme le sondage le prévoit. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre transverse touché. |
| VI | Simplicité / YAGNI | ✅ | Pas d'historique des demandes (le journal d'administration le tient) ; pas de notification ; le stock local existant sert de relais vers les surfaces au lieu de réécrire leurs sept lectures. |

Re-check post-design : inchangé.

## Project Structure

### Documentation (this feature)

```text
specs/20261017-133422-rattachement-fiche-athlete/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── auth-me-athlete-claim.md
│   └── admin-athlete-claims.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/<rev>_athlete_claims.py          # nouvelle table
├── app/models/athlete_claim.py                        # modèle
├── app/models/user.py                                 # relation possédée `athlete_claim`
├── app/repositories/athlete_claim_repository.py       # seul point de passage
├── app/repositories/user_repository.py                # `_OWNED_TABLES` + écriture de `athlete_id`
├── app/core/permissions.py                            # P.ATHLETE_CLAIMS_REVIEW
├── app/services/athlete_claims.py                     # règles
├── app/services/membership.py                         # « ou rattaché »
├── app/services/athlete_merge.py                      # report des demandes
├── app/services/opposition_service.py                 # suppression des demandes avec la fiche
├── app/services/admin_badge_counts.py                 # pastille `claims`
├── app/schemas/athlete_claim.py, app/schemas/auth.py  # DTO, champs additifs
├── app/api/v1/auth.py                                 # routes utilisateur
├── app/api/v1/admin_athlete_claims.py, router.py      # routes back-office
└── tests/…                                            # un fichier par couche

frontend/
├── lib/types.ts, lib/api/client.ts, lib/queries/auth.ts, lib/queries/admin.ts
├── app/providers.tsx                                  # SessionAthleteSync
├── app/(public_restricted)/athletes/[id]/AthleteSelection.tsx   # « C'est moi »
├── components/auth/UserMenu.tsx (+ UserMenuDropdown.tsx)        # état, détachement
├── components/layout/AppNav.tsx, components/dashboard/MaSaison.tsx  # gestes masqués si rattaché
├── app/admin/rattachements/page.tsx, components/admin/AthleteClaimsTable.tsx
├── components/layout/nav.config.ts                    # entrée + pastille
└── components/legal/content/confidentialite.tsx       # mention du lien compte → fiche
```

**Structure Decision**: application web existante, aucun dossier nouveau hors de l'écran admin.

## Complexity Tracking

Aucune violation.
