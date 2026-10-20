# Page « Mon compte » (#1663) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** une page `/mon-compte`, réservée aux connectés, qui rassemble les informations du compte et ses gestes sensibles (se détacher de sa fiche, annuler sa demande, supprimer son compte), le menu du compte ne gardant que « Mon compte » et « Se déconnecter ».

**Architecture:** un endpoint de lecture `GET /auth/me/identities` (les fournisseurs ne sont pas dans `/auth/me`, appelé sur chaque page : on ne l'alourdit pas). Côté front, une route sœur `app/mon-compte/` hors du groupe gardé par le code du site (supprimer son compte est un droit RGPD qui ne dépend pas du code), gardée par `spaceRefusal` comme `/encadrement`. Les dialogues `DangerConfirm` de `UserMenu` déménagent tels quels dans un composant client `AccountPage`.

**Tech Stack:** FastAPI, Pydantic v2, pytest ; Next.js 16 App Router, React Query, Vitest + RTL.

**Spec:** issue #1663 + décisions de cadrage du 20/10 (URL `/mon-compte`).

## Global Constraints

- Copie en français, vouvoiement, « athlète » jamais « coureur » (`frontend/AGENTS.md`).
- Nouveaux identifiants en anglais (Principe I) ; l'existant français ne se renomme pas.
- Écran public nouveau : composants `@/components/tcn` (Card, Button, Eyebrow…), `DangerConfirm` pour tout geste destructif (#499).
- Squelette sur `isPending`, jamais `isLoading`.
- Ne pas toucher : `frontend/app/(public_restricted)/mon-espace`, carte d'accueil, guide (`app/(public_restricted)/guide`), config pytest/vitest, conftest, `ci.yml`.
- Ajout de champ/endpoint seulement : aucun changement cassant de `/api/v1` (Principe IV).
- Pas de migration.

## Review Focus

- Session illisible (backend endormi) sur `/mon-compte` : la garde laisse passer, la page affiche une erreur avec « Réessayer », jamais « vous n'êtes pas connecté ».
- Compte sans fiche ni demande : la section fiche propose d'aller dans Mon espace, aucun bouton de détachement.
- Demande refusée : état affiché, aucun geste d'annulation (le backend n'annule qu'une demande en attente).
- Refus de suppression (dernier administrateur, 409) : le message serveur s'affiche dans le dialogue, qui reste ouvert.
- Identité d'un fournisseur retiré du registre : `label` retombe sur le slug, pas d'erreur 500.

---

### Task 1: `GET /auth/me/identities`

**Files:**
- Modify: `backend/app/schemas/auth.py` (nouveau schéma), `backend/app/api/v1/auth.py` (route à côté de `/auth/me/teammates`)
- Test: `backend/tests/test_api/test_my_identities_api.py` (calquer l'amorçage de session sur `test_my_teammates_api.py`)

**Interfaces:**
- Produces: `GET /api/v1/auth/me/identities` → `list[AccountIdentityRead]`, `AccountIdentityRead{provider: str, label: str, email: str, created_at: UtcDatetime}`, trié par `created_at`.

- [ ] **Step 1: tests qui échouent**
  - `test_identities_requires_session` : anonyme → 401.
  - `test_identities_lists_only_own_accounts_identities` : deux comptes avec une identité `github` chacun ; la réponse du premier contient exactement son identité, `label == "GitHub"`, son `email`, et jamais `subject` ni `secret_hash` (clés absentes du JSON).
  - `test_identity_of_unregistered_provider_falls_back_to_slug` : identité `provider="ancien"` → `label == "ancien"`.
- [ ] **Step 2:** `uv run pytest tests/test_api/test_my_identities_api.py -n 0` → FAIL (404).
- [ ] **Step 3: implémenter** `list_my_identities(user=Depends(current_user))` : `user.identities` (relation existante, pas de requête à écrire), `label = registry.get(i.provider).label if registry.get(i.provider) else i.provider`. Docstring d'une ligne citant #1663.
- [ ] **Step 4:** le test passe ; `uv run ruff check .` propre.
- [ ] **Step 5: commit** `feat(auth): list the session account's sign-in identities (#1663)`

### Task 2: route `/mon-compte` et composant `AccountPage`

**Files:**
- Create: `frontend/app/mon-compte/layout.tsx`, `frontend/app/mon-compte/page.tsx`, `frontend/components/auth/AccountPage.tsx`, `frontend/components/auth/AccountPage.test.tsx`
- Modify: `frontend/lib/api/client.ts` (`getMyIdentities`), `frontend/lib/queries/keys.ts` + `frontend/lib/queries/auth.ts` (`useMyIdentities()`), `frontend/lib/types.ts` (`AccountIdentity`), `frontend/app/routes-garde-site.test.ts` (ajouter `"mon-compte"` à la liste des routes sœurs)

**Interfaces:**
- Consumes: Task 1.
- Produces: `AccountPage()` (client, sans props) ; hooks existants `useSession`, `useDeleteAccount`, `useDetachAthlete`, `useCancelAthleteClaim`.

- [ ] **Step 1: tests qui échouent** (`AccountPage.test.tsx`, client de test et `fetch` simulé comme `UserMenu.test.tsx`)
  - affiche adresse, nom affiché, « Compte créé le … » (date `fr-FR`), libellés des fournisseurs (« GitHub »), « Adhérent » si `is_member` sinon « Non adhérent » ;
  - fiche rattachée : nom complet + lien « Ouvrir Mon espace » vers `/mon-espace` + bouton « Me détacher de ma fiche » qui ouvre le `DangerConfirm` existant (titre « Vous détacher de votre fiche ? ») ;
  - demande en attente : « Demande en attente : <nom> » + bouton « Annuler la demande » ; demande refusée : texte seul, pas de bouton ;
  - ni fiche ni demande : lien vers `/mon-espace` pour la rattacher, aucun bouton de détachement ;
  - « Zone sensible » : bouton destructif « Supprimer mon compte » → dialogue « Supprimer votre compte ? » ; confirmation → `DELETE /auth/me` puis navigation vers `/` ; un 409 affiche le message serveur dans le dialogue ;
  - `isPending` de la session → squelette ; session en erreur → message + « Réessayer » ;
  - le bloc « Mes données » de `#1674` n'existe pas encore : rien à tester ici.
- [ ] **Step 2:** `npx vitest run components/auth/AccountPage.test.tsx app/routes-garde-site.test.ts` → FAIL.
- [ ] **Step 3: implémenter**
  - `layout.tsx` : `spaceRefusal("Mon compte", () => true, null)` puis `children` (anonyme → `/login`, panne → laisse passer).
  - `page.tsx` : `metadata.title = "Mon compte"`, `PageShell` + `Eyebrow`/titre, rend `<AccountPage />`.
  - `AccountPage` : sections `Card` « Compte », « Fiche athlète », « Zone sensible » (en bas). Les deux `DangerConfirm` et leurs `mutate` sont **déplacés** depuis `UserMenu` sans changer leur copie ni leur comportement (`router.push("/")` après suppression).
- [ ] **Step 4:** tests verts, `npm run lint` propre.
- [ ] **Step 5: commit** `feat(auth): add the account page at /mon-compte (#1663)`

### Task 3: menu du compte et textes légaux

**Files:**
- Modify: `frontend/components/auth/UserMenu.tsx`, `frontend/components/auth/UserMenuDropdown.tsx`, `frontend/components/auth/UserMenu.test.tsx`, `frontend/components/legal/content/confidentialite.tsx`, `frontend/components/legal/content/confidentialite.test.tsx`, `docs/auth/membres.md` (s'il cite le menu du compte)

**Interfaces:**
- Consumes: route `/mon-compte` (Task 2).
- Produces: `UserMenuDropdown({ email, nom, deconnexionEnCours, onDeconnexion, children })` (props `onSuppression` et `actions` retirées).

- [ ] **Step 1: tests qui échouent** (`UserMenu.test.tsx`)
  - menu bureau et tiroir : un lien « Mon compte » vers `/mon-compte` ; plus aucun « Supprimer mon compte », « Me détacher de ma fiche », « Annuler la demande » ;
  - « Se déconnecter » inchangé ; le lien du tiroir appelle `onNavigate`.
  - `confidentialite.test.tsx` : le texte renvoie à la page « Mon compte » et non plus au « menu du compte » (mettre à jour les deux assertions des lignes ~189 et ~195).
- [ ] **Step 2:** tests → FAIL.
- [ ] **Step 3: implémenter** : retirer de `UserMenu` les états, hooks et dialogues déplacés ; lien du menu bureau en `DropdownMenuItem render={<Link href="/mon-compte" />}` ; dans le tiroir un `Link` stylé en bouton secondaire. Politique : remplacer « depuis le menu du compte » par « depuis la page Mon compte » aux trois endroits.
- [ ] **Step 4:** `npx vitest run components/auth components/legal` vert, `npm run lint`, `npm run build`.
- [ ] **Step 5: commit** `feat(auth): replace account deletion in the menu with a link to Mon compte (#1663)`

Hors périmètre de cette PR : le guide membre (autre session) ; le signaler dans la PR.
