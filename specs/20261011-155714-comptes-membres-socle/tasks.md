# Tasks: Comptes membres, socle

**Input**: `specs/20261011-155714-comptes-membres-socle/` (spec, plan, research, data-model, contracts, quickstart). Le sondage `docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md` prime.

**Tests**: obligatoires (Principe III, TDD sans réseau). Chaque test est écrit et vu échouer avant son implémentation.

**Livraison**: Phase 3 (US1) = PR #1334 sur `feat/1334-member-email-list` ; Phase 4 (US2) = PR #1322 sur `feat/1322-open-sign-in` ; Phase 5 (US3) = PR #1323 sur `feat/1323-entra-external-id`. Branches empilées, cible finale `epic/1312-member-accounts`.

Chemins relatifs à la racine du dépôt ; commandes backend depuis `backend/`.

## Phase 1: Setup

- [X] T001 Vérifier la base de départ : `uv sync`, `uv run alembic heads` rend `3c751af1cc83`, `uv run pytest -m "not integration" -q` vert, `cd frontend && npm ci && npm test` vert ; noter tout échec préexistant dans `.superpowers/sdd/1312/progress.md`

## Phase 2: Foundational

Aucune tâche bloquante commune : la table de US1 est le prérequis de US2, portée par US1.

## Phase 3: User Story 1, liste d'adhérents (Priority: P1) · #1334 · MVP

**Goal**: un administrateur importe l'export AssoConnect et tient la liste des adresses d'adhérents par saison.

**Independent Test**: import CLI et API d'un CSV, réimport qui retire une adresse, entrée manuelle qui survit, purge (quickstart § US1).

### Tests (écrits d'abord)

- [X] T002 [P] [US1] Tests du repository dans `backend/tests/test_repositories/test_member_email_repository.py` : `replace_imported` (ajout, retrait des `import` absentes, `manual` intactes, compte rendu), `add_manual` (nouvelle, promotion `import`→`manual`, doublon manuel), `remove`, `list_season`, `seasons`, `counting_season` (saison en cours non vide, repli sur la précédente si vide), `counts(email, today)`, `purge_before` (dry-run et réel)
- [X] T003 [P] [US1] Tests du service dans `backend/tests/test_services/test_member_emails_service.py` : en-têtes reconnus (`Email`, `E-mail`, `Adresse e-mail`, `Courriel`), première colonne reconnue retenue, normalisation `strip().casefold()`, doublons fusionnés, ligne invalide comptée `ignored`, fichier sans colonne → `MissingEmailColumnError` 422, aucune adresse valide → `NoValidEmailError` 422, saison hors bornes → `SeasonOutOfRangeError`, aucune colonne autre que l'e-mail n'est lue, `audit.record` appelé (`member_emails.import`, `.add`, `.remove`)
- [X] T004 [P] [US1] Tests API dans `backend/tests/test_api/test_admin_member_emails_api.py` selon `contracts/admin-member-emails.md` : 401 sans session, 403 sans `member_emails:manage`, GET (tri, `counting_season`, `seasons`), POST import multipart (200 et 422 sans écriture), POST manuel (201, 409, 422), DELETE (204, 404), garde du code de site appliquée
- [X] T005 [P] [US1] Tests CLI dans `backend/tests/test_cli/test_import_member_emails.py` selon `contracts/cli-import-member-emails.md` : sortie texte, `--json` (stdout JSON seul), code 1 sur `DomainError` sans écriture, code 2 fichier introuvable
- [X] T006 [P] [US1] Étendre `backend/tests/test_services/test_retention_service.py` et `backend/tests/test_cli/test_purge_retention.py` : champ `member_emails` du `RetentionOutcome`, purge des saisons `< season_of(today) - 1`, ligne du rapport

### Implementation

