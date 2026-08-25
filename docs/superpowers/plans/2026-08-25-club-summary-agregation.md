# Agrégation serveur de /club — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le transport de 5000 participations par page `/club` par
un nouvel endpoint `GET /club/summary` (agrégation SQL) + une réduction du
`page_size` des résultats récents, sans changer le rendu visible de la page.

**Architecture:** `app/api/v1/club.py` (nouveau routeur, fin) délègue à
`app/services/club_service.py` (bucketing des podiums par mode de rang), qui
appelle deux nouvelles fonctions de repository faisant l'agrégation en SQL —
`athlete_repository.club_roster` (GROUP BY) et `participation_repository.club_podiums`
(SELECT filtré, colonnes utiles seulement). Côté front, `club/page.tsx` passe
de 2 à 3 appels parallèles, tous légers ; `ClubPodiumKpi` et `PodiumsList`
restent des composants client lisant `?rank=` via `useSearchParams`
(`pushState`, inchangé) mais reçoivent un payload pré-agrégé au lieu du
tableau complet.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, pytest ; Next.js
16 App Router, TypeScript, Vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-08-25-club-summary-agregation-design.md`

## Global Constraints

- Aucun plafond sur `podiums` (contrat « voir les N autres » = la totalité) — pas de `LIMIT` sur `club_podiums`.
- `roster` reste plafonné à 12 (paramètre `limit`, valeur par défaut).
- `federal_only` : même défaut neutre (`False`) et même `federal_clause(Course.event_type)` que partout ailleurs.
- Toute nouvelle fonction lisant des participations doit exclure `is_pending_validation=True` via `validated_clause` (#270) — invariant vérifié par test comportemental, pas par lecture statique.
- Identifiants techniques nouveaux en anglais (Principe I) : `club_roster`, `club_podiums`, `ClubRosterEntry`, `ClubPodiumEntry`, `ClubPodiums`, `ClubSummary`, `get_club_summary`.
- `RankTypeToggle`/`pushState` sur `?rank=` : **ne pas toucher**.

---

## Task 1: Schémas Pydantic `ClubSummary`

**Files:**
- Create: `backend/app/schemas/club.py`
- Test: `backend/tests/test_schemas/test_club.py` (créer le dossier s'il n'existe pas déjà — vérifier `ls backend/tests/test_schemas` d'abord ; sinon poser le test dans `tests/test_services/test_club_service.py` au lieu d'un dossier dédié, cf. remarque Task 5)

**Interfaces:**
- Produces: `ClubRosterEntry(athlete_id: int, prenom: str, nom: str, count: int, podiums: int, podiums_overall: int, podiums_gender: int, podiums_category: int)`, `ClubPodiumEntry(participation_id: int, athlete_id: int, athlete_name: str, event_name: str, event_type: str, is_relay: bool, event_date: str | None, rank: int, scope: str, total_time: str | None)`, `ClubPodiums(scratch: list[ClubPodiumEntry], category: list[ClubPodiumEntry], gender: list[ClubPodiumEntry], all: list[ClubPodiumEntry])`, `ClubSummary(roster: list[ClubRosterEntry], podiums: ClubPodiums)`.

Ce sont de purs conteneurs de données (pas de logique) : pas de test dédié à
ce fichier seul — ils sont exercés par les tests du service (Task 5) et de
l'API (Task 6). Écrire directement le fichier.

- [ ] **Step 1: Écrire `app/schemas/club.py`**

```python
"""Schémas Pydantic pour la synthèse club (#581)."""
from pydantic import BaseModel


class ClubRosterEntry(BaseModel):
    """Un athlète du roster club, avec ses podiums ventilés par portée."""

    athlete_id: int
    prenom: str
    nom: str
    count: int
    podiums: int
    podiums_overall: int
    podiums_gender: int
    podiums_category: int


class ClubPodiumEntry(BaseModel):
    """Une participation podium, aplatie pour l'affichage (pas d'objet imbriqué)."""

    participation_id: int
    athlete_id: int
    athlete_name: str
    event_name: str
    event_type: str
    is_relay: bool
    event_date: str | None = None
    rank: int
    scope: str
    total_time: str | None = None


class ClubPodiums(BaseModel):
    """Podiums du club, ventilés par mode de rang (miroir de `rank_counters`)."""

    scratch: list[ClubPodiumEntry]
    category: list[ClubPodiumEntry]
    gender: list[ClubPodiumEntry]
    all: list[ClubPodiumEntry]


class ClubSummary(BaseModel):
    roster: list[ClubRosterEntry]
    podiums: ClubPodiums
```

- [ ] **Step 2: Vérifier que le module s'importe sans erreur**

Run: `cd backend && uv run python -c "from app.schemas.club import ClubSummary; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/schemas/club.py
git commit -m "feat(581): schémas ClubSummary/ClubRosterEntry/ClubPodiumEntry"
```

---

## Task 2: `athlete_repository.club_roster()`

**Files:**
- Modify: `backend/app/repositories/athlete_repository.py`
- Test: `backend/tests/test_repositories/test_athlete_repository.py`

**Interfaces:**
- Consumes: `Athlete`, `Participation`, `Course` models (déjà importés dans ce fichier) ; `tcn_clause`, `federal_clause`, `validated_clause` (déjà importés).
- Produces: `club_roster(db: Session, *, federal_only: bool = False, limit: int = 12) -> list[tuple[Athlete, int, int, int, int, int]]` — tuple = `(athlete, count, podiums, podiums_overall, podiums_gender, podiums_category)`, trié `count desc, podiums desc, nom, prenom`, plafonné à `limit`.

- [ ] **Step 1: Écrire les tests, en échec**

Ajouter à la fin de `tests/test_repositories/test_athlete_repository.py` :

```python
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def _course(db_session, nom, event_type="triathlon-m"):
    return course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 16), event_type=event_type
    )


def _part(db_session, athlete, course, bib, **kwargs):
    kwargs.setdefault("club", "TCN")
    kwargs.setdefault("status", "finisher")
    return participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=bib, **kwargs
    )


def test_club_roster_trie_par_volume_puis_podiums_puis_nom(db_session):
    alice = athlete_repository.get_or_create(db_session, nom="ALICE", prenom="A", club="TCN")
    bob = athlete_repository.get_or_create(db_session, nom="BOB", prenom="B", club="TCN")
    c1 = _course(db_session, "C1")
    c2 = _course(db_session, "C2")
    _part(db_session, alice, c1, "1", rank_overall=1)
    _part(db_session, alice, c2, "2")
    _part(db_session, bob, c1, "3", rank_overall=2)
    db_session.flush()

    lignes = athlete_repository.club_roster(db_session)

    assert [a.nom for a, *_ in lignes] == ["ALICE", "BOB"]
    alice_row = lignes[0]
    assert alice_row[1:] == (2, 1, 1, 0, 0)  # count, podiums, overall, gender, category


def test_club_roster_ventile_les_podiums_par_portee_independamment(db_session):
    # Une seule participation, podium sur les trois portées à la fois
    # (cas mesuré Hadrien à Mesquer, #488) : les trois compteurs de portée
    # s'incrémentent chacun, `podiums` (dédupliqué) ne compte qu'une fois.
    ath = athlete_repository.get_or_create(db_session, nom="MULTI", prenom="M", club="TCN")
    course = _course(db_session, "C")
    _part(db_session, ath, course, "1", rank_overall=2, rank_category=1, rank_gender=2)
    db_session.flush()

    (a, count, podiums, po, pg, pc) = athlete_repository.club_roster(db_session)[0]
    assert (count, podiums, po, pg, pc) == (1, 1, 1, 1, 1)


def test_club_roster_exclut_hors_club(db_session):
    exterieur = athlete_repository.get_or_create(db_session, nom="DEHORS", prenom="D", club="Un Autre Club")
    course = _course(db_session, "C")
    _part(db_session, exterieur, course, "1", club="Un Autre Club")
    db_session.flush()

    assert athlete_repository.club_roster(db_session) == []


def test_club_roster_respecte_federal_only(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="TRAILEUR", prenom="T", club="TCN")
    course = _course(db_session, "Trail", event_type="trail")
    _part(db_session, ath, course, "1")
    db_session.flush()

    assert athlete_repository.club_roster(db_session, federal_only=False) != []
    assert athlete_repository.club_roster(db_session, federal_only=True) == []


