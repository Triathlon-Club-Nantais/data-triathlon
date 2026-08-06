# Implementation Plan: Actions d'administration sur les épreuves, les athlètes et les résultats

**Branch**: `feat-admin-actions-crud-sur-les-courses-athl-tes` | **Date**: 2026-08-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20260806-180938-admin-crud-actions/spec.md` (issue #117)

## Summary

Ouvrir quatre gestes correctifs au back-office — supprimer une épreuve,
corriger une épreuve, corriger un coureur, rattacher un résultat à un autre
coureur — chacun tracé dans un journal d'audit nominatif.

L'approche s'appuie sur ce qui existe : le socle d'habilitation (#115) fournit
`require_permission`, et ajouter un pouvoir n'y coûte aucune migration. La
cascade de suppression est déjà portée par l'ORM. La liste d'épreuves de l'écran
est `GET /courses`, inchangée. Le gating d'interface se lit dans
`SessionUser.permissions`, exposé depuis #115. Le layout `/admin` garde déjà ses
futures sous-routes.

Ce qui est neuf : **une table** (`admin_action_log`) avec sa migration, **un
module de routes** (`admin_data.py`) portant **quatre gestes et deux lectures
réservées**, **un service** (`admin_actions.py`), **cinq pouvoirs**, **une page**
et ses composants.

Quatre écarts par rapport au texte de #117, tous tranchés avec le mainteneur.
Deux en spécification (§Décisions tranchées) : la correction d'épreuve **entre**
dans le périmètre — l'issue se contredisait — et les fiches coureur qui perdent
leur dernier résultat sont **purgées**. Deux en clarification (§Clarifications) :
le rattachement s'appuie sur une **recherche de coureurs réservée** montrant ce
qui départage deux homonymes, et la confirmation de suppression annonce
l'ampleur **réelle**, fiches coureur comprises. Ces deux derniers ajoutent les
seules routes de lecture de la feature — aucune route publique ne pouvait les
rendre sans publier des dates de naissance ou charger un contrat public d'un
besoin d'administration.

## Technical Context

**Language/Version**: Python 3.13 (backend, `uv`), TypeScript 5 / Node 26 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ; Next.js 16 App Router, TanStack Query, shadcn/ui, Tailwind, sonner

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en test

**Testing**: pytest (`-m "not integration"`, sans réseau), vitest côté front

**Target Platform**: Render (API) + Vercel (front)

**Project Type**: application web — backend et frontend séparés dans le même dépôt

**Performance Goals**: aucun objectif de débit. Gestes ponctuels d'administration, quelques dizaines par an. La cascade ORM d'une suppression émet un `DELETE` par participation : quelques secondes pour une épreuve de 3 000 finishers, assumé (research.md §D4).

**Constraints**: aucune modification de contrat public existant (Principe IV) ; aucune session SQLAlchemy hors de `repositories/` (Principe II) ; tests sans réseau (Principe III) ; une seule migration, relue à la main.

**Scale/Scope**: base d'un club — quelques centaines d'épreuves, quelques milliers de coureurs. 6 routes (4 gestes + 2 lectures réservées), 1 table, 5 pouvoirs, 1 page front.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Messages d'erreur, libellés de pouvoirs et UI en **français** (les `DomainError` sont du texte utilisateur, cf. clause « cas mixte ») ; identifiants, codes de pouvoirs, valeurs de `action`, noms de tests et logs en **anglais**. `nom` / `prenom` conservés : gelés par contrat public. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `admin_data.py` valide et délègue ; `admin_actions.py` ne touche aucune `Session` autrement que par les repositories ; les écritures nouvelles (`course_repository.delete`, `athlete_repository.delete_orphans_among`, `admin_action_log_repository.create`) vivent dans `repositories/`. Le `db.commit()` de fin de route suit le patron du dépôt (`admin.py`, `admin_roles.py`, `auth.py`) : le router **clôt** la transaction, il n'ouvre pas de session et ne construit aucune requête — ce que le principe interdit. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque route, chaque refus et chaque invariant a son test **écrit avant**. Aucun appel réseau : la feature ne scrape rien. |
| IV | Contrats API et CLI stables | ✅ | Strictement additif sous `/api/v1/admin/*`. Aucune route existante modifiée — en particulier `GET /athletes` ne gagne **pas** `birth_date` (FR-025). `GET /admin/permissions` gagne des entrées : extension d'inventaire, pas rupture. La signature de `delete_orphans` ne bouge pas pour son appelant CLI. |
| V | Neutralité par défaut des paramètres transverses | N/A | La feature n'ajoute aucun paramètre transverse (`scope`, `federal_only`, `seasons`) et n'en impose aucun : l'écran d'administration consomme `GET /courses` sans portée, donc non filtré — le défaut neutre. |
| VI | Simplicité / YAGNI | ✅ | Aucune abstraction spéculative : pas de couche d'audit générique, pas de hook SQLAlchemy, pas de moteur de règles. Une table, un service. Les deux lectures réservées ne sont pas du confort : sans elles, l'admin choisit une fiche à l'aveugle et confirme une destruction sous-déclarée — deux erreurs sans retour en arrière. Voir Complexity Tracking. |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

**Re-check après Phase 1** : les artefacts de design (data-model, contrats,
quickstart) ne modifient aucun statut. Deux points ont été **resserrés** en
cours de design plutôt que relâchés :

- la purge des orphelins est passée d'un appel global à un appel **ciblé**
  (research.md §D5), ce qui supprime un effet de bord hors périmètre du geste ;
- le journal est écrit dans la **transaction du geste**, ce qui rend FR-015
  structurel au lieu de défensif.

**Re-check après `/speckit-clarify` (2026-08-06)** : deux routes de lecture et
un pouvoir s'ajoutent, aucun statut ne change. Le Principe IV y gagne même une
garde explicite : la date de naissance ne peut pas être servie par extension
d'un contrat public, c'est `athletes:read` qui la porte (research.md §D10). Le
Principe VI est le seul à peser un coût supplémentaire, tracé ci-dessous.

## Project Structure

### Documentation (this feature)

```text
specs/20260806-180938-admin-crud-actions/
├── spec.md              # /speckit-specify
├── plan.md              # ce fichier
├── research.md          # Phase 0 — 9 décisions techniques
├── data-model.md        # Phase 1 — AdminActionLog + invariants
├── quickstart.md        # Phase 1 — validation de bout en bout
├── contracts/
│   └── admin-data-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — non créé par /speckit-plan
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/
│   │   ├── admin_data.py                   # NOUVEAU — 6 routes, 6 gardes
│   │   └── router.py                       # + admin_data dans la boucle de montage
│   ├── core/
│   │   └── permissions.py                  # + 5 membres de P, + 2 FEATURE_*
│   ├── models/
│   │   └── admin_action_log.py             # NOUVEAU
│   ├── repositories/
│   │   ├── admin_action_log_repository.py  # NOUVEAU — create + list_for_entity
│   │   ├── athlete_repository.py           # + delete_orphans_among, + only_on_course,
│   │   │                                   #   + search_admin (identité + compteur)
│   │   ├── course_repository.py            # + delete, + update_identity
│   │   └── participation_repository.py     # + exists_for_athlete_on_course, + reassign
│   ├── schemas/
│   │   └── admin.py                        # + AdminCourseUpdate / AdminAthleteUpdate /
│   │                                       #   AdminAthleteRead / ParticipationReassign /
│   │                                       #   CourseDeletionImpact
│   └── services/
│       └── admin_actions.py                # NOUVEAU — les 4 gestes + le journal
├── alembic/versions/
│   └── <rev>_admin_action_log.py           # NOUVEAU — 1 table, 3 index
└── tests/
    ├── test_api/test_admin_data_api.py           # NOUVEAU
    ├── test_services/test_admin_actions.py       # NOUVEAU
    └── test_repositories/
        ├── test_admin_action_log_repository.py   # NOUVEAU
        └── test_athlete_repository.py            # + delete_orphans_among

frontend/
├── app/admin/courses/
│   ├── page.tsx                            # NOUVEAU — couverte par le layout /admin
│   └── page.test.tsx                       # NOUVEAU
├── components/admin/
│   ├── CoursesAdminTable.tsx               # NOUVEAU + .test.tsx
│   ├── AthleteSearchPicker.tsx             # NOUVEAU + .test.tsx — départage les homonymes
│   ├── DeleteCourseDialog.tsx              # NOUVEAU + .test.tsx — annonce l'ampleur réelle
│   ├── EditCourseDialog.tsx                # NOUVEAU + .test.tsx
│   ├── EditAthleteDialog.tsx               # NOUVEAU + .test.tsx
│   └── ReassignParticipationDialog.tsx     # NOUVEAU + .test.tsx
└── lib/
    ├── api/client.ts                       # + 6 méthodes
    ├── queries/admin.ts                    # + 4 mutations, + 2 lectures
    ├── queries/keys.ts                     # + clés d'invalidation
    └── types.ts                            # + types des corps de requête
```

**Structure Decision**: application web à deux piles, structure existante
respectée à la lettre. Aucun nouveau dossier de premier niveau. Le découpage
backend suit `admin_roles.py`, qui a déjà créé le précédent d'un module
d'administration par domaine ; le découpage frontend suit
`components/admin/PendingProvidersTable.tsx`, y compris sa distinction 401 /
403 / panne.

## Ordre d'exécution

Le socle traverse les quatre gestes ; il vient d'abord. Ensuite, une user story
par tranche, chacune livrable et testable seule (spec §User Scenarios).
`tasks.md` détaille ce découpage en sept phases — le « Socle » ci-dessous y est
scindé en *Setup* (ligne de base) et *Foundational* (le bloquant).

1. **Socle** — modèle `AdminActionLog`, migration, repository du journal,
   pouvoirs, module de routes vide monté, service vide. Rien d'utilisateur
   encore : c'est ce qui rend les quatre tranches suivantes indépendantes.
2. **US1 — supprimer une épreuve** (P1) : `course_repository.delete`,
   `delete_orphans_among`, route d'impact, route de suppression, écran + modale
   annonçant l'ampleur réelle. Le test qui compare l'impact annoncé au nombre
   réellement supprimé (SC-007) vient **avec** cette tranche, pas après.
3. **US2 — rattacher un résultat** (P2), avec la recherche réservée
   (`athletes:read`) et son sélecteur.
4. **US3 — corriger un coureur** (P3).
5. **US4 — corriger une épreuve** (P4).
6. **Clôture** : `requesting-code-review` → `verification-before-completion` →
   `finishing-a-development-branch`, et non-régressions du quickstart §3.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucun principe en ⚠️. Deux points ont été pesés au titre du Principe VI et
retenus comme **justifiés, non comme dérogations** :

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Cinq pouvoirs plutôt qu'un | FR-009 les exige individuellement, et le dépôt sépare déjà `participations:write` de `participations:delete` au même motif. `athletes:read` s'y ajoute comme **garde d'une donnée personnelle** (FR-025), sur le patron de `users:read` | Un `admin:data` unique : confier le renommage d'une épreuve emporterait le pouvoir d'en supprimer trois mille résultats, et la lecture des dates de naissance de tout le club. Le geste le plus dangereux fixerait le seuil des autres. |
| Deux routes de lecture réservées | Sans elles, deux gestes irréversibles s'exécutent en aveugle : choisir un coureur sans voir ce qui le distingue d'un homonyme, confirmer une destruction dont l'ampleur annoncée est fausse | Réutiliser les lectures publiques : `GET /athletes` ne rend pas `birth_date` (et ne doit pas la rendre — FR-025), `GET /courses/{id}/summary` est un contrat public qu'un besoin d'administration n'a pas à alourdir. |
| Un service `admin_actions.py` plutôt que la logique dans les routes | Les quatre gestes partagent la purge des orphelins et l'écriture du journal ; les inliner dupliquerait quatre fois l'invariant « action et trace indissociables » | Router direct : c'est ce que fait `DELETE /participations/{id}` aujourd'hui (`db.delete` dans la route), et c'est justement l'entorse au Principe II que ce plan ne reproduit pas. |
