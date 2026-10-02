# Implementation Plan: Une identité stable par athlète réel

**Branch**: `epic/1146-athlete-identity` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20261001-144131-athlete-identity/spec.md`

## Summary

Une fiche par personne réelle, une personne par fiche. L'identité devient une **clé normalisée stockée** (`last_name_key`, `first_name_key`, sans accents ni ponctuation), plus un **rang d'homonyme** : la base garantit une seule fiche principale par clé (`UNIQUE(last_name_key, first_name_key, homonym_rank)`), et l'import ne vise que la principale. La création devient idempotente sous concurrence (`INSERT … ON CONFLICT DO NOTHING` + relecture). L'import tente ensuite les variantes mémorisées par les fusions, puis l'inversion et la concaténation. Une ligne à dossard neuf sur une fiche déjà présente sur l'épreuve individuelle reçoit une fiche d'homonyme. Les corrections admin sont protégées par un drapeau `athlete_locked` et par l'appariement sans dossard sur la clé source `source_identity_key`. Une fusion admin (aperçu, refus nommés, journal) et une revue d'identité calquée sur celle des épreuves en doublon règlent les cas ambigus. Une commande `reconcile-athletes`, simulée avant d'être appliquée, reprend le stock de production. Détail : `research.md`.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript strict (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 sync (`on_conflict_do_nothing` des dialectes `postgresql` et `sqlite`), Pydantic v2, Alembic, Typer ; Next.js 16, TanStack Query, shadcn/ui. Aucune dépendance nouvelle.

**Storage**: PostgreSQL 16 (Azure en prod, Supabase en preview), SQLite en dev. Trois migrations (PR 1, 2, 5).

**Testing**: pytest sans réseau (SQLite par défaut, PostgreSQL via `TEST_POSTGRES_URL` dans le job CI `backend-postgres`), `typer.testing.CliRunner`, vitest.

**Target Platform**: Render (API), Vercel (front).

**Project Type**: application web (backend + frontend).

**Performance Goals**: résolution d'un lot d'import sans requête par ligne (deux requêtes groupées par tranche, plus une de repli limitée aux clés non résolues) ; rétro-remplissage de ≈108 000 fiches et ≈300 000 participations dans la migration en quelques dizaines de secondes.

**Constraints**: migration non bloquante au déploiement Render (les doublons existants reçoivent un rang, ils ne la font pas échouer) ; parité SQLite/PostgreSQL sans `unaccent` dans les index ; contrat `/api/v1` uniquement étendu ; budget infra nul (aucun service ajouté).

**Scale/Scope**: ≈108 000 fiches, ≈5 000 à 8 000 fusions à la reprise, quelques dizaines de cas en revue après reprise ; 7 sous-issues, 6 PR.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants neufs en anglais (`last_name_key`, `homonym_rank`, `athlete_aliases`, `reconcile-athletes`) ; messages de refus, libellés de revue et UI en français ; `nom`/`prenom` existants non renommés (règle de transition). |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Requêtes de résolution, fusion, revue et reprise dans `athlete_repository`, `athlete_alias_repository`, `ignored_athlete_pair_repository` ; services `athlete_merge`, `athlete_identity_review`, `athlete_reconciliation` n'ouvrent que des transactions ; la CLI n'appelle que des services. Club : `core/club.tcn_clause` uniquement. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque PR commence par ses tests rouges (scénarios de la spec) ; test de concurrence à deux sessions sur PostgreSQL dans `tests/test_repositories` (job CI existant), sauté hors PostgreSQL ; migration testée par le motif « upgrade à la révision précédente, insérer, upgrade, vérifier » de `test_migrations.py`. |
| IV | Contrats API et CLI stables | ✅ | Routes et champs ajoutés seulement (`contracts/admin-api.md`) ; 409 de `PATCH /admin/athletes/{id}` enrichi d'un champ ; rapport d'import enrichi de `homonyms_created` ; nouvelle commande au contrat stdout/stderr et aux codes 0/1/2/130. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun paramètre `scope`, `federal_only` ou `seasons` ajouté ni modifié. |
| VI | Simplicité / YAGNI | ✅ | Deux tables neuves, chacune exigée par la spec (variantes : Q2 ; écarts de revue : FR-022, motif existant) ; la revue se calcule à la volée au lieu d'une table de cas ; repli par égalité de concaténation au lieu d'une énumération de découpages ; pas de nouveau mode de workflow pour un geste de reprise ponctuel. |

**Point de gouvernance** : la section « Additional Constraints » de la constitution énonce « `Athlete` (unique par nom/prénom/DDN) », que cette epic rend faux (unique par clé normalisée et rang d'homonyme). Amendement **PATCH** à proposer (issue + accord d'un mainteneur, procédure « Governance ») dans la PR 1, avec mise à jour de `docs/modele-donnees.md` et `backend/app/models/AGENTS.md`.

**Re-check post-design** : inchangé, tous ✅ / N/A.

## Project Structure

### Documentation (this feature)

```text
specs/20261001-144131-athlete-identity/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── admin-api.md
│   └── cli-reconcile-athletes.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   ├── <rev>_athlete_identity_key.py           # PR 1
│   ├── <rev>_participation_source_identity.py  # PR 2
│   └── <rev>_athlete_aliases_and_review.py     # PR 5
├── app/
│   ├── core/athlete_identity.py                # identity_key (PR 1)
│   ├── models/
│   │   ├── athlete.py                          # clés, rang, contrainte (PR 1)
│   │   ├── participation.py                    # athlete_locked, source_identity_key (PR 2)
│   │   ├── athlete_alias.py                    # PR 5
│   │   └── ignored_athlete_pair.py             # PR 5
│   ├── repositories/
│   │   ├── athlete_repository.py               # résolution par clé, ON CONFLICT, repli, homonymes
│   │   ├── athlete_alias_repository.py         # PR 5
│   │   └── ignored_athlete_pair_repository.py  # PR 5
│   ├── services/
│   │   ├── import_service.py                   # _Persister : clés, multiset par clé source, FR-008, réconciliation
│   │   ├── admin_actions.py                    # update_athlete (clé + 409 enrichi), reassign (athlete_locked)
│   │   ├── athlete_merge.py                    # PR 5
│   │   ├── athlete_identity_review.py          # PR 5
│   │   └── athlete_reconciliation.py           # PR 6
│   ├── api/v1/
│   │   ├── admin_data.py                       # merge-impact, merge
│   │   └── admin_athlete_identity.py           # revue (PR 5)
│   ├── schemas/admin.py, schemas/athlete_identity.py
│   └── cli/commands/reconcile_athletes.py      # PR 6
└── tests/
    ├── test_core/test_athlete_identity.py
    ├── test_repositories/test_athlete_identity_concurrency.py   # PostgreSQL
    ├── test_import_service.py, test_admin_actions.py, test_athlete_merge.py, …
    ├── test_migrations.py
    └── test_cli/test_reconcile_athletes.py

