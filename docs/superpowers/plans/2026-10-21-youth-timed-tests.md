# Tests chronométrés des jeunes : plan d'implémentation (#1365)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** enregistrer des tests chronométrés datés sur la fiche d'un jeune et
afficher une liste et une courbe par épreuve.

**Architecture:** une table `profile_measurements` sur le patron de
`profile_log_entries` (cascade ORM depuis le profil, donc purgée par
`purge-retention` sans code de plus), deux routes d'écriture et une de
suggestions sous `/admin/profiles`, un champ additif dans le détail du profil,
deux filtres facultatifs sur `GET /admin/training-sessions`. Côté front, une
carte `ProfileMeasurements` sur la fiche, et `ProgressionChart` généralisé par
un axe configurable.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 sync, Alembic, Pydantic v2, pytest ;
Next.js 16, React Query, vitest.

**Spec:** `docs/superpowers/specs/2026-10-21-youth-timed-tests-design.md`

## Global Constraints

- Commandes backend depuis `backend/` (`uv run …`), front depuis `frontend/`.
- Couches `api → services → repositories → DB` : seul un repository requête la Session.
- Tout identifiant entier en chemin, requête ou corps se type `DbId` (`app/schemas/ids.py`).
- Une seule migration Alembic, `down_revision` = tête courante (`f545c4879538` aujourd'hui ; revérifiée au rebase avant PR).
- Français pour l'UI et les messages d'erreur rendus ; anglais pour identifiants, tests, docstrings techniques, logs.
- Pas de tiret de ponctuation (—, –) dans le code ni les textes produits.
- `duration_tenths` : entier, dixièmes de seconde, 1 à 864000.
- `event` : retrait des blancs de bord, 1 à 100 caractères, comparé tel quel (casse comprise).
- Lecture des tests (`measurements`) : `None` sans `jeunes:read`, comme `log_entries`.
- Commits Conventional Commits, sans trailer `Co-Authored-By`.
- PostHog (#1307) : la fiche vit sous `/encadrement/jeunes/<id>`, déjà filtrée par `YOUTH_PATH` et testée (`frontend/lib/posthog.test.ts`, « /encadrement/jeunes/7 »). Rien à coder ; ne pas déplacer l'écran.

## Review Focus

1. Supprimer une séance qui porte un test : la séance part, le test reste avec `training_session_id = null` (test en tâche 1).
2. Saisie de durée mal formée (« 7:75 », « 42,35 », « abc », « 0 ») : refus en français sous le champ, aucun appel (test en tâche 3).
3. Séance d'un autre jour ou d'un autre jeune envoyée à l'API : 422, rien d'écrit (test en tâche 2).
4. Supprimer le test d'un autre profil par son id : 404 (test en tâche 2).
5. Fiche athlète et Mon espace inchangées par la généralisation de la courbe : les tests existants de `ProgressionChart` passent sans modification de leurs assertions (tâche 4).

---

### Task 1: Modèle, migration, purge et séance supprimée

**Files:**
- Create: `backend/app/models/profile_measurement.py`
- Modify: `backend/app/models/__init__.py`, `backend/app/models/personal_profile.py` (relation `measurements`), `backend/app/models/AGENTS.md` (inventaire, une ligne)
- Modify: `backend/app/repositories/profile_repository.py`, `backend/app/repositories/training_session_repository.py:126-130`
- Create: `backend/alembic/versions/<rev>_profile_measurements.py` (autogenerate)
- Test: `backend/tests/test_repositories/test_profile_repository.py`, `backend/tests/test_repositories/test_training_session_repository.py`, `backend/tests/test_services/test_retention_service.py`

**Interfaces:**
- Produces: modèle `ProfileMeasurement` (`__tablename__ = "profile_measurements"`, colonnes du tableau de la spec : `id`, `profile_id`, `measured_on`, `event` (`String(100)`), `duration_tenths`, `training_session_id` nullable, `created_by_user_id` nullable, `created_at`), relation `profile` ; `PersonalProfile.measurements` avec `cascade="all, delete-orphan"`.
- Produces (repository `profile_repository`) :
  - `list_measurements(db, profile_id: int) -> list[ProfileMeasurement]`, triés `event`, `measured_on`, `created_at` croissants.
  - `add_measurement(db, *, profile_id: int, measured_on: date, event: str, duration_tenths: int, training_session_id: int | None = None, created_by_user_id: int | None = None) -> ProfileMeasurement`
  - `get_measurement(db, profile_id: int, measurement_id: int) -> ProfileMeasurement | None` (None si l'id existe sous un autre profil)
  - `delete_measurement(db, measurement: ProfileMeasurement) -> None`
  - `list_measurement_events(db, organisation_id: int) -> list[str]`, distinctes, triées, jointes aux profils de l'organisation.
- Produces (`training_session_repository.delete_training_session`) : remet à `NULL` le `training_session_id` des `ProfileMeasurement` de la séance (un `update()` SQL) avant `db.delete`.

- [ ] **Step 1: Tests qui échouent**

`test_profile_repository.py` :
- `test_measurements_come_out_by_event_then_date` : trois tests ajoutés dans le désordre (« 50 m nage » 2026-10-14, « 1000 m » 2026-10-03, « 50 m nage » 2026-10-03) → `[(m.event, m.measured_on) for m in list_measurements(...)] == [("1000 m", date(2026,10,3)), ("50 m nage", date(2026,10,3)), ("50 m nage", date(2026,10,14))]`.
- `test_get_measurement_ignores_another_profile` : un test du profil A, `get_measurement(db, B.id, m.id) is None`.
- `test_measurement_events_are_distinct_and_sorted` : « 50 m nage » deux fois, « 1000 m » → `["1000 m", "50 m nage"]`.

`test_training_session_repository.py` :
- `test_deleting_a_session_keeps_its_measurements_without_session` : un test rattaché à la séance ; après `delete_training_session`, `db.get(ProfileMeasurement, m.id).training_session_id is None`.

`test_retention_service.py` (helper `_profile` existant, `NOW` existant) :
- `test_purging_a_profile_takes_its_measurements_with_it` : profil fini le 2025-06-30, un test ajouté, `purge_expired(db, now=NOW)` → `db.get(ProfileMeasurement, m.id) is None`.

- [ ] **Step 2: Lancer, constater l'échec**

Run: `uv run pytest tests/test_repositories/test_profile_repository.py tests/test_repositories/test_training_session_repository.py tests/test_services/test_retention_service.py -n 0 -q`
Expected: FAIL à l'import de `app.models.profile_measurement`.

- [ ] **Step 3: Modèle, relation, fonctions de repository** (signatures ci-dessus). Docstring du modèle sur le patron de `profile_log_entry.py` (rationale : #1365, la spec). Mettre à jour la docstring de `profile_repository.delete` (« son journal et ses tests partent par la cascade ORM »).

- [ ] **Step 4: Migration**

Run: `uv run alembic revision --autogenerate -m "profile measurements"` puis `uv run alembic upgrade head` puis `uv run alembic heads`
Expected: une seule tête, la nouvelle révision, `down_revision = "f545c4879538"`. Relire le fichier : uniquement la création de `profile_measurements` et son index `profile_id`.

- [ ] **Step 5: Lancer, constater le succès**

Run: commande du step 2.
Expected: PASS.

- [ ] **Step 6: Commit** `feat(jeunes): store timed tests of a youth profile (#1365)`

---

### Task 2: Service et API

**Files:**
- Modify: `backend/app/schemas/profile.py`, `backend/app/services/profile_service.py`, `backend/app/api/v1/admin_profiles.py`
- Modify: `backend/app/repositories/training_session_repository.py` (`list_all`), `backend/app/services/training_session_service.py:90`, `backend/app/api/v1/admin_training_sessions.py:43-49`
- Test: `backend/tests/test_auth/test_admin_profiles_api.py`, `backend/tests/test_api/test_admin_training_sessions.py`

**Interfaces:**
- Consumes: tâche 1.
- Produces (schémas) :
  - `ProfileMeasurementRead` : `id: int, measured_on: date, event: str, duration_tenths: int, training_session_id: int | None, created_at: UtcDatetime`.
  - `ProfileMeasurementCreate` (`extra="forbid"`, `str_strip_whitespace=True`) : `measured_on: date`, `event: str = Field(min_length=1, max_length=100)`, `duration_tenths: int = Field(ge=1, le=864000)`, `training_session_id: DbId | None = None`.
  - `ProfileDetailRead.measurements: list[ProfileMeasurementRead] | None`.
- Produces (service `profile_service`) :
  - `profile_detail_view` rend `measurements` (`None` sans données personnelles).
  - `add_measurement(db, actor: User, profile: PersonalProfile, *, measured_on, event, duration_tenths, training_session_id=None) -> PersonalProfile` ; lève `MeasurementSessionError(DomainError)` (status 422, message « Cette séance n'est pas une séance de ce jeune à cette date. ») si la séance n'existe pas, n'est pas à `measured_on` ou n'a pas le profil parmi ses inscrits (`training_session_repository.get` + `find_participant`). `logger.info("Profile measurement added: actor=%s profile=%s", …)`.
  - `delete_measurement(db, actor, profile, measurement_id: int) -> None` ; `NotFoundError("Ce test n'existe pas.")` si `get_measurement` rend `None`. `logger.info` équivalent.
  - `list_measurement_events(db) -> list[str]` (organisation par `default_organisation_id`).
- Produces (routes, `jeunes:write` sauf mention) :
  - `GET /admin/profiles/measurement-events` (`jeunes:read`) → `list[str]`, **déclarée avant** `GET /admin/profiles/{profile_id}`.
  - `POST /admin/profiles/{profile_id}/measurements` → `ProfileDetailRead`, 201, patron `add_log_entry` (`_detail_for`, commit).
  - `DELETE /admin/profiles/{profile_id}/measurements/{measurement_id}` → 204.
  - `GET /admin/training-sessions?profile_id=&date=` : deux `Query` facultatifs (`DbId | None`, `date | None`) passés à `list_training_session_views(db, *, profile_id=None, on=None)` puis `training_session_repository.list_all(db, *, profile_id=None, on=None)` (filtre `EXISTS` sur `TrainingParticipant` pour `profile_id`, égalité sur `date`). Absents, réponse inchangée.

- [ ] **Step 1: Tests qui échouent** (`test_admin_profiles_api.py`, fixture `profile` et `ouvrir_session` existantes)

- `test_a_measurement_appears_in_the_detail` : `POST {BASE}/{id}/measurements` `{"measured_on": "2026-10-03", "event": " 50 m nage ", "duration_tenths": 423}` → 201, `body["measurements"] == [{"id": ANY, "measured_on": "2026-10-03", "event": "50 m nage", "duration_tenths": 423, "training_session_id": None, "created_at": ANY}]`.
- `test_a_measurement_with_an_invalid_duration_is_refused` : paramétré `duration_tenths` ∈ `[0, 864001]` et `event` ∈ `["", "x" * 101]` → 422.
- `test_a_measurement_tied_to_a_session_of_the_youth_that_day` : séance du 2026-10-03 créée par `POST /api/v1/admin/training-sessions`, jeune inscrit par `POST …/participants` → 201, `training_session_id` rendu.
- `test_a_measurement_tied_to_a_foreign_session_is_refused` : paramétré « autre date » et « jeune non inscrit » → 422, `measurements == []` au `GET` suivant.
- `test_deleting_a_measurement` : 204, puis absent du détail.
- `test_deleting_a_measurement_of_another_profile_returns_404` : test créé sous un profil A, `DELETE {BASE}/{B}/measurements/{m}` → 404.
- `test_measurement_events_are_suggested` : deux profils, épreuves « 50 m nage » et « 1000 m » → `GET {BASE}/measurement-events` == `["1000 m", "50 m nage"]`.
- Ajouter les trois routes aux paramétrages existants des gardes (`test_a_write_resource_refuses_the_anonymous`, `…_without_privilege`, `test_jeunes_read_alone_does_not_pass_any_write` pour POST/DELETE ; `test_a_read_refuses_*` pour `measurement-events`).
- Étendre `_profile_writes` / `test_writes_hide_personal_data_from_a_session_without_jeunes_read` : le POST d'un test rend `measurements is None` sans `jeunes:read`.

`test_admin_training_sessions.py` :
- `test_the_list_filters_by_profile_and_date` : deux séances le 2026-10-03, le jeune inscrit à une seule, une troisième le 2026-10-04 où il est inscrit → `?profile_id=&date=2026-10-03` rend la seule première.

- [ ] **Step 2: Lancer, constater l'échec**

Run: `uv run pytest tests/test_auth/test_admin_profiles_api.py tests/test_api/test_admin_training_sessions.py -q`
Expected: FAIL (404/405 sur les nouvelles routes, `KeyError: 'measurements'`).

- [ ] **Step 3: Schémas, service, routes** (interfaces ci-dessus). Docstring de module de `admin_profiles.py` : compter les nouvelles ressources.

- [ ] **Step 4: Suite complète backend et lint**

Run: `uv run pytest -m "not integration" -q` puis `uv run ruff check .`
Expected: PASS, dont `tests/test_api/test_id_bounds_api.py` et les inventaires de routes de `tests/test_auth/` (s'ils exigent d'inscrire les nouvelles routes, les inscrire).

- [ ] **Step 5: Commit** `feat(jeunes): record and delete timed tests through the API (#1365)`

---

### Task 3: Saisie et affichage d'une durée

**Files:**
- Create: `frontend/lib/utils/duration.ts`, `frontend/lib/utils/duration.test.ts`

**Interfaces:**
- Produces: `parseDuration(text: string): number | null` (dixièmes, `null` si invalide) et `formatDuration(tenths: number): string`.

Règles de `parseDuration` : blancs de bord retirés ; `ss[,d]`, `m:ss[,d]`, `h:mm:ss[,d]` ; virgule ou point ; au plus un chiffre décimal ; sous des minutes, secondes < 60 sur deux chiffres ; sous des heures, minutes < 60 sur deux chiffres ; résultat de 1 à 864000, sinon `null`.
Règles de `formatDuration` : sous une minute « 42,3 s » / « 42 s » ; sinon « 7:42,3 » / « 7:42 » ; au delà d'une heure « 1:02:05 ». Le dixième n'apparaît que s'il est non nul.

- [ ] **Step 1: Tests qui échouent**

```ts
it.each([
  ["42,3", 423], ["42.3", 423], ["42", 420], [" 7:42,3 ", 4623], ["7:42", 4620], ["1:02:05", 37250], ["0,1", 1],
])("lit %s", (texte, attendu) => expect(parseDuration(texte)).toBe(attendu));
it.each(["", "abc", "0", "7:75", "42,35", "1:2:05", "1:60:00", "25:00:00", "-3"])("refuse %s", (texte) =>
  expect(parseDuration(texte)).toBeNull());
it.each([[423, "42,3 s"], [420, "42 s"], [4623, "7:42,3"], [4620, "7:42"], [37250, "1:02:05"]])(
  "affiche %i", (dixiemes, attendu) => expect(formatDuration(dixiemes)).toBe(attendu));
```

- [ ] **Step 2: Lancer, constater l'échec** — Run: `npx vitest run lib/utils/duration.test.ts` ; Expected: FAIL (module absent).
- [ ] **Step 3: Implémenter** les deux fonctions (une expression régulière par forme suffit).
- [ ] **Step 4: Lancer, constater le succès** — même commande, PASS.
- [ ] **Step 5: Commit** `feat(jeunes): parse and format timed-test durations (#1365)`

---

### Task 4: Généraliser `ProgressionChart`

**Files:**
- Modify: `frontend/components/charts/ProgressionChart.tsx`, `frontend/lib/utils/ranking.ts` (type `ProgressionPoint`) et tout consommateur que `npx tsc --noEmit` signale (`lib/mon-espace.ts`, `components/mon-espace/OngletProgression.tsx`, `lib/utils/ranking.test.ts`, `ProgressionChart.test.tsx`)
- Test: `frontend/components/charts/ProgressionChart.test.tsx`

**Interfaces:**
- Produces: `ProgressionPoint` devient `{ id: number; eventDate: string; value: number }` (renommage de `participationId` → `id`, `percent` → `value`, sens inchangé).
- Produces: `export interface ProgressionAxis { max: number; tick(value: number): string; label(value: number): string; spoken(value: number): string; caption: string; ariaLabel: string; emptyTitle: string; emptyDescription: string }` et `export const PERCENT_AXIS: ProgressionAxis`, qui porte exactement les valeurs actuelles (`max: 100`, `tick: pctFr(v, 0)`, `label: "Top " + pctFr(v, 0)`, `spoken: "top v pour cent"`, la légende, le libellé `aria-label`, les deux textes de l'état vide).
- Produces: `ProgressionChart({ points, comparaison, nonFiables, axis = PERCENT_AXIS })`. Le plafond `bottom = Math.min(axis.max, …)` remplace le `100` en dur ; tout le reste du calcul est inchangé.

- [ ] **Step 1: Test qui échoue** — `it("trace une durée avec son propre axe")` : trois points `value` 450, 430, 423 et un axe de test dont `label` rend `formatDuration` ; le texte « 42,3 s » est affiché, aucun « % » n'apparaît, la légende de l'axe de test remplace « Classement au sein du peloton ».
- [ ] **Step 2: Lancer, constater l'échec** — Run: `npx vitest run components/charts/ProgressionChart.test.tsx` ; Expected: FAIL.
- [ ] **Step 3: Renommer `ProgressionPoint` et ajouter `axis`.** Les tests existants n'ont droit qu'au renommage des champs, aucune assertion ne change.
- [ ] **Step 4: Vérifier** — Run: `npx vitest run components/charts lib/utils lib/mon-espace* components/mon-espace` puis `npx tsc --noEmit` ; Expected: PASS, aucune erreur de type.
- [ ] **Step 5: Commit** `refactor(charts): let ProgressionChart draw any value axis (#1365)`

---

### Task 5: Carte « Tests chronométrés » sur la fiche jeune

**Files:**
- Create: `frontend/components/admin/jeunes/ProfileMeasurements.tsx`, `frontend/components/admin/jeunes/ProfileMeasurements.test.tsx`
- Modify: `frontend/lib/types.ts` (`ProfileMeasurement`, `ProfileDetail.measurements`), `frontend/lib/api/client.ts` (près de `addProfileLogEntry`), `frontend/lib/queries/admin.ts`, `frontend/lib/queries/keys.ts`, `frontend/components/admin/ProfileDetail.tsx` (carte posée sous le journal de bord)

**Interfaces:**
- Consumes: `parseDuration`, `formatDuration` (tâche 3) ; `ProgressionChart`, `ProgressionAxis` (tâche 4) ; routes de la tâche 2.
- Produces:
  - Type `ProfileMeasurement { id: number; measured_on: string; event: string; duration_tenths: number; training_session_id: number | null; created_at: string }` ; `ProfileDetail.measurements: ProfileMeasurement[] | null`.
  - Client : `addProfileMeasurement(id, body: { measured_on: string; event: string; duration_tenths: number; training_session_id: number | null })`, `deleteProfileMeasurement(id, measurementId)`, `listMeasurementEvents()`, `listTrainingSessions(filtre?: { profileId: number; date: string })` (paramètres de requête ajoutés seulement si fournis).
  - Hooks : `useAddProfileMeasurement()`, `useDeleteProfileMeasurement()` (invalident `queryKeys.profile(id)` et `queryKeys.measurementEvents()`), `useMeasurementEvents()`, `useTrainingSessionsOn(profileId, date)` (clé `queryKeys.trainingSessionsOn(profileId, date)`).
  - Composant `ProfileMeasurements({ profileId, measurements, peutEcrire }: { profileId: number; measurements: ProfileMeasurement[]; peutEcrire: boolean })`. `ProfileDetail` ne le rend que si `data.measurements !== null`.

Écran (textes exacts) : titre « Tests chronométrés » (même style que « Journal de bord ») ; formulaire si `peutEcrire` : « Date » (défaut `localToday()`), « Épreuve » (`<datalist>` des suggestions), « Durée » (aide « 42,3 ou 7:42 ou 1:02:05 », `inputMode="decimal"`), « Séance » (`<select>` avec une option « Aucune », masqué si la liste du jour est vide), bouton « Enregistrer le test ». Durée illisible : « Durée illisible. Exemples : 42,3 ou 7:42. » sous le champ, `aria-invalid`, aucun appel. Erreur serveur : `toast.error(messageDeRefus(erreur))`. Sans test : « Aucun test chronométré pour l'instant. » (même rendu que l'état vide du journal). Par épreuve (ordre de l'API) : sous-titre, `ProgressionChart` avec un axe `DURATION_AXIS` défini dans ce fichier (`max: Infinity`, `tick`/`label`/`spoken` = `formatDuration`, `ariaLabel` « Évolution de la durée (plus court, meilleur) », légende « Durée à chaque test, plus haut, plus rapide. », état vide « Pas encore assez de tests » / « Trois tests de cette épreuve sont nécessaires pour tracer une progression. »), puis la liste (date `formatDate`, durée `formatDuration`, « Supprimer » si `peutEcrire`, confirmé par `useDangerConfirm` sur le patron de son usage dans `ProfileDetail.tsx`).

- [ ] **Step 1: Tests qui échouent** (`ProfileMeasurements.test.tsx`, mocks sur le patron de `ProfileDetail.test.tsx`)
  - deux épreuves → deux sous-titres, une liste par épreuve, durées formatées (« 42,3 s »).
  - saisie « 7:42,3 » → `addProfileMeasurement` appelé avec `duration_tenths: 4623` et l'épreuve débarrassée de ses bords.
  - saisie « 7:75 » → message « Durée illisible. Exemples : 42,3 ou 7:42. », aucun appel.
  - `peutEcrire` faux → ni formulaire ni bouton « Supprimer ».
  - aucune séance ce jour → pas de champ « Séance » ; une séance → option proposée et `training_session_id` envoyé.
- [ ] **Step 2: Lancer, constater l'échec** — Run: `npx vitest run components/admin/jeunes/ProfileMeasurements.test.tsx` ; Expected: FAIL.
- [ ] **Step 3: Types, client, hooks, composant, branchement dans `ProfileDetail`.**
- [ ] **Step 4: Vérifier** — Run: `npm test`, `npm run lint`, `npm run build` ; Expected: tout vert.
- [ ] **Step 5: Commit** `feat(jeunes): record timed tests and show their progression on the youth page (#1365)`
