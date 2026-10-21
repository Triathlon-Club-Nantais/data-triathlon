# Taux d'assiduité par jeune et par groupe (#1364) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exploiter l'appel déjà stocké (`training_participant.present`) pour afficher un taux d'assiduité sur la fiche jeune (avec la série d'absences en cours) et sur chaque carte de la page des groupes.

**Architecture:** Deux requêtes de lecture dans `training_session_repository` (historique de présence d'un profil, agrégat par groupe), bornées par la saison FFTri ; `profile_service` et `training_group_service` en tirent des champs additionnels des réponses existantes ; le front les affiche. Aucune écriture, aucune migration.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 sync, Pydantic v2, pytest ; Next.js 16, TanStack Query, vitest.

**Spec:** issue #1364 (`gh issue view 1364`) + décisions de brainstorming du 2026-10-21, reprises dans Global Constraints.

## Global Constraints

- Saison = saison FFTri en cours, bascule au **1er novembre** (`SEASON_SWITCH_MONTH = 11` de `app/services/fftri_category.py`) : saison S = [S-1-11-01, S-10-31] incluses. Décision utilisateur, même si les taux repartent à vide le 1/11.
- `present IS NULL` (appel non fait) n'entre ni au numérateur ni au dénominateur.
- Taux d'un groupe = présences aux **séances qui visent ce groupe** (`training_session_groups`), quel que soit le participant. Un jeune qui change de groupe laisse son historique à l'ancien. Une séance visant deux groupes compte pour les deux. Décision utilisateur.
- Séance annulée = séance supprimée (cascade sur ses inscriptions) ou jamais pointée : exclue d'office, aucun code dédié.
- Aucune migration. Lecture seule sur les présences.
- Garde `jeunes:read` : `attendance` du détail profil vaut `None` sans ce pouvoir (même règle que `emergency_contact`/`notes`/`log_entries`, #1472). La liste des groupes est déjà gardée.
- Couches `api → services → repositories` ; seuls les repositories construisent des requêtes.
- Champs **ajoutés** aux réponses `/api/v1`, aucun champ retiré ni renommé.
- Le front reste sous `/encadrement/jeunes/*`, déjà couvert par le filtre PostHog (#1307) : aucune route nouvelle.
- Session parallèle sur #1365 (épreuves chronométrées) : toucher `frontend/components/admin/ProfileDetail.tsx` d'**une seule ligne** (le bloc vit dans son propre composant).
- Libellés UI en français, identifiants et tests en anglais (noms de composants front : convention française du dossier `components/admin/jeunes`). Pas de tiret de ponctuation dans la copie.
- Commits Conventional Commits, sans trailer `Co-Authored-By`.

## Review Focus

- Séance du 31 octobre vs 1er novembre : la borne de saison doit être incluse des deux côtés, testée en Task 1.
- Deux séances le même jour dont une sans heure : la série d'absences doit lire la séance sans heure comme la plus tardive (patron `list_all`), testée en Task 1.
- Jeune pointé dans une séance multi-groupes : compté dans chaque groupe visé, testé en Task 1.
- Aucun appel dans la saison : la fiche dit « Aucun appel cette saison. », la carte « Assiduité : aucun appel », jamais `NaN %` ni `0 %` ; testé en Task 3.
- Écriture du profil avec `jeunes:write` seul : `attendance` à `None`, testé en Task 2 via `PERSONAL_FIELDS`.

---

### Task 1: Borne de saison FFTri et requêtes de présence

**Files:**
- Modify: `backend/app/services/fftri_category.py`
- Modify: `backend/app/repositories/training_session_repository.py`
- Test: `backend/tests/test_repositories/test_training_session_repository.py`
- Test: `backend/tests/test_services/test_fftri_category.py` (existant, y ajouter)

**Interfaces:**
- Produces:
  - `fftri_season_bounds(on: date) -> tuple[date, date]` dans `app/services/fftri_category.py` : bornes incluses de la saison FFTri contenant `on`. Factoriser le calcul de saison avec `fftri_category` (un helper privé `_fftri_season(on) -> int`).
  - `training_session_repository.presence_history_of_profile(db: Session, profile_id: int, *, date_from: date, date_to: date) -> list[bool]` : les `present` non NULL du profil sur les séances de `[date_from, date_to]`, **la plus récente d'abord** : `date desc`, puis `start_time.is_(None) desc` (séance sans heure = la plus tardive de sa date, miroir de `list_all`), puis `start_time desc`, puis `TrainingSession.id desc`.
  - `training_session_repository.attendance_by_group(db: Session, *, date_from: date, date_to: date) -> dict[int, tuple[int, int]]` : `training_group_id → (attended, pointed)` en une requête (`training_session_groups` ⨝ `TrainingSession` ⨝ `TrainingParticipant`, `present IS NOT NULL`, `group_by` groupe ; `attended` = `sum(case((present.is_(True), 1), else_=0))`). Un groupe sans séance pointée n'apparaît pas.

- [ ] **Step 1: Write the failing tests**

`test_fftri_category.py` :
```python
def test_fftri_season_bounds_switch_on_november_first():
    assert fftri_season_bounds(date(2026, 10, 31)) == (date(2025, 11, 1), date(2026, 10, 31))
    assert fftri_season_bounds(date(2026, 11, 1)) == (date(2026, 11, 1), date(2027, 10, 31))
```

`test_training_session_repository.py` (profils 1, 2, 42 fournis par la fixture `_profils` ; groupes via `training_group_repository.create(db_session, organisation_id=..., name=...)`, liaison via `training_session_repository.set_groups`, inscription via `training_session_repository.add_participant(..., present=...)`) ; `SEASON = (date(2025, 11, 1), date(2026, 10, 31))` :

- `test_presence_history_keeps_pointed_sessions_of_the_season_latest_first` : profil 1 inscrit à 2025-10-31 (True), 2025-11-01 (True), 2026-03-04 (None), 2026-03-11 18:00 (True), 2026-03-11 sans heure (False), 2026-11-01 (True) → `presence_history_of_profile(db_session, 1, date_from=..., date_to=...) == [False, True, True]`.
- `test_presence_history_ignores_a_deleted_session` : séance pointée False puis `delete_training_session` → `== []`.
- `test_attendance_by_group_follows_the_session_group_across_a_group_change` : groupe A, séance A (2026-01-07) avec profil 1 True et profil 2 None ; groupe B, séance B (2026-02-04) avec profil 1 False ; groupe C sans séance → `== {A.id: (1, 1), B.id: (0, 1)}`.
- `test_attendance_by_group_counts_a_multi_group_session_for_each_group` : séance visant A et B, profil 1 True, profil 2 False → `{A.id: (1, 2), B.id: (1, 2)}`.
- `test_attendance_by_group_ignores_sessions_outside_the_season` : séance A du 2025-10-31 pointée True → `== {}`.

- [ ] **Step 2: Run tests to verify they fail**

Run (depuis `backend/`): `uv run pytest tests/test_repositories/test_training_session_repository.py tests/test_services/test_fftri_category.py -n 0 -q`
Expected: FAIL (ImportError / AttributeError sur les trois nouveaux noms).

- [ ] **Step 3: Implement the three functions** (signatures ci-dessus).

- [ ] **Step 4: Run tests to verify they pass**

Même commande. Expected: PASS. Puis `uv run ruff check .` : aucun avertissement.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fftri_category.py backend/app/repositories/training_session_repository.py backend/tests/test_repositories/test_training_session_repository.py backend/tests/test_services/test_fftri_category.py
git commit -m "feat(jeunes): query season attendance per youth and per training group (#1364)"
```

### Task 2: Exposer l'assiduité dans l'API (détail profil, liste des groupes)

**Files:**
- Modify: `backend/app/services/profile_service.py` (`profile_detail_view`, nouvelle `attendance_summary`)
- Modify: `backend/app/services/training_group_service.py` (`list_group_views`)
- Modify: `backend/app/schemas/profile.py` (`ProfileAttendanceRead`, champ `ProfileDetailRead.attendance`)
- Modify: `backend/app/schemas/training_group.py` (`TrainingGroupRead.attended`, `.pointed`)
- Test: `backend/tests/test_services/test_profile_service.py` (à créer)
- Test: `backend/tests/test_auth/test_admin_profiles_api.py`
- Test: `backend/tests/test_api/test_admin_training_groups.py`

**Interfaces:**
- Consumes: `fftri_season_bounds`, `presence_history_of_profile`, `attendance_by_group` (Task 1).
- Produces (contrat JSON lu par Task 3) :
  - `GET /admin/profiles/{id}` : `"attendance": {"attended": int, "pointed": int, "absence_streak": int} | null`, `null` sans `jeunes:read`.
  - `GET /admin/training-groups` : chaque élément gagne `"attended": int, "pointed": int` (0 et 0 sans séance pointée).
  - `profile_service.attendance_summary(history: list[bool]) -> dict` : `{"attended": sum, "pointed": len, "absence_streak": nombre de False en tête de liste}`.
- La date du jour vient de `utcnow().date()` (`from app.core.time import utcnow`, importé dans chaque service pour être figeable par `monkeypatch.setattr(<module>, "utcnow", ...)`).

- [ ] **Step 1: Write the failing tests**

`test_profile_service.py` :
```python
@pytest.mark.parametrize(("history", "expected"), [
    ([], {"attended": 0, "pointed": 0, "absence_streak": 0}),
    ([False, False, True, False], {"attended": 1, "pointed": 4, "absence_streak": 2}),
    ([True, False], {"attended": 1, "pointed": 2, "absence_streak": 0}),
])
def test_attendance_summary(history, expected):
    assert profile_service.attendance_summary(history) == expected
```

`test_admin_profiles_api.py` :
- Ajouter `"attendance"` à `PERSONAL_FIELDS` (les tests #1472 existants couvrent alors le `None` sans `jeunes:read`).
- `test_detail_reports_the_season_attendance` : horloge figée `monkeypatch.setattr(profile_service, "utcnow", lambda: datetime(2026, 10, 15, 12, 0))` ; profil inscrit (via repositories) à 2026-09-02 True puis 2026-09-09 False → `body["attendance"] == {"attended": 1, "pointed": 2, "absence_streak": 1}`.

`test_admin_training_groups.py` :
- `test_full_cycle` : l'égalité de la liste devient `[{"id": group_id, "name": "Benjamins mercredi", "member_count": 1, "attended": 0, "pointed": 0}]`.
- `test_list_reports_the_season_attendance_of_each_group` : horloge figée sur `training_group_service.utcnow` à 2026-10-15 ; une séance du groupe le 2026-09-02 avec `profile_id` présent → l'élément du groupe porte `"attended": 1, "pointed": 1`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services/test_profile_service.py tests/test_auth/test_admin_profiles_api.py tests/test_api/test_admin_training_groups.py -n 0 -q`
Expected: FAIL (`attendance_summary` absent, clés `attendance`/`attended` absentes).

- [ ] **Step 3: Implement**

`attendance` ne se calcule que dans la branche `with_personal_data` de `profile_detail_view` (`None` sinon). `list_group_views` appelle `attendance_by_group` une fois et lit `.get(group.id, (0, 0))`. Schémas : `ProfileAttendanceRead(BaseModel)` avec les trois `int`, `ProfileDetailRead.attendance: ProfileAttendanceRead | None`.

- [ ] **Step 4: Run tests to verify they pass**

Même commande, puis la suite complète `uv run pytest -m "not integration" -q` et `uv run ruff check .`. Expected: tout PASS (une autre égalité stricte sur ces réponses casserait ici : la mettre à jour, sans retirer de champ).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/app/schemas backend/tests
git commit -m "feat(jeunes): expose season attendance on the youth profile and training groups (#1364)"
```

### Task 3: Bloc « Présence » sur la fiche jeune et assiduité des groupes

**Files:**
- Modify: `frontend/lib/types.ts` (`ProfileAttendance`, `ProfileDetail.attendance`, `TrainingGroup.attended`/`.pointed`)
- Modify: `frontend/lib/utils/format.ts` (`tauxAssiduite`)
- Create: `frontend/components/admin/jeunes/PresenceDuProfil.tsx`
- Modify: `frontend/components/admin/ProfileDetail.tsx` (une ligne, avant `<GroupesDuProfil …/>`)
- Modify: `frontend/components/admin/jeunes/GroupesList.tsx` (une ligne dans la carte, sous le nombre de membres)
- Test: `frontend/lib/utils/format.test.ts`, `frontend/components/admin/jeunes/PresenceDuProfil.test.tsx`, `frontend/components/admin/jeunes/GroupesList.test.tsx`

**Interfaces:**
- Consumes: le contrat JSON de Task 2.
- Produces:
  - `interface ProfileAttendance { attended: number; pointed: number; absence_streak: number }` ; `ProfileDetail.attendance: ProfileAttendance | null` (documenter : `null` sans `jeunes:read`).
  - `tauxAssiduite(attended: number, pointed: number): number | null` : `null` si `pointed === 0`, sinon `Math.round((100 * attended) / pointed)`.
  - `PresenceDuProfil({ attendance }: { attendance: ProfileAttendance })`, rendu dans `ProfileDetail` par `{data.attendance && <PresenceDuProfil attendance={data.attendance} />}`.

Copie exacte (espace insécable U+00A0 avant `%`) :
- Titre de section : `Présence` (même style que « Groupes » : `text-lg font-bold`).
- Sous-titre discret (`text-[var(--tcn-text-faint)] text-sm`) : `Saison FFTri en cours, depuis le 1er novembre. Seules les séances pointées comptent.`
- `pointed === 0` : `Aucun appel cette saison.`
- Sinon : `Assiduité : {taux} % ({motCompte(attended, "séance")} sur {pointed})`.
- `absence_streak === 1` : `Dernière séance manquée.` ; `absence_streak >= 2` : `{n} séances manquées d'affilée.` ; rien à 0.
- Carte de groupe : `Assiduité : {taux} %`, ou `Assiduité : aucun appel` si `pointed === 0`.

- [ ] **Step 1: Write the failing tests**

- `format.test.ts` : `tauxAssiduite(0, 0)` → `null` ; `tauxAssiduite(2, 3)` → `67` ; `tauxAssiduite(3, 3)` → `100`.
- `PresenceDuProfil.test.tsx` : `{1, 2, 1}` affiche `Assiduité : 50 % (1 séance sur 2)` et `Dernière séance manquée.` ; `{0, 0, 0}` affiche `Aucun appel cette saison.` et aucun `%` ; `{1, 4, 3}` affiche `3 séances manquées d'affilée.` ; `{4, 4, 0}` n'affiche aucune ligne « manquée ».
- `GroupesList.test.tsx` : étendre la donnée simulée avec `attended`/`pointed` ; un groupe `{3, 4}` affiche `Assiduité : 75 %`, un groupe `{0, 0}` affiche `Assiduité : aucun appel`.

- [ ] **Step 2: Run tests to verify they fail**

Run (depuis `frontend/`): `npx vitest run lib/utils/format.test.ts components/admin/jeunes/PresenceDuProfil.test.tsx components/admin/jeunes/GroupesList.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement** (types, helper, composant, deux insertions).

- [ ] **Step 4: Verify**

Run: `npm test`, `npm run lint`, `npm run build`. Expected: tout vert (une fixture `TrainingGroup`/`ProfileDetail` d'un autre test qui ne compile plus reçoit les nouveaux champs).

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(jeunes): show attendance on the youth profile and training group cards (#1364)"
```