def test_club_roster_plafonne_a_limit(db_session):
    course = _course(db_session, "C")
    for i in range(3):
        ath = athlete_repository.get_or_create(db_session, nom=f"N{i}", prenom="P", club="TCN")
        _part(db_session, ath, course, str(i))
    db_session.flush()

    assert len(athlete_repository.club_roster(db_session, limit=2)) == 2
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py -k club_roster -v`
Expected: FAIL — `AttributeError: module 'app.repositories.athlete_repository' has no attribute 'club_roster'`

- [ ] **Step 3: Implémenter `club_roster`**

Ajouter dans `app/repositories/athlete_repository.py`, à la suite de
`list_with_season_participation_count` :

```python
def club_roster(
    db: Session, *, federal_only: bool = False, limit: int = 12
) -> list[tuple[Athlete, int, int, int, int, int]]:
    """Top athlètes du club par volume, podiums ventilés par portée (#581).

    Agrégation entièrement en SQL — aucune participation individuelle n'est
    chargée. `podiums` compte les participations avec au moins un podium
    (dédupliqué) ; `podiums_overall`/`gender`/`category` sont des compteurs
    indépendants, une même participation pouvant incrémenter les trois à la
    fois (cf. #488 côté front, comportement repris à l'identique).
    """
    cond_overall = Participation.rank_overall.between(1, 3)
    cond_gender = Participation.rank_gender.between(1, 3)
    cond_category = Participation.rank_category.between(1, 3)

    total = func.count(Participation.id)
    podiums = func.sum(case((or_(cond_overall, cond_gender, cond_category), 1), else_=0))
    podiums_overall = func.sum(case((cond_overall, 1), else_=0))
    podiums_gender = func.sum(case((cond_gender, 1), else_=0))
    podiums_category = func.sum(case((cond_category, 1), else_=0))

    requete = (
        db.query(Athlete, total, podiums, podiums_overall, podiums_gender, podiums_category)
        .join(Participation, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(tcn_clause(Participation.club))
        .group_by(Athlete.id)
    )
    if federal_only:
        requete = requete.filter(federal_clause(Course.event_type))
    return (
        requete.order_by(total.desc(), podiums.desc(), Athlete.nom, Athlete.prenom)
        .limit(limit)
        .all()
    )
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py -k club_roster -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/repositories/athlete_repository.py tests/test_repositories/test_athlete_repository.py
git commit -m "feat(581): athlete_repository.club_roster — roster agrégé en SQL"
```

---

## Task 3: `participation_repository.club_podiums()`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py`
- Test: `backend/tests/test_repositories/test_participation_repository.py`

**Interfaces:**
- Produces: `club_podiums(db: Session, *, federal_only: bool = False) -> list[Row]` — chaque ligne : `(id, rank_overall, rank_gender, rank_category, total_time, athlete_id, athlete_prenom, athlete_nom, event_name, event_type, is_relay, event_date)`. Filtré sur `rank_overall BETWEEN 1 AND 3 OR rank_gender BETWEEN 1 AND 3 OR rank_category BETWEEN 1 AND 3`, club TCN, `federal_only`, exclusion des pendantes. Pas de tri (le bucketing/tri par mode est fait par `club_service`, Task 5).

- [ ] **Step 1: Écrire les tests, en échec**

Ajouter à la fin de `tests/test_repositories/test_participation_repository.py` :

```python
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def test_club_podiums_ne_rend_que_les_lignes_podium(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    podium = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=2, total_time="01:00:00",
    )
    hors_podium = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="2",
        club="TCN", status="finisher", rank_overall=40, total_time="01:10:00",
    )
    db_session.flush()

    rows = participation_repository.club_podiums(db_session)

    assert [r[0] for r in rows] == [podium.id]


def test_club_podiums_inclut_une_ligne_sur_chacune_des_trois_portees(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    scratch = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    genre = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="2",
        club="TCN", status="finisher", rank_gender=2,
    )
    categorie = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="3",
        club="TCN", status="finisher", rank_category=3,
    )
    db_session.flush()

    ids = {r[0] for r in participation_repository.club_podiums(db_session)}
    assert ids == {scratch.id, genre.id, categorie.id}


def test_club_podiums_exclut_hors_club(db_session):
    exterieur = athlete_repository.get_or_create(db_session, nom="D", prenom="D", club="Un Autre Club")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=exterieur.id, course_id=course.id, bib_number="1",
        club="Un Autre Club", status="finisher", rank_overall=1,
    )
    db_session.flush()

    assert participation_repository.club_podiums(db_session) == []


def test_club_podiums_respecte_federal_only(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="T", prenom="T", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Trail", event_date=date(2026, 5, 16), event_type="trail"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.flush()

    assert participation_repository.club_podiums(db_session, federal_only=False) != []
    assert participation_repository.club_podiums(db_session, federal_only=True) == []
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_repositories/test_participation_repository.py -k club_podiums -v`
Expected: FAIL — `AttributeError: ... has no attribute 'club_podiums'`

- [ ] **Step 3: Implémenter `club_podiums`**

Ajouter dans `app/repositories/participation_repository.py`, à la suite de
`for_stats` :

```python
def club_podiums(db: Session, *, federal_only: bool = False):
    """Participations podium du club (rang ≤3 sur au moins une portée), #581.

    Colonnes utiles seulement — jamais l'entité `Participation` complète
    (même logique que `summary_rows_for_course`). Pas de tri ni de plafond
    ici : la ventilation par mode de rang et le tri se font en Python, côté
    `app.services.club_service` — `PodiumsList` promet la liste complète.
    """
    q = (
        db.query(
            Participation.id,
            Participation.rank_overall,
            Participation.rank_gender,
            Participation.rank_category,
            Participation.total_time,
            Athlete.id,
            Athlete.prenom,
            Athlete.nom,
            Course.name,
            Course.event_type,
            Course.is_relay,
            Course.event_date,
        )
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(tcn_clause(Participation.club))
        .filter(
            or_(
                Participation.rank_overall.between(1, 3),
                Participation.rank_gender.between(1, 3),
                Participation.rank_category.between(1, 3),
            )
        )
    )
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.all()
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_repositories/test_participation_repository.py -k club_podiums -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/repositories/participation_repository.py tests/test_repositories/test_participation_repository.py
git commit -m "feat(581): participation_repository.club_podiums — lignes podium filtrées en SQL"
```

---

## Task 4: Verrouiller l'exclusion des pendantes sur les deux nouvelles fonctions

**Files:**
- Modify: `backend/tests/test_repositories/test_pending_exclusion.py`
- Modify: `backend/app/api/AGENTS.md` (tableau des neuf fonctions → onze)

**Interfaces:**
- Consumes: `athlete_repository.club_roster`, `participation_repository.club_podiums` (Tasks 2-3), le helper `_duo(db_session)` déjà présent dans ce fichier de test.

- [ ] **Step 1: Ajouter les deux fonctions au test comportemental, en échec**

Dans `test_pending_exclusion.py`, ajouter sous le bloc `#562` :

```python
# --- #581 : deux fonctions supplémentaires, agrégation club ---


def test_club_roster_exclut_une_pendante(db_session):
    course, _, validee = _duo(db_session)
    lignes = athlete_repository.club_roster(db_session)
    assert lignes[0][1] == 1  # count : seule la validée est comptée


def test_club_podiums_exclut_une_pendante(db_session):
    course, pendante, validee = _duo(db_session)
    # `_duo` pose rank_overall=1 (pendante) et rank_overall=2 (validée) : les
    # deux sont podium, seule la validée doit apparaître.
    rows = participation_repository.club_podiums(db_session)
    assert [r[0] for r in rows] == [validee.id]
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_repositories/test_pending_exclusion.py -k "club_roster or club_podiums" -v`
Expected: FAIL avant l'implémentation des Tasks 2-3 ; si Tasks 2-3 sont déjà faites (ordre normal du plan), ce test doit déjà PASS — dans ce cas, passer directement au Step 3 (documentation) sans modifier de code de production.

- [ ] **Step 3: Mettre à jour le tableau de `backend/app/api/AGENTS.md`**

Dans la section « Résultats en attente de validation », ajouter deux lignes
au tableau (après `list_with_season_participation_count`) :

```markdown
| `club_roster` | `athlete_repository.py` | `GET /club/summary` → roster (#581) |
| `club_podiums` | `participation_repository.py` | `GET /club/summary` → podiums (#581) |
```

- [ ] **Step 4: Mettre à jour le docstring du fichier de test**

Dans l'en-tête de `test_pending_exclusion.py`, remplacer « neuf fonctions
publiques » par « onze fonctions publiques » et ajouter une phrase sur #581
sur le modèle du paragraphe `#562` déjà présent.

- [ ] **Step 5: Lancer toute la suite `test_pending_exclusion.py`**

Run: `cd backend && uv run pytest tests/test_repositories/test_pending_exclusion.py -v`
Expected: tous PASS

- [ ] **Step 6: Commit**

```bash
cd backend && git add tests/test_repositories/test_pending_exclusion.py app/api/AGENTS.md
git commit -m "test(581): verrouille l'exclusion des pendantes sur club_roster/club_podiums"
```

---

## Task 5: `app/services/club_service.py` — bucketing par mode de rang

**Files:**
- Create: `backend/app/services/club_service.py`
- Test: `backend/tests/test_services/test_club_service.py`

**Interfaces:**
- Consumes: `athlete_repository.club_roster`, `participation_repository.club_podiums` (Tasks 2-3), `ClubRosterEntry`, `ClubPodiumEntry`, `ClubPodiums`, `ClubSummary` (Task 1).
- Produces: `get_club_summary(db: Session, *, federal_only: bool = False) -> ClubSummary`.

- [ ] **Step 1: Écrire les tests, en échec**

Créer `tests/test_services/test_club_service.py` :

```python
"""Bucketing des podiums par mode de rang pour /club/summary (#581)."""
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import club_service


def _course(db_session, nom, event_type="triathlon-m"):
    return course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 16), event_type=event_type
    )


def test_get_club_summary_vide_sans_participation(db_session):
    summary = club_service.get_club_summary(db_session)
    assert summary.roster == []
    assert summary.podiums.scratch == []
    assert summary.podiums.category == []
    assert summary.podiums.gender == []
    assert summary.podiums.all == []


def test_get_club_summary_roster_reprend_les_compteurs_du_repository(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.flush()

    summary = club_service.get_club_summary(db_session)

    assert len(summary.roster) == 1
    entry = summary.roster[0]
    assert entry.athlete_id == ath.id
    assert entry.nom == "A"
    assert entry.count == 1
    assert entry.podiums == 1
    assert entry.podiums_overall == 1
    assert entry.podiums_gender == 0
    assert entry.podiums_category == 0


def test_get_club_summary_podiums_scratch_ne_prend_que_rank_overall(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_category=1,  # podium cat, pas scratch
    )
    db_session.flush()

    summary = club_service.get_club_summary(db_session)

    assert summary.podiums.scratch == []
    assert len(summary.podiums.category) == 1
    assert summary.podiums.category[0].scope == "category"
    assert summary.podiums.category[0].rank == 1


def test_get_club_summary_podiums_all_prend_le_meilleur_des_trois(db_session):
    # rang égal (5) sur les trois : priorité overall > gender > category,
    # même règle que `_rank_counters`/`bestRank` côté front.
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    course = _course(db_session, "C")
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=2, rank_gender=2, rank_category=2,
    )
    db_session.flush()

    entry = club_service.get_club_summary(db_session).podiums.all[0]
    assert entry.scope == "overall"
    assert entry.rank == 2


def test_get_club_summary_podiums_tries_par_rang_puis_date_desc(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="A", club="TCN")
    ancien = course_repository.get_or_create(
        db_session, name="Ancien", event_date=date(2026, 1, 1), event_type="triathlon-m"
    )
    recent = course_repository.get_or_create(
        db_session, name="Recent", event_date=date(2026, 6, 1), event_type="triathlon-m"
    )
    p_rang3_ancien = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=ancien.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=3,
    )
    p_rang1_recent = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=recent.id, bib_number="2",
        club="TCN", status="finisher", rank_overall=1,
    )
    p_rang3_recent = participation_repository.create(
        db_session, athlete_id=ath.id, course_id=recent.id, bib_number="3",
        club="TCN", status="finisher", rank_overall=3,
    )
    db_session.flush()

    ids = [e.participation_id for e in club_service.get_club_summary(db_session).podiums.scratch]
    # rang 1 en tête, puis les deux rang 3 départagés par date décroissante.
    assert ids == [p_rang1_recent.id, p_rang3_recent.id, p_rang3_ancien.id]
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_services/test_club_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.club_service'`

- [ ] **Step 3: Implémenter `app/services/club_service.py`**

```python
"""Synthèse club : roster et podiums calculés côté serveur (#581).

Le bucketing par mode de rang reprend la sémantique déjà posée par
`stats_service._rank_counters` (#376) et, avant elle, par
`frontend/lib/utils/club-aggregate.ts` (`bestRank`/`listPodiums`) : « all »
retient le meilleur des trois rangs, départagé overall > gender > category
à égalité.
"""
from sqlalchemy.orm import Session

from app.repositories import athlete_repository, participation_repository
from app.schemas.club import ClubPodiumEntry, ClubPodiums, ClubRosterEntry, ClubSummary

_SCOPES = ("overall", "gender", "category")


def _meilleur(rangs: dict[str, int | None]) -> tuple[str, int] | None:
    valides = [(s, r) for s, r in rangs.items() if r is not None and 1 <= r <= 3]
    if not valides:
        return None
    return min(valides, key=lambda item: (item[1], _SCOPES.index(item[0])))


def _entree(row, scope: str, rang: int) -> ClubPodiumEntry:
    (pid, _rank_overall, _rank_gender, _rank_category, total_time,
     athlete_id, prenom, nom, event_name, event_type, is_relay, event_date) = row
    return ClubPodiumEntry(
        participation_id=pid,
        athlete_id=athlete_id,
        athlete_name=f"{prenom} {nom}".strip(),
        event_name=event_name or "",
        event_type=event_type or "",
        is_relay=bool(is_relay),
        event_date=event_date.isoformat() if event_date else None,
        rank=rang,
        scope=scope,
        total_time=total_time,
    )


def _trier(entries: list[ClubPodiumEntry]) -> list[ClubPodiumEntry]:
    # Stable : trier d'abord par date décroissante, puis par rang croissant —
    # à rang égal, l'ordre par date décroissante posé au premier passage survit.
    par_date = sorted(entries, key=lambda e: e.event_date or "", reverse=True)
    return sorted(par_date, key=lambda e: e.rank)


def _bucket_podiums(rows) -> ClubPodiums:
    buckets: dict[str, list[ClubPodiumEntry]] = {
        "scratch": [], "category": [], "gender": [], "all": [],
    }
    for row in rows:
        _, rank_overall, rank_gender, rank_category, *_ = row
        if rank_overall is not None and 1 <= rank_overall <= 3:
            buckets["scratch"].append(_entree(row, "overall", rank_overall))
        if rank_category is not None and 1 <= rank_category <= 3:
            buckets["category"].append(_entree(row, "category", rank_category))
        if rank_gender is not None and 1 <= rank_gender <= 3:
            buckets["gender"].append(_entree(row, "gender", rank_gender))
        meilleur = _meilleur(
            {"overall": rank_overall, "gender": rank_gender, "category": rank_category}
        )
        if meilleur:
            scope, rang = meilleur
            buckets["all"].append(_entree(row, scope, rang))
    return ClubPodiums(**{k: _trier(v) for k, v in buckets.items()})


def get_club_summary(db: Session, *, federal_only: bool = False) -> ClubSummary:
    """Roster (top 12) et podiums (4 modes de rang) du club, agrégés côté serveur."""
    roster_rows = athlete_repository.club_roster(db, federal_only=federal_only)
    podium_rows = participation_repository.club_podiums(db, federal_only=federal_only)
    roster = [
        ClubRosterEntry(
            athlete_id=a.id, prenom=a.prenom, nom=a.nom,
            count=count, podiums=podiums,
            podiums_overall=po, podiums_gender=pg, podiums_category=pc,
        )
        for a, count, podiums, po, pg, pc in roster_rows
    ]
    return ClubSummary(roster=roster, podiums=_bucket_podiums(podium_rows))
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_services/test_club_service.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/club_service.py tests/test_services/test_club_service.py
git commit -m "feat(581): club_service.get_club_summary — bucketing des podiums par mode de rang"
```

---

## Task 6: Routeur `GET /club/summary`

**Files:**
- Create: `backend/app/api/v1/club.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_api/test_club_api.py`

**Interfaces:**
- Consumes: `club_service.get_club_summary` (Task 5).
- Produces: route `GET /api/v1/club/summary?federal_only=bool` → `ClubSummary` JSON.

- [ ] **Step 1: Écrire les tests, en échec**

Créer `tests/test_api/test_club_api.py` :

```python
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def test_club_summary_club_vide(client, db_session):
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200
    assert resp.json() == {
        "roster": [],
        "podiums": {"scratch": [], "category": [], "gender": [], "all": []},
    }


def test_club_summary_forme_de_la_reponse(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["roster"][0]["nom"] == "A"
    assert body["roster"][0]["count"] == 1
    assert len(body["podiums"]["scratch"]) == 1
    assert body["podiums"]["scratch"][0]["athlete_name"] == "Alice A"


def test_club_summary_accessible_sans_authentification(client, db_session):
    """FR-006 — pas de cookie de session requis, comme les autres routes de lecture."""
    resp = client.get("/api/v1/club/summary")
    assert resp.status_code == 200


def test_club_summary_federal_only(client, db_session):
    ath = athlete_repository.get_or_create(db_session, nom="T", prenom="T", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Trail", event_date=date(2026, 5, 16), event_type="trail"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/summary", params={"federal_only": "true"})
    assert resp.json()["roster"] == []
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_api/test_club_api.py -v`
Expected: FAIL — 404 (route inexistante)

- [ ] **Step 3: Écrire `app/api/v1/club.py`**

```python
"""Router Club : synthèse agrégée (roster + podiums) de la page /club (#581)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.club import ClubSummary
from app.services import club_service

router = APIRouter(tags=["club"])


@router.get("/club/summary", response_model=ClubSummary)
def get_club_summary(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Roster (top 12) et podiums (4 modes de rang) du club, agrégés côté serveur."""
    return club_service.get_club_summary(db, federal_only=federal_only)
```

- [ ] **Step 4: Monter le routeur dans `router.py`**

Dans `app/api/v1/router.py`, ajouter `club` à l'import (ordre alphabétique,
entre `benevoles` et `courses`) :

