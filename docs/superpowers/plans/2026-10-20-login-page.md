# Page de connexion adhérent / administration (#1666) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** habiller `/login` aux couleurs du club et séparer nettement la connexion adhérent (Google ou code par e-mail, mise en avant) de l'accès administration (GitHub, secondaire et discret), le classement venant du backend.

**Architecture:** chaque fournisseur d'identité déclare une `audience` (`"member"` ou `"admin"`), rendue par `GET /auth/methods` (ajout de champ, Principe IV respecté). La page groupe les méthodes par audience : un bloc « Espace adhérent » principal, puis un bloc « Administration » séparé et discret. Le flux OAuth ne change pas.

**Tech Stack:** FastAPI, Pydantic v2, pytest ; Next.js 16, React Query, Vitest + RTL.

**Spec:** issue #1666.

## Global Constraints

- Copie en français, vouvoiement ; composants `@/components/tcn` et tokens `--tcn-*`, plus de styles inline pour ce qui a un composant ou une classe (`frontend/AGENTS.md`).
- Garder le lien `<a href="/api/v1/auth/{slug}/authorize">` et l'événement PostHog `login_initiated` (sendBeacon, send_instantly) ; garder `withPostHog` au montage.
- Garder les états : chargement, erreur de `/auth/methods` avec « Réessayer », aucune méthode, `?error=`.
- Mobile 360 px et AA : contraste, focus visible (anneau `--tcn-orange`), libellés explicites.
- Ne pas toucher : `backend/tests/**/conftest.py`, config pytest/vitest, `test/setup.ts`, `ci.yml`, `app/(public_restricted)/mon-espace`, carte d'accueil, guide.
- Flux OAuth (`/auth/{slug}/authorize`, callback) inchangé.

## Review Focus

- Seulement GitHub configuré (déploiement sans Entra) : pas de bloc adhérent vide ; l'accès administration reste visible et utilisable.
- Seulement Entra configuré : pas de bloc administration vide.
- Fournisseur sans `audience` (doublure de test du conftest) : `/auth/methods` rend `"member"`, jamais une 500.
- `?error=` affiché au-dessus des deux blocs, quel que soit le parcours qui a échoué.
- Focus clavier : l'ordre de tabulation suit l'ordre visuel (adhérent puis administration).

---

### Task 1: `audience` des moyens de connexion

**Files:**
- Modify: `backend/app/services/auth/idp/base.py` (Protocol : `audience: Literal["member", "admin"]`, docstring d'une ligne), `idp/github.py` (`audience = "admin"`), `idp/entra.py` (`audience = "member"`), `backend/app/schemas/auth.py` (`AuthMethodRead.audience: Literal["member", "admin"]`), `backend/app/api/v1/auth.py` (`list_methods`)
- Test: `backend/tests/test_auth/test_api_methods.py` (mettre à jour les égalités de dict existantes), `backend/tests/test_auth/test_entra_provider.py` si une assertion compare le dict entier

**Interfaces:**
- Produces: `GET /api/v1/auth/methods` → `[{slug, label, audience: "member" | "admin"}]`.

- [ ] **Step 1: tests qui échouent**
  - `test_github_is_an_admin_method` : la réponse vaut `[{"slug": "github", "label": "GitHub", "audience": "admin"}]` (adapter les deux égalités existantes du fichier à cette forme).
  - `test_entra_is_a_member_method` : Entra configuré (même amorçage que `test_entra_provider.py` ~l.398) → sa méthode porte `"audience": "member"`.
  - `test_a_provider_without_audience_is_listed_as_member` : la fixture `doublure` existante (sans `audience`) apparaît avec `"audience": "member"`, statut 200.
- [ ] **Step 2:** `uv run --project backend pytest backend/tests/test_auth/test_api_methods.py backend/tests/test_auth/test_entra_provider.py -n 0` → FAIL.
- [ ] **Step 3: implémenter.** Dans `list_methods` : `audience=getattr(method, "audience", "member")` avec, au-dessus, le commentaire `# shortcut: la doublure du conftest de test_auth ne déclare pas d'audience (conftest gelé cette semaine), retirer le défaut quand elle en porte une.`
- [ ] **Step 4:** les deux fichiers passent, puis `uv run --project backend pytest -m "not integration" backend/tests/test_auth -q`, `uv run --project backend ruff check backend`.
- [ ] **Step 5: commit** `feat(auth): tag each sign-in method with its audience (#1666)`

### Task 2: page `/login` en deux parcours

**Files:**
- Modify: `frontend/lib/types.ts` (`AuthMethod.audience: "member" | "admin"`), `frontend/app/login/page.tsx`, `frontend/app/login/page.test.tsx`; tout autre test ou fixture TS qui construit un `AuthMethod` (le typecheck les signale).

**Interfaces:**
- Consumes: Task 1.

- [ ] **Step 1: tests qui échouent** (`page.test.tsx`, garder tous les tests d'état existants en ajoutant `audience` aux fixtures)
  - avec `[{entra, member}, {github, admin}]` : une région « Espace adhérent » (heading) contient le lien « Continuer avec Google ou code par e-mail » ; une région « Administration » (heading) contient « Continuer avec GitHub » et le texte « Réservé aux administrateurs du site. » ; dans le DOM, le lien adhérent précède le lien admin.
  - seulement `github/admin` : pas de heading « Espace adhérent » ; le bloc administration est rendu.
  - seulement `entra/member` : pas de heading « Administration ».
  - l'intro nouvelle remplace l'ancienne (mettre à jour le test #1031/#1322) : elle dit que la connexion adhérent ouvre l'espace personnel, et que les résultats se consultent aussi avec le code d'accès du club, sans compte.
  - `login_initiated` part toujours au clic, avec `provider` = slug, pour les deux blocs.
- [ ] **Step 2:** `npm --prefix frontend test -- app/login` → FAIL.
- [ ] **Step 3: implémenter.**
  - Carte principale `Card` : `Eyebrow` « Espace adhérent », h1 « Connexion », intro, `?error=` et états, puis les liens adhérent en bouton primaire (classes `tcn-btn` existantes, comme le lien « Mon compte » du tiroir de `UserMenu.tsx` ; vérifier les variantes dans `globals.css`).
  - Sous la carte, séparé : un bloc discret (pas de `Card` pleine, texte `--tcn-text-muted`) avec un h2 « Administration », « Réservé aux administrateurs du site. » et les liens admin en bouton secondaire.
  - Un seul composant de lien partagé par les deux blocs (href + `captureEvent`), pour ne pas dupliquer le `onClick`.
  - Supprimer les styles inline remplacés par des classes ou des composants.
- [ ] **Step 4:** `npm --prefix frontend test -- app/login`, puis `npm --prefix frontend test`, `npm --prefix frontend run lint`, `npm --prefix frontend run build`.
- [ ] **Step 5: commit** `feat(auth): split the login page into member and admin access (#1666)`