frontend/
├── app/admin/identites/page.tsx                # revue (PR 5)
├── components/admin/AthleteIdentityReviewTable.tsx
├── components/athletes/MergeAthleteDialog.tsx  # depuis AthleteAdminPanel
├── components/layout/nav.config.ts             # entrée + badge
└── lib/api/client.ts, lib/queries/admin.ts, lib/queries/nav-badges.ts

docs/
├── api/admin-donnees.md                        # fusion, revue, 409 enrichi
├── modele-donnees.md                           # identité, contraintes
└── ci-cd.md                                    # procédure reconcile-athletes
backend/app/cli/AGENTS.md, backend/app/models/AGENTS.md
```

**Structure Decision** : application web existante (`backend/` + `frontend/`), aucun dossier nouveau hors des modules listés. Livraison par sous-issue dans la branche d'intégration, ordre et contenu en `research.md` R10 :

1. **PR 1, #907 + #908 (résolution)** : clé normalisée, rangs, contrainte, résolution par clé, repli inversion et concaténation.
2. **PR 2, #900 + #896** : identité sans `birth_date`, `athlete_locked`, `source_identity_key`, appariement sans dossard par clé source, règle de réconciliation.
3. **PR 3, #981** : création idempotente, test de concurrence PostgreSQL.
4. **PR 4, #967** : homonymes distingués à l'import.
5. **PR 5, #908 + #907 + #967 (revue)** : fusion admin, variantes, revue, UI.
6. **PR 6, #906** : commande de reprise et procédure de production.

Chaque PR cible `epic/1146-athlete-identity`, `Refs #1146` ; la PR parapluie vers `main` porte `Closes #1146` et les `Closes` des sous-issues. La reprise en production se lance **après** le déploiement de la PR parapluie.

## Risques

| Risque | Parade |
| --- | --- |
| Migration lente ou bloquante au démarrage Render | rétro-remplissage en Python par lots (motif `ccda2de245af`), rangs au lieu d'échec ; essai sur une copie de la base de preview avant fusion |
| Normalisation divergente entre migration et code | règle figée dans la migration, test qui compare les deux sur un jeu de chaînes (accents, ligatures, ponctuation) |
| Fusion automatique d'homonymes réels à la reprise | gardes de refus (dossards sur une même épreuve, comptes, dates de naissance) ; inversions et concaténations seulement sur signaux concordants (Q3) ; simulation relue avant application |
| Rescrape sans dossard après renormalisation « NOM, Prénom » | la reprise recalcule `source_identity_key` des participations touchées |
| Fiche principale recréée sur une variante pendant une fusion | motif de revue `alias_collision` |

## Complexity Tracking

Aucune violation à justifier (Constitution Check sans ⚠️).