```python
from app.api.v1 import (
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_benevole_access,
    admin_course_duplicates,
    admin_course_merge,
    admin_course_rescrape,
    admin_course_sources,
    admin_data,
    admin_feedback,
    admin_groups,
    admin_roles,
    admin_sessions,
    admin_site_access,
    athletes,
    auth,
    benevoles,
    club,
    courses,
    feedback,
    health,
    participations,
    scrape,
    site_access,
    stats,
)
```

Puis ajouter `club` au groupe gardé par `require_site_access`, à côté de
`athletes` :

```python
for module in (
    scrape,
    athletes,
    club,
    courses,
    participations,
    stats,
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_benevole_access,
    admin_course_duplicates,
    admin_course_merge,
    admin_course_rescrape,
    admin_course_sources,
    admin_data,
    admin_feedback,
    admin_roles,
    admin_groups,
    admin_sessions,
):
```

- [ ] **Step 5: Lancer les tests, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_api/test_club_api.py -v`
Expected: 4 PASS

- [ ] **Step 6: Vérifier que le routeur reste dans le filet de garde**

`test_site_access_gate.py` dérive son inventaire de `app.openapi()["paths"]` —
aucune liste tenue à la main à mettre à jour : `/club/summary` n'est sous
aucun des `ROUTES_EXEMPTEES_PREFIXES`, donc le test la classera
automatiquement parmi les routes gardées par le mot de passe site.

Run: `cd backend && uv run pytest tests/test_auth/test_site_access_gate.py tests/test_auth/test_public_routes_still_open.py -v`
Expected: PASS

- [ ] **Step 7: Lancer toute la suite backend**

Run: `cd backend && uv run pytest -m "not integration"`
Expected: tous PASS

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/api/v1/club.py app/api/v1/router.py tests/test_api/test_club_api.py
git commit -m "feat(581): GET /club/summary — endpoint agrégé"
```

