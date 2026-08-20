# Implementation Plan: Actions d'administration sur la page d'un coureur

**Branch**: `feat/439-athlete-admin-actions` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260820-095442-page-athlete-actions-admin/spec.md`

## Summary

Porter sur la page publique `/athletes/[id]` les quatre gestes correctifs qui
existent déjà côté back-office — corriger l'identité, corriger le club actuel,
supprimer un résultat, réattribuer un résultat — chacun visible **si et seulement
si** la session porte son pouvoir, évalué pouvoir par pouvoir.

L'approche tient en trois mouvements, du plus lourd au plus léger :

1. **Une addition de schéma** : `athletes.club_locked` (booléen, défaut `False`),
   posée par la correction manuelle du club et respectée par
   `athlete_repository.resolve`, seul écrivain de `Athlete.club` sur le chemin
   d'import. C'est ce qui fait tenir FR-018 (« la correction prime sur
   l'import »), tranché avec le demandeur.
2. **Deux écarts backend comblés** : `AdminAthleteUpdate` gagne un champ `club`
   optionnel, et `DELETE /participations/{id}` — aujourd'hui sans entrée au
   journal et avec un `db.delete()` dans la route — délègue à un service qui
   journalise, sans changer ni son chemin ni son 204.
3. **Le surfaçage frontend**, l'essentiel du volume : deux composants clients
   dans `components/athletes/`, bâtis sur `tcn/`, gardés par `useSession()`, la
   page restant rendue par `serverFetch` pour ne rien coûter de plus au visiteur
   anonyme (SC-004).

4. **Un alignement d'une ligne dans le back-office** (FR-020) : l'écran qui offre
   déjà la réattribution ne teste qu'un pouvoir alors que son sélecteur en exige
   deux, et annonce donc un geste qui finit en 403. C'est le seul point de la
   branche hors de la page coureur, et il est la contrepartie assumée du couplage
   de FR-004 — une règle par geste, pas par écran (D6).

Aucun nouveau pouvoir, aucun nouveau chemin d'API. Détail des onze décisions et
des alternatives écartées : [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 / Node 22 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic,
`slowapi` — côté front Next.js 16 (App Router), `@tanstack/react-query`,
Tailwind 4, `sonner`

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement. Une
migration Alembic (une colonne booléenne `NOT NULL DEFAULT false`)

**Testing**: pytest (marker `integration` pour le réseau réel, exclu par défaut),
vitest + React Testing Library

**Target Platform**: API sur Render, frontend sur Vercel ; navigateurs modernes,
consultation mobile incluse

**Project Type**: application web à deux déploiements — `backend/` (API `/api/v1`)
et `frontend/` (Next.js)

**Performance Goals**: la lecture du drapeau `club_locked` sur le chemin d'import
coûte **zéro requête** (attribut déjà hydraté par `resolve`) ; la page reste en
rendu serveur statique pour le public, et les gestes ne s'ajoutent qu'au bundle
client de cette page

**Constraints**:

- La page doit rester rendue via `apiServer.getAthlete` (bâti sur `serverFetch`,
  donc sans cookies) : y lire la session au rendu la rendrait dynamique, et six
  pages publiques dépendent de ce choix (SC-004, `frontend/AGENTS.md`).
- `DELETE /participations/{id}` est une route `/api/v1` publiée : chemin, verbe et
  code de statut inchangés (Principe IV).
- `birth_date` est la seule donnée personnelle fermée du site : jamais affichée
  ni renvoyée sans `athletes:read` (US1-AC4).
- Les boutons masqués ne protègent rien : les gardes de route restent la seule
  autorité (FR-009).

**Scale/Scope**: une poignée d'administrateurs du club, corrections ponctuelles —
aucun besoin d'action de masse ni de sélection multiple. Périmètre technique :
4 gestes, 1 page, 1 colonne, 4 pouvoirs déjà existants.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Libellés, confirmations et messages d'erreur en français (FR-017) ; identifiants, tests et docstrings en anglais. `club_locked` est un identifiant technique ; `DuplicateError` porte déjà un message français sérialisé vers le front. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | La feature **corrige** un écart existant : `db.delete()` quitte la route `participations.py` pour `participation_repository.delete`, orchestré par `admin_actions.delete_participation`. Aucune des deux exemptions nommées (`cache.py`, `reclassify.py`) n'est touchée. `flush` dans le service, `commit` dans la route. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque comportement neuf a son test écrit d'abord : repository (le club figé résiste à `resolve`), service (journal de suppression, pose du drapeau), API (champ `club` accepté, 403 par pouvoir), migration (un `test_downgrade_puis_upgrade_de_club_locked` **à ajouter** dans `test_migrations.py`, qui ne couvre l'aller-retour que révision par révision), et vitest pour la visibilité pouvoir par pouvoir. Zéro réseau : les tests portent sur la base et sur des mutations mockées. |
| IV | Contrats API et CLI stables | ✅ | Aucun chemin, verbe ni code de statut modifié. `AdminAthleteUpdate` gagne un champ **optionnel** (addition compatible) ; `club_locked` n'est pas exposé (D2). Aucune commande CLI touchée. |
| V | Neutralité par défaut des paramètres transverses | N/A | La feature n'introduit aucun paramètre de lecture transverse (`scope`, `federal_only`, `page_size`) ni n'en change la valeur par défaut. |
| VI | Simplicité / YAGNI | ✅ | Une seule addition de schéma, exigée par FR-018 et non spéculative. Écartés faute de besoin constaté : l'exposition du drapeau dans l'API (D2), un geste de dé-verrouillage (D3), une seconde route de suppression (D4), une huitième colonne d'actions (D9). |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

**Re-évaluation après Phase 1** : les six statuts tiennent. La conception détaillée
n'a ajouté ni entité, ni chemin d'API, ni dépendance — `data-model.md` porte une
colonne et deux invariants, `contracts/` ne décrit qu'un champ ajouté et un corps
de route réécrit. Complexity Tracking reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/20260820-095442-page-athlete-actions-admin/
├── spec.md              # Specification (/speckit-specify)
├── plan.md              # This file (/speckit-plan)
├── research.md          # Phase 0 — 11 décisions, alternatives écartées
├── data-model.md        # Phase 1 — la colonne club_locked et ses invariants
├── quickstart.md        # Phase 1 — scénarios de validation exécutables
├── contracts/
│   ├── api.md           # Les 3 ressources touchées, avant / après
│   └── ui.md            # Contrat de visibilité pouvoir par pouvoir
├── checklists/
│   └── requirements.md  # Qualité de la spec — 16/16
└── tasks.md             # Phase 2 (/speckit-tasks — pas créé ici)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <rev>_club_locked_athlete.py        # NEW — colonne booléenne, NOT NULL DEFAULT false
├── app/
│   ├── models/athlete.py                   # MOD — club_locked
│   ├── schemas/admin.py                    # MOD — AdminAthleteUpdate.club
│   ├── repositories/
│   │   ├── athlete_repository.py           # MOD — resolve() respecte club_locked
│   │   └── participation_repository.py     # MOD — delete()
│   ├── services/admin_actions.py           # MOD — update_athlete pose le drapeau
│   │                                       #       NEW  — delete_participation (journal)
│   └── api/v1/participations.py            # MOD — la route délègue, ne supprime plus
└── tests/
    ├── test_repositories/test_athlete_repository.py     # MOD — club figé vs club suivi
    ├── test_repositories/test_participation_repository.py  # MOD — delete()
    ├── test_services/test_admin_actions.py              # MOD — drapeau + journal
    ├── test_services/test_import_service.py             # MOD — l'import ne réécrit pas
    ├── test_api/test_admin_data_api.py                  # MOD — PATCH club, 403
    ├── test_api/test_participations_api.py              # MOD — 204 + entrée au journal
    └── test_migrations.py                               # MOD — aller-retour de la révision club_locked

frontend/
├── app/athletes/[id]/page.tsx              # MOD — monte les composants, reste sur apiServer.getAthlete
├── components/athletes/                    # NEW — répertoire
│   ├── AthleteAdminPanel.tsx               # NEW — identité + club (athletes:write)
│   ├── AthleteAdminPanel.test.tsx          # NEW
│   ├── ParticipationAdminActions.tsx       # NEW — supprimer / rattacher, par ligne
│   └── ParticipationAdminActions.test.tsx  # NEW
├── components/admin/                       # le seul point hors de la page coureur (FR-020)
│   ├── CourseParticipationsDialog.tsx      # MOD — la réattribution exige aussi athletes:read
│   └── CourseParticipationsDialog.test.tsx # MOD — le cas « un seul pouvoir »
├── lib/
│   ├── api/client.ts                       # MOD — deleteParticipation
│   └── queries/admin.ts                    # MOD — useDeleteParticipation, club dans le PATCH
└── lib/types.ts                            # MOD — le club dans le corps de mise à jour
```

**Structure Decision**: application web à deux déploiements, structure existante
inchangée. Le backend suit ses quatre couches (`api → services → repositories →
DB`), chaque fichier touché restant dans la sienne. Le frontend gagne **un** seul
répertoire, `components/athletes/`, aligné sur les répertoires par domaine
existants (`courses/`, `club/`, `benevoles/`, `scrape/`) ; ses composants sont
bâtis sur `components/tcn/` conformément à la frontière posée par
`frontend/AGENTS.md`, et les tests sont colocalisés comme partout dans le front.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation : les six principes passent en ✅ ou N/A. Table volontairement
vide.