- [X] T007 [US1] Modèle `MemberEmail` dans `backend/app/models/member_email.py` (colonnes et `UniqueConstraint("email", "season")` de `data-model.md`, constantes `SOURCE_IMPORT`/`SOURCE_MANUAL`) ; l'exporter dans `backend/app/models/__init__.py`
- [X] T008 [US1] Migration `uv run alembic revision --autogenerate -m "member emails"` dans `backend/alembic/versions/`, `down_revision = "3c751af1cc83"`, relire puis `uv run alembic upgrade head` et `downgrade -1`/`upgrade head`
- [X] T009 [US1] Repository `backend/app/repositories/member_email_repository.py` (fonctions de T002, seule couche à requêter `member_emails`)
- [X] T010 [US1] Pouvoir `P.MEMBER_EMAILS_MANAGE = Permission("member_emails:manage", ...)` libellé et description en français, ajouté à `ALL` dans `backend/app/core/permissions.py`
- [X] T011 [US1] Service `backend/app/services/member_emails_service.py` : `import_file(db, *, season, content, filename, user_id) -> MemberEmailsImportReport`, `add(db, *, email, season, user_id)`, `remove(db, *, entry_id, user_id)`, `list_season(db, season, today)` ; réutiliser `sheet_source.read_table`, `_header_key`/`_column` de `club_members_service` (les extraire dans `sheet_source` si l'import croisé crée un couplage, sans dupliquer) ; erreurs `DomainError` françaises ; aucun commit
- [X] T012 [US1] Schémas `backend/app/schemas/member_email.py` (`MemberEmailOut`, `MemberEmailsSeasonOut`, `MemberEmailCreate`, `MemberEmailsImportReport`)
- [X] T013 [US1] Routes `backend/app/api/v1/admin_member_emails.py` (garde par route, `read_bounded_upload`, commit dans le routeur) et inscription dans le tuple gardé de `backend/app/api/v1/router.py`
- [X] T014 [US1] Commande `backend/app/cli/commands/import_member_emails.py`, renderer `render_member_emails_import_report` dans `backend/app/cli/reports.py`, enregistrement `import-member-emails` dans `backend/app/cli/__init__.py`, invocation ajoutée à `backend/app/cli/AGENTS.md`
- [X] T015 [US1] Purge : champ `member_emails` dans `RetentionOutcome`, appel dans les deux branches de `purge_expired` (`backend/app/services/retention_service.py`), ligne dans `render_retention_report`, docstring de `backend/app/cli/commands/purge_retention.py`
- [X] T016 [P] [US1] Frontend données : types dans `frontend/lib/types.ts`, appels dans `frontend/lib/api/client.ts` (GET, upload import, POST, DELETE), clés dans `frontend/lib/queries/keys.ts`, hooks `useMemberEmails`, `useImportMemberEmails`, `useAddMemberEmail`, `useRemoveMemberEmail` dans `frontend/lib/queries/admin.ts`
- [X] T017 [US1] Test vitest d'abord puis écran : `frontend/components/admin/MemberEmailsPanel.test.tsx` puis `MemberEmailsPanel.tsx` (sélecteur de saison, mention de la saison qui compte, import avec compte rendu, ajout, retrait avec confirmation, états vide/chargement/erreur en français) ; page `frontend/app/admin/adresses-adherents/{layout,page}.tsx` + `page.test.tsx` sur le patron de `frontend/app/admin/membres/`
- [X] T018 [US1] Entrée de navigation `a-adresses-adherents` (groupe « Données », `permission: "member_emails:manage"`, `description`, `helpAnchor`) dans `frontend/components/layout/nav.config.ts`, écran déclaré là où `ecran("/admin/membres")` l'est, section d'aide correspondante dans le guide d'administration ; `nav.config.test.ts` vert
- [X] T019 [US1] RGPD : avenant « liste des adresses d'adhérents (#1334) » avant `## Hors de cette décision, signalé` dans `docs/superpowers/specs/2026-10-01-base-legale-decision.md` (Traitement, Base légale, Minimisation, Conservation) ; `frontend/components/legal/content/confidentialite.tsx` (données traitées, finalité, ligne de conservation, `updatedAt`)
- [X] T020 [US1] Documentation : `docs/auth/membres.md` (liste d'adhérents : distincte d'`allowed_emails`, règles d'import, saison qui compte, purge) et renvoi depuis `backend/app/services/auth/AGENTS.md` et la table d'`AGENTS.md` racine
- [X] T021 [US1] Vérification US1 : `uv run pytest -m "not integration"`, `uv run ruff check .`, `npm test`, `npm run lint`, `npm run build`, `tests/test_permissions_catalogue.py` vert ; commit et PR #1334

## Phase 4: User Story 2, connexion ouverte (Priority: P1) · #1322

**Goal**: un adhérent se connecte sans être dans `allowed_emails` et le site s'ouvre sans code partagé ; un non-adhérent sans rôle n'obtient rien.

**Independent Test**: quickstart § US2, avec `DoublureProvider`.

### Tests (écrits d'abord)

- [X] T022 [P] [US2] Tests `backend/tests/test_services/test_membership.py` : `is_member` vrai si `users.email` dans la saison qui compte, faux pour un compte inactif, pour `SYSTEM_USER_EMAIL`, pour une adresse d'une saison antérieure ; retrait pris en compte immédiatement
- [X] T023 [US2] Réécrire les tests de refus « hors liste » dans `backend/tests/test_auth/test_provisioning.py`, `test_identity_rejection.py`, `test_flow.py`, `test_error_codes_closed_set.py` : connexion acceptée sans rôle ; conserver les refus `email_unverified` et compte désactivé ; ajouter FR-016 (adresse retenue : autorisation, puis liste d'adhérents, puis principale) et le rôle du premier jour inchangé ; mettre à jour les docstrings de `test_api_methods.py`, `test_not_configured.py`, `test_services/test_allowed_emails.py`
- [X] T024 [P] [US2] Étendre `backend/tests/test_auth/test_site_access_gate.py` : session adhérente sans cookie de site → accès ; session non adhérente → 401 ; anonyme inchangé ; `GET /site-access/session` suit la règle ; retrait de l'adresse → 401 à la requête suivante
- [X] T025 [P] [US2] Tests API auth : `/auth/me` expose `is_member` ; retour de parcours redirige vers `/admin` si administre, `/` sinon (dans `backend/tests/test_auth/` à côté des tests du callback existants) ; un compte sans rôle reçoit 403 sur un échantillon de routes gardées (`test_public_routes_still_open.py` reste vert) ; le plafond de débit de `/auth/{provider}/authorize` s'applique toujours (création massive de comptes)

### Implementation

- [X] T026 [US2] Service `backend/app/services/membership.py` : `is_member(db, user, today) -> bool`, `retained_email(db, identity) -> str` (FR-016), via `member_email_repository` et `allowed_email_repository`
- [X] T027 [US2] `backend/app/services/auth/provisioning.py` : retirer le refus `account_not_allowed` pour adresse hors liste, retenir l'adresse via `membership.retained_email`, garder `email_unverified`, compte inactif et `_grant_initial_role` ; journaliser la création d'un compte sans rôle au niveau info ; mettre à jour le commentaire d'`account_not_allowed` dans `backend/app/services/auth/errors.py` et les docstrings de `backend/app/core/config.py`
- [X] T028 [US2] `backend/app/api/deps.py` : `require_site_access` reçoit `optional_user` et rend la main pour un compte adhérent (avant la vérification du cookie)
- [X] T029 [US2] `backend/app/schemas/auth.py` champ `is_member`, rempli dans `backend/app/api/v1/auth.py` ; redirection du callback vers `/` pour un non-administrateur
- [X] T030 [P] [US2] Frontend : test vitest puis relais du cookie de session SSO (nom se terminant par `tcn_session`) en plus de `tcn_site_session` dans `serverFetch` de `frontend/lib/api/server.ts`, commentaire mis à jour (pourquoi le partage de cache n'est pas dégradé, R4)
- [X] T031 [US2] Frontend : `is_member` dans `SessionUser` (`frontend/lib/types.ts`) ; `SiteAccessGate` (`frontend/components/site-access/SiteAccessGate.tsx`) propose « Adhérent du club ? Se connecter » quand des moyens de connexion existent, et pour une session non adhérente affiche « Votre compte n'est pas reconnu comme adhérent : saisissez le code d'accès ou demandez l'ajout de votre adresse » ; libellé `account_not_allowed` dans `frontend/lib/constants.ts` et `frontend/app/login/page.test.tsx` devient « compte désactivé » ; un test vérifie que la navigation n'offre aucune entrée vers le back-office à une session sans `can_administer` (FR-017) ; tests vitest d'abord
- [X] T032 [US2] Documentation : `backend/app/services/auth/AGENTS.md` (la liste d'autorisation ne conditionne plus la connexion, dispense de la garde site pour un adhérent), `docs/auth/liste-autorisation.md`, `docs/auth/membres.md` (statut adhérent dérivé), `frontend/AGENTS.md` (relais du cookie de session dans `serverFetch`) ; politique de confidentialité (comptes ouverts aux adhérents, plus seulement au back-office)
- [X] T033 [US2] Vérification US2 (mêmes commandes que T021) ; commit et PR #1322

## Phase 5: User Story 3, Entra External ID (Priority: P2) · #1323

**Goal**: se connecter par Google ou par code e-mail via Entra External ID ; infrastructure décrite dans le dépôt.

**Independent Test**: `tests/test_auth/test_entra_provider.py` sans réseau ; déploiement réel par l'exploitant (quickstart § US3).

### Tests (écrits d'abord)

- [X] T034 [P] [US3] `backend/tests/test_auth/test_entra_provider.py` : clé RSA générée par joserfc, `httpx.MockTransport` servant découverte, JWKS et point de jeton ; `authorize()` sans réseau, URL avec `nonce`, `code_challenge` S256, `scope=openid profile email`, `round_trip={"verifier","nonce"}` ; jeton valide avec `email` et `xms_edov: true` → `ExternalIdentity(provider="entra", subject=oid, email_verified=True, verified_emails=(email,))` ; refus `provider_error` pour signature, `iss`, `aud`, `nonce`, `exp` invalides ; `email_unverified` si `email` absent ou `xms_edov` absent/faux ; `provider_unavailable` sur erreur réseau ; `kid` inconnu → un seul rafraîchissement du JWKS ; cache de la découverte
- [X] T035 [P] [US3] Tests de configuration et registre : `is_configured()` exige les quatre réglages `AUTH_ENTRA_*` ; `/auth/methods` liste `entra` seulement configuré ; mise à jour du test « un processus neuf ne charge que GitHub » (charge GitHub et Entra) ; parcours complet callback avec `entra` via `MockTransport` jusqu'à la session
- [X] T036 [US3] `backend/tests/test_core_http.py` : ajouter `services/auth/idp/entra.py` à `_FABRIQUES` avec son test positif (la fabrique utilise `guarded_transport`)

### Implementation

- [X] T037 [US3] Réglages `auth_entra_subdomain`, `auth_entra_tenant_id`, `auth_entra_client_id`, `auth_entra_client_secret: SecretStr` dans `backend/app/core/config.py` ; clés dans `render.yaml` ; `backend/.env.example`
- [X] T038 [US3] `backend/app/services/auth/idp/entra.py` : `EntraIdentityProvider(transport_factory=http.guarded_transport)`, `slug="entra"`, `label="Google ou code par e-mail"`, `authorize` (PKCE + nonce, points de terminaison construits), `fetch_identity` (échange du code, découverte et JWKS en cache 1 h, validation `joserfc` + `CodeIDToken` avec `iss` de la découverte et `aud`, règle `xms_edov`), erreurs `LoginError` de l'ensemble fermé ; enregistrement dans `backend/app/services/auth/idp/registry.py`
- [X] T039 [US3] Infrastructure `infra/entra-external-id/main.bicep` + `main.bicepparam` (tenant `ciamDirectories`, `location: 'Europe'`, `sku Base/A0`, `countryCode: 'FR'`, sortie `tenantId`) ; valider par `az bicep build` si disponible, sinon noter la validation manuelle
- [X] T040 [US3] `infra/entra-external-id/configure-tenant.sh` idempotent (`set -euo pipefail`, `az rest` Graph v1.0, lecture avant écriture) : application web (redirect URI, claims optionnels `email` et `xms_edov`, permissions `openid profile email`), principal de service, consentement administrateur, secret (affiché une fois, jamais écrit sur disque), fournisseur Google (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` en variables d'environnement), parcours d'inscription avec code e-mail et Google, application rattachée ; `shellcheck` si disponible
- [X] T041 [US3] `infra/entra-external-id/AGENTS.md` + `CLAUDE.md` (`@AGENTS.md`) : prérequis (rôle Tenant Creator), ordre de déploiement, étape manuelle du client Google (URI de redirection), FinOps (0 € jusqu'à 50 000 MAU, interdits : Front Door, SMS, client credentials), procédure FR-021 et repli ; ligne ajoutée à la table d'`AGENTS.md` racine ; section dans `docs/infra-azure.md`
- [X] T042 [US3] Documentation des réglages : table `AUTH_*` de `backend/README.md`, `docs/ci-cd.md` (variables par environnement), `backend/app/services/auth/AGENTS.md` (second fournisseur, règle `xms_edov`, réglages) ; politique de confidentialité : Microsoft (Entra External ID) comme sous-traitant d'authentification, cookie `tcn_auth_state` générique, `updatedAt`
- [X] T043 [US3] Sondage : section « Résultat du test sur tenant » dans `docs/superpowers/specs/2026-10-11-comptes-membres-sondage.md`, marquée « à faire par l'exploitant avant production » (FR-021)
- [X] T044 [US3] Vérification US3 (mêmes commandes que T021) ; commit et PR #1323

## Phase 6: Polish

- [ ] T045 Revue de code de chaque PR (`requesting-code-review`), corrections, `verification-before-completion`
- [ ] T046 Mettre à jour les sous-issues #1334, #1322, #1323 (liens PR) et le suivi `member-accounts-1312`

## Dependencies

- US1 (Phase 3) n'a aucune dépendance ; US2 dépend de `member_email_repository` (T009) ; US3 dépend des règles d'ouverture de US2 (T027) pour son parcours complet (T035), mais T034, T037 à T041 peuvent démarrer après US1.
- Dans chaque phase : tests → modèle/migration → repository → service → API/CLI → frontend → docs → vérification.

## Parallel Example

US1 : T002, T003, T004, T005, T006 en parallèle (fichiers distincts), puis T016 en parallèle de T013/T014.
US3 : T034, T035 en parallèle ; T039/T040/T041 (infra) en parallèle du code backend T037/T038.

## Implementation Strategy

MVP = US1 (#1334), livrable seul : la liste existe et se tient avant que personne ne s'en serve. Puis US2, qui la rend utile ; puis US3, qui apporte un moyen de connexion adapté aux adhérents. Chaque PR passe la suite complète avant d'être poussée.