---

## Task 7: Frontend — types et déplacement de `PodiumScope`

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/podium-scope.tsx`
- Modify: `frontend/lib/labels.ts`

**Interfaces:**
- Produces (dans `lib/types.ts`) : `ClubRosterEntry`, `ClubPodiumEntry`, `ClubPodiums`, `ClubSummary` — miroir exact des schémas Pydantic de Task 1.
- Produces (dans `lib/podium-scope.tsx`) : `export type PodiumScope = "overall" | "category" | "gender";` (déménagé depuis `lib/utils/club-aggregate.ts`, supprimé de là en Task 12).

Pas de test dédié — types uniquement, exercés par les tests des composants (Tasks 8-11).

- [ ] **Step 1: Ajouter les types dans `lib/types.ts`**

À la suite de l'interface `Stats` :

```ts
// Miroir de ClubRosterEntry/ClubPodiumEntry/ClubPodiums/ClubSummary backend (#581).
export interface ClubRosterEntry {
  athlete_id: number;
  prenom: string;
  nom: string;
  count: number;
  podiums: number;
  podiums_overall: number;
  podiums_gender: number;
  podiums_category: number;
}

export interface ClubPodiumEntry {
  participation_id: number;
  athlete_id: number;
  athlete_name: string;
  event_name: string;
  event_type: string;
  is_relay: boolean;
  event_date: string | null;
  rank: number;
  scope: "overall" | "gender" | "category";
  total_time: string | null;
}

export interface ClubPodiums {
  scratch: ClubPodiumEntry[];
  category: ClubPodiumEntry[];
  gender: ClubPodiumEntry[];
  all: ClubPodiumEntry[];
}

export interface ClubSummary {
  roster: ClubRosterEntry[];
  podiums: ClubPodiums;
}
```

- [ ] **Step 2: Déplacer `PodiumScope` dans `lib/podium-scope.tsx`**

En haut de `lib/podium-scope.tsx`, remplacer :

```ts
import type { PodiumScope } from "@/lib/utils/club-aggregate";
```

par :

```ts
export type PodiumScope = "overall" | "category" | "gender";
```

- [ ] **Step 3: Mettre à jour l'import dans `lib/labels.ts`**

Chercher `from "@/lib/utils/club-aggregate"` dans `lib/labels.ts` et le
remplacer par `from "@/lib/podium-scope"`.

Run: `cd frontend && command grep -n "club-aggregate" lib/labels.ts`
Expected (avant l'édition) : une ligne d'import à corriger.

- [ ] **Step 4: Vérifier la compilation TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune nouvelle erreur liée à `PodiumScope` (les composants
`ClubPodiumKpi`/`PodiumsList`/`ClubDashboard` n'ont pas encore été réécrits —
des erreurs *existantes* sur ces fichiers seuls sont attendues jusqu'à la
Task 12 ; ne pas s'y arrêter ici, seul l'import de `PodiumScope` doit résoudre).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add lib/types.ts lib/podium-scope.tsx lib/labels.ts
git commit -m "feat(581): types front ClubSummary, PodiumScope déménagé vers lib/podium-scope"
```

---

## Task 8: `apiServer.getClubSummary`

**Files:**
- Modify: `frontend/lib/api/server.ts`
- Test: `frontend/lib/api/server.test.ts` (vérifier son existence — sinon, ce call est exercé indirectement par le test de `club/page.tsx`, Task 12 ; dans ce cas, sauter le test dédié et documenter pourquoi dans le message de commit)

**Interfaces:**
- Produces: `apiServer.getClubSummary(opts: { federal_only?: boolean } = {}, fetchOpts: FetchOpts = {}) => Promise<ClubSummary>`.

- [ ] **Step 1: Vérifier s'il existe un test unitaire de `server.ts`**

Run: `cd frontend && ls lib/api/server.test.ts 2>&1`

Si le fichier n'existe pas, sauter directement au Step 3 (implémentation) —
`apiServer.getClubSummary` sera exercé par `club/page.test.tsx` (Task 12), qui
mocke déjà `apiServer` au niveau du module.

- [ ] **Step 2 (si le fichier de test existe) : ajouter un cas, en échec**

Suivre le patron des tests existants de ce fichier pour `getStats`/
`listParticipations` — un appel à `apiServer.getClubSummary({ federal_only: true })`
doit produire une requête vers `/club/summary?federal_only=true`.

- [ ] **Step 3: Ajouter `getClubSummary` dans `lib/api/server.ts`**

À la suite de `getStats` :

```ts
getClubSummary: (
  opts: { federal_only?: boolean } = {},
  fetchOpts: FetchOpts = {},
) => serverFetch<ClubSummary>(`/club/summary${toQuery(opts)}`, fetchOpts),
```

Ajouter `ClubSummary` à l'import de types en tête de fichier (à côté de
`Stats`, `Participation`, etc.).

- [ ] **Step 4: Lancer les tests concernés (ou, à défaut, la compilation)**

