# Opposition en libre-service pour un membre rattaché (#1673) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un membre connecté et rattaché à sa fiche masque lui-même ses résultats depuis la « Zone sensible » de `/mon-compte`, avec la même prévisualisation que l'admin et une confirmation explicite. L'opposition créée est celle de l'admin, journalisée avec le membre pour auteur.

**Architecture:** deux routes self-service sous `/auth/me/opposition` (prévisualisation, application), sans corps : l'athlète visé est toujours `user.athlete_id`. Le service réutilise `opposition_service.preview` et `opposition_service.apply` (acteur = le membre). Décision de cadrage : l'application n'est immédiate que si la prévisualisation ne touche **que** la fiche du membre (`athletes == 1`) ; sinon (homonymes) refus « écrivez au club ». Pas de migration. Pas de levée en libre-service.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest ; Next.js 16, React Query, Vitest + RTL.

**Spec:** issue #1673 + cadrage utilisateur (immédiat seulement si la fiche du membre est seule, sinon « écrivez au club » ; geste dans la Zone sensible de Mon compte).

## Global Constraints

- Branche empilée sur `worktree-1663-mon-compte` (PR #1737, page Mon compte) : ne rien modifier de #1663 hors de ce que la tâche demande.
- Copie en français, vouvoiement, aucun tiret comme ponctuation de phrase ; identifiants et noms de tests en anglais.
- `/api/v1` : ajouts seulement (Principe IV).
- Ne pas toucher : `backend/tests/**/conftest.py`, config pytest/vitest, `test/setup.ts`, `ci.yml`, `app/(public_restricted)/mon-espace`, carte d'accueil, guide.
- Le journal s'écrit dans le service (`backend/app/api/AGENTS.md`, #935) ; `opposition_service.apply` commite déjà lui-même.

## Review Focus

- Un membre ne peut jamais viser une autre fiche : pas de corps accepté, l'athlète vient de la session.
- Homonymes (`athletes > 1`) : refus côté serveur, pas seulement côté interface.
- Après application, la session du membre n'a plus de fiche rattachée et l'interface le reflète sans rechargement.
- Le journal porte le membre comme auteur (`opposition.apply`).

---

### Task 1: routes `/auth/me/opposition`

**Files:**
- Modify: `backend/app/services/opposition_service.py` (fonction `apply_for_member(db, user) -> AthleteOpposition`), `backend/app/api/v1/auth.py` (deux routes), `backend/app/schemas/opposition.py` seulement si un schéma manque.
- Test: `backend/tests/test_api/test_my_opposition_api.py` (nouveau) ; les tests d'inventaire de routes qui échouent (`backend/tests/test_auth/test_public_routes_still_open.py`, `test_site_access_gate.py`, `test_permissions_catalogue.py`) s'il le faut.
- Docs: `backend/app/api/AGENTS.md` (liste des lectures « ne portent que sur soi » sous « Protéger une ressource »), `docs/api/admin-donnees.md` section « Droit d'opposition (#334) » (une phrase sur le libre-service #1673).

**Interfaces:**
- Produces:
  - `POST /api/v1/auth/me/opposition/preview` → 200 `OppositionPreviewRead {athletes, results, already_opposed}` pour `user.athlete_id`. 403 si non rattaché.
  - `POST /api/v1/auth/me/opposition` → 204 (en-têtes `NO_STORE_HEADERS`). 403 si non rattaché ; 409 `DomainError` « Votre nom correspond à plusieurs fiches. Écrivez au club pour exercer votre droit d'opposition. » si `athletes != 1`.
  - Les deux : garde `current_user`, sans `require_site_access` (un droit RGPD ne dépend pas du code du site), aucun corps lu.

- [ ] **Step 1: tests qui échouent** (`test_my_opposition_api.py`, sur le modèle de `test_athlete_claims_api.py` / `test_api_delete_me.py`)
  - `test_preview_counts_the_member_own_results` : membre rattaché → `athletes == 1`, `results` = nombre de ses participations.
  - `test_unlinked_member_gets_403` (preview et apply).
  - `test_anonymous_gets_401` (preview et apply).
  - `test_apply_anonymises_and_detaches` : 204 ; fiche supprimée, résultats anonymisés, `user.athlete_id` à `None`, une `AthleteOpposition` créée avec `applied_by_user_id` = le membre et `requested_on` = aujourd'hui (Paris).
  - `test_apply_is_logged_with_the_member_as_author` : ligne `admin_action_log` `action="opposition.apply"`, `actor` = le membre.
  - `test_another_athlete_is_never_touched` : un second athlète (nom différent) et un corps `{"athlete_id": <autre>}` envoyé : l'autre fiche et ses résultats restent intacts.
  - `test_homonyms_are_refused_with_write_to_the_club` : un homonyme du membre existe → preview `athletes == 2`, apply 409 avec le message exact, rien n'est modifié.
- [ ] **Step 2:** `uv run --project backend pytest backend/tests/test_api/test_my_opposition_api.py -n 0` → FAIL.
- [ ] **Step 3: implémenter.** `apply_for_member` : `preview(db, athlete_id=user.athlete_id)` ; si `athletes != 1`, `DomainError` avec le message ci-dessus (vérifier quel statut `DomainError` donne et l'aligner sur 409 comme les autres conflits du fichier) ; sinon `apply(db, user, athlete_id=user.athlete_id, nom=None, prenom=None, requested_on=club_today())`. La route 403 si `user.athlete_id is None`, comme les autres routes `/auth/me/*` qui l'exigent.
- [ ] **Step 4:** le fichier passe, puis `uv run --project backend pytest -m "not integration" backend/tests/test_api backend/tests/test_auth backend/tests/test_services -q`, `uv run --project backend ruff check backend`.
- [ ] **Step 5: commit** `feat(rgpd): let a linked member oppose publication of their own results (#1673)`

### Task 2: geste « Masquer mes résultats » dans Mon compte

**Files:**
- Modify: `frontend/lib/api/client.ts` (`previewMyOpposition`, `applyMyOpposition`), `frontend/lib/queries/auth.ts` (mutation sur le modèle de `useDetachAthlete` / `useSessionMutation`, qui invalide aussi les requêtes de résultats comme `useApplyOpposition` dans `lib/queries/admin.ts`), `frontend/components/auth/AccountPage.tsx` (Zone sensible), `frontend/components/legal/content/confidentialite.tsx` (passage « vous opposer à la présence de vos résultats », ~l.226).
- Test: `frontend/components/auth/AccountPage.test.tsx`, `frontend/components/legal/content/confidentialite.test.tsx`.

**Interfaces:**
- Consumes: Task 1.

- [ ] **Step 1: tests qui échouent**
  - membre rattaché : la Zone sensible propose « Masquer mes résultats » ; non rattaché : le bouton est absent.
  - clic : la prévisualisation est demandée ; tant qu'elle n'est pas arrivée, l'action est bloquée (`actionBloquee`) ; avec `athletes == 1`, la boîte annonce le nombre de résultats anonymisés, la suppression de la fiche et du rattachement, et que seule le club peut lever l'opposition ; confirmer appelle `applyMyOpposition`, puis la page n'affiche plus de fiche rattachée et un message de succès s'affiche.
  - `athletes > 1` : la boîte n'offre pas de confirmation et dit d'écrire au club (lien `mailto` ou page contact existante, reprendre celle que cite déjà la politique de confidentialité).
  - échec de l'application : message d'erreur en `--tcn-danger-text` (`role="alert"`), comme les autres erreurs de la page.
  - politique de confidentialité : le passage sur l'opposition dit qu'un membre rattaché à sa fiche peut l'exercer lui-même depuis la page Mon compte, et que la levée passe par le club.
- [ ] **Step 2:** `npm --prefix frontend test -- components/auth components/legal` → FAIL.
- [ ] **Step 3: implémenter** avec `DangerConfirm` comme les deux gestes déjà présents dans la page ; même ordre de cartes, bouton dans la Zone sensible avant « Supprimer mon compte ». `updatedAt` de la politique reste `2026-10-20` (même jour).
- [ ] **Step 4:** `npm --prefix frontend test -- components/auth components/legal`, puis `npm --prefix frontend test`, `npm --prefix frontend run lint`, `npm --prefix frontend run build`.
- [ ] **Step 5: commit** `feat(rgpd): add the hide-my-results gesture to Mon compte (#1673)`
