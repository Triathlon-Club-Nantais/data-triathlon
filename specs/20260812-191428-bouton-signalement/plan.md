# Implementation Plan: Bouton de signalement (bug / feedback)

**Branch**: `feat/267-bouton-signalement` | **Date**: 2026-08-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/20260812-191428-bouton-signalement/spec.md` (issue #267)

## Summary

Ouvrir un canal de retour à faible friction — un bouton flottant public, sans
compte requis — qui atterrit dans une nouvelle section « Retours utilisateurs »
du panel admin, avec liste triable, vue détail et changement de statut.

L'approche s'appuie sur un précédent direct déjà en place : `POST
/admin/pending-providers` (`app/api/v1/admin.py`) est **exactement** le même
patron — un formulaire public non gardé, sous le préfixe `/admin/`, à côté de
lectures et d'écritures gardées chacune par leur propre pouvoir
(`require_permission`). Ce dossier réplique ce patron pour une seconde
ressource plutôt que d'en inventer un troisième. Le socle d'habilitation
(#115) fournit `require_permission` et l'ajout de pouvoirs n'y coûte aucune
migration (`core/permissions.py`, dataclasses gelées).

Ce qui est neuf : **une table** (`user_feedback`) avec sa migration, **un
module de routes** (`admin_feedback.py`, quatre routes dont une publique),
**un service** (`feedback_service.py` — honeypot, limitation de débit,
transitions de statut), **deux pouvoirs**, **un composant public** (bouton +
formulaire, `components/tcn/`) monté dans `app/layout.tsx`, et **une page
admin** (`admin/retours-utilisateurs`).

Aucune intégration GitHub par API n'est construite (hors périmètre v1,
explicite dans l'issue) : l'action « Promouvoir » est une construction d'URL
`github.com/{repo}/issues/new?...` côté frontend, `{repo}` étant la même
valeur littérale que `settings.github_repository` — déjà présent côté backend
pour une autre feature (déclenchement de batches, `services/batch_runs.py`) —
dupliquée dans une constante frontend dédiée (`frontend/lib/github.ts`), sur
le patron déjà tranché par `CLUB_NAME` (`frontend/lib/club.ts`) : sans appel
réseau ni endpoint créé pour relayer une chaîne statique.

## Technical Context

**Language/Version**: Python 3.13 (backend, `uv`), TypeScript 5 / Node (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ; Next.js 16 App Router, TanStack Query, shadcn/ui (`@base-ui/react` dialog), Tailwind

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en test — nouvelle table `user_feedback`

**Testing**: pytest (`-m "not integration"`, sans réseau), vitest côté front

**Target Platform**: Render (API) + Vercel (front)

**Project Type**: application web — backend et frontend séparés dans le même dépôt

**Performance Goals**: aucun objectif de débit. Volume attendu de l'ordre de
quelques signalements par semaine pour un club ; la limitation de débit
anti-spam vise des pics automatisés, pas une charge normale.

**Constraints**: formulaire de création accessible sans authentification
(Principe V n'est pas concerné, ce n'est pas un paramètre de filtrage) ;
aucune session SQLAlchemy hors de `repositories/` (Principe II) ; tests sans
réseau (Principe III) ; aucun appel réseau sortant vers l'API GitHub (hors
périmètre v1, cf. issue) ; une seule migration, relue à la main.

**Scale/Scope**: base d'un club — volume de signalements modeste. Quatre
routes (1 création publique + 3 gardées), 1 table, 2 pouvoirs, 1 composant
public, 1 page admin.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | UI du formulaire, libellés de statut (« nouveau », « en cours », « traité », « ignoré ») et messages d'erreur affichés en **français** ; identifiants (`UserFeedback`, `feedback_service`, `FEEDBACK_READ`), colonnes DB, noms de tests et logs en **anglais**. Aucun mot métier gelé par contrat public n'est concerné ici (table neuve). |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `admin_feedback.py` valide et délègue ; `feedback_service.py` porte le honeypot, la limitation de débit et les transitions de statut sans toucher `Session` — la requête de comptage par IP et les écritures vivent dans `feedback_repository.py`. Même patron que `admin.py` / `admin_actions.py`. |
| III | TDD sans réseau (non-négociable) | ✅ | Aucun appel réseau : la construction du lien GitHub est une chaîne de caractères, pas une requête. Chaque route, chaque refus (honeypot, débit dépassé, permission absente) a son test écrit avant. |
| IV | Contrats API et CLI stables | ✅ | Strictement additif sous `/api/v1/admin/*` (nouvelles routes). Aucun contrat existant modifié ; `GET /admin/permissions` gagne des entrées (extension d'inventaire, pas rupture, même précédent que #117). |
| V | Neutralité par défaut des paramètres transverses | N/A | La feature n'ajoute et ne consomme aucun des paramètres transverses existants (`scope`, `federal_only`, `seasons`). |
| VI | Simplicité / YAGNI | ✅ | Limitation de débit par simple requête de comptage sur la table déjà nécessaire (aucune dépendance nouvelle type `slowapi` — aucune n'existe dans le dépôt, cf. research.md §D1) ; pas de GitHub App ni d'appel API GitHub (explicitement écarté par l'issue) ; pas d'endpoint créé pour relayer `settings.github_repository`, dupliqué en constante frontend sur le patron déjà tranché par `CLUB_NAME` (research.md §D3). |

Un principe en ⚠️ doit être justifié dans « Complexity Tracking » ci-dessous
avec l'alternative rejetée et la raison. Un principe violé sans justification
bloque le passage à `/speckit-tasks`.

**Re-check après Phase 1** : les artefacts de design (data-model, contrats,
quickstart) ne modifient aucun statut ci-dessus. Aucune ligne de Complexity
Tracking n'a été nécessaire.

## Project Structure

### Documentation (this feature)

```text
specs/20260812-191428-bouton-signalement/
├── spec.md              # /speckit-specify
├── plan.md              # ce fichier
├── research.md          # Phase 0 — décisions techniques
├── data-model.md        # Phase 1 — UserFeedback + invariants
├── quickstart.md        # Phase 1 — validation de bout en bout
├── contracts/
│   └── feedback-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks — non créé par /speckit-plan
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/v1/
│   │   ├── admin_feedback.py               # NOUVEAU — 4 routes (1 publique, 3 gardées)
│   │   └── router.py                       # + admin_feedback dans la boucle de montage
│   ├── core/
│   │   └── permissions.py                  # + FEEDBACK_READ, FEEDBACK_MANAGE, + FEATURE_FEEDBACK
│   ├── models/
│   │   └── user_feedback.py                # NOUVEAU
│   ├── repositories/
│   │   └── feedback_repository.py          # NOUVEAU — create, list, get, update_status,
│   │                                       #   set_github_url, count_recent_by_ip
│   ├── schemas/
│   │   └── feedback.py                     # NOUVEAU — FeedbackCreate/Read/StatusUpdate/GithubUrlUpdate
│   └── services/
│       └── feedback_service.py             # NOUVEAU — honeypot, rate-limit, transitions
├── alembic/versions/
│   └── <rev>_user_feedback.py              # NOUVEAU — 1 table, index (status, created_at)
└── tests/
    ├── test_api/test_admin_feedback_api.py       # NOUVEAU
    ├── test_services/test_feedback_service.py     # NOUVEAU
    └── test_repositories/test_feedback_repository.py  # NOUVEAU

frontend/
├── app/
│   ├── layout.tsx                          # + montage du bouton flottant global
│   └── admin/retours-utilisateurs/
│       ├── page.tsx                        # NOUVEAU — couverte par le layout /admin
│       └── page.test.tsx                   # NOUVEAU
├── components/
│   ├── tcn/
│   │   └── FeedbackButton.tsx              # NOUVEAU + .test.tsx — bouton flottant + formulaire
│   │                                       #   (compose ui/dialog, patron « AppNav + ui/sheet »)
│   └── admin/
│       ├── FeedbackTable.tsx               # NOUVEAU + .test.tsx — liste triable
│       └── FeedbackDetailDialog.tsx        # NOUVEAU + .test.tsx — détail + statut + promotion
├── components/layout/
│   └── nav.config.ts                       # + entrée « Retours utilisateurs », permission dédiée
└── lib/
    ├── api/client.ts                       # + submitFeedback, + 3 méthodes admin
    ├── queries/admin.ts                    # + lecture liste/détail, + mutations statut/URL
    ├── queries/keys.ts                     # + clés d'invalidation
    ├── types.ts                            # + types Feedback*
    └── github.ts                           # NOUVEAU — GITHUB_REPOSITORY, patron `lib/club.ts`
```

**Structure Decision**: application web existante (backend/ + frontend/,
Option « web application »). Aucune nouvelle app, aucun nouveau projet — la
feature s'insère dans les couches et dossiers déjà en place, en répliquant le
patron « formulaire public sous `/admin/` + lectures/écritures gardées » déjà
établi par #115 (`pending-providers`).

## Complexity Tracking

*Aucune ligne — aucune violation de la Constitution Check ci-dessus.*
