---

description: "Task list — liste d'autorisation en base et gestion depuis le back-office"
---

# Tasks: Liste d'autorisation en base, gérée depuis le back-office

**Input**: Design documents from `specs/20260806-174652-auth-liste-autorisation-base/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Principe III de la constitution — **TDD non-négociable**. Chaque tâche
d'implémentation est précédée de son test rouge. Aucune tâche n'appelle le
réseau : la feature n'a aucune sortie HTTP.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers distincts, aucune dépendance sur une tâche inachevée)
- **[Story]** : US1 / US2 / US3, tracé vers `spec.md`
- Chemins depuis la racine du dépôt

---

## Phase 1: Setup

**Purpose**: partir d'un état vert connu. Rien à initialiser — le dépôt, les
dépendances et l'outillage existent ; `email-validator` est déjà installé par
`fastapi[standard]` (research R8), aucune dépendance n'est ajoutée.

- [X] T001 Relever la base de référence : `cd backend && uv run pytest -m "not integration"` puis `cd frontend && npm test`, et noter les compteurs. La phase 2 casse volontairement des tests existants ; sans ce relevé, on ne saura pas distinguer une régression d'un test à réécrire.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: la table, sa lecture, et le débranchement de la variable
d'environnement. **Aucune user story ne peut commencer avant.**

**⚠️ CRITICAL**: à la fin de cette phase, la liste vit en base et la variable
d'environnement n'existe plus. C'est l'incrément le plus risqué de la feature —
il touche le parcours de connexion et la configuration de production.

- [X] T002 [P] Créer le modèle `AllowedEmail` dans `backend/app/models/allowed_email.py` (colonnes de `data-model.md`, `email` `UNIQUE` et indexé, `created_by` en `relationship` sens unique vers `User`, **sans** `ondelete`) et l'enregistrer dans `backend/app/models/__init__.py`
- [X] T003 [P] Écrire les tests **rouges** du repository dans `backend/tests/test_repositories/test_allowed_email_repository.py` : `exists` insensible à la casse et aux espaces, `list_all` trié par adresse avec `created_by` chargé en une requête, `add` idempotent sous contrainte `UNIQUE`, `delete` sans erreur sur ligne absente
- [X] T004 Faire passer T003 : `backend/app/repositories/allowed_email_repository.py` — insertion tentée sous `db.begin_nested()` et `IntegrityError` rattrapée en relisant la ligne, patron exact de `user_role_repository.grant` (research R7). `flush()`, jamais `commit()`
- [X] T005 Générer la migration du schéma : `cd backend && uv run alembic revision --autogenerate -m "allowed emails"`, relire la révision à la main, `down_revision = 'f6a7b8c9d0e1'`
- [X] T006 Écrire le test **rouge** de la reprise dans `backend/tests/test_migrations.py` : avec `monkeypatch.setenv("AUTH_ALLOWED_EMAILS", " A@Exemple.FR ,b@exemple.fr,a@exemple.fr ")`, `command.upgrade(head)` sur base SQLite jetable insère **deux** lignes normalisées ; sans la variable, aucune
- [X] T007 Faire passer T006 : la migration de T005 lit `os.environ.get("AUTH_ALLOWED_EMAILS", "")` dans son `upgrade()`, normalise, dédoublonne et `op.bulk_insert`. Commenter *pourquoi* `os.environ` et non `Settings` (research R2) — le réglage disparaît en T011
- [X] T008 Réécrire les tests de `backend/tests/test_auth/test_provisioning.py` en **rouge** : les six `monkeypatch.setenv("AUTH_ALLOWED_EMAILS", …)` deviennent des insertions en base via le repository ; ajouter le cas « liste vide en base → `account_not_allowed` » et « casse différente → accepté ». Deux exigences y sont éprouvées nommément : **FR-002** — un test unique qui refuse une adresse, l'insère, puis retente et l'accepte **sans rien réinitialiser** (c'est la propriété qui *est* la feature : le défaut de l'issue était un `lru_cache`) ; et **FR-006** — le test d'invariant de #114 « identité externe inconnue → **nouvel** utilisateur, même si l'adresse est déjà en base » est **conservé** tel quel, la liste autorisant sans jamais apparier
- [X] T009 Faire passer T008 : `backend/app/services/auth/provisioning.py` — `_is_allowed(db, email)` délègue à `allowed_email_repository.exists`, l'unique appelant lui passe `db`. Aucune requête écrite dans le service (Principe II), aucun cache (research R1). Mettre à jour la docstring qui décrit la variable d'environnement
- [X] T010 Mettre en **rouge** les tests du garde de configuration : supprimer les quatre tests d'`auth_allowed_emails` de `backend/tests/test_config.py` ; dans `backend/tests/test_auth/`, adapter **six** fichiers — `test_api_methods.py` (liste vide en base → `/auth/methods` rend les méthodes configurées), `test_not_configured.py`, `test_startup_warning.py` (le réglage n'est plus cité), `conftest.py` (la clé `AUTH_ALLOWED_EMAILS` disparaît des variables posées), `test_flow.py` (le refus pour adresse non autorisée passe par la base) et `test_identity_rejection.py`. Le relevé est exhaustif : à la fin de T011, `grep -rn AUTH_ALLOWED_EMAILS backend/tests backend/app` ne rend plus rien. Le reste du dépôt (configuration et documentation) est traité en phase 6, et `specs/` n'est jamais réécrit — ce sont des artefacts historiques
- [X] T011 Faire passer T010 : supprimer `auth_allowed_emails` de `backend/app/core/config.py` (champ, mention dans le validateur CSV partagé avec `cors_origins`, et terme du `auth_is_configured`) et la ligne correspondante de `backend/app/main.py` (`_warn_if_auth_unconfigured`)

**Checkpoint**: `uv run pytest -m "not integration"` est vert, la liste vit en
base, la variable d'environnement n'est plus lue par le code applicatif. Rien
n'est encore administrable — c'est l'objet des phases suivantes.

---

## Phase 3: User Story 1 - Autoriser un contributeur sans redéployer (Priority: P1) 🎯 MVP

**Goal**: consulter et alimenter la liste depuis `/admin`, sans redéploiement.

**Independent Test**: connecté avec un rôle `admin`, ajouter une adresse depuis
l'écran, puis ouvrir une session avec le compte externe qui la porte — sans
redémarrer le serveur.

### Tests for User Story 1

> Écrire ces tests **d'abord**, vérifier qu'ils échouent.

- [X] T012 [P] [US1] Tests **rouges** du service dans `backend/tests/test_services/test_allowed_emails.py` : `add` normalise (minuscules, espaces), est idempotent, et rend `(entrée, créée)` ; `list_all` trie par adresse
- [X] T013 [P] [US1] Tests **rouges** de l'API dans `backend/tests/test_api/test_admin_allowed_emails.py` : `GET` 200 (liste possiblement vide), `POST` 201, `POST` répété 201 sans doublon, `POST` d'une adresse mal formée 422, et pour les deux ressources 401 anonyme puis 403 connecté-sans-pouvoir (l'ordre 401-avant-403 est vérifié, pas supposé)
- [X] T014 [P] [US1] Tests **rouges** du composant dans `frontend/components/admin/AllowedEmailsTable.test.tsx` : rend la liste, l'état vide dit « aucune adresse autorisée », un `403` affiche un refus **et non** l'état vide (le défaut corrigé sur `PendingProvidersTable`), la soumission du formulaire appelle la mutation et invalide la requête

### Implementation for User Story 1

- [X] T015 [US1] Ajouter `ALLOWED_EMAILS_MANAGE` (`allowed_emails:manage`, libellés français) à `P` **et** à `ALL` dans `backend/app/core/permissions.py`, dans la fonctionnalité `FEATURE_ROLES` existante. `tests/test_permissions_catalogue.py` reste **rouge** jusqu'à T019 : c'est son rôle
- [X] T016 [P] [US1] Ajouter `AllowedEmailRead` (dont `created_by_name` = nom d'affichage ou `null` — **pas** `created_by`, qui se lirait comme un identifiant à côté de la colonne `created_by_user_id`) et `AllowedEmailCreate` (`email: str` — **amendé à l'implémentation** : `EmailStr` posé sur le champ fait rendre à FastAPI son 422 par défaut, `detail` en liste et message anglais, ce qui rompt FR-010 ; la validation vit donc dans `services/auth/allowed_emails`, où les deux appelants la partagent) à `backend/app/schemas/admin.py`, **et** corriger la docstring de ce même fichier (ligne ~101) qui décrit le peuplement d'`users` comme borné par `AUTH_ALLOWED_EMAILS`
- [X] T017 [P] [US1] Ajouter `set_active(db, users, active)` à `backend/app/repositories/user_repository.py` et corriger la docstring de `list_all` qui cite `AUTH_ALLOWED_EMAILS`
- [X] T018 [US1] Créer `backend/app/services/auth/allowed_emails.py` avec `list_all(db)` et `add(db, email, actor)` (dépend de T004, T016)
- [X] T019 [US1] Créer `backend/app/api/v1/admin_allowed_emails.py` avec `GET` et `POST`, chacun gardé individuellement par `require_permission(P.ALLOWED_EMAILS_MANAGE)`, et le monter dans `backend/app/api/v1/router.py`. Couche mince : aucune écriture directe en base (méta-test AST de #115)
- [X] T020 [P] [US1] Front, plomberie : type `AllowedEmail` dans `frontend/lib/types.ts`, trois appels dans `frontend/lib/api/client.ts`, clé dans `frontend/lib/queries/keys.ts`, hooks `useAllowedEmails` / `useAddAllowedEmail` dans `frontend/lib/queries/admin.ts`
- [X] T021 [US1] Créer `frontend/components/admin/AllowedEmailsTable.tsx` : table (adresse, ajoutée le, par) + formulaire d'ajout, sur le patron de `PendingProvidersTable.tsx` — `Card`, `Skeleton`, `EmptyState`, `toast`, et la fonction `messageDErreur` qui distingue 401 / 403 / autre
- [X] T022 [US1] Donner à l'écran sa propre destination. **Amendé après essai de l'interface** : la décision initiale (« un second bloc sur `/admin` ») mêlait l'administration des personnes à celle des données sur un même écran. À la place — `frontend/app/admin/acces/page.tsx` nouvelle, `frontend/app/admin/page.tsx` réduite à son seul sujet et retitrée, section « Gestion des utilisateurs » dans `nav.config.ts` (accès + les trois écrans à venir de #115 et #197), et filtrage par **pouvoir** dans `AppNav.tsx` — `minRole: ROLE.ADMIN` aurait rendu l'entrée invisible pour tout le monde, `rank` ne valant jamais cet échelon
- [X] T023 [US1] Vérifier que `backend/tests/test_auth/test_public_routes_still_open.py` et `backend/tests/test_permissions_catalogue.py` passent au vert sans y ajouter d'exception : les deux ressources sont gardées, le pouvoir garde bien une ressource

**Checkpoint**: US1 est livrable seule. Le retrait n'existe pas encore ; une
adresse ajoutée par erreur se retire par la base ou en réinscrivant — c'est
l'objet d'US2.

---

## Phase 4: User Story 2 - Retirer un accès, et qu'il soit réellement fermé (Priority: P2)

**Goal**: le retrait ferme l'accès **au geste**, sessions ouvertes comprises, et
reste réversible.

**Independent Test**: deux comptes connectés, en retirer un depuis l'écran, et
constater que sa requête suivante rend 401 sans qu'il se soit déconnecté.

### Tests for User Story 2

- [X] T024 [P] [US2] Tests **rouges** du service dans `backend/tests/test_services/test_allowed_emails.py` : `remove` supprime la ligne **et** passe à `is_active = False` **tous** les comptes portant l'adresse (casse ignorée, `users.email` n'étant pas unique) ; idempotent sur identifiant inconnu ; ne supprime ni l'utilisateur, ni ses rôles (FR-017)
- [X] T025 [P] [US2] Test **rouge** de l'invariant dans `backend/tests/test_services/test_allowed_emails.py` : retirer l'adresse du **dernier** administrateur actif lève `LastAdministratorError` (409) et ne modifie rien ; avec deux administrateurs actifs, le retrait passe
- [X] T026 [P] [US2] Test **rouge** de bout en bout dans `backend/tests/test_api/test_admin_allowed_emails.py` : `DELETE` 204, `DELETE` d'un identifiant inconnu 204, 409 sur le dernier administrateur, 401/403 ; **et** une requête authentifiée du compte retiré rend 401 juste après, sans toucher à `user_sessions`
- [X] T027 [P] [US2] Test **rouge** de la symétrie dans `backend/tests/test_services/test_allowed_emails.py` : réinscrire une adresse repasse ses comptes à `is_active = True` (sans quoi la réinscription n'ouvre rien, research R4)
- [X] T028 [P] [US2] Test **rouge** du composant dans `frontend/components/admin/AllowedEmailsTable.test.tsx` : le bouton « Retirer » appelle la mutation, un 409 affiche son message tel que rendu par l'API

### Implementation for User Story 2

- [X] T029 [US2] Ajouter `remove(db, entry_id, actor)` à `backend/app/services/auth/allowed_emails.py`, encadré par `authorization.administrateurs_preserves(db)` **sans** argument d'organisation, et désactivant via `user_repository.set_active` (dépend de T017, T018)
- [X] T030 [US2] Étendre `add()` de la réactivation symétrique, dans le même service
- [X] T031 [US2] Ajouter `DELETE /admin/allowed-emails/{id}` à `backend/app/api/v1/admin_allowed_emails.py`, gardé individuellement, 204 y compris sur identifiant inconnu
- [X] T032 [US2] Front : hook `useRemoveAllowedEmail` dans `frontend/lib/queries/admin.ts` et colonne d'action dans `AllowedEmailsTable.tsx`

**Checkpoint**: US1 et US2 fonctionnent indépendamment. L'administration
complète est livrable, hors amorçage d'une installation neuve.

---

## Phase 5: User Story 3 - Amorcer une installation depuis le serveur (Priority: P3)

**Goal**: sortir du cercle « liste vide → personne ne se connecte → personne
n'ouvre le back-office ».

**Independent Test**: sur une base vierge, une commande puis une connexion.

### Tests for User Story 3

- [X] T033 [P] [US3] Tests **rouges** dans `backend/tests/test_cli/test_allow_email.py`, contrat de `contracts/cli.md` : adresse inscrite → code `0` et message ; adresse déjà présente → `0` et « rien à faire » ; adresse mal formée → `2`, **rien écrit** ; réinscription d'une adresse dont des comptes étaient fermés → mentionne les comptes réactivés

### Implementation for User Story 3

- [X] T034 [US3] Créer `backend/app/cli/commands/allow_email.py` (couche mince : `session_scope` + appel au service de T018/T030, zéro logique métier) et l'enregistrer dans `backend/app/cli/__init__.py`
- [X] T035 [US3] Corriger le message d'erreur « adresse inconnue » de `backend/app/cli/commands/grant_role.py`, qui renvoie vers `AUTH_ALLOWED_EMAILS`, pour qu'il renvoie vers `allow-email` ; mettre à jour l'assertion de `backend/tests/test_cli/test_grant_role.py`
- [X] T036 [US3] Dérouler l'amorçage complet de `quickstart.md` §1-2 sur une base vierge (`uv run python scripts/reset_db.py --no-seed --yes`) : `allow-email`, connexion, `grant-role --role admin`

**Checkpoint**: les trois stories sont indépendamment fonctionnelles.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: la propagation documentaire de la suppression du réglage — le
rayon d'impact relevé au plan. Un réglage à moitié supprimé est pire qu'un
réglage conservé : il reste dans un tableau que quelqu'un renseignera.

- [X] T037 [P] Retirer `AUTH_ALLOWED_EMAILS` de `backend/.env.example`. **Amendé en revue de code** : l'entrée **reste** dans `render.yaml`, avec le commentaire qui dit pourquoi — c'est elle que lit la reprise de T007, et la retirer du même geste ferait dépendre la mise en production d'un comportement d'hébergeur non vérifié, sans rattrapage (`plan: free` n'ouvre aucun shell). Elle se retire dans une PR de suivi, une fois la reprise constatée dans `/admin/acces`
- [X] T038 [P] Mettre à jour le tableau des réglages de `backend/README.md` (le réglage disparaît) et sa phrase sur la naissance d'un utilisateur, qui le cite
- [X] T039 [P] Mettre à jour `docs/ci-cd.md` : retirer les deux mentions du réglage et **ajouter l'ordre de mise en production 1-2-3** de `quickstart.md` §7 (déployer → vérifier → supprimer la variable dans le tableau de bord Render). Inverser 1 et 3 ferme l'accès à tout le monde
- [X] T040 [P] Mettre à jour `backend/app/services/auth/AGENTS.md` : « Huit réglages `AUTH_*` » → sept, la puce du fail-closed, et une section courte sur la liste en base (le pouvoir unique, la symétrie ajout/retrait, le couplage daté avec #169)
- [X] T041 [P] Ajouter la commande à `backend/app/cli/AGENTS.md` et à la table des commandes d'`AGENTS.md` à la racine, à côté de `grant-role`
- [X] T042 [P] Ajouter à `backend/app/models/AGENTS.md` une section sur `allowed_emails`, sur le patron de celle que #115 y a posée pour le RBAC : la table autorise sans identifier, `created_by_user_id` nomme celui qui accorde et jamais celui qui reçoit, aucun rattachement à une organisation
- [~] T043 **Partiel** — §5 (liste vide) et les filets sont déroulés et verts ; §3 et §4 (l'écran et le retrait dans un navigateur) ne le sont pas : le parcours OAuth n'est utilisable que depuis l'espace de travail principal (une application GitHub n'accepte qu'une seule URL de retour, port compris). Les tests d'API et de composant couvrent les mêmes assertions. Dérouler `quickstart.md` en entier, §3 à §5 comprises (l'écran, le retrait qui ferme vraiment, la liste vide qui n'ouvre rien)
- [X] T044 Vérification finale : `cd backend && uv run pytest -m "not integration" && uv run ruff check .` puis `cd frontend && npm test && npm run lint && npm run build`, et comparer les compteurs à ceux de T001

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)** : aucune dépendance.
- **Foundational (T002-T011)** : bloque **tout**. La chaîne T002 → T003 → T004 → T005 → T006 → T007 est séquentielle (le modèle avant la migration, la migration avant sa reprise) ; T008-T011 suivent T004.
- **US1 (T012-T023)** : dépend de la phase 2 entière.
- **US2 (T024-T032)** : dépend de la phase 2 et de T017/T018 (le service et `set_active` d'US1).
- **US3 (T033-T036)** : dépend de la phase 2 et du service (T018, T030).
- **Polish (T037-T044)** : T037-T039 dépendent de T011 (le réglage doit avoir disparu du code avant qu'on le retire de la configuration).

### User Story Dependencies

- **US1 (P1)** : indépendante après la phase 2. C'est le MVP.
- **US2 (P2)** : réutilise le service et le router d'US1 — livrable après elle, testable indépendamment.
- **US3 (P3)** : ne dépend d'aucune autre story sur le fond, seulement du service partagé. Peut être menée en parallèle d'US2. **T033-T034 se remontent dès T018** — la commande n'a besoin que du service `add`, et c'est ce qui rend l'MVP exerçable sur une base vierge (voir §MVP).

### Within Each User Story

- Les tests sont écrits **et rouges** avant l'implémentation (Principe III).
- Modèle → repository → service → route → interface.
- T015 laisse volontairement `test_permissions_catalogue.py` rouge jusqu'à T019 : le méta-test **est** le filet qui exige qu'un pouvoir ajouté garde une ressource.

### Parallel Opportunities

- T002 et T003 en parallèle (modèle et test de repository, fichiers distincts).
- T012, T013, T014 en parallèle (trois fichiers de test distincts).
- T016, T017, T020 en parallèle (schémas, repository, plomberie front).
- T024 à T028 en parallèle.
- T037 à T042 en parallèle (six fichiers de configuration et de documentation distincts).
- **Pas** de parallélisme entre T021 et T032, ni entre T018/T029/T030 : mêmes fichiers.

---

## Parallel Example: User Story 1

```bash
# Les trois tests rouges d'US1, ensemble :
Task: "Tests du service dans backend/tests/test_services/test_allowed_emails.py"
Task: "Tests de l'API dans backend/tests/test_api/test_admin_allowed_emails.py"
Task: "Tests du composant dans frontend/components/admin/AllowedEmailsTable.test.tsx"

