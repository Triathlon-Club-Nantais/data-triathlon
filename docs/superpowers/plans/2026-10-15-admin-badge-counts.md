# Pastilles du rail admin en un appel (#1385) Implementation Plan

> **For agentic workers:** executor named by the user: inline, task by task (superpowers:executing-plans style), no fan-out. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Le rail admin obtient ses huit compteurs par un seul `GET /api/v1/admin/badge-counts`, filtré par les pouvoirs de la session.

**Architecture:** Un service `admin_badge_counts.counts(db, codes, validation=...)` ne calcule que les compteurs que les pouvoirs ouvrent, en réutilisant les comptes existants (dont `cached_candidates` via `course_duplicates.count` et `athlete_identity_review.count`, #1384). La route vit dans `api/v1/admin.py`, garde `current_user`, rend un `BadgeCounts` sans les clés absentes. Côté front, `useNavBadges` fait une requête (`useAdminBadgeCounts`), invalidée par toute mutation réussie (même règle que le cache backend : toute écriture le vide).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 sync, pytest ; Next.js 16, TanStack Query, vitest.

**Spec:** issue #1385 (pas de design séparé).

## Global Constraints

- Clés de la réponse = clés de pastille de `nav.config.ts` : `quality`, `duplicates`, `providers`, `feedback` (statut `nouveau`), `identities`, `members`, `volunteer`, `validation`.
- Pouvoir par clé, inchangé : `quality:override`, `courses:sources`, `pending_providers:read`, `feedback:read`, `athletes:write`, `club_members:manage`, `athletes:volunteer_validate` ; `validation` = `benevole_access:manage` ou cookie bénévoles valide.
- `staleTime` de la requête unique : 5 min (le plus long des huit d'aujourd'hui) ; invalidée par `MutationCache.onSuccess`.
- Suppression des `*/count` sans autre consommateur ; `GET /admin/feedback/counts` reste (`FeedbackTable`).
- Git : `/usr/bin/git`, Conventional Commits anglais, aucun trailer.

---

### Task 1: Backend endpoint

**Files:**
- Create: `backend/app/services/admin_badge_counts.py`, `backend/tests/test_api/test_admin_badge_counts_api.py`
- Modify: `backend/app/api/deps.py` (extraire `has_benevole_access`), `backend/app/api/v1/admin.py`, `backend/app/schemas/count.py`

**Interfaces:**
- Produces: `GET /api/v1/admin/badge-counts` → `{"quality"?: int, ...}` ; 401 sans session.

- [ ] Test : un admin (fixture `client`) reçoit les huit clés ; `_session_etroite(client, db_session, "athletes:write")` ne reçoit que `identities` ; anonyme 401.
- [ ] Lancer, voir l'échec (404).
- [ ] Implémenter service, schéma `BadgeCounts` (`int | None = None`, `response_model_exclude_none=True`), route.
- [ ] Lancer, voir le succès. Commit `perf(admin): serve the rail badge counts from one endpoint (#1385)`.

### Task 2: Supprimer les `*/count` orphelins

**Files:** `admin.py`, `admin_course_duplicates.py`, `admin_athlete_identity.py`, `admin_club_members.py`, `admin_volunteer_actions.py`, `benevoles.py`, schémas devenus inutiles, tests qui les appelaient (réécrits sur `/admin/badge-counts`), `docs/api/admin-donnees.md`, `backend/app/api/AGENTS.md`.

- [ ] Réécrire les assertions des tests existants vers `badge-counts`, supprimer les tests de garde propres aux routes retirées (la garde est couverte en Task 1).
- [ ] Supprimer les routes, `uv run pytest -m "not integration"`, `uv run ruff check .`. Commit `refactor(admin)!: drop the per-badge count endpoints (#1385)`.

### Task 3: Front, un appel

**Files:** `frontend/lib/api/client.ts`, `frontend/lib/types.ts`, `frontend/lib/queries/{keys,admin,nav-badges}.ts`, `frontend/app/providers.tsx`, `frontend/components/admin/AdminIndex.tsx`, `frontend/components/layout/AppNav.tsx`, tests `nav-badges.test.tsx`, `AppNav.test.tsx`, `AdminIndex.test.tsx`.

- [ ] Test `nav-badges.test.tsx` : le rail appelle `getAdminBadgeCounts` une seule fois, rien pour un visiteur sans pouvoir d'admin, garde 5 min.
- [ ] Lancer, voir l'échec ; implémenter (`useAdminBadgeCounts`, `useNavBadges(canAdminister)`, `loading: boolean`, invalidation globale, `setQueryData` de #1352 reporté sur la clé unique).
- [ ] Adapter `AppNav.test.tsx`/`AdminIndex.test.tsx` ; `npm test`, `npm run lint`, `npm run build`. Commit `perf(admin): fetch the rail badges in one call (#1385)`.