Run: `cd frontend && npx tsc --noEmit 2>&1 | command grep -i "server.ts"`
Expected: aucune sortie (pas d'erreur de type sur ce fichier)

- [ ] **Step 5: Commit**

```bash
cd frontend && git add lib/api/server.ts
git commit -m "feat(581): apiServer.getClubSummary"
```

---

## Task 9: Réécrire `ClubPodiumKpi`

**Files:**
- Modify: `frontend/components/club/ClubPodiumKpi.tsx`
- Modify: `frontend/components/club/ClubPodiumKpi.test.tsx`

**Interfaces:**
- Consumes: `DashboardRankCounters` (déjà défini dans `lib/types.ts`, déjà consommé par `StatCardsRank`).
- Produces: `ClubPodiumKpi({ rankCounters: DashboardRankCounters })` (remplace la prop `participations: Participation[]`).

- [ ] **Step 1: Réécrire le test, en échec**

Remplacer entièrement `ClubPodiumKpi.test.tsx` :

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { DashboardRankCounters } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { ClubPodiumKpi } from "./ClubPodiumKpi";

const RANK_COUNTERS: DashboardRankCounters = {
  scratch: { victories: 0, podiums: 4, top10: 0 },
  category: { victories: 0, podiums: 7, top10: 0 },
  all: { victories: 0, podiums: 11, top10: 0 },
  gender: {
    women: { victories: 0, podiums: 2, top10: 0 },
    men: { victories: 0, podiums: 3, top10: 0 },
  },
};

describe("ClubPodiumKpi — lit rank_counters (#581, miroir de StatCardsRank)", () => {
  it("sans ?rank= (défaut scratch) : lit rankCounters.scratch.podiums", () => {
    searchParams = new URLSearchParams();
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("?rank=category : lit rankCounters.category.podiums", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("?rank=all : lit rankCounters.all.podiums", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("11")).toBeInTheDocument();
  });

  it("?rank=gender : somme women.podiums + men.podiums", () => {
    searchParams = new URLSearchParams("rank=gender");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("nomme la portée du décompte, mode par mode (PROF-3, #488)", () => {
    searchParams = new URLSearchParams();
    const { unmount } = render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("général")).toBeInTheDocument();
    unmount();

    searchParams = new URLSearchParams("rank=all");
    render(<ClubPodiumKpi rankCounters={RANK_COUNTERS} />);
    expect(screen.getByText("général, genre ou catégorie")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd frontend && npx vitest run components/club/ClubPodiumKpi.test.tsx`
Expected: FAIL (le composant attend encore `participations`, pas `rankCounters`)

- [ ] **Step 3: Réécrire `ClubPodiumKpi.tsx`**

```tsx
"use client";
import { useSearchParams } from "next/navigation";
import { StatCard } from "@/components/tcn";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { rankTypeLabel } from "@/lib/labels";
import type { DashboardRankCounters } from "@/lib/types";

/**
 * KPI « Podiums » côté client — recalcule selon `?rank=…` sans re-fetch RSC.
 * Lit `rankCounters` (déjà calculé côté backend, #376) au lieu de recompter
 * sur les participations brutes (#581) : même source que `StatCardsRank`.
 * Les autres KPI (Résultats / Athlètes / Épreuves) ne dépendent pas du rank
 * et restent SSR dans `ClubDashboard`. Miroir du couple `StatCardsRank` +
 * `PodiumsList` (issue #132).
 */
export function ClubPodiumKpi({ rankCounters }: { rankCounters: DashboardRankCounters }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const count =
    rankType === "gender"
      ? rankCounters.gender.women.podiums + rankCounters.gender.men.podiums
      : rankCounters[rankType].podiums;
  return (
    <StatCard
      label="Podiums"
      value={count}
      accent={false}
      delta={rankTypeLabel(rankType, { form: "long" })}
    />
  );
}
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd frontend && npx vitest run components/club/ClubPodiumKpi.test.tsx`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/club/ClubPodiumKpi.tsx components/club/ClubPodiumKpi.test.tsx
git commit -m "refactor(581): ClubPodiumKpi lit rank_counters au lieu de recompter sur les participations"
```

---

## Task 10: Réécrire `PodiumsList`

**Files:**
- Modify: `frontend/components/club/PodiumsList.tsx`
- Modify: `frontend/components/club/PodiumsList.test.tsx`

**Interfaces:**
- Consumes: `ClubPodiums`, `ClubPodiumEntry` (Task 7), `PODIUM_SCOPE_META`, `podiumScopeLabel` (inchangés).
- Produces: `PodiumsList({ podiums: ClubPodiums })` (remplace `participations: Participation[]`). `APERCU_PODIUMS` inchangé (export conservé).

- [ ] **Step 1: Réécrire le test, en échec**

Remplacer entièrement `PodiumsList.test.tsx` — même structure que l'existant
(lu en amont du plan), en remplaçant la fixture `Participation[]` par une
fixture `ClubPodiums` construite directement par mode :

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ClubPodiumEntry, ClubPodiums } from "@/lib/types";

let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

import { PodiumsList, APERCU_PODIUMS } from "./PodiumsList";

function entry(over: Partial<ClubPodiumEntry> & { participation_id: number }): ClubPodiumEntry {
  return {
    participation_id: over.participation_id,
    athlete_id: over.athlete_id ?? over.participation_id,
    athlete_name: over.athlete_name ?? "P N",
    event_name: over.event_name ?? `Course ${over.participation_id}`,
    event_type: over.event_type ?? "triathlon-m",
    is_relay: over.is_relay ?? false,
    event_date: over.event_date ?? "2026-05-10",
    rank: over.rank ?? 1,
    scope: over.scope ?? "overall",
    total_time: over.total_time ?? "01:59:00",
  };
}

const EMPTY: ClubPodiums = { scratch: [], category: [], gender: [], all: [] };

const PODIUMS: ClubPodiums = {
  scratch: [entry({ participation_id: 2, scope: "overall", rank: 2 })],
  category: [entry({ participation_id: 1, scope: "category", rank: 1 })],
  gender: [entry({ participation_id: 3, scope: "gender", rank: 1 })],
  all: [
    entry({ participation_id: 1, scope: "category", rank: 1 }),
    entry({ participation_id: 2, scope: "overall", rank: 2 }),
    entry({ participation_id: 3, scope: "gender", rank: 1 }),
  ],
};

describe("PodiumsList — filtrage selon ?rank= (#104, #132, #581)", () => {
  it("sans ?rank= (défaut scratch) : n'affiche que les badges « Général »", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByText("Général")).toBeInTheDocument();
    expect(screen.queryByText("Catégorie")).not.toBeInTheDocument();
    expect(screen.queryByText("Genre")).not.toBeInTheDocument();
  });

  it("?rank=category : n'affiche que les badges « Catégorie »", () => {
    searchParams = new URLSearchParams("rank=category");
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByText("Catégorie")).toBeInTheDocument();
    expect(screen.queryByText("Général")).not.toBeInTheDocument();
  });

  it("?rank=all : montre le mélange des trois scopes", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByText("Général")).toBeInTheDocument();
    expect(screen.getByText("Catégorie")).toBeInTheDocument();
    expect(screen.getByText("Genre")).toBeInTheDocument();
  });

  it("liste vide → message d'attente, aucun badge", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={EMPTY} />);
    expect(screen.getByText("Pas encore de podium enregistré.")).toBeInTheDocument();
  });
});

describe("PodiumsList — icône par scope (#128)", () => {
  it("?rank=all : chaque scope porte une icône avec aria-label distinct", () => {
    searchParams = new URLSearchParams("rank=all");
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByLabelText("Podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("Podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("Podium de genre")).toBeInTheDocument();
  });
});

describe("PodiumsList — annonce du changement (#477)", () => {
  it("annonce le nombre de podiums affichés dans une région role=status", () => {
    searchParams = new URLSearchParams();
    render(<PodiumsList podiums={PODIUMS} />);
    expect(screen.getByRole("status")).toHaveTextContent("1 podium affiché");
  });
});