# Puis les trois implémentations indépendantes :
Task: "Schémas AllowedEmailRead / AllowedEmailCreate dans backend/app/schemas/admin.py"
Task: "set_active() dans backend/app/repositories/user_repository.py"
Task: "Plomberie front : types.ts, client.ts, keys.ts, queries/admin.ts"
```

---

## Implementation Strategy

### MVP (US1 seule)

1. Phase 1 — état de départ relevé.
2. Phase 2 — **la partie risquée** : à sa fin, la liste vit en base et le
   réglage n'est plus lu. Ne pas enchaîner avant que `pytest` soit vert.
3. Phase 3 — US1.
4. **S'arrêter et valider** : ajouter une adresse depuis l'écran, se connecter
   avec.

**Une borne à connaître avant de démarrer** : sur une **base vierge**, les phases
1-3 ne suffisent pas à s'exercer. La liste est vide, personne ne peut ouvrir de
session, donc personne n'atteint l'écran qui inscrirait la première adresse — le
cercle qu'US3 est faite pour rompre. En production la question ne se pose pas :
la reprise de T007 remplit la table au déploiement. En développement, deux
sorties, au choix : dérouler **T033-T034 dès T018** (la commande ne dépend que du
service `add`), ou insérer une ligne à la main dans `allowed_emails`. La première
est préférable — elle fait avancer le travail au lieu de le contourner.

### Livraison incrémentale

1. Phases 1-2 → socle en place, comportement inchangé pour l'utilisateur final.
2. + US1 → l'ajout sans redéploiement (le besoin de l'issue).
3. + US2 → le retrait effectif.
4. + US3 → l'amorçage d'une installation neuve.
5. + Polish → la propagation documentaire, **sans laquelle la mise en production
   est dangereuse** : l'ordre de déploiement de T039 est ce qui évite de vider la
   source de la reprise.

### Ce qu'il ne faut pas faire

- **Livrer la phase 2 sans T007.** Le déploiement viderait la liste de
  production et fermerait l'accès à tout le monde, administrateurs compris.
- **Faire T037 avant T011.** Retirer la variable de la configuration avant que
  le code cesse de la lire, c'est le même verrouillage, juste plus tôt.
- **Ajouter une exception à `test_public_routes_still_open.py`.** Si ce test
  rougit, c'est qu'une ressource n'est pas gardée — pas qu'il faut l'assouplir.

---

## Notes

- `[P]` = fichiers distincts, aucune dépendance.
- Un commit par tâche ou par groupe cohérent, en Conventional Commits.
- La branche est déjà créée (`auth-liste-dautorisation-en-base-et-gestion-depu`)
  et le worktree dédié : ne pas en créer une seconde.
- Fin de branche, commune aux trois voies : `requesting-code-review` →
  `verification-before-completion` → `finishing-a-development-branch`.
