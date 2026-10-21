# Demande d'adhésion au club : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un compte connecté non adhérent demande à rejoindre le TCN ; un administrateur valide (l'adresse rejoint `member_emails`) ou refuse ; le rattachement de fiche devient réservé aux adhérents.

**Architecture:** une table `member_requests` (patron `athlete_claims`, avec `organisation_id`), un service `services/member_requests.py`, deux routes côté compte sous `/auth/me/member-request`, trois routes admin sous `/admin/member-requests`, une permission `member_requests:review`, une pastille. Côté front : une carte « Adhésion au club » sur `/mon-compte` (seul formulaire), des liens vers elle depuis Mon espace, la fiche athlète et l'écran du code ; la file sur `/admin/adresses-adherents`.

**Tech Stack:** FastAPI, SQLAlchemy 2 (sync), Alembic, Pydantic v2, pytest ; Next.js 16, TanStack Query, vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-demande-adhesion-design.md` (issue #1785).

## Global Constraints

- TDD : chaque tâche écrit son test, le voit échouer, puis code.
- Couches `api → services → repositories → DB` ; seuls les repositories construisent des requêtes.
- Identifiants, tests, docstrings techniques en anglais ; UI et messages `DomainError` en français.
- Aucun endpoint `/api/v1` existant n'est modifié en contrat, sauf ajout de champs ; `POST /auth/me/athlete-claim` change de garde (décision du design).
- Migration : `down_revision = "c38bc1342485"` ; avant la PR, rebase sur `origin/main`, une seule tête (`uv run alembic heads`). Rebase seulement, jamais de merge de `main` dans la branche.
- Commits Conventional, suffixe `(#1785)`, sans trailer `Co-Authored-By`.
- Pas de tiret de ponctuation (—, –) dans le code ni les textes.
- Commandes backend depuis `backend/` : `uv run pytest -m "not integration" <cible>`, `uv run ruff check .`. Front depuis `frontend/` : `npx vitest run <fichier>`, `npm run lint`, `npx tsc --noEmit`.

## Contrat d'API (figé, partagé par les tâches back et front)

```
POST   /auth/me/member-request          body MemberRequestCreate  → 201 MemberRequestRead
DELETE /auth/me/member-request          → 204 (supprime la demande EN ATTENTE seulement)
GET    /auth/me                         + champ member_request: MemberRequestRead | null
GET    /admin/member-requests           → 200 list[MemberRequestReviewRead]   (member_requests:review)
POST   /admin/member-requests/{id}/approve → 204                              (member_requests:review)
POST   /admin/member-requests/{id}/reject  → 204                              (member_requests:review)
GET    /admin/badge-counts              + clé member_requests: int | null

MemberRequestCreate  { first_name: str, last_name: str, birth_date: date | null, phone: str | null }
MemberRequestRead    { id, status: "pending"|"rejected", first_name, last_name, birth_date, phone,
                       created_at: UtcDatetime, decided_at: UtcDatetime | null }
MemberRequestReviewRead { id, created_at, first_name, last_name, birth_date, phone, user: ClaimantRead }
```

Erreurs de `POST /auth/me/member-request` :
- 422 : prénom ou nom vide après `strip`, plus de 100 caractères ; ni `birth_date` ni `phone` ; `birth_date` future ou avant 1900-01-01 ; `phone` hors `^[0-9+ .()-]{6,32}$` après `strip`.
- 409 `AlreadyMemberError` : « Votre compte est déjà reconnu adhérent. »
- 409 `RejectedRecentlyError` : « Votre demande a été refusée. Vous pourrez en envoyer une nouvelle à partir du JJ/MM/AAAA. » (date = `decided_at + 30 jours`).
- Une demande en attente est remplacée (nouveaux champs, nouvelle `created_at`).

## Review Focus

1. Double clic sur « Envoyer » : deux POST simultanés ne donnent jamais un 500 (upsert `ON CONFLICT`, test Task 2).
2. Deux administrateurs valident et refusent la même demande : un seul geste passe, l'autre reçoit 404 (`get_pending` verrouillé, test Task 2).
3. Une personne refusée envoie `DELETE` puis `POST` pour contourner les 30 jours : `DELETE` ne supprime que l'attente (test Task 2).
4. L'adresse devient adhérente (import AssoConnect) pendant que la demande attend : la validation réussit quand même, sans 409 (test Task 2).
5. Suppression du compte avec une demande : la demande part avec lui (test Task 1).

## Ordre et parallélisme

- Vague 1, en parallèle : Task 1 (données), Task 4 (garde du rattachement), Task 6 (front compte), Task 7 (front admin). Les tâches front codent contre le contrat ci-dessus et des réponses simulées.
- Vague 2, en parallèle : Task 2 (service + routes compte), Task 5 (rétention + politique), après Task 1.
- Vague 3 : Task 3 (permission, routes admin, pastille, doc), après Task 2.
- Fin : `uv run pytest -m "not integration"`, `npm test`, `npm run lint`, `npm run build`.

Tâches parallèles : chacune ne `git add` que ses propres fichiers.

---

### Task 1: Table `member_requests`, modèle, repository, migration

**Files:**
- Create: `backend/app/models/member_request.py`
- Modify: `backend/app/models/__init__.py` (export), `backend/app/models/user.py` (relation)
- Create: `backend/app/repositories/member_request_repository.py`
- Modify: `backend/app/repositories/__init__.py` si les repositories y sont listés
- Create: `backend/alembic/versions/<rev>_member_requests_1785.py` (`uv run alembic revision --autogenerate -m "member requests (#1785)"`, puis compléter à la main la partie données)
- Test: `backend/tests/test_repositories/test_member_request_repository.py` (ou le dossier où vit `test_athlete_claim_repository`, s'il existe), `backend/tests/test_migrations.py`

**Interfaces:**
- Produces:
  - `models.member_request`: `STATUS_PENDING = "pending"`, `STATUS_REJECTED = "rejected"`, `class MemberRequest` (table `member_requests`) : `id`, `user_id` (FK `users.id`), `organisation_id` (FK `organisations.id`, non nul), `first_name: str` (String(100)), `last_name: str` (String(100)), `birth_date: date | None`, `phone: str | None` (String(32)), `status` (String(16), index), `created_at`, `decided_at: datetime | None`, `user` relation. `UniqueConstraint("user_id", "organisation_id", name="uq_member_request_user_organisation")`.
  - `User.member_requests: Mapped[list["MemberRequest"]]`, `cascade="all, delete-orphan"` (même esprit que `User.athlete_claim`).
  - `member_request_repository`:
    - `get_for_user(db, user_id: int, organisation_id: int) -> MemberRequest | None`
    - `get_pending(db, request_id: int) -> MemberRequest | None` (`with_for_update`, `populate_existing`, comme `athlete_claim_repository.get_pending`)
    - `upsert_pending(db, *, user_id: int, organisation_id: int, first_name: str, last_name: str, birth_date: date | None, phone: str | None) -> MemberRequest` (un seul `dialect_insert ... on_conflict_do_update(index_elements=[user_id, organisation_id])`, comme `athlete_claim_repository.replace_pending`)
    - `reject(db, request: MemberRequest, *, now: datetime) -> None`
    - `delete_request(db, request: MemberRequest) -> None`
    - `delete_pending_for_user(db, user_id: int, organisation_id: int) -> None`
    - `list_pending(db, organisation_id: int) -> list[MemberRequest]` (`selectinload(user)`, tri `created_at, id`)
    - `count_pending(db, organisation_id: int) -> int`
    - `delete_rejected_before(db, cutoff: datetime) -> int` et `delete_pending_before(db, cutoff: datetime) -> int` (comptent sans supprimer si appelées via un `count_*` équivalent : suivre la forme `dry_run` de `retention_service`, qui appelle des fonctions `count_*`/`delete_*` ; ajouter `count_rejected_before` et `count_pending_before` si c'est sa forme).
- Migration : crée la table, puis insère dans `role_permissions` une ligne `member_requests:review` pour chaque `role_id` qui porte déjà `member_emails:manage` (lire les colonnes de `models/role_permission.py`). `downgrade` supprime ces lignes puis la table.

- [ ] **Step 1: Write the failing tests**

```python
def test_upsert_pending_replaces_the_previous_request(db_session, user, tcn):
    first = member_request_repository.upsert_pending(db_session, user_id=user.id, organisation_id=tcn.id,
        first_name="Ana", last_name="Lopez", birth_date=None, phone="0601020304")
    second = member_request_repository.upsert_pending(db_session, user_id=user.id, organisation_id=tcn.id,
        first_name="Ana", last_name="López", birth_date=date(1990, 5, 1), phone=None)
    assert second.id == first.id
    assert (second.last_name, second.birth_date, second.phone, second.status) == ("López", date(1990, 5, 1), None, "pending")

def test_upsert_pending_resets_a_rejected_request(...):  # status back to pending, decided_at None

def test_list_pending_and_count_skip_rejected(...):  # 2 pending + 1 rejected → list of 2, count 2

def test_delete_pending_for_user_keeps_a_rejected_request(...):

def test_deleting_the_account_deletes_its_requests(...):  # db.delete(user); flush → no row left

def test_member_requests_table_up_and_down(sqlite_url):  # in test_migrations.py
    # upgrade head: columns == {"id","user_id","organisation_id","first_name","last_name",
    #   "birth_date","phone","status","created_at","decided_at"}
    # a role holding member_emails:manage before upgrade also holds member_requests:review after
    # downgrade "c38bc1342485": table gone, no role_permissions row with member_requests:review
```

- [ ] **Step 2: Run, expect FAIL** : `uv run pytest -m "not integration" tests/test_repositories/test_member_request_repository.py tests/test_migrations.py -k member_request -n 0` → ImportError / table absente.
- [ ] **Step 3: Implement** le modèle, la relation, le repository et la migration ci-dessus.
- [ ] **Step 4: Run, expect PASS** (même commande), puis `uv run alembic heads` → une seule tête, la nouvelle révision.
- [ ] **Step 5: Commit** : `feat(members): store join requests per account and organisation (#1785)`

---

### Task 2: Service et routes côté compte

**Files:**
- Create: `backend/app/services/member_requests.py`
- Create: `backend/app/schemas/member_request.py`
- Modify: `backend/app/api/v1/auth.py` (deux routes, champ `member_request` de `/auth/me`), `backend/app/schemas/auth.py` (`SessionUserRead.member_request`), `backend/app/services/account_export.py` + `backend/app/schemas/account_export.py` (la demande figure dans l'export RGPD)
- Test: `backend/tests/test_services/test_member_requests.py`, `backend/tests/test_api/test_member_requests_api.py`

**Interfaces:**
- Consumes: Task 1 (`member_request_repository`, `MemberRequest`), `membership.is_member`, `role_repository.default_organisation`, `member_emails_service.add` et `AlreadyListedError`, `core.season.current_season`, `services.audit.record`.
- Produces:
  - `REQUEST_AGAIN_AFTER = timedelta(days=30)` (lu aussi par Task 5).
  - `class AlreadyMemberError(DomainError)` (409), `class RejectedRecentlyError(DomainError)` (409, message avec la date, voir Contrat).
  - `current_for(db, user: User) -> MemberRequest | None` (organisation par défaut)
  - `request_membership(db, user: User, data: MemberRequestCreate, *, now: datetime) -> MemberRequest`
  - `cancel_pending(db, user: User) -> None`
  - `list_pending(db) -> list[MemberRequest]`
  - `approve(db, request_id: int, *, actor_id: int) -> None` : `member_emails_service.add(db, email=request.user.email, season=current_season(), user_id=actor_id)`, `AlreadyListedError` absorbée, puis suppression, puis `audit.record(action="member_request.approve", entity_type="user", entity_id=user_id, payload={"request_id": ...})`. Pas de prénom, nom, date ni téléphone dans le payload du journal.
  - `reject(db, request_id: int, *, actor_id: int) -> None` : `action="member_request.reject"`.
  - Une demande absente ou plus en attente : `NotFoundError("Cette demande n'est plus en attente.")`.
  - Schémas `MemberRequestCreate` (validation du Contrat, `model_validator` pour « au moins l'un des deux »), `MemberRequestRead`, `MemberRequestReviewRead` (réutilise `ClaimantRead` de `schemas/athlete_claim.py`).
  - Routes : `POST /auth/me/member-request` (201, `current_user`, sans garde du site : l'écran du code doit pouvoir y mener), `DELETE /auth/me/member-request` (204, `NO_STORE_HEADERS` comme `cancel_athlete_claim`).

- [ ] **Step 1: Write the failing tests**

```python
# services
def test_a_member_cannot_ask(...):              # is_member True → AlreadyMemberError
def test_a_pending_request_is_replaced(...):
def test_rejected_less_than_30_days_ago_refuses_with_the_date(...):
    # decided_at = now - 29 days → RejectedRecentlyError, message contains (decided_at + 30 days) as "%d/%m/%Y"
def test_rejected_30_days_ago_can_ask_again(...):  # status back to pending
def test_cancel_keeps_a_rejected_request(...):     # Review Focus 3
def test_approve_adds_the_address_for_the_current_season_and_deletes_the_request(...):
    # member_email_repository.counts(db, user.email, today) is True; current_for() is None; audit action "member_request.approve"
def test_approve_succeeds_when_the_address_is_already_listed(...):  # Review Focus 4
def test_approve_then_reject_the_same_request_raises_not_found(...):  # Review Focus 2
def test_reject_sets_status_and_decided_at(...):

# API
def test_post_member_request_returns_201_and_shows_in_auth_me(client, ...):
def test_post_member_request_requires_birth_date_or_phone(client, ...):   # 422
def test_post_member_request_rejects_a_future_birth_date(client, ...):    # 422
def test_post_member_request_twice_never_500(client, ...):                # Review Focus 1: two POSTs → 201, 201, one row
def test_post_member_request_is_anonymous_401(client):
def test_delete_member_request_returns_204(client, ...):
def test_account_export_includes_the_member_request(client, ...):
```

- [ ] **Step 2: Run, expect FAIL** : `uv run pytest -m "not integration" tests/test_services/test_member_requests.py tests/test_api/test_member_requests_api.py`
- [ ] **Step 3: Implement** le service, les schémas et les routes.
- [ ] **Step 4: Run, expect PASS** (même commande), plus `tests/test_api/test_auth*.py` pour `/auth/me`.
- [ ] **Step 5: Commit** : `feat(members): let a non-member ask to join the club from their account (#1785)`

---

### Task 3: Permission, file d'administration, pastille, doc

**Files:**
- Modify: `backend/app/core/permissions.py` (`P.MEMBER_REQUESTS_REVIEW`, ajouté à `ALL` après `ATHLETE_CLAIMS_REVIEW`)
- Create: `backend/app/api/v1/admin_member_requests.py`
- Modify: `backend/app/api/v1/router.py` (inclusion, sous la garde du site comme les autres `admin_*`)
- Modify: `backend/app/services/admin_badge_counts.py`, `backend/app/schemas/count.py` (`member_requests: int | None = None`)
- Modify: `docs/auth/membres.md` (section « Demande d'adhésion » : qui demande, ce que valide fait, durées)
- Test: `backend/tests/test_api/test_admin_member_requests_api.py`, tests existants du catalogue (`tests/test_core/test_permissions.py`, `tests/test_permissions_catalogue.py`)

**Interfaces:**
- Consumes: Task 2 (`member_requests.list_pending/approve/reject`, `MemberRequestReviewRead`), Task 1 (`member_request_repository.count_pending`).
- Produces:
  - `MEMBER_REQUESTS_REVIEW = Permission("member_requests:review", "Valider les demandes d'adhésion", "Voir les demandes d'adhésion des comptes non adhérents (nom, date de naissance ou téléphone, adresse) et les valider ou les refuser. Valider ajoute l'adresse à la liste des adhérents de la saison.", FEATURE_MEMBER_EMAILS)`
  - Pastille `"member_requests": (P.MEMBER_REQUESTS_REVIEW.code, lambda db: member_request_repository.count_pending(db, <organisation par défaut>.id))`.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_member_requests_needs_the_permission(client, ...):     # 403 without, 200 with "member_requests:review"
def test_list_member_requests_returns_pending_only_with_the_account(client, ...):
def test_approve_member_request_returns_204_and_makes_a_member(client, ...):  # then GET /auth/me as the requester: is_member True
def test_reject_member_request_returns_204(client, ...):
def test_approve_unknown_request_returns_404(client, ...):
def test_badge_counts_include_member_requests_for_a_reviewer(client, ...):   # {"member_requests": 1}
```

- [ ] **Step 2: Run, expect FAIL** : `uv run pytest -m "not integration" tests/test_api/test_admin_member_requests_api.py`
- [ ] **Step 3: Implement** (routeur fin sur le modèle d'`admin_athlete_claims.py` : le service journalise, le routeur commite).
- [ ] **Step 4: Run, expect PASS**, puis `uv run pytest -m "not integration" tests/test_core/test_permissions.py tests/test_permissions_catalogue.py` (le catalogue exige que chaque pouvoir garde une ressource et porte son français).
- [ ] **Step 5: Commit** : `feat(members): review join requests in the back-office (#1785)`

---

### Task 4: Rattachement réservé aux adhérents

**Files:**
- Modify: `backend/app/api/deps.py` (nouvelle dépendance `require_member`), `backend/app/api/v1/auth.py:375-391` (`POST /auth/me/athlete-claim`)
- Test: `backend/tests/test_api/test_athlete_claims_api.py`

**Interfaces:**
- Produces: `require_member(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User` ; lève `NotMemberError(DomainError)` 403, message « Réservé aux adhérents du club : demandez d'abord à rejoindre le club depuis Mon compte. »
- `POST /auth/me/athlete-claim` remplace `dependencies=[Depends(require_site_access)]` par `user: User = Depends(require_member)` ; garder le commentaire sur l'énumération des fiches, adapté (un adhérent passe aussi la garde du site).

- [ ] **Step 1: Write the failing tests**

```python
def test_claim_by_a_non_member_with_the_site_code_is_403(client, ...):
def test_claim_by_a_member_still_returns_201(client, ...):
def test_a_pending_claim_of_a_non_member_can_still_be_approved(client, ...):
```

Adapter les tests existants qui créaient une demande avec le seul code d'accès : leur compte doit devenir adhérent (adresse dans `member_emails`).

- [ ] **Step 2: Run, expect FAIL** : `uv run pytest -m "not integration" tests/test_api/test_athlete_claims_api.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS**, plus `tests/test_api/test_result_claims_api.py` et `tests/test_services/test_athlete_claims.py`.
- [ ] **Step 5: Commit** : `feat(auth): reserve the athlete claim to club members (#1785)`

---

### Task 5: Rétention et politique de confidentialité

**Files:**
- Modify: `backend/app/services/retention_service.py` (`RetentionOutcome.member_requests_rejected`, `member_requests_pending`), `backend/app/cli/reports.py` (`render_retention_report`)
- Modify: `frontend/components/legal/content/confidentialite.tsx` (+ son test)
- Test: `backend/tests/test_services/test_retention_service.py`, le test CLI de `purge-retention` s'il fige la sortie, `frontend/components/legal/content/confidentialite.test.tsx`

**Interfaces:**
- Consumes: Task 1 (`delete_rejected_before`, `delete_pending_before` et leurs `count_*`), Task 2 (`REQUEST_AGAIN_AFTER`).
- Produces: `PENDING_MEMBER_REQUEST_RETENTION = timedelta(days=183)` ; refus purgés quand `decided_at < now - REQUEST_AGAIN_AFTER`, attentes quand `created_at < now - PENDING_MEMBER_REQUEST_RETENTION`.
- Politique : dans la section des durées, une entrée « Demandes d'adhésion (prénom, nom, date de naissance ou téléphone, adresse e-mail) : supprimées à la validation ou à l'annulation ; 30 jours après un refus ; 6 mois sans décision. » Finalité : vérifier la demande et recontacter la personne.

- [ ] **Step 1: Write the failing tests**

```python
def test_purge_deletes_requests_rejected_more_than_30_days_ago(...):   # 31 days → deleted, 29 days → kept
def test_purge_deletes_requests_pending_for_more_than_6_months(...):   # 184 days → deleted, 182 → kept
def test_purge_dry_run_counts_member_requests_without_deleting(...):
```

```ts
it("annonce la durée de conservation des demandes d'adhésion", () => {
  // render; expect text matching /Demandes d'adhésion/ and /6 mois sans décision/
});
```

- [ ] **Step 2: Run, expect FAIL** : `uv run pytest -m "not integration" tests/test_services/test_retention_service.py` ; `npx vitest run components/legal/content/confidentialite.test.tsx`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS** (mêmes commandes, plus les tests de `purge-retention` sous `tests/test_cli`).
- [ ] **Step 5: Commit** : `feat(rgpd): purge join requests and announce their retention (#1785)`

---

### Task 6: Front, côté compte

**Files:**
- Modify: `frontend/lib/types.ts` (`MemberRequest`, `SessionUser.member_request: MemberRequest | null`), `frontend/lib/api/client.ts` (`requestMembership(body)`, `cancelMembershipRequest()`), `frontend/lib/queries/auth.ts` (`useRequestMembership`, `useCancelMembershipRequest` via `useSessionMutation`)
- Create: `frontend/components/auth/MemberRequestCard.tsx` (+ `.test.tsx`)
- Modify: `frontend/components/auth/AccountPage.tsx` (carte rendue sous « Mes informations » quand `!session.is_member`, ancre `id="adhesion"`)
- Modify: `frontend/components/mon-espace/InvitationMonEspace.tsx` (+ test)
- Modify: `frontend/components/site-access/SiteAccessGate.tsx:95-99` (+ test)
- Modify: le rendu de `AthleteClaimAction` sur la fiche (`frontend/app/(public_restricted)/athletes/[id]/page.tsx` ou son composant) (+ `page.test.tsx`)

**Interfaces:**
- Consumes: le Contrat d'API ; `CLUB_NAME_SHORT` (`frontend/lib/club.ts`).
- Textes figés :
  - Titre de carte : « Adhésion au club ».
  - Aide : « Ces informations permettent au club de vérifier votre demande ou de vous recontacter. Indiquez votre date de naissance ou votre téléphone. »
  - Champs : « Prénom », « Nom », « Date de naissance » (`type="date"`), « Téléphone » (`type="tel"`, `autoComplete="tel"`).
  - Bouton : « Demander à rejoindre le {CLUB_NAME_SHORT} ».
  - En attente : « Votre demande d'adhésion est en attente : un administrateur du club la valide. » + bouton secondaire « Annuler la demande ».
  - Refusée : le message 409 du serveur si renvoi trop tôt ; sinon « Votre précédente demande a été refusée. » au-dessus du formulaire.
  - Mon espace, compte connecté non adhérent sans fiche : « Mon espace est réservé aux adhérents du club. » + lien « Demander à rejoindre le club » vers `/mon-compte#adhesion`. Un adhérent garde l'invitation actuelle au rattachement.
  - Écran du code, `non-adherent` : « Votre compte n'est pas reconnu comme adhérent : saisissez le code d'accès ou » + lien « demandez à rejoindre le club » vers `/mon-compte#adhesion`.
  - Fiche athlète, connecté non adhérent : pas de « C'est moi » ; à la place le lien « Rejoindre le club pour rattacher votre fiche » vers `/mon-compte#adhesion`.
- Validation côté client : prénom, nom requis ; au moins date ou téléphone (message « Indiquez votre date de naissance ou votre téléphone. ») ; les erreurs serveur s'affichent dans une `Alert` `role="alert"`, comme `AthleteClaimAction`.

- [ ] **Step 1: Write the failing tests** (vitest + Testing Library, `apiClient` simulé comme dans les tests voisins)

```ts
// MemberRequestCard.test.tsx
it("envoie prénom, nom et téléphone", ...)            // requestMembership called with {first_name, last_name, birth_date: null, phone}
it("refuse l'envoi sans date de naissance ni téléphone", ...)  // message shown, no call
it("montre l'attente et permet d'annuler", ...)       // member_request.status "pending"
it("affiche le refus du serveur", ...)                // 409 message in role="alert"
// InvitationMonEspace.test.tsx
it("invite un non-adhérent à rejoindre le club", ...) // link href "/mon-compte#adhesion"
it("garde l'invitation au rattachement pour un adhérent", ...)
// SiteAccessGate test
it("mène un connecté non adhérent vers la demande d'adhésion", ...)
// athletes/[id]/page.test.tsx
it("ne propose pas « C'est moi » à un non-adhérent", ...)
```

- [ ] **Step 2: Run, expect FAIL** : `npx vitest run components/auth components/mon-espace components/site-access "app/(public_restricted)/athletes"`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS** (même commande), puis `npx tsc --noEmit` et `npm run lint`.
- [ ] **Step 5: Commit** : `feat(frontend): ask to join the club from the account page (#1785)`

---

### Task 7: Front, file d'administration

**Files:**
- Modify: `frontend/lib/types.ts` (`MemberRequestReview`, `AdminBadgeCounts.member_requests`), `frontend/lib/api/client.ts` (`getMemberRequests`, `approveMemberRequest(id)`, `rejectMemberRequest(id)`), `frontend/lib/queries/admin.ts` (`useMemberRequests`, mutations qui invalident aussi la liste `member_emails` et `adminBadgeCounts`)
- Create: `frontend/components/admin/MemberRequestsTable.tsx` (+ `.test.tsx`), sur le modèle d'`AthleteClaimsTable`
- Modify: `frontend/app/admin/adresses-adherents/page.tsx` (la file au-dessus de `MemberEmailsPanel`, titre « Demandes d'adhésion », rendue seulement si la session porte `member_requests:review`)
- Modify: `frontend/components/layout/nav.config.ts` (`badge: "member_requests"` sur `a-adresses-adherents`) et le type des clés de pastille s'il est déclaré (`lib/queries/nav-badges.ts`)

**Interfaces:**
- Consumes: le Contrat d'API.
- Colonnes : Nom (prénom nom), Date de naissance (format `JJ/MM/AAAA` ou « Non renseignée »), Téléphone (ou « Non renseigné »), Adresse du compte, Demandée le ; actions « Valider » et « Refuser ».
- Vide : « Aucune demande d'adhésion en attente. »

- [ ] **Step 1: Write the failing tests**

```ts
it("liste les demandes avec la date de naissance ou le téléphone", ...)
it("valide une demande", ...)          // approveMemberRequest(id) called
it("refuse une demande", ...)
it("dit qu'il n'y a aucune demande", ...)
```

- [ ] **Step 2: Run, expect FAIL** : `npx vitest run components/admin/MemberRequestsTable.test.tsx`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect PASS**, puis `npx tsc --noEmit`, `npm run lint`, et les tests de `nav.config` s'ils figent les pastilles.
- [ ] **Step 5: Commit** : `feat(frontend): review join requests next to the member e-mails (#1785)`