describe("PodiumsList — extension de la liste (PROF-3, #488)", () => {
  const NEUF: ClubPodiums = {
    ...EMPTY,
    scratch: Array.from({ length: 9 }, (_, i) =>
      entry({ participation_id: i + 1, scope: "overall", rank: 1 }),
    ),
  };

  it("n'offre pas d'extension quand tout tient dans l'aperçu", () => {
    searchParams = new URLSearchParams();
    render(
      <PodiumsList
        podiums={{ ...EMPTY, scratch: NEUF.scratch.slice(0, APERCU_PODIUMS) }}
      />,
    );
    expect(screen.queryByRole("button", { name: /Voir les/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(APERCU_PODIUMS);
  });

  it("ouvre la liste entière au clic", async () => {
    searchParams = new URLSearchParams();
    const user = userEvent.setup();
    render(<PodiumsList podiums={NEUF} />);

    await user.click(screen.getByRole("button", { name: "Voir les 3 autres podiums" }));

    expect(screen.getAllByRole("listitem")).toHaveLength(9);
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd frontend && npx vitest run components/club/PodiumsList.test.tsx`
Expected: FAIL

- [ ] **Step 3: Réécrire `PodiumsList.tsx`**

```tsx
"use client";
import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Medal } from "@/components/ui/medal";
import { AnnonceStatut } from "@/components/tcn";
import { SportBadge } from "@/components/results/SportBadge";
import { formatEventName } from "@/lib/utils/event";
import { RANK_PARAM, rankTypeFromParam } from "@/lib/rank";
import { podiumScopeLabel } from "@/lib/labels";
import { PODIUM_SCOPE_META } from "@/lib/podium-scope";
import type { ClubPodiums } from "@/lib/types";

/**
 * Taille de l'aperçu de la liste (#488, PROF-3). Le KPI « Podiums » deux blocs
 * plus haut annonce le total ; tronquer sans le dire faisait mentir la moitié
 * de l'écran. Le bouton d'extension dit combien il reste, et ouvre tout.
 */
export const APERCU_PODIUMS = 6;

/**
 * Liste des podiums récents côté client — lit `?rank=…` et sélectionne le
 * bucket déjà calculé côté serveur (#581), sans re-fetch. Voir issue #132
 * (latence toggle) : le mécanisme de bascule est inchangé, seul le payload a
 * changé de forme (un `ClubPodiums` pré-agrégé au lieu du tableau complet des
 * participations).
 */
export function PodiumsList({ podiums }: { podiums: ClubPodiums }) {
  const sp = useSearchParams();
  const rankType = rankTypeFromParam(sp.get(RANK_PARAM) ?? undefined);
  const [etendu, setEtendu] = useState(false);
  const tous = podiums[rankType];
  const affiches = etendu ? tous : tous.slice(0, APERCU_PODIUMS);
  const restants = tous.length - affiches.length;

  const annonce = (
    <AnnonceStatut texte={`${affiches.length} podium${affiches.length > 1 ? "s" : ""} affiché${affiches.length > 1 ? "s" : ""}`} />
  );

  if (affiches.length === 0) {
    return (
      <>
        {annonce}
        <p className="py-6 text-center text-sm text-[var(--tcn-text-faint)]">
          Pas encore de podium enregistré.
        </p>
      </>
    );
  }
  return (
    <>
      {annonce}
      <ul className="divide-y">
        {affiches.map((p) => {
          const { Icon, label, title } = PODIUM_SCOPE_META[p.scope];
          return (
            <li key={p.participation_id} className="flex items-center gap-3 py-2.5">
              <span className="relative inline-block">
                <Medal rank={p.rank} size={28} />
                <span
                  role="img"
                  aria-label={label}
                  title={title}
                  className="absolute -right-1 -bottom-1 inline-grid place-content-center rounded-full bg-background p-[1px] text-foreground"
                >
                  <Icon size={12} strokeWidth={2.5} aria-hidden="true" />
                </span>
              </span>
              <div className="min-w-0 flex-1">
                <Link href={`/athletes/${p.athlete_id}`} className="font-semibold hover:underline">
                  {p.athlete_name}
                </Link>
                <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--tcn-text-faint)]">
                  <span className="truncate">{formatEventName(p.event_name, p.is_relay)}</span>
                  <SportBadge type={p.event_type} />
                  <span className="micro-label">{podiumScopeLabel(p.scope)}</span>
                </div>
              </div>
              {p.total_time && <span className="num text-sm font-bold">{p.total_time}</span>}
            </li>
          );
        })}
      </ul>
      {tous.length > APERCU_PODIUMS && (
        <button
          type="button"
          onClick={() => setEtendu((v) => !v)}
          aria-expanded={etendu}
          className="mt-3 text-sm font-medium text-accent-ink hover:underline"
        >
          {etendu
            ? "Réduire la liste"
            : restants > 1
              ? `Voir les ${restants} autres podiums`
              : "Voir l'autre podium"}
        </button>
      )}
    </>
  );
}
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd frontend && npx vitest run components/club/PodiumsList.test.tsx`
Expected: tous PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/club/PodiumsList.tsx components/club/PodiumsList.test.tsx
git commit -m "refactor(581): PodiumsList consomme le ClubPodiums pré-agrégé du backend"
```

---

## Task 11: Réécrire `ClubDashboard`

**Files:**
- Modify: `frontend/components/club/ClubDashboard.tsx`
- Modify: `frontend/components/club/ClubDashboard.test.tsx`

**Interfaces:**
- Consumes: `ClubSummary` (Task 7), `ClubPodiumKpi` (Task 9), `PodiumsList` (Task 10).
- Produces: `ClubDashboard({ stats: Stats, summary: ClubSummary, recent: Participation[] })` — remplace `{ stats, participations }`. `APERCU_ROSTER` **supprimé comme export** (devient l'argument `limit` par défaut de `club_roster` côté backend — Task 2) ; si un test en a encore besoin comme constante d'assertion, le redéfinir localement dans le test à `12`.

- [ ] **Step 1: Réécrire le test, en échec**

Remplacer entièrement `ClubDashboard.test.tsx` :

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ClubSummary, Participation, Stats } from "@/lib/types";

vi.mock("@/components/charts/BarList", () => ({ BarList: () => <div data-testid="barlist" /> }));
vi.mock("@/components/charts/MonthlyTrend", () => ({ MonthlyTrend: () => <div data-testid="monthly" /> }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));

import { ClubDashboard } from "./ClubDashboard";

const APERCU_ROSTER = 12;

const STATS: Stats = {
  total: 1,
  athletes: 1,
  events: 1,
  by_type: {},
  by_month: {},
  recent: [],
  rank_counters: {
    scratch: { victories: 0, podiums: 0, top10: 0 },
    category: { victories: 0, podiums: 0, top10: 0 },
    all: { victories: 0, podiums: 0, top10: 0 },
    gender: { women: { victories: 0, podiums: 0, top10: 0 }, men: { victories: 0, podiums: 0, top10: 0 } },
  },
};

const EMPTY_SUMMARY: ClubSummary = {
  roster: [],
  podiums: { scratch: [], category: [], gender: [], all: [] },
};

function rosterEntry(i: number, podiums = 0) {
  return {
    athlete_id: i,
    prenom: "P",
    nom: `N${i}`,
    count: 10 - i,
    podiums,
    podiums_overall: podiums,
    podiums_gender: 0,
    podiums_category: 0,
  };
}

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id, name: `Course ${over.id}`, event_date: "2026-05-10",
      event_type: "triathlon-m", provider: "manuel", source_url: "", is_relay: false,
    },
    club: "TCN", is_tcn: true, category: null, bib_number: null,
    rank_overall: over.rank_overall ?? null, rank_category: over.rank_category ?? null,
    rank_gender: over.rank_gender ?? null, total_time: "01:59:00", status: "finisher",
    is_relay: false, splits: null, created_at: "2026-05-11T10:00:00Z",
  };
}

describe("ClubDashboard — smoke", () => {
  it("rend les 4 KPI de synthèse", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} />);
    expect(screen.getByText("Résultats")).toBeInTheDocument();
    expect(screen.getByText("Athlètes")).toBeInTheDocument();
    expect(screen.getByText("Épreuves")).toBeInTheDocument();
    expect(screen.getByText("Podiums")).toBeInTheDocument();
  });

  it("empty state quand aucun résultat", () => {
    render(
      <ClubDashboard
        stats={{ ...STATS, total: 0 }}
        summary={EMPTY_SUMMARY}
        recent={[]}
      />,
    );
    expect(screen.getByText("Aucun résultat de club")).toBeInTheDocument();
  });

  it("roster : décompose les podiums d'un athlète par scope, avec tooltip", () => {
    const summary: ClubSummary = {
      ...EMPTY_SUMMARY,
      roster: [{
        athlete_id: 1, prenom: "P", nom: "N", count: 3,
        podiums: 1, podiums_overall: 1, podiums_gender: 1, podiums_category: 1,
      }],
    };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(screen.getByLabelText("1 podium général")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de catégorie")).toBeInTheDocument();
    expect(screen.getByLabelText("1 podium de genre")).toBeInTheDocument();
  });

  it("roster : aucun badge scope pour un athlète sans podium", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 0)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(screen.queryByLabelText(/podium général/)).not.toBeInTheDocument();
  });

  // Le roster arrive déjà plafonné à 12 côté backend (#581, club_roster) :
  // ClubDashboard ne tronque plus rien, il rend `summary.roster` tel quel.
  it("roster : rend tel quel et renvoie vers /club/athletes", () => {
    const summary: ClubSummary = {
      ...EMPTY_SUMMARY,
      roster: Array.from({ length: APERCU_ROSTER }, (_, i) => rosterEntry(i + 1)),
    };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);

    const section = screen
      .getByRole("heading", { name: "Les athlètes les plus actifs" })
      .closest("section");
    expect(section?.querySelectorAll('a[href^="/athletes/"]')).toHaveLength(APERCU_ROSTER);
    expect(screen.getByRole("link", { name: "Voir saison par saison →" })).toHaveAttribute(
      "href",
      "/club/athletes",
    );
  });

  it("roster : titre « Athlètes du club » sous le plafond", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(screen.getByRole("heading", { name: "Athlètes du club" })).toBeInTheDocument();
  });

  it("nomme la portée des podiums du roster en légende (PROF-3, #488)", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 1)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(
      screen.getByText("Les podiums comptés ici cumulent le général, le genre et la catégorie."),
    ).toBeInTheDocument();
  });

  it("n'affiche pas la légende des podiums quand aucun athlète de l'aperçu n'en a", () => {
    const summary: ClubSummary = { ...EMPTY_SUMMARY, roster: [rosterEntry(1, 0)] };
    render(<ClubDashboard stats={STATS} summary={summary} recent={[part({ id: 1 })]} />);
    expect(
      screen.queryByText("Les podiums comptés ici cumulent le général, le genre et la catégorie."),
    ).not.toBeInTheDocument();
  });

  it("résultats récents : rend `recent` directement, sans re-tri", () => {
    const recent = [part({ id: 5 }), part({ id: 9 })];
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={recent} />);
    expect(screen.getAllByRole("link", { name: /Course \d/ })).toHaveLength(2);
  });

  // #581 : le bandeau de troncature disparaît — roster et podiums sont exacts,
  // il n'y a plus de plafond à annoncer.
  it("ne rend plus de bandeau de troncature", () => {
    render(<ClubDashboard stats={STATS} summary={EMPTY_SUMMARY} recent={[part({ id: 1 })]} />);
    expect(screen.queryByText(/derniers résultats importés/)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd frontend && npx vitest run components/club/ClubDashboard.test.tsx`
Expected: FAIL

- [ ] **Step 3: Réécrire `ClubDashboard.tsx`**

Reprendre le fichier lu en amont du plan, avec ces changements :

- Signature : `{ stats, summary, recent }: { stats: Stats; summary: ClubSummary; recent: Participation[] }`.
- Supprimer les imports `buildRoster`, `clubSummary`, `recentParticipations`, `CLUB_PARTICIPATIONS_PAGE_SIZE`, `type RosterEntry` ; ajouter `import type { ClubSummary, Participation, Stats } from "@/lib/types";`.
- Supprimer la constante exportée `APERCU_ROSTER` (n'est plus utilisée ici — le plafond vit désormais côté backend, `club_roster(..., limit=12)`).
- `const summary_ = clubSummary(participations)` → utiliser directement `stats.total`/`stats.athletes`/`stats.events` pour les 3 premiers KPI (déjà le cas dans l'existant, aucun changement).
- `const roster = buildRoster(participations); const apercu = roster.slice(0, APERCU_ROSTER);` → `const roster = summary.roster;` (déjà plafonné).
- `const tronque = ...` et le bloc JSX du bandeau `{tronque && (...)}` : **supprimés entièrement**.
- `const recent = recentParticipations(participations, 6);` → supprimé ; utiliser directement la prop `recent`.
- `<ClubPodiumKpi participations={participations} />` → `<ClubPodiumKpi rankCounters={stats.rank_counters} />`.
- `<PodiumsList participations={participations} />` → `<PodiumsList podiums={summary.podiums} />`.
- La condition d'`EmptyState` (`participations.length === 0`) → `stats.total === 0` (même invariant que `/dashboard`, cf. `app/(public_restricted)/dashboard/page.tsx`).
- Le titre conditionnel (`roster.length > APERCU_ROSTER ? "Les athlètes les plus actifs" : "Athlètes du club"`) → comparer `stats.athletes > roster.length` (le roster est désormais toujours ≤ 12 ; le titre doit refléter s'il existe des athlètes au-delà de l'aperçu rendu, information portée par `stats.athletes`).
- `RosterPodiumBadges` : adapter la lecture de `roster.podiumsByScope[scope]` en `roster.podiums_${scope}` (aplati, plus d'objet imbriqué) — soit renommer les champs consommés (`r.podiums_overall`, `r.podiums_gender`, `r.podiums_category`), soit garder la fonction avec une signature `{ overall, gender, category }` construite à l'appel. Choisir la seconde option pour ne pas re-router les trois champs partout :

```tsx
function RosterPodiumBadges({ overall, gender, category }: { overall: number; gender: number; category: number }) {
  const values: Record<PodiumScope, number> = { overall, gender, category };
  const scopes: PodiumScope[] = ["overall", "gender", "category"];
  return (
    <span className="flex shrink-0 items-center gap-1.5">
      {scopes.map((scope) => {
        const n = values[scope];
        if (n === 0) return null;
        const { Icon, label, title } = PODIUM_SCOPE_META[scope];
        return (
          <span
            key={scope}
            className="num inline-flex items-center gap-0.5 text-sm font-bold text-accent-ink"
            title={`${n} ${title.toLowerCase()}`}
            aria-label={`${n} ${label.toLowerCase()}`}
          >
            <Icon size={14} strokeWidth={2.5} aria-hidden="true" />
            {n}
          </span>
        );
      })}
    </span>
  );
}
```

  Et son appel : `{r.podiums > 0 && <RosterPodiumBadges overall={r.podiums_overall} gender={r.podiums_gender} category={r.podiums_category} />}`.

- Import `PodiumScope` depuis `@/lib/podium-scope` (déménagé en Task 7) au lieu de `@/lib/utils/club-aggregate`.
- La légende `{apercu.some((r) => r.podiums > 0) && ...}` → `{roster.some((r) => r.podiums > 0) && ...}`.
- Le roster se rend par `roster.map((r) => ...)` (au lieu de `apercu.map(...)`), avec `r.athleteId` → `r.athlete_id`, `r.name` → `` `${r.prenom} ${r.nom}` ``.

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd frontend && npx vitest run components/club/ClubDashboard.test.tsx`
Expected: tous PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add components/club/ClubDashboard.tsx components/club/ClubDashboard.test.tsx
git commit -m "refactor(581): ClubDashboard consomme ClubSummary au lieu du tableau complet des participations"
```

---

## Task 12: `club/page.tsx` — trois fetches légers

**Files:**
- Modify: `frontend/app/(public_restricted)/club/page.tsx`
- Modify: `frontend/app/(public_restricted)/club/page.test.tsx`

**Interfaces:**
- Consumes: `apiServer.getStats`, `apiServer.getClubSummary` (Task 8), `apiServer.listParticipations`.

- [ ] **Step 1: Réécrire le test, en échec**

Remplacer entièrement `club/page.test.tsx` — même structure que l'existant
(lu en amont), avec un mock `getClubSummary` en plus :

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import type { ClubSummary, Participation, Stats } from "@/lib/types";

const getStats = vi.fn();
const getClubSummary = vi.fn();
const listParticipations = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown, fetchOpts?: unknown) => getStats(opts, fetchOpts),
    getClubSummary: (opts: unknown, fetchOpts?: unknown) => getClubSummary(opts, fetchOpts),
    listParticipations: (filters: unknown, fetchOpts?: unknown) => listParticipations(filters, fetchOpts),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/club",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/charts/BarList", () => ({ BarList: () => <div data-testid="barlist" /> }));
vi.mock("@/components/charts/MonthlyTrend", () => ({ MonthlyTrend: () => <div data-testid="monthly" /> }));

import ClubPage from "./page";

const STATS: Stats = {
  total: 42, athletes: 10, events: 5,
  by_type: {}, by_month: {}, recent: [],
  rank_counters: {
    scratch: { victories: 0, podiums: 0, top10: 0 },
    category: { victories: 0, podiums: 0, top10: 0 },
    all: { victories: 0, podiums: 0, top10: 0 },
    gender: { women: { victories: 0, podiums: 0, top10: 0 }, men: { victories: 0, podiums: 0, top10: 0 } },
  },
};

const SUMMARY: ClubSummary = { roster: [], podiums: { scratch: [], category: [], gender: [], all: [] } };

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: over.athlete ?? { id: over.id, nom: "N", prenom: "P", gender: "F", club: "TCN" },
    course: over.course ?? {
      id: over.id, name: `Course ${over.id}`, event_date: "2026-05-10",
      event_type: "triathlon-m", provider: "manuel", source_url: "", is_relay: false,
    },
    club: "TCN", is_tcn: true, category: null, bib_number: null,
    rank_overall: over.rank_overall ?? null, rank_category: null, rank_gender: null,
    total_time: "01:59:00", status: "finisher", is_relay: false, splits: null,
    created_at: "2026-05-11T10:00:00Z",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  getStats.mockResolvedValue(STATS);
  getClubSummary.mockResolvedValue(SUMMARY);
  listParticipations.mockResolvedValue([part({ id: 1 })]);
});

async function renderClub(searchParams: Record<string, string | undefined> = {}) {
  const ui = await ClubPage({ searchParams: Promise.resolve(searchParams) });
  return render(ui);
}

describe("ClubPage", () => {
  it("demande une fenêtre de revalidation courte sur les trois appels (#352)", async () => {
    await renderClub({});
    expect(getStats).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(getClubSummary).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
    expect(listParticipations).toHaveBeenCalledWith(expect.anything(), { revalidateSeconds: 30 });
  });

  // #581 : la page ne demande plus le plafond de /participations — seulement
  // les 6 résultats récents affichés. Le roster et les podiums viennent de
  // /club/summary, agrégés côté serveur.
  it("demande 6 résultats récents, pas 5000", async () => {
    await renderClub({});
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ page_size: 6 }),
      expect.anything(),
    );
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `cd frontend && npx vitest run "app/(public_restricted)/club/page.test.tsx"`
Expected: FAIL

- [ ] **Step 3: Réécrire `club/page.tsx`**

```tsx
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { RankTypeToggle } from "@/components/layout/RankTypeToggle";
import { ClubDashboard } from "@/components/club/ClubDashboard";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { CLUB_NAME } from "@/lib/club";

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);

  // Fenêtre de revalidation courte (#352) — même raison qu'en page d'accueil.
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };
  const [stats, summary, recent] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
    apiServer.getClubSummary({ federal_only }, revalidateOpts),
    apiServer.listParticipations(
      { scope: SCOPE_CLUB, federal_only, page_size: 6 },
      revalidateOpts,
    ),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow={CLUB_NAME}
          title="Espace club"
          description={`Synthèse, podiums et athlètes du ${CLUB_NAME}.`}
          actions={
            <div className="flex flex-wrap items-center gap-3">
              <RankTypeToggle />
              <DisciplineToggle />
            </div>
          }
        />
        <ClubDashboard stats={stats} summary={summary} recent={recent} />
      </div>
    </PageShell>
  );
}
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `cd frontend && npx vitest run "app/(public_restricted)/club/page.test.tsx"`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
cd frontend && git add "app/(public_restricted)/club/page.tsx" "app/(public_restricted)/club/page.test.tsx"
git commit -m "refactor(581): club/page.tsx demande /club/summary + 6 résultats récents au lieu de 5000 participations"
```

---

## Task 13: Nettoyage — code mort

**Files:**
- Modify: `frontend/lib/utils/club-aggregate.ts`
- Modify: `frontend/lib/utils/club-aggregate.test.ts`
- Modify: `frontend/lib/club.ts`

**Interfaces:**
- Produces: `lib/utils/club-aggregate.ts` n'exporte plus que `recentParticipations` (toujours utilisée par `app/(public_restricted)/athletes/[id]/EventsTable.tsx`).

- [ ] **Step 1: Confirmer qu'aucun appelant restant ne dépend des fonctions à retirer**

Run: `cd frontend && command grep -rln "buildRoster\|clubSummary\|bestRank\|isPodium\|bestPodiumRank\|listPodiums\|isTopN\|RosterEntry" --include="*.ts*" . | command grep -v node_modules | command grep -v "lib/utils/club-aggregate"`
Expected: aucune sortie (déjà vérifié en amont du plan — cette étape reconfirme après les Tasks 9-12)

- [ ] **Step 2: Retirer les tests des fonctions supprimées**

Dans `lib/utils/club-aggregate.test.ts`, supprimer les blocs `describe` :
`bestPodiumRank`, `bestRank`, `isTopN`, `listPodiums`, `isPodium / isTopN — paramètre rankType`,
`buildRoster`, `clubSummary`. Ne garder que le bloc `describe("recentParticipations", ...)`
et retirer les imports devenus inutiles en tête de fichier (ne garder que
`recentParticipations` dans l'import depuis `./club-aggregate`).

- [ ] **Step 3: Lancer les tests, vérifier qu'ils passent encore (fichier réduit)**

Run: `cd frontend && npx vitest run lib/utils/club-aggregate.test.ts`
Expected: PASS (le seul test restant, `recentParticipations`, n'a pas changé)

- [ ] **Step 4: Retirer le code mort de `club-aggregate.ts`**

Ne garder dans `lib/utils/club-aggregate.ts` que : l'import `Participation`
depuis `@/lib/types`, et la fonction `recentParticipations` (inchangée).
Supprimer : `PodiumScope` (déménagé Task 7), `BestRank`, `candidatesFor`,
`bestRank`, `isTopN`, `bestPodiumRank`, `isPodium`, `PodiumEntry`, `listPodiums`,
`RosterEntry`, `fullName`, `buildRoster`, `ClubSummary` (l'interface locale —
distincte du nouveau type backend du même nom, à ne pas confondre), `clubSummary`.

- [ ] **Step 5: Retirer `CLUB_PARTICIPATIONS_PAGE_SIZE` de `lib/club.ts`**

Supprimer la constante `CLUB_PARTICIPATIONS_PAGE_SIZE` et son commentaire
(le "ponytail" décrivant le plafond de 5000) — `CLUB_NAME` et
`CLUB_NAME_SHORT` restent inchangés.

- [ ] **Step 6: Vérifier qu'aucun import ne référence plus la constante supprimée**

Run: `cd frontend && command grep -rn "CLUB_PARTICIPATIONS_PAGE_SIZE" --include="*.ts*" . | command grep -v node_modules`
Expected: aucune sortie

- [ ] **Step 7: Lancer toute la suite frontend et la compilation**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: aucune erreur de type, tous les tests PASS

- [ ] **Step 8: Commit**

```bash
cd frontend && git add lib/utils/club-aggregate.ts lib/utils/club-aggregate.test.ts lib/club.ts
git commit -m "refactor(581): retire le code mort de club-aggregate.ts et le plafond de page_size côté front"
```

---

## Task 14: Vérification finale

**Files:** aucun (validation seule)

- [ ] **Step 1: Suite backend complète + lint**

Run: `cd backend && uv run pytest -m "not integration" && uv run ruff check .`
Expected: tous PASS, aucune erreur ruff

- [ ] **Step 2: Suite frontend complète + lint + build**

Run: `cd frontend && npx vitest run && npm run lint && npm run build`
Expected: tous PASS, build production réussi

- [ ] **Step 3: Vérification manuelle de `/club` en développement**

Démarrer les deux serveurs de dev (`uv run python scripts/dev_server.py` côté
backend, `npm run dev` côté front), ouvrir `/club` dans un navigateur, et
vérifier à l'onglet Réseau que la charge de `GET /club/summary` et de
`GET /participations?...&page_size=6` sont chacune de l'ordre de quelques ko
(pas de requête `page_size=5000`). Vérifier aussi que le toggle de type de
rang (`RankTypeToggle`) continue de mettre à jour le KPI Podiums et la liste
de podiums **sans requête réseau** (Network tab : aucun nouvel appel au clic).

- [ ] **Step 4: Rebase / merge vers la branche de travail principale du worktree, si applicable**

Aucune action git destructive ici — se limiter à confirmer que tous les
commits des Tasks 1-13 sont présents (`git log --oneline` sur la branche du
worktree) avant de passer à `finishing-a-development-branch` (hors périmètre
de ce plan, cf. `AGENTS.md` § Workflow IA).
