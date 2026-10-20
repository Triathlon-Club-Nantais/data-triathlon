# « Ma saison au club » dans Mon espace (#1671) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** le membre rattaché voit en tête de la colonne de droite de Mon espace où il en est de la validation de la saison en cours : épreuves comptées sur 3, bénévolat, statut.

**Architecture:** endpoint `GET /auth/me/season-quota` qui appelle `admin_actions.season_quota` tel quel pour la fiche rattachée et la saison en cours, `null` sans fiche. Un composant `MaSaisonAuClub` le lit et s'insère en premier dans `ColonneDroite`.

**Tech Stack:** FastAPI, Pydantic v2, pytest ; Next.js 16, TanStack Query, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-20-mon-espace-vague-2-design.md` (section « #1671 »).

## Global Constraints

- La règle du quota vit dans `core.season.season_quota_met` et `admin_actions.season_quota` : ne la dupliquer ni côté front ni dans un nouveau service. Le seuil affiché (« sur 3 ») vient de `SEASON_QUOTA_EVENTS` exposé par l'API, pas d'une constante front.
- Principe IV : endpoint et champs ajoutés seulement.
- Texte visible en français ; identifiants, tests, commits en anglais.
- Jamais de tiret (—, –, -) comme ponctuation dans les commentaires, textes UI, messages de commit ou corps de PR.
- Ne pas toucher : config pytest/vitest, conftest, ci.yml, `frontend/app/login`, `/account`, `components/auth`, la fiche athlète, les écrans jeunes.
- Aucun trailer `Co-Authored-By`, aucune mention d'IA.

## Review Focus

- Changement de saison au 1ᵉʳ septembre : la carte suit `current_season()` du serveur, jamais la sélection de la page (titre « Saison Y — Y+1 » via `seasonLabel`).
- Disciplines hors FFTRI et DNS : non comptées (déjà dans `season_quota`, test API qui le fige).
- Bénévolat en attente seulement : afficher « en attente de validation », pas « aucune action ».
- Plus de 3 épreuves : « 5 épreuves comptées », sans « 5 sur 3 » trompeur (afficher « 3 requises » à part, ou plafonner la jauge).
- Erreur réseau : la carte affiche un message court, le reste de la colonne s'affiche.

---

### Task 1: `GET /auth/me/season-quota`

**Files:**
- Modify: `backend/app/schemas/admin.py` (`SeasonQuota` : champs ajoutés `season: int`, `required_events: int`) ou un `MySeasonQuota` dédié dans `backend/app/schemas/` si l'ajout gêne l'endpoint admin ; préférer l'ajout à `SeasonQuota` (un seul schéma, champs additifs).
- Modify: `backend/app/services/admin_actions.py` (`season_quota` rend aussi `season` et `required_events=SEASON_QUOTA_EVENTS`)
- Modify: `backend/app/api/v1/auth.py` (nouvelle route, à côté de `list_my_volunteer_actions`)
- Test: `backend/tests/test_api/test_my_season_quota_api.py` (fixtures et client authentifié copiés du patron de `tests/test_api/test_result_claims_api.py`)

**Interfaces:**
- Produces: `GET /api/v1/auth/me/season-quota` → `SeasonQuota | null` = `{validated_count, has_volunteer_action, has_pending_volunteer_action, season_validated, quota_met, season, required_events}`.

- [ ] **Step 1: tests qui échouent** :
  - `test_unauthenticated_is_401`.
  - `test_without_claimed_athlete_returns_null` : 200, corps `null`.
  - `test_counts_current_season_for_claimed_athlete` : horloge figée (patron `utcnow` figé déjà utilisé dans les tests de saison) ; 2 résultats finisher validés FFTRI dans la saison en cours, 1 DNS, 1 de la saison précédente, une action de bénévolat validée → `validated_count == 2`, `has_volunteer_action is True`, `quota_met is False`, `season == current_season()`, `required_events == 3`.
  - `test_admin_season_quota_still_works` : l'endpoint admin rend les deux champs ajoutés (non régression du schéma partagé).
- [ ] **Step 2:** `uv run pytest tests/test_api/test_my_season_quota_api.py -n 0 -q` → FAIL.
- [ ] **Step 3:** route `get_my_season_quota(user = Depends(current_user), db = Depends(get_db)) -> SeasonQuota | None` : `None` si `user.athlete_id is None`, sinon `admin_actions.season_quota(db, athlete_id=user.athlete_id, season=current_season())`.
- [ ] **Step 4:** PASS ; `uv run pytest -m "not integration" -q` et `uv run ruff check .` propres.
- [ ] **Step 5: Commit** `feat(api): expose my season validation progress under /auth/me (#1671)`.

### Task 2: carte « Ma saison au club »

**Files:**
- Modify: `frontend/lib/types.ts` (type `SeasonQuota` s'il existe déjà côté admin : `git grep -n 'SeasonQuota' frontend/lib` ; y ajouter `season`, `required_events`)
- Modify: `frontend/lib/api/client.ts` (`getMySeasonQuota: () => request<SeasonQuota | null>("/auth/me/season-quota")`)
- Modify: `frontend/lib/queries/keys.ts` et `frontend/lib/queries/auth.ts` (`useMySeasonQuota(enabled: boolean)`, clé `mySeasonQuota()`)
- Create: `frontend/components/mon-espace/MaSaisonAuClub.tsx`, `frontend/components/mon-espace/MaSaisonAuClub.test.tsx`
- Modify: `frontend/components/mon-espace/ColonneDroite.tsx` (rendre `<MaSaisonAuClub />` en premier ; si la carte `MesDemandes` de #1670 est déjà sur main, la placer juste après)

**Interfaces:**
- Consumes: `GET /auth/me/season-quota` (tâche 1).
- Produces: `export function MaSaisonAuClub(): JSX.Element | null`.

- [ ] **Step 1: tests qui échouent** :
  - `shows validated season` : `season_validated: true` → « Saison validée ».
  - `shows quota met awaiting club validation` : `quota_met: true, season_validated: false` → « Conditions remplies, en attente de validation par le club ».
  - `shows what is missing` : `validated_count: 1, required_events: 3, has_volunteer_action: false, has_pending_volunteer_action: true` → « 1 épreuve comptée », « 3 requises » (formulation libre mais les deux nombres visibles), « en attente de validation » pour le bénévolat ; aucune action → lien « Déclarer une action » vers `/benevolat`.
  - `renders nothing when the API returns null`.
  - `shows the season in the title` : `season: 2026` → titre contenant `seasonLabel(2026)`.
- [ ] **Step 2:** `npx vitest run components/mon-espace/MaSaisonAuClub.test.tsx` → FAIL.
- [ ] **Step 3:** implémenter, même enveloppe de carte que `ProchainPalier` ; pluriels corrects ; squelette court pendant le chargement (`Skeleton`), message court en erreur.
- [ ] **Step 4:** brancher dans `ColonneDroite` ; `npx vitest run components/mon-espace` → PASS.
- [ ] **Step 5:** `npm test`, `npm run lint`, `npx tsc --noEmit` propres.
- [ ] **Step 6: Commit** `feat(mon-espace): show my season validation progress (#1671)`.
