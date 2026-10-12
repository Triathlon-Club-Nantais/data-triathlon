# Tasks: Suppression des comptes (sur demande et après 5 ans d'inactivité)

**Input**: `specs/20261012-134400-suppression-comptes/` (spec, plan, research, data-model, contracts, quickstart).

**Tests**: obligatoires (Principe III, TDD sans réseau). Chaque test est écrit et vu échouer avant son implémentation.

**Livraison**: une PR sur `feat/1326-account-deletion`, empilée sur `feat/1323-entra-external-id`, cible finale `epic/1312-member-accounts`.

Chemins relatifs à la racine du dépôt ; commandes backend depuis `backend/`. Toute commande Alembic ou d'écriture en base tourne sous `DATABASE_URL=sqlite:///<scratchpad>/…`, `engine.url` vérifié avant.

## Phase 1: Setup

- [X] T001 Vérifier la base de départ : `uv run alembic heads` rend `cf8130e7fb21` (SQLite jetable), `uv run pytest -m "not integration" -q` et `cd frontend && npm test` verts ; noter tout échec préexistant dans `.superpowers/sdd/1312/progress.md`

## Phase 2: Foundational (colonne `last_seen_at`)

- [X] T002 Test dans `backend/tests/test_auth/test_models.py` : un `User` neuf a un `last_seen_at` non nul ; dans `backend/tests/test_migrations.py`, la migration rattrape `last_seen_at = created_at` sur une ligne existante et la colonne est `NOT NULL` (suivre le patron des tests de migration existants)
- [X] T003 Colonne `last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)` dans `backend/app/models/user.py`
- [X] T004 Migration `backend/alembic/versions/<rev>_users_last_seen_at.py` (`down_revision = "cf8130e7fb21"`) : ajout nullable, `UPDATE users SET last_seen_at = COALESCE(created_at, CURRENT_TIMESTAMP)`, `batch_alter_table` → `NOT NULL` ; `upgrade head`, `downgrade -1`, `upgrade head`, `alembic check` sur SQLite jetable

**Checkpoint**: T002 vert.

## Phase 3: User Story 1, suppression volontaire (Priority: P1) · MVP

**Goal**: un utilisateur connecté supprime son compte depuis son menu.

**Independent Test**: compte avec identité, sessions, rôle, groupe, fiche athlète et références facultatives ; `DELETE /auth/me` : tout ce qui appartient au compte disparaît, les références facultatives sont à `NULL`, la fiche reste, la session ne vaut plus rien.

### Tests (écrits d'abord)

- [X] T005 [P] [US1] Tests du repository dans `backend/tests/test_auth/test_account_references.py` : `user_repository.required_references()` contient exactement les cinq colonnes obligatoires de `research.md` D1 et aucune des quatre tables possédées ; `has_required_reference(db, user_id)` vrai si une ligne `admin_action_log` / `season_validations` / `ignored_identity_cases` cite le compte, faux sinon ; `detach_optional_references(db, user_id)` met à `NULL` `volunteer_actions.declared_by_user_id`, `allowed_emails.created_by_user_id`, `user_feedback.user_id` sans toucher les lignes d'autres comptes
- [X] T006 [P] [US1] Tests du service dans `backend/tests/test_auth/test_account_deletion.py` (fixture `db_session_fk` pour que les FK se vérifient comme en PostgreSQL ; compte système semé dans la fixture) : `accounts.delete_account(db, user, origin="request")` supprime compte, identités, sessions, rôles, groupes ; la fiche athlète reste ; références facultatives à `NULL` ; ligne `account.delete` au journal, auteur = compte système, `payload == {"origin": "request"}`, aucune adresse ni nom dans la ligne ; `AccountStillReferencedError` (409, message français « Contactez le club ») sans rien supprimer ; dernier administrateur → `LastAdministratorError` sans rien supprimer ; compte système → `SystemAccountDeletionError` ; reconnexion par la même identité externe après suppression → compte neuf sans rôle ni groupe (`provisioning`)
- [X] T007 [P] [US1] Tests API dans `backend/tests/test_auth/test_api_delete_me.py` selon `contracts/auth-delete-me.md` : 204 et cookies session + `tcn_logged_in` effacés, toutes les sessions du compte invalides ; 401 anonyme ; 409 référence obligatoire (rien supprimé) ; 409 dernier administrateur ; en-têtes `no-store` ; ajouter la route à l'inventaire de `backend/tests/test_auth/test_public_routes_still_open.py` si ce test l'exige

### Implementation

- [X] T008 [US1] `backend/app/repositories/user_repository.py` : `required_references()` / inventaire lu dans `Base.metadata` (research D1), `has_required_reference`, `detach_optional_references`, `delete(db, user)`
- [X] T009 [US1] Service `backend/app/services/auth/accounts.py` : erreurs `AccountStillReferencedError`, `SystemAccountDeletionError` (`DomainError` 409, messages français), `delete_account(db, user, *, origin)` selon `data-model.md` (garde `authorization.administrateurs_preserves`, auteur `benevole_access.system_user_id`), sans commit
- [X] T010 [US1] Route `DELETE /auth/me` dans `backend/app/api/v1/auth.py` : `current_user`, `accounts.delete_account(..., origin="request")`, `db.commit()`, réponse 204 avec les effacements de cookies de `logout` (factoriser l'effacement en une fonction locale partagée par les deux routes)
- [X] T011 [P] [US1] Tests frontend dans `frontend/components/auth/UserMenu.test.tsx` (et `DeleteAccountDialog.test.tsx` si composant séparé) : l'entrée « Supprimer mon compte » ouvre une boîte de dialogue accessible (rôle `dialog`, titre), le texte dit ce qui est effacé et que résultats et fiche athlète restent ; « Annuler » ferme sans appel ; confirmer appelle `DELETE /auth/me` puis navigue vers `/` ; un 409 affiche le message du backend dans la boîte ; présent aussi dans le tiroir mobile
- [X] T012 [US1] `frontend/lib/api/client.ts` (`deleteAccount`), `frontend/lib/queries/auth.ts` (`useDeleteAccount`, invalide la session), `frontend/components/auth/DeleteAccountDialog.tsx` (shadcn `Dialog`), branchement dans `frontend/components/auth/UserMenu.tsx`
- [X] T013 [P] [US1] Test puis libellés dans `frontend/lib/admin-action-log.ts` et `frontend/lib/admin-action-log.test.ts` : action `account.delete` (« Suppression d'un compte »), clé `origin` (« Origine »), valeurs `request` (« à la demande de son titulaire ») et `inactivity` (« 5 ans sans activité ») ; le test de catalogue (#1043) reste vert

**Checkpoint**: US1 testable seule.

## Phase 4: User Story 2, expiration après 5 ans (Priority: P1)

**Goal**: la purge hebdomadaire supprime les comptes sans rôle inactifs depuis 5 ans.

**Independent Test**: comptes variés, passe à blanc puis réelle ; seuls les éligibles disparaissent ; supprimés et sautés comptés.

### Tests (écrits d'abord)

- [X] T014 [P] [US2] Étendre `backend/tests/test_services/test_retention_service.py` : compte sans rôle inactif depuis plus de 5 × 365 jours supprimé (journal `origin: "inactivity"`) ; inactif depuis moins conservé ; porteur d'un rôle conservé ; éligible cité par `season_validations` conservé et compté `accounts_skipped` ; compte système jamais supprimé ; passe à blanc compte sans supprimer ; un compte cité seulement par une ligne de journal de plus de 12 mois est supprimé en passe réelle
- [X] T015 [P] [US2] Étendre `backend/tests/test_cli/test_purge_retention.py` : champs `accounts_deleted` / `accounts_skipped` dans `--json`, deux lignes du rapport texte (contrat `contracts/cli-purge-retention.md`)

### Implementation

- [X] T016 [US2] `user_repository.list_inactive_without_role(db, cutoff)` dans `backend/app/repositories/user_repository.py` (sans rôle, adresse ≠ `SYSTEM_USER_EMAIL`, `last_seen_at < cutoff`)
- [X] T017 [US2] `accounts.purge_inactive(db, *, now, dry_run) -> tuple[int, int]` et `ACCOUNT_INACTIVITY = timedelta(days=5 * 365)` dans `backend/app/services/auth/accounts.py`
- [X] T018 [US2] `backend/app/services/retention_service.py` : champs `accounts_deleted`, `accounts_skipped` de `RetentionOutcome`, appel après la purge du journal ; `backend/app/cli/reports.py` (`render_retention_report`) et docstring de `backend/app/cli/commands/purge_retention.py`

**Checkpoint**: US2 testable seule (avec le service de US1).

## Phase 5: User Story 3, activité tenue à jour (Priority: P1)

**Goal**: la date de dernière activité suit les connexions et l'usage, au plus une écriture par jour.

**Independent Test**: une connexion pose la date ; deux résolutions le même jour n'écrivent qu'une fois ; le lendemain, la date est repoussée.

### Tests (écrits d'abord)

- [X] T019 [US3] Étendre `backend/tests/test_auth/test_session.py` : `open_for` pose `last_seen_at` à maintenant ; `resolve` le jour même n'émet aucun `UPDATE users` (compter les requêtes par `event.listen(engine, "before_cursor_execute")`) ; `resolve` le lendemain (horloge figée par `monkeypatch` de `utcnow` dans `session`) repousse la date et la commite

### Implementation

- [X] T020 [US3] `user_repository.touch_last_seen(db, user_id, now)` (UPDATE conditionné, research D4) et appels dans `backend/app/services/auth/session.py` (`open_with_token`, `resolve`)

## Phase 6: Polish & documentation

- [X] T021 [P] Politique de confidentialité `frontend/components/legal/content/confidentialite.tsx` : paragraphe « Les comptes », ligne « Compte » du tableau (5 ans sans activité, suppression depuis le menu), « Vos droits » ; `updatedAt` dans le même commit ; tests de `frontend/components/legal/` à jour s'ils figent le texte
- [X] T022 [P] Avenant dans `docs/superpowers/specs/2026-10-01-base-legale-decision.md` (durée des comptes, suppression sur demande et à l'expiration) et ligne « Compte du back-office » du tableau des durées
- [X] T023 [P] `infra/entra-external-id/AGENTS.md` : rappel de la suppression manuelle de l'utilisateur dans l'annuaire Entra après une suppression de compte (le site ne connaît que l'`oid` de l'identité, perdu avec elle : noter l'`oid` ou l'adresse avant)
- [X] T024 [P] Section « Suppression des comptes (#1326) » dans `backend/app/services/auth/AGENTS.md` (inventaire par le schéma, auteur système, activité une fois par jour, écart de la passe à blanc) ; ligne `purge-retention` de `backend/app/cli/AGENTS.md` si elle énumère les durées
- [X] T025 Vérification finale : backend `uv run pytest -m "not integration" -q`, `uv run ruff check .` ; frontend `npm test`, `npm run lint`, `npm run build` ; consigner dans `.superpowers/sdd/1312/progress.md`

## Dependencies & Execution Order

- Phase 2 bloque US2 et US3 (colonne). US1 ne lit pas la colonne mais la migration doit précéder tout test de schéma.
- US2 dépend du service de US1 (T009). US3 est indépendante de US1 et US2.
- Tests avant implémentation dans chaque phase ; [P] = fichiers distincts.

## Parallel Example: User Story 1

```text
T005, T006, T007 (tests backend) en parallèle ; puis T008 → T009 → T010.
T011 et T013 (frontend) en parallèle des tâches backend ; T012 après T011.
```

## Implementation Strategy

MVP = Phases 1 à 3 (suppression volontaire). Puis US2 (expiration), US3 (activité), puis la documentation. Un commit Conventional par tâche ou groupe cohérent test + implémentation.

## Phase 7: Corrections de revue (PR #1357)

- [X] R01 [US1] `entra_oids` dans le payload `account.delete` (test puis service), libellé du journal côté front ; procédure Entra par relevé du journal de production, jamais par comparaison (`infra/entra-external-id/AGENTS.md`), FR-009, research D10, avenant, politique (« dans le mois qui suit »)
- [X] R02 [US3] Écriture de `last_seen_at` par une session à part ; test prouvant qu'un état en attente de la requête n'est pas commité
- [X] R03 [US2] Échéance à la date du calendrier, 5 ans plus tôt (29 février → 28), tests autour des années bissextiles
- [X] R04 Migration : `last_seen_at` = dernière ouverture de session, à défaut la création ; upgrade/downgrade/upgrade et `alembic check` sur SQLite jetable
- [X] R05 [US2] Compte désactivé sans rôle : expire aussi, test et `services/auth/AGENTS.md`
- [X] R06 [US1] Auteur « Système » pour `account.delete` dans le journal (test)
- [X] R07 [US1] Style destructif sur « Supprimer mon compte » (menu et tiroir), plus sur « Se déconnecter »
- [X] R08 Politique : « un compte qui porte un rôle est gardé tant qu'il le porte »
