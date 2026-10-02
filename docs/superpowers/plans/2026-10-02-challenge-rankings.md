# Classements Challenge (#1008) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stocker les classements « Challenge » (cumul d'un athlète sur plusieurs épreuves du même jour) dans des tables dédiées liées à N épreuves, les exclure par construction de tous les compteurs et stats, et les afficher sur la fiche athlète, la page d'épreuve et une page de classement.

**Architecture:** Trois tables (`challenges`, `challenge_courses`, `challenge_results`) derrière un `challenge_repository`. `persist_steps` met de côté les heats dont le nom contient « challenge », persiste le reste, puis `challenge_service.match` apparie leurs lignes aux athlètes des épreuves du même jour : au moins 90 % présents sur au moins deux épreuves, c'est un Challenge ; sinon les lignes repartent dans le flux normal. Une commande CLI `requalify-challenges` applique le même test aux `Course` existantes.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 sync, Alembic, pytest ; Next.js 16 App Router, TypeScript, vitest.

**Spec:** `docs/superpowers/specs/2026-10-02-challenge-rankings-design.md`

## Global Constraints

- Couches : `api → services → repositories → DB`. Seuls les repositories appellent `db.query/execute/get/delete` (verrouillé par `tests/test_layering.py`).
- Langue : français pour ce qui est visible (UI, messages, docs), anglais pour identifiants, tests, docstrings techniques, logs, commits.
- Jamais de tiret (—, –, ou trait d'union de ponctuation) dans la prose, les commentaires ou l'UI. Virgule, point ou parenthèses.
- Commits Conventional Commits, **sans** trailer `Co-Authored-By`.
- `/api/v1` : champs uniquement **additifs** (Principe IV).
- Seuils : `MIN_COVERAGE = 0.9`, `MIN_COURSES_PER_ATHLETE = 2`, `MIN_LINK_SHARE = 0.5`.
- Tests backend depuis `backend/` : `uv run pytest -m "not integration" <cible>` ; lint `uv run ruff check .`. Front depuis `frontend/` : `npm test -- <cible>`, `npm run lint`, `npm run build`.
- Raffinement du design, à reporter dans la spec en Task 1 : une ligne Challenge n'est **jamais** créatrice d'athlète. Elle est appariée par identité `(nom, prénom)` normalisée (et l'ordre inverse, cas Klikego tout en majuscules) aux athlètes **déjà présents sur les épreuves du même jour** ; une ligne sans appariement unique est écartée. Conséquence voulue : une personne opposée (#334) ou un nom masqué, déjà anonymisés sur les épreuves, ne sont jamais réintroduits par un Challenge.

---

### Task 1: Modèle, migration et repository

**Files:**
- Create: `backend/app/models/challenge.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/c1a11e9e1008_challenges.py`
- Create: `backend/app/repositories/challenge_repository.py`
- Modify: `backend/app/repositories/__init__.py` (exporter `challenge_repository` comme les autres, si le paquet les réexporte)
- Modify: `docs/superpowers/specs/2026-10-02-challenge-rankings-design.md` (raffinement « jamais créatrice d'athlète », cf. Global Constraints)
- Test: `backend/tests/test_repositories/test_challenge_repository.py`

**Interfaces:**
- Produces:
  - modèles `Challenge`, `ChallengeCourse`, `ChallengeResult` ;
  - `challenge_repository.upsert(db, *, name: str, event_date: date, source_url: str) -> Challenge`
  - `challenge_repository.replace_links(db, challenge: Challenge, course_ids: list[int]) -> None`
  - `challenge_repository.upsert_result(db, challenge: Challenge, **fields) -> ChallengeResult` (clé `bib_number`, sinon `athlete_id`)
  - `challenge_repository.get(db, challenge_id: int) -> Challenge | None`
  - `challenge_repository.list_for_athlete(db, athlete_id: int) -> list[ChallengeResult]`
  - `challenge_repository.list_for_course(db, course_id: int) -> list[Challenge]`
  - `challenge_repository.ranked_counts(db, challenge_ids: list[int]) -> dict[int, int]`
  - `challenge_repository.delete_all(db) -> int`

- [ ] **Step 1: Write the failing test**

```python
"""Tables Challenge (#1008) : identité, liens vers N épreuves, lignes classées."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import challenge_repository

DAY = date(2026, 5, 13)


def _course(db, name):
    course = Course(name=name, event_date=DAY, event_type="triathlon-m")
    db.add(course)
    db.flush()
    return course


def _athlete(db, nom):
    athlete = Athlete(nom=nom, prenom="Jean")
    db.add(athlete)
    db.flush()
    return athlete


def test_upsert_is_idempotent_on_name_and_date(db_session):
    first = challenge_repository.upsert(db_session, name="START CHALLENGE", event_date=DAY, source_url="u")
    again = challenge_repository.upsert(db_session, name="START CHALLENGE", event_date=DAY, source_url="u2")
    assert first.id == again.id
    assert again.source_url == "u2"


def test_links_and_results_round_trip(db_session):
    xs, m = _course(db_session, "XS"), _course(db_session, "M")
    athlete = _athlete(db_session, "DUPONT")
    challenge = challenge_repository.upsert(db_session, name="START CHALLENGE", event_date=DAY, source_url="u")
    challenge_repository.replace_links(db_session, challenge, [xs.id, m.id])
    challenge_repository.upsert_result(
        db_session, challenge, athlete_id=athlete.id, bib_number="12",
        rank_overall=1, rank_gender=1, rank_category=None,
        total_time="06:50:33", status="finisher", raw_data={},
    )
    challenge_repository.upsert_result(
        db_session, challenge, athlete_id=athlete.id, bib_number="12",
        rank_overall=2, rank_gender=1, rank_category=None,
        total_time="06:50:34", status="finisher", raw_data={},
    )
    db_session.flush()

    assert [c.id for c in challenge_repository.list_for_course(db_session, xs.id)] == [challenge.id]
    rows = challenge_repository.list_for_athlete(db_session, athlete.id)
    assert [(r.rank_overall, r.total_time) for r in rows] == [(2, "06:50:34")]
    assert challenge_repository.ranked_counts(db_session, [challenge.id]) == {challenge.id: 1}

    challenge_repository.replace_links(db_session, challenge, [m.id])
    assert challenge_repository.list_for_course(db_session, xs.id) == []


def test_delete_all_removes_challenges_and_rows(db_session):
    challenge = challenge_repository.upsert(db_session, name="C", event_date=DAY, source_url="u")
    athlete = _athlete(db_session, "MARTIN")
    challenge_repository.upsert_result(
        db_session, challenge, athlete_id=athlete.id, bib_number="1", rank_overall=1,
        rank_gender=None, rank_category=None, total_time="01:00:00", status="finisher", raw_data={},
    )
    assert challenge_repository.delete_all(db_session) == 1
    assert challenge_repository.list_for_athlete(db_session, athlete.id) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -m "not integration" tests/test_repositories/test_challenge_repository.py -v`
Expected: FAIL, `ImportError: cannot import name 'challenge_repository'`.

- [ ] **Step 3: Write the models**

`backend/app/models/challenge.py` :

```python
"""Classement Challenge (#1008) : le cumul d'un athlète sur plusieurs épreuves du même jour.

Ses lignes ne sont pas des `Participation` : elles n'entrent dans aucun compteur,
aucun `federal_only`, aucune validation de saison ni aucune statistique, par
construction et non par une clause à ne pas oublier.
"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (UniqueConstraint("name", "event_date", name="uq_challenge_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    event_date: Mapped[date] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String, default="")
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    links: Mapped[list["ChallengeCourse"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )
    results: Mapped[list["ChallengeResult"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan"
    )


class ChallengeCourse(Base):
    __tablename__ = "challenge_courses"

    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    challenge: Mapped[Challenge] = relationship(back_populates="links")
    course: Mapped["Course"] = relationship()  # noqa: F821


class ChallengeResult(Base):
    __tablename__ = "challenge_results"
    __table_args__ = (UniqueConstraint("challenge_id", "bib_number", name="uq_challenge_result_bib"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[int] = mapped_column(
        ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT : une fiche porteuse de lignes Challenge ne disparaît pas en silence.
    athlete_id: Mapped[int] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"), index=True
    )
    bib_number: Mapped[str | None] = mapped_column(String, nullable=True)
    rank_overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_gender: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_category: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_time: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="finisher")
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    challenge: Mapped[Challenge] = relationship(back_populates="results")
    athlete: Mapped["Athlete"] = relationship()  # noqa: F821
```

Dans `backend/app/models/__init__.py`, ajouter `from app.models.challenge import Challenge, ChallengeCourse, ChallengeResult` et les trois noms dans `__all__` (ordre alphabétique).

- [ ] **Step 4: Write the repository**

`backend/app/repositories/challenge_repository.py` :

```python
"""Accès aux tables Challenge (#1008)."""
from collections.abc import Sequence
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.challenge import Challenge, ChallengeCourse, ChallengeResult


def upsert(db: Session, *, name: str, event_date: date, source_url: str) -> Challenge:
    challenge = (
        db.query(Challenge)
        .filter(Challenge.name == name, Challenge.event_date == event_date)
        .one_or_none()
    )
    if challenge is None:
        challenge = Challenge(name=name, event_date=event_date)
        db.add(challenge)
    challenge.source_url = source_url
    challenge.scraped_at = utcnow()
    db.flush()
    return challenge


def replace_links(db: Session, challenge: Challenge, course_ids: Sequence[int]) -> None:
    db.query(ChallengeCourse).filter(ChallengeCourse.challenge_id == challenge.id).delete(
        synchronize_session="fetch"
    )
    db.add_all(ChallengeCourse(challenge_id=challenge.id, course_id=cid) for cid in sorted(set(course_ids)))
    db.flush()


def upsert_result(db: Session, challenge: Challenge, **fields) -> ChallengeResult:
    query = db.query(ChallengeResult).filter(ChallengeResult.challenge_id == challenge.id)
    if fields.get("bib_number"):
        query = query.filter(ChallengeResult.bib_number == fields["bib_number"])
    else:
        query = query.filter(
            ChallengeResult.bib_number.is_(None), ChallengeResult.athlete_id == fields["athlete_id"]
        )
    row = query.one_or_none()
    if row is None:
        row = ChallengeResult(challenge_id=challenge.id)
        db.add(row)
    for key, value in fields.items():
        setattr(row, key, value)
    db.flush()
    return row


def get(db: Session, challenge_id: int) -> Challenge | None:
    return (
        db.query(Challenge)
        .options(
            selectinload(Challenge.results).selectinload(ChallengeResult.athlete),
            selectinload(Challenge.links).selectinload(ChallengeCourse.course),
        )
        .filter(Challenge.id == challenge_id)
        .one_or_none()
    )


def list_for_athlete(db: Session, athlete_id: int) -> list[ChallengeResult]:
    return (
        db.query(ChallengeResult)
        .join(Challenge, Challenge.id == ChallengeResult.challenge_id)
        .options(selectinload(ChallengeResult.challenge).selectinload(Challenge.links).selectinload(ChallengeCourse.course))
        .filter(ChallengeResult.athlete_id == athlete_id)
        .order_by(Challenge.event_date.desc(), Challenge.id)
        .all()
    )


def list_for_course(db: Session, course_id: int) -> list[Challenge]:
    return (
        db.query(Challenge)
        .join(ChallengeCourse, ChallengeCourse.challenge_id == Challenge.id)
        .filter(ChallengeCourse.course_id == course_id)
        .order_by(Challenge.name)
        .all()
    )


def ranked_counts(db: Session, challenge_ids: Sequence[int]) -> dict[int, int]:
    if not challenge_ids:
        return {}
    rows = (
        db.query(ChallengeResult.challenge_id, func.count(ChallengeResult.id))
        .filter(
            ChallengeResult.challenge_id.in_(challenge_ids),
            ChallengeResult.rank_overall.is_not(None),
        )
        .group_by(ChallengeResult.challenge_id)
        .all()
    )
    return {challenge_id: count for challenge_id, count in rows}


def list_for_athlete_ids(db: Session, athlete_id: int) -> list[ChallengeResult]:
    """Lignes à anonymiser ou à réattribuer (opposition, fusion)."""
    return db.query(ChallengeResult).filter(ChallengeResult.athlete_id == athlete_id).all()


def delete_all(db: Session) -> int:
    db.query(ChallengeResult).delete(synchronize_session=False)
    db.query(ChallengeCourse).delete(synchronize_session=False)
    deleted = db.query(Challenge).delete(synchronize_session=False)
    db.flush()
    return deleted
```

Si `backend/app/repositories/__init__.py` importe explicitement ses modules, y ajouter `challenge_repository`.

- [ ] **Step 5: Write the migration**

Vérifier d'abord la tête : `uv run alembic heads` (attendu `f2b8d4e61a37`, sinon prendre la tête rendue comme `down_revision`). Puis `backend/alembic/versions/c1a11e9e1008_challenges.py`, sur le gabarit de `f2b8d4e61a37_athlete_oppositions.py` (en-tête, `__all__`) :

```python
"""challenges

Classements Challenge (#1008) : `challenges`, `challenge_courses` (liens vers N
épreuves) et `challenge_results`, hors de `participations` par construction.

Revision ID: c1a11e9e1008
Revises: f2b8d4e61a37
Create Date: 2026-10-02 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1a11e9e1008'
down_revision: Union[str, None] = 'f2b8d4e61a37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "event_date", name="uq_challenge_identity"),
    )
    op.create_table(
        "challenge_courses",
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("challenge_id", "course_id"),
    )
    op.create_index("ix_challenge_courses_course_id", "challenge_courses", ["course_id"])
    op.create_table(
        "challenge_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), nullable=False),
        sa.Column("bib_number", sa.String(), nullable=True),
        sa.Column("rank_overall", sa.Integer(), nullable=True),
        sa.Column("rank_gender", sa.Integer(), nullable=True),
        sa.Column("rank_category", sa.Integer(), nullable=True),
        sa.Column("total_time", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["athlete_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id", "bib_number", name="uq_challenge_result_bib"),
    )
    op.create_index("ix_challenge_results_challenge_id", "challenge_results", ["challenge_id"])
    op.create_index("ix_challenge_results_athlete_id", "challenge_results", ["athlete_id"])


def downgrade() -> None:
    op.drop_table("challenge_results")
    op.drop_table("challenge_courses")
    op.drop_table("challenges")
```

Puis `uv run alembic upgrade head` et `uv run alembic check` : `check` ne doit proposer aucune opération (sinon aligner modèle et migration, noms d'index compris).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" tests/test_repositories/test_challenge_repository.py tests/test_migrations.py tests/test_layering.py -v`
Expected: PASS.

- [ ] **Step 7: Report the design refinement in the spec**

Dans `docs/superpowers/specs/2026-10-02-challenge-rankings-design.md`, section 1, remplacer « L'athlète est résolu par le même `mapping` que les participations, donc la même fiche est reliée. » par :

```markdown
Une ligne Challenge n'est **jamais** créatrice d'athlète : elle est appariée par
identité `(nom, prénom)` normalisée, ou dans l'ordre inverse (Klikego publie
« PRÉNOM NOM » en majuscules), aux athlètes déjà présents sur les épreuves du
même jour. Une ligne sans appariement unique est écartée. Une personne opposée
(#334) ou un nom masqué, déjà anonymisés sur les épreuves, ne sont donc jamais
réintroduits par un Challenge.
```

Et à l'étape 3 de la section 2, remplacer « on résout l'athlète de chaque ligne mise à l'écart par le `mapping` habituel » par « on apparie chaque ligne mise à l'écart aux athlètes des épreuves du même jour (section 1) ».

- [ ] **Step 8: Commit**

```bash
git add backend/app/models backend/alembic/versions/c1a11e9e1008_challenges.py backend/app/repositories backend/tests/test_repositories/test_challenge_repository.py docs/superpowers/specs/2026-10-02-challenge-rankings-design.md
git commit -m "feat(challenges): add challenge tables and repository (#1008)"
```

---

### Task 2: Prédicat `heat_is_challenge`

**Files:**
- Modify: `backend/app/scrapers/utils.py` (à côté de `heat_is_relay`)
- Test: `backend/tests/test_scrapers_utils.py`

**Interfaces:**
- Produces: `heat_is_challenge(name: str | None) -> bool`

- [ ] **Step 1: Write the failing test** (ajouter en fin de `tests/test_scrapers_utils.py`)

```python
import pytest

from app.scrapers.utils import heat_is_challenge


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MEDOC ATLANTIQUE FRENCHMAN 2026 - START CHALLENGE (XS - M - L)", True),
        ("SUPER CHALLENGE (XS - M - L - XXL)", True),
        ("Challenge 1er Tour", True),
        ("CHALLENGÉ", True),
        ("La Baule - Challenge", True),
        ("Triathlon M", False),
        ("Challenger Tour", False),
        ("", False),
        (None, False),
    ],
)
def test_heat_is_challenge(name, expected):
    assert heat_is_challenge(name) is expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -m "not integration" tests/test_scrapers_utils.py -k heat_is_challenge -v`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Write minimal implementation** (dans `app/scrapers/utils.py`, sous `heat_is_relay`)

```python
def heat_is_challenge(name: str | None) -> bool:
    """Le nom du heat annonce-t-il un classement Challenge ? (#1008)

    Signal nécessaire, pas suffisant : l'import ne requalifie le heat qu'après
    avoir mesuré que ses athlètes courent aussi d'autres épreuves du même jour
    (`services/challenge_service.match`). « La Baule - Challenge », un relais,
    passe ce filtre et échoue au second.
    """
    words = _WORD_SPLIT_RE.split(strip_accents(name or "").lower())
    return "challenge" in words
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest -m "not integration" tests/test_scrapers_utils.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scrapers/utils.py backend/tests/test_scrapers_utils.py
git commit -m "feat(scrapers): detect challenge heat names (#1008)"
```

---

### Task 3: Appariement et enregistrement (`challenge_service`)

**Files:**
- Modify: `backend/app/repositories/challenge_repository.py` (ajout `athletes_on_date`)
- Create: `backend/app/services/challenge_service.py`
- Test: `backend/tests/test_services/test_challenge_service.py`

**Interfaces:**
- Consumes: `challenge_repository.upsert/replace_links/upsert_result` (Task 1), `heat_is_challenge` (Task 2), `mapping.total_time`, `mapping.derive_status`.
- Produces:
  - `challenge_repository.athletes_on_date(db, event_date: date) -> list[tuple[int, str, str, int, str]]` : `(athlete_id, nom, prenom, course_id, course_name)` pour chaque participation d'une épreuve de ce jour ;
  - `@dataclass(frozen=True) ChallengeRow(nom, prenom, bib_number, rank_overall, rank_gender, rank_category, total_time, status, raw_data)` avec `ChallengeRow.from_scraped(scraped: ScrapedResult)` et `ChallengeRow.from_participation(participation: Participation)` ;
  - `@dataclass(frozen=True) ChallengeMatch(athlete_ids: dict[int, int], course_ids: list[int])` : index de ligne → athlete_id, épreuves liées ;
  - `challenge_service.match(db, rows: list[ChallengeRow], *, event_date: date | None, exclude_course_ids: set[int] = frozenset()) -> ChallengeMatch | None`
  - `challenge_service.save(db, *, name: str, event_date: date, source_url: str, rows: list[ChallengeRow], found: ChallengeMatch) -> Challenge`

- [ ] **Step 1: Write the failing tests**

```python
"""Appariement d'un heat Challenge aux épreuves du même jour (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import challenge_repository
from app.services import challenge_service
from app.services.challenge_service import ChallengeRow

DAY = date(2026, 5, 13)


def _course(db, name, day=DAY):
    course = Course(name=name, event_date=day, event_type="triathlon-m")
    db.add(course)
    db.flush()
    return course


def _runner(db, nom, *courses):
    athlete = Athlete(nom=nom, prenom="Jean")
    db.add(athlete)
    db.flush()
    for i, course in enumerate(courses):
        db.add(Participation(athlete_id=athlete.id, course_id=course.id, bib_number=f"{nom}-{i}"))
    db.flush()
    return athlete


def _row(nom, prenom="Jean", bib=None, rank=1):
    return ChallengeRow(
        nom=nom, prenom=prenom, bib_number=bib or nom, rank_overall=rank, rank_gender=None,
        rank_category=None, total_time="06:50:33", status="finisher", raw_data={},
    )


def _field(db, size=10):
    xs, m, l = _course(db, "XS"), _course(db, "M"), _course(db, "L")
    names = [f"NOM{i}" for i in range(size)]
    for nom in names:
        _runner(db, nom, xs, m, l)
    return (xs, m, l), names


def test_full_overlap_is_a_challenge_linked_to_every_course(db_session):
    (xs, m, l), names = _field(db_session)
    found = challenge_service.match(db_session, [_row(n) for n in names], event_date=DAY)
    assert found is not None
    assert found.course_ids == sorted([xs.id, m.id, l.id])
    assert len(found.athlete_ids) == 10


def test_ninety_percent_is_enough_eighty_nine_is_not(db_session):
    _, names = _field(db_session, size=9)
    rows = [_row(n) for n in names] + [_row("INCONNU")]
    assert challenge_service.match(db_session, rows, event_date=DAY) is not None
    rows.append(_row("AUTRE"))
    assert challenge_service.match(db_session, rows, event_date=DAY) is None


def test_athletes_on_a_single_course_do_not_count(db_session):
    solo = _course(db_session, "Relais")
    names = [f"NOM{i}" for i in range(5)]
    for nom in names:
        _runner(db_session, nom, solo)
    assert challenge_service.match(db_session, [_row(n) for n in names], event_date=DAY) is None


def test_other_days_and_challenge_courses_are_not_candidates(db_session):
    other_day = _course(db_session, "XS", day=date(2026, 5, 14))
    m = _course(db_session, "M")
    old_challenge = _course(db_session, "START CHALLENGE")
    for nom in ("A", "B"):
        _runner(db_session, nom, other_day, m, old_challenge)
    assert challenge_service.match(db_session, [_row("A"), _row("B")], event_date=DAY) is None


def test_reversed_names_match(db_session):
    xs, m = _course(db_session, "XS"), _course(db_session, "M")
    _runner(db_session, "DUPONT", xs, m)
    found = challenge_service.match(db_session, [_row("Jean", prenom="DUPONT")], event_date=DAY)
    assert found is not None


def test_link_threshold_keeps_only_courses_with_half_the_field(db_session):
    (xs, m, l), names = _field(db_session)
    extra = _course(db_session, "Kids")
    _runner(db_session, "SEUL", extra, xs)
    rows = [_row(n) for n in names] + [_row("SEUL")]
    found = challenge_service.match(db_session, rows, event_date=DAY)
    assert found is not None
    assert extra.id not in found.course_ids
    assert xs.id in found.course_ids


def test_save_writes_challenge_results_and_links(db_session):
    (xs, m, l), names = _field(db_session, size=3)
    rows = [_row(n, rank=i + 1) for i, n in enumerate(names)]
    found = challenge_service.match(db_session, rows, event_date=DAY)
    challenge = challenge_service.save(
        db_session, name="START CHALLENGE", event_date=DAY, source_url="u", rows=rows, found=found
    )
    assert sorted(link.course_id for link in challenge.links) == sorted([xs.id, m.id, l.id])
    assert sorted(r.rank_overall for r in challenge.results) == [1, 2, 3]
    assert challenge_repository.ranked_counts(db_session, [challenge.id]) == {challenge.id: 3}


def test_unmatched_rows_are_not_saved(db_session):
    _, names = _field(db_session)
    rows = [_row(n) for n in names] + [_row("INCONNU", bib="999")]
    found = challenge_service.match(db_session, rows, event_date=DAY)
    challenge = challenge_service.save(
        db_session, name="C", event_date=DAY, source_url="u", rows=rows, found=found
    )
    assert "999" not in {r.bib_number for r in challenge.results}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_service.py -v`
Expected: FAIL, `ImportError`.

- [ ] **Step 3: Add the repository query** (dans `challenge_repository.py`)

```python
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation


def athletes_on_date(db: Session, event_date: date) -> list[tuple[int, str, str, int, str]]:
    """(athlete_id, nom, prenom, course_id, course_name) de chaque participation du jour."""
    return (
        db.query(Athlete.id, Athlete.nom, Athlete.prenom, Course.id, Course.name)
        .join(Participation, Participation.athlete_id == Athlete.id)
        .join(Course, Course.id == Participation.course_id)
        .filter(Course.event_date == event_date)
        .all()
    )
```

- [ ] **Step 4: Write the service**

`backend/app/services/challenge_service.py` :

```python
"""Classements Challenge (#1008) : appariement aux épreuves du jour, enregistrement.

Un heat dont le nom annonce un Challenge n'en est un que si ses athlètes courent
aussi les autres épreuves du même jour : `MIN_COVERAGE` d'entre eux doivent
figurer sur au moins `MIN_COURSES_PER_ATHLETE` épreuves. Les épreuves liées sont
celles où figure au moins `MIN_LINK_SHARE` du classement.

Une ligne n'est jamais créatrice d'athlète : sans appariement unique, elle est
écartée. Une personne opposée (#334) ou un nom masqué, déjà anonymisés sur les
épreuves, ne reviennent donc pas par ce chemin.
"""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models.challenge import Challenge
from app.models.participation import Participation
from app.repositories import challenge_repository
from app.scrapers.base import ScrapedResult
from app.scrapers.utils import heat_is_challenge
from app.services import mapping

MIN_COVERAGE = 0.9
MIN_COURSES_PER_ATHLETE = 2
MIN_LINK_SHARE = 0.5


@dataclass(frozen=True)
class ChallengeRow:
    nom: str
    prenom: str
    bib_number: str | None
    rank_overall: int | None
    rank_gender: int | None
    rank_category: int | None
    total_time: str | None
    status: str
    raw_data: dict | None

    @classmethod
    def from_scraped(cls, scraped: ScrapedResult) -> "ChallengeRow":
        return cls(
            nom=scraped.athlete_name, prenom=scraped.athlete_firstname,
            bib_number=scraped.bib_number or None, rank_overall=scraped.rank_overall,
            rank_gender=scraped.rank_gender, rank_category=scraped.rank_category,
            total_time=mapping.total_time(scraped), status=mapping.derive_status(scraped),
            raw_data=scraped.raw_data or None,
        )

    @classmethod
    def from_participation(cls, participation: Participation) -> "ChallengeRow":
        return cls(
            nom=participation.athlete.nom, prenom=participation.athlete.prenom,
            bib_number=participation.bib_number, rank_overall=participation.rank_overall,
            rank_gender=participation.rank_gender, rank_category=participation.rank_category,
            total_time=participation.total_time, status=participation.status,
            raw_data=participation.raw_data,
        )


@dataclass(frozen=True)
class ChallengeMatch:
    #: Index de la ligne dans `rows` -> athlète apparié.
    athlete_ids: dict[int, int] = field(default_factory=dict)
    course_ids: list[int] = field(default_factory=list)


def _key(nom: str | None, prenom: str | None) -> tuple[str, str]:
    return ((nom or "").strip().lower(), (prenom or "").strip().lower())


def match(
    db: Session,
    rows: list[ChallengeRow],
    *,
    event_date: date | None,
    exclude_course_ids: frozenset[int] | set[int] = frozenset(),
) -> ChallengeMatch | None:
    if not rows or event_date is None:
        return None
    by_key: dict[tuple[str, str], dict[int, set[int]]] = {}
    for athlete_id, nom, prenom, course_id, course_name in challenge_repository.athletes_on_date(db, event_date):
        if course_id in exclude_course_ids or heat_is_challenge(course_name):
            continue
        by_key.setdefault(_key(nom, prenom), {}).setdefault(athlete_id, set()).add(course_id)

    athlete_ids: dict[int, int] = {}
    per_course: Counter[int] = Counter()
    covered = 0
    for index, row in enumerate(rows):
        candidates = by_key.get(_key(row.nom, row.prenom)) or by_key.get(_key(row.prenom, row.nom))
        if not candidates or len(candidates) != 1:
            continue
        ((athlete_id, course_ids),) = candidates.items()
        athlete_ids[index] = athlete_id
        per_course.update(course_ids)
        if len(course_ids) >= MIN_COURSES_PER_ATHLETE:
            covered += 1
    if covered < MIN_COVERAGE * len(rows):
        return None
    linked = sorted(cid for cid, count in per_course.items() if count >= MIN_LINK_SHARE * len(rows))
    return ChallengeMatch(athlete_ids=athlete_ids, course_ids=linked)


def save(
    db: Session,
    *,
    name: str,
    event_date: date,
    source_url: str,
    rows: list[ChallengeRow],
    found: ChallengeMatch,
) -> Challenge:
    challenge = challenge_repository.upsert(db, name=name, event_date=event_date, source_url=source_url)
    challenge_repository.replace_links(db, challenge, found.course_ids)
    for index, athlete_id in found.athlete_ids.items():
        row = rows[index]
        challenge_repository.upsert_result(
            db, challenge, athlete_id=athlete_id, bib_number=row.bib_number,
            rank_overall=row.rank_overall, rank_gender=row.rank_gender,
            rank_category=row.rank_category, total_time=row.total_time,
            status=row.status, raw_data=row.raw_data,
        )
    db.refresh(challenge)
    return challenge
```

Note : si `mapping.total_time` / `mapping.derive_status` exigent un import circulaire (mapping importe des repositories, pas les services : aucun cycle attendu), garder l'import tel quel.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_service.py tests/test_layering.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/challenge_repository.py backend/app/services/challenge_service.py backend/tests/test_services/test_challenge_service.py
git commit -m "feat(challenges): match challenge rows to same-day courses (#1008)"
```

---

### Task 4: Branchement dans l'import (`persist_steps`)

**Files:**
- Modify: `backend/app/services/import_service.py` (`_Persister.__init__`, `_Persister.finalize`, `persist_steps`, `persist_results` et tout autre résumé qui lit `persister.reconciled`)
- Test: `backend/tests/test_services/test_challenge_on_import.py`

**Interfaces:**
- Consumes: `heat_is_challenge` (Task 2), `challenge_service.match/save`, `ChallengeRow.from_scraped` (Task 3).
- Produces: `_Persister.challenges: int` ; clé `"challenges"` dans le dict de `persist_results`.

- [ ] **Step 1: Write the failing tests**

```python
"""Un heat Challenge devient un `Challenge`, pas une épreuve de plus (#1008)."""
from datetime import date

from app.models.challenge import Challenge, ChallengeResult
from app.models.course import Course
from app.scrapers.base import ScrapedResult
from app.services import import_service, stats_service

URL = "https://www.klikego.com/resultats/medoc-atlantique-frenchman-triathlon-carcans-2026/1354050643080-23"
DAY = date(2026, 5, 13)
EVENT = "MEDOC ATLANTIQUE FRENCHMAN 2026"


def _row(heat: str, nom: str, bib: str, *, time="02:00:00", rank=1) -> ScrapedResult:
    return ScrapedResult(
        source_url=f"{URL}?heat={heat}", provider="klikego", athlete_name=nom,
        athlete_firstname="Jean", bib_number=bib, event_name=f"{EVENT} - {heat}",
        event_date=DAY, event_type="triathlon-m", total_time=time, rank_overall=rank,
    )


def _batch(names, *, challenge_heat="START CHALLENGE (XS - M - L)"):
    rows = []
    for i, nom in enumerate(names):
        rows.append(_row("XS", nom, f"xs{i}", rank=i + 1))
        rows.append(_row("M", nom, f"m{i}", rank=i + 1))
    for i, nom in enumerate(names):
        rows.append(_row(challenge_heat, nom, f"c{i}", time="06:50:33", rank=i + 1))
    return rows


def test_challenge_heat_is_stored_as_a_challenge(db_session):
    names = [f"NOM{i}" for i in range(5)]
    outcome = import_service.persist_results(db_session, URL, _batch(names))

    courses = db_session.query(Course).all()
    assert sorted(c.name.rsplit(" - ", 1)[1] for c in courses) == ["M", "XS"]
    assert all(c.participation_count == 5 for c in courses)
    challenge = db_session.query(Challenge).one()
    assert challenge.name == f"{EVENT} - START CHALLENGE (XS - M - L)"
    assert sorted(link.course_id for link in challenge.links) == sorted(c.id for c in courses)
    assert db_session.query(ChallengeResult).count() == 5
    assert outcome["challenges"] == 1


def test_stats_are_identical_with_or_without_the_challenge_heat(db_session):
    names = [f"NOM{i}" for i in range(5)]
    without = [r for r in _batch(names) if "CHALLENGE" not in r.event_name]
    import_service.persist_results(db_session, URL, without)
    before = stats_service.stats(db_session)
    import_service.persist_results(db_session, URL, _batch(names))
    assert db_session.query(Challenge).count() == 1
    assert stats_service.stats(db_session) == before


def test_isolated_challenge_heat_stays_a_course(db_session):
    rows = [_row("La Baule - Challenge", f"SOLO{i}", f"b{i}") for i in range(4)]
    import_service.persist_results(db_session, URL, rows)
    assert db_session.query(Challenge).count() == 0
    assert db_session.query(Course).one().participation_count == 4


def test_reimport_is_idempotent(db_session):
    names = [f"NOM{i}" for i in range(5)]
    import_service.persist_results(db_session, URL, _batch(names))
    import_service.persist_results(db_session, URL, _batch(names))
    assert db_session.query(Challenge).count() == 1
    assert db_session.query(ChallengeResult).count() == 5
```

Avant de lancer : vérifier le nom réel de la fonction de stats globales (`grep -n "^def " app/services/stats_service.py`) et remplacer `stats_service.stats(db_session)` par celle qui sert `GET /stats` avec ses paramètres par défaut (par exemple `stats_service.overview(db)`). Si `persist_results` refuse une URL Klikego factice, prendre le patron de `tests/test_services/test_reclassification_on_import.py` (fonction `_importer` avec `patch_scraper`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_on_import.py -v`
Expected: FAIL (`Challenge` absent, `KeyError: 'challenges'`).

- [ ] **Step 3: Make `finalize` re-entrant**

Dans `_Persister.finalize`, la seconde boucle déplace `_pending_splits` dans `_pending` sans les vider : un second appel les résoudrait deux fois. Remplacer :

```python
        for course_id, splits in self._pending_splits.items():
            self._pending[course_id] = splits
            self._resolve_pending(course_id)
```

par :

```python
        for course_id, splits in self._pending_splits.items():
            self._pending[course_id] = splits
            self._resolve_pending(course_id)
        # Un second passage (lignes Challenge rendues au flux normal, #1008) ne
        # doit pas résoudre deux fois les mêmes découpages.
        self._pending_splits.clear()
```

et dans `__init__`, après `self.reconciled = 0` : `self.challenges = 0`.

- [ ] **Step 4: Hook the challenge step into `persist_steps`**

Ajouter les imports en tête de `import_service.py` :

```python
from app.scrapers.utils import heat_is_challenge
from app.services import challenge_service
from app.services.challenge_service import ChallengeRow
```

(si `app.scrapers.utils` est déjà importé, ajouter le nom à l'import existant).

Remplacer le corps de `persist_steps` (après la docstring, qu'on complète d'une phrase sur #1008) par :

```python
    held = [r for r in results if heat_is_challenge(r.event_name)]
    results = [r for r in results if not heat_is_challenge(r.event_name)]
    _redate_heats(db, results)
    _reclassify_heats(db, url, results)
    _renumber_duplicate_ranks(results)
    _renumber_relay_split_ranks(db, results)
    persister = _Persister(db, url)
    yield 0, persister
    for done, scraped in enumerate(results, start=1):
        persister.add(scraped)
        yield done, persister
    persister.finalize()
    leftovers = _persist_challenges(db, url, held, persister)
    if leftovers:
        _renumber_duplicate_ranks(leftovers)
        for scraped in leftovers:
            persister.add(scraped)
        persister.finalize()
```

et ajouter, juste au-dessus de `persist_steps` :

```python
def _persist_challenges(
    db: Session, url: str, held: list[ScrapedResult], persister: "_Persister"
) -> list[ScrapedResult]:
    """Enregistre les heats Challenge appariés (#1008) ; rend les lignes des autres.

    Après `finalize` : l'appariement lit en base les participations du jour,
    celles de ce lot comprises. Un heat qui échoue au test redevient une épreuve.
    """
    groups: dict[tuple, list[ScrapedResult]] = {}
    for scraped in held:
        groups.setdefault((scraped.event_name, scraped.event_date), []).append(scraped)
    leftovers: list[ScrapedResult] = []
    for (name, event_date), rows in groups.items():
        challenge_rows = [ChallengeRow.from_scraped(r) for r in rows]
        found = challenge_service.match(db, challenge_rows, event_date=event_date)
        if found is None:
            leftovers.extend(rows)
            continue
        challenge_service.save(
            db, name=name, event_date=event_date,
            source_url=rows[0].source_url or url, rows=challenge_rows, found=found,
        )
        persister.challenges += 1
    return leftovers
```

Dans `persist_results`, ajouter `"challenges": persister.challenges,` au dict rendu. Puis `grep -n "persister.reconciled" app/services/*.py app/api/v1/*.py` : partout où un résumé d'import est construit à partir du persister (SSE `done`, rescrape, CLI), ajouter la même clé `challenges`, et l'ajouter au schéma Pydantic de réponse correspondant s'il en existe un (champ `challenges: int = 0`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_on_import.py tests/test_services/test_import_service.py tests/test_services/test_reclassification_on_import.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest -m "not integration"` puis `uv run ruff check .`
Expected: tout vert (la base de référence connue : 1 échec préexistant éventuel, à comparer avec `main` avant de conclure).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/import_service.py backend/tests/test_services/test_challenge_on_import.py
git commit -m "feat(import): store matched challenge heats as challenges (#1008)"
```

(ajouter aux `git add` tout fichier touché à l'étape 4 pour la clé `challenges`.)

---

### Task 5: Raccordement à l'athlète (orphelins, purges, opposition)

**Files:**
- Modify: `backend/app/repositories/athlete_repository.py` (`referenced_outside_results`)
- Modify: `backend/app/services/admin_actions.py` (`wipe_all_participations`, `wipe_all_courses`)
- Modify: `backend/app/services/opposition_service.py` (`preview`, `_anonymise`)
- Test: `backend/tests/test_services/test_challenge_athlete_links.py`

**Interfaces:**
- Consumes: `challenge_repository.list_for_athlete_ids`, `challenge_repository.delete_all` (Task 1).

- [ ] **Step 1: Write the failing tests**

```python
"""Une fiche porteuse de lignes Challenge n'est ni orpheline ni oubliée (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.challenge import ChallengeResult
from app.models.user import User
from app.repositories import athlete_repository, challenge_repository
from app.services import admin_actions, opposition_service

DAY = date(2026, 5, 13)


def _challenger(db, nom="DUPONT"):
    athlete = Athlete(nom=nom, prenom="Jean")
    db.add(athlete)
    db.flush()
    challenge = challenge_repository.upsert(db, name="C", event_date=DAY, source_url="u")
    challenge_repository.upsert_result(
        db, challenge, athlete_id=athlete.id, bib_number="1", rank_overall=1, rank_gender=None,
        rank_category=None, total_time="06:50:33", status="finisher", raw_data={"nom": nom},
    )
    return athlete


def test_athlete_with_challenge_rows_is_not_an_orphan(db_session):
    athlete = _challenger(db_session)
    assert athlete_repository.delete_orphans_among(db_session, [athlete.id]) == []


def test_wipe_all_courses_removes_challenges_first(db_session, admin_user):
    _challenger(db_session)
    admin_actions.wipe_all_courses(db_session, user_id=admin_user.id)
    assert db_session.query(ChallengeResult).count() == 0
    assert db_session.query(Athlete).count() == 0


def test_opposition_anonymises_challenge_rows(db_session, admin_user):
    athlete = _challenger(db_session)
    assert opposition_service.preview(db_session, athlete_id=athlete.id).results == 1
    opposition_service.apply(db_session, admin_user, athlete_id=athlete.id, requested_on=DAY)
    row = db_session.query(ChallengeResult).one()
    assert row.athlete.nom.startswith("Anonyme")
    assert row.raw_data == {}
```

Fixture `admin_user` : réutiliser celle de `tests/test_services/test_opposition_on_import.py` ou des tests d'opposition existants (`grep -rn "def admin_user\|User(" tests/test_services | head`) ; à défaut, créer `User(email="admin@test", ...)` avec les champs obligatoires du modèle. Vérifier aussi le nom exact du champ de `OppositionPreview` qui compte les résultats (`grep -n "class OppositionPreview" -A 6 app/services/opposition_service.py`) et l'utiliser à la place de `.results`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_athlete_links.py -v`
Expected: FAIL sur les trois tests.

- [ ] **Step 3: Implement**

`athlete_repository.referenced_outside_results` : ajouter la ligne Challenge à la disjonction, et une phrase à la docstring.

```python
from app.models.challenge import ChallengeResult

    # ...docstring : « Les lignes Challenge (#1008) aussi : un cumul n'est pas une
    # participation, mais il désigne la fiche (FK RESTRICT). »
    return or_(
        exists().where(VolunteerAction.athlete_id == athlete_id),
        exists().where(SeasonValidation.athlete_id == athlete_id),
        exists().where(User.athlete_id == athlete_id),
        exists().where(ChallengeResult.athlete_id == athlete_id),
    )
```

`admin_actions.wipe_all_participations` et `wipe_all_courses` : juste avant `athlete_repository.delete_unreferenced(db)`, ajouter `resume["challenges_deleted"] = challenge_repository.delete_all(db)` (import `challenge_repository`). Une purge totale des résultats emporte les cumuls qui en dérivent.

`opposition_service` :

```python
from app.repositories import challenge_repository  # ajouter à l'import groupé existant


def _appearances(db: Session, athlete: Athlete) -> tuple[list, list, list]:
    carried = participation_repository.list_carried_by(db, athlete.id)
    carried_ids = {participation.id for participation in carried}
    links = [
        link for link in participation_repository.teammate_links_of(db, athlete.id)
        if link.participation_id not in carried_ids
    ]
    return carried, links, challenge_repository.list_for_athlete_ids(db, athlete.id)
```

Dans `preview` : `carried, links, challenge_rows = _appearances(...)` et `results += len(carried) + len(links) + len(challenge_rows)`.

Dans `_anonymise` : `carried, links, challenge_rows = _appearances(db, athlete)`, puis avant `user_repository.detach_athlete(...)` :

```python
    for row in challenge_rows:
        anonymous = athlete_repository.get_or_create(
            db, nom=f"Anonyme challenge {row.challenge_id}-{row.bib_number or row.id}",
            prenom="", gender=athlete.gender or "",
        )
        row.athlete_id = anonymous.id
        row.raw_data = {}
```

et `return len(carried) + len(links) + len(challenge_rows)`. Si un autre appelant consomme `_appearances` (`grep -n "_appearances" app`), l'adapter au triplet.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_athlete_links.py tests/test_services -k "opposition or wipe or orphan" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/athlete_repository.py backend/app/services/admin_actions.py backend/app/services/opposition_service.py backend/tests/test_services/test_challenge_athlete_links.py
git commit -m "feat(challenges): keep challenge rows in orphan, wipe and opposition flows (#1008)"
```

---

### Task 6: Commande CLI `requalify-challenges`

**Files:**
- Modify: `backend/app/repositories/course_repository.py` (ajout `list_named_like`)
- Modify: `backend/app/services/challenge_service.py` (ajout `requalify`)
- Create: `backend/app/cli/commands/requalify_challenges.py`
- Modify: `backend/app/cli/__init__.py`, `backend/app/cli/reports.py`
- Modify: `backend/app/cli/AGENTS.md` (documenter la commande, sur le modèle de `purge-timepulse-duplicates`)
- Test: `backend/tests/test_services/test_challenge_requalify.py`, `backend/tests/test_cli/test_requalify_challenges.py`

**Interfaces:**
- Consumes: `match`, `save`, `ChallengeRow.from_participation` (Task 3), `admin_actions.delete_course`.
- Produces:
  - `course_repository.list_named_like(db, fragment: str) -> list[Course]` (insensible à la casse, participations et athlètes chargés) ;
  - `@dataclass(frozen=True) Requalified(course_id: int, name: str, linked_course_ids: list[int], rows: int)` ;
  - `challenge_service.requalify(db, *, user_id: int | None) -> list[Requalified]` : `user_id=None` liste sans rien écrire.

- [ ] **Step 1: Write the failing service test**

```python
"""Reprise des épreuves Challenge déjà importées comme des épreuves (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.challenge import Challenge
from app.models.course import Course
from app.models.participation import Participation
from app.models.user import User
from app.services import challenge_service

DAY = date(2026, 5, 13)


def _seed(db):
    xs = Course(name="E - XS", event_date=DAY, event_type="triathlon-xs")
    m = Course(name="E - M", event_date=DAY, event_type="triathlon-m")
    challenge = Course(name="E - START CHALLENGE (XS - M - L)", event_date=DAY, event_type="triathlon-l")
    db.add_all([xs, m, challenge])
    db.flush()
    for i in range(5):
        athlete = Athlete(nom=f"NOM{i}", prenom="Jean")
        db.add(athlete)
        db.flush()
        for course, bib in ((xs, f"x{i}"), (m, f"m{i}"), (challenge, f"c{i}")):
            db.add(Participation(athlete_id=athlete.id, course_id=course.id, bib_number=bib,
                                 rank_overall=i + 1, total_time="02:00:00"))
    db.flush()
    return xs, m, challenge


def test_dry_run_lists_without_writing(db_session):
    xs, m, challenge = _seed(db_session)
    found = challenge_service.requalify(db_session, user_id=None)
    assert [(r.course_id, r.linked_course_ids, r.rows) for r in found] == [
        (challenge.id, sorted([xs.id, m.id]), 5)
    ]
    assert db_session.get(Course, challenge.id) is not None
    assert db_session.query(Challenge).count() == 0


def test_apply_converts_and_deletes_the_course(db_session, admin_user):
    xs, m, challenge = _seed(db_session)
    challenge_service.requalify(db_session, user_id=admin_user.id)
    assert db_session.get(Course, challenge.id) is None
    stored = db_session.query(Challenge).one()
    assert len(stored.results) == 5
    assert db_session.query(Athlete).count() == 5
```

(fixture `admin_user` comme en Task 5.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_requalify.py -v`
Expected: FAIL, `AttributeError: requalify`.

- [ ] **Step 3: Implement**

`course_repository.py` :

```python
def list_named_like(db: Session, fragment: str) -> list[Course]:
    """Épreuves dont le nom contient `fragment`, casse ignorée, résultats chargés."""
    return (
        db.query(Course)
        .options(selectinload(Course.participations).selectinload(Participation.athlete))
        .filter(func.lower(Course.name).contains(fragment.lower()))
        .order_by(Course.id)
        .all()
    )
```

(ajouter les imports `selectinload`, `Participation`, `func` s'ils manquent ; vérifier que `Participation.athlete` est bien le nom de la relation, sinon l'adapter.)

`challenge_service.py` :

```python
from app.repositories import course_repository
from app.services import admin_actions


@dataclass(frozen=True)
class Requalified:
    course_id: int
    name: str
    linked_course_ids: list[int]
    rows: int


def requalify(db: Session, *, user_id: int | None) -> list[Requalified]:
    """Requalifie en Challenge les épreuves déjà importées qui en sont (#1008).

    `user_id=None` liste seulement. Sinon, enregistre le Challenge **puis** supprime
    l'épreuve par le geste d'administration (journalisé) : ses athlètes restent,
    référencés par les lignes Challenge.
    """
    done: list[Requalified] = []
    for course in course_repository.list_named_like(db, "challenge"):
        if not heat_is_challenge(course.name) or course.event_date is None:
            continue
        rows = [ChallengeRow.from_participation(p) for p in course.participations]
        found = match(db, rows, event_date=course.event_date, exclude_course_ids={course.id})
        if found is None:
            continue
        done.append(Requalified(course.id, course.name, found.course_ids, len(found.athlete_ids)))
        if user_id is not None:
            save(db, name=course.name, event_date=course.event_date,
                 source_url=course.source_url, rows=rows, found=found)
            admin_actions.delete_course(db, course_id=course.id, user_id=user_id)
    return done
```

Si l'import de `admin_actions` depuis `challenge_service` crée un cycle (admin_actions importera `challenge_repository`, pas `challenge_service` : aucun cycle attendu), le placer dans la fonction.

`cli/commands/requalify_challenges.py`, calqué sur `purge_timepulse_duplicates.py` :

```python
"""Commande `requalify-challenges` : reprise ponctuelle de #1008. Zéro logique métier.

Sans `--yes`, elle liste les épreuves qui sont des classements Challenge ; avec,
elle les convertit et les supprime par le geste d'administration (journalisé au
nom de `--by-email`).
"""
import typer

from app.cli.reports import emit_report, render_challenge_requalification_report
from app.core.database import session_scope
from app.repositories import user_repository
from app.services import challenge_service

USAGE = 2


def requalify_challenges(
    yes: bool = typer.Option(False, "--yes", help="Convertit vraiment (sinon : liste seulement)."),
    by_email: str | None = typer.Option(
        None, "--by-email", help="Compte au nom duquel le journal consigne la suppression."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="stdout ne contient que le JSON ; le rapport texte passe sur stderr."
    ),
) -> None:
    """Liste, ou convertit avec `--yes`, les épreuves qui sont des classements Challenge."""
    with session_scope() as db:
        if not yes:
            found = challenge_service.requalify(db, user_id=None)
        else:
            comptes = user_repository.find_by_email(db, by_email) if by_email else []
            if not comptes:
                typer.echo("--yes exige --by-email, l'adresse d'un compte existant.", err=True)
                raise typer.Exit(USAGE)
            found = challenge_service.requalify(db, user_id=comptes[0].id)

    rows = [
        {"course_id": r.course_id, "name": r.name, "linked_course_ids": r.linked_course_ids,
         "rows": r.rows}
        for r in found
    ]
    emit_report(
        render_challenge_requalification_report(rows, converted=yes),
        {"converted": yes, "challenges": rows},
        json_output=json_output,
    )
```

Vérifier que `session_scope` commite en sortie (comme pour `purge-timepulse-duplicates`) ; sinon ne rien ajouter, le comportement suit celui de la commande modèle.

`cli/reports.py` :

```python
def render_challenge_requalification_report(rows: list[dict], *, converted: bool) -> str:
    """Épreuves requalifiées en classements Challenge (#1008)."""
    lignes = ["=== CLASSEMENTS CHALLENGE ==="]
    if not rows:
        lignes.append("Aucune épreuve à requalifier.")
        return "\n".join(lignes)
    for row in rows:
        liees = ", ".join(str(i) for i in row["linked_course_ids"])
        lignes.append(f"{row['course_id']}  {row['name']}  ({row['rows']} lignes)  →  {liees}")
    lignes.append(
        f"{len(rows)} épreuve(s) requalifiée(s)." if converted
        else f"{len(rows)} épreuve(s) à requalifier : relancer avec --yes --by-email <adresse>."
    )
    return "\n".join(lignes)
```

`cli/__init__.py` : importer `requalify_challenges` et `app.command("requalify-challenges")(requalify_challenges)` (ordre alphabétique).

- [ ] **Step 4: Write the CLI test**

Prendre le patron du test existant de `purge-timepulse-duplicates` (`ls tests/test_cli`, puis l'ouvrir) : même façon de pointer `session_scope` sur `db_session`, même `CliRunner`. Cas : sans `--yes`, sortie JSON `{"converted": false, "challenges": [...]}` et base inchangée ; `--yes` sans `--by-email` sort en code 2.

- [ ] **Step 5: Run tests**

Run: `uv run pytest -m "not integration" tests/test_services/test_challenge_requalify.py tests/test_cli -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/course_repository.py backend/app/services/challenge_service.py backend/app/cli backend/tests/test_services/test_challenge_requalify.py backend/tests/test_cli
git commit -m "feat(cli): requalify existing challenge courses (#1008)"
```

---

### Task 7: API (fiche athlète, résumé d'épreuve, classement)

**Files:**
- Create: `backend/app/schemas/challenge.py`
- Modify: `backend/app/schemas/participation.py` (`AthleteDetail.challenges`)
- Modify: `backend/app/schemas/course.py` (`CourseSummary.challenges`)
- Modify: `backend/app/api/v1/athletes.py`, `backend/app/api/v1/courses.py`
- Create: `backend/app/api/v1/challenges.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/services/challenge_service.py` (vues)
- Test: `backend/tests/test_api/test_challenges_api.py`

**Interfaces:**
- Produces (JSON) :
  - `GET /athletes/{id}` : `challenges: [{id, name, event_date, rank_overall, ranked_count, total_time, courses: [{id, name}]}]`
  - `GET /courses/{id}/summary` : `challenges: [{id, name, ranked_count}]`
  - `GET /challenges/{id}` : `{id, name, event_date, courses: [{id, name}], results: [{athlete_id, nom, prenom, rank_overall, total_time, status}]}` trié par rang (sans rang en fin) ; 404 si absent.
  - `challenge_service.for_athlete(db, athlete_id) -> list[dict]`, `challenge_service.for_course(db, course_id) -> list[dict]`, `challenge_service.detail(db, challenge_id) -> dict | None`.

- [ ] **Step 1: Write the failing API tests**

```python
"""Exposition des classements Challenge (#1008)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import challenge_repository

DAY = date(2026, 5, 13)


def _seed(db):
    xs = Course(name="E - XS", event_date=DAY, event_type="triathlon-xs")
    db.add(xs)
    first, second = Athlete(nom="DUPONT", prenom="Jean"), Athlete(nom="MARTIN", prenom="Paul")
    db.add_all([first, second])
    db.flush()
    challenge = challenge_repository.upsert(db, name="E - START CHALLENGE", event_date=DAY, source_url="u")
    challenge_repository.replace_links(db, challenge, [xs.id])
    for athlete, rank, bib in ((second, 2, "2"), (first, 1, "1")):
        challenge_repository.upsert_result(
            db, challenge, athlete_id=athlete.id, bib_number=bib, rank_overall=rank,
            rank_gender=None, rank_category=None, total_time=f"06:5{rank}:00", status="finisher", raw_data={},
        )
    db.commit()
    return xs, first, challenge


def test_athlete_detail_lists_challenges(client, db_session):
    xs, athlete, challenge = _seed(db_session)
    body = client.get(f"/api/v1/athletes/{athlete.id}").json()
    assert body["challenges"] == [{
        "id": challenge.id, "name": "E - START CHALLENGE", "event_date": "2026-05-13",
        "rank_overall": 1, "ranked_count": 2, "total_time": "06:51:00",
        "courses": [{"id": xs.id, "name": "E - XS"}],
    }]
    assert body["participations"] == []


def test_course_summary_lists_challenges(client, db_session):
    xs, _, challenge = _seed(db_session)
    body = client.get(f"/api/v1/courses/{xs.id}/summary").json()
    assert body["challenges"] == [{"id": challenge.id, "name": "E - START CHALLENGE", "ranked_count": 2}]


def test_challenge_detail_is_ranked(client, db_session):
    _, _, challenge = _seed(db_session)
    body = client.get(f"/api/v1/challenges/{challenge.id}").json()
    assert [r["nom"] for r in body["results"]] == ["DUPONT", "MARTIN"]
    assert body["courses"][0]["name"] == "E - XS"


def test_unknown_challenge_is_404(client):
    assert client.get("/api/v1/challenges/999").status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest -m "not integration" tests/test_api/test_challenges_api.py -v`
Expected: FAIL (clé `challenges` absente, 404 sur la route).

- [ ] **Step 3: Schemas**

`backend/app/schemas/challenge.py` :

```python
"""Schémas des classements Challenge (#1008). Tous additifs au contrat `/api/v1`."""
from datetime import date

from pydantic import BaseModel


class ChallengeCourseOut(BaseModel):
    id: int
    name: str


class AthleteChallengeOut(BaseModel):
    id: int
    name: str
    event_date: date
    rank_overall: int | None
    ranked_count: int
    total_time: str | None
    courses: list[ChallengeCourseOut]


class CourseChallengeOut(BaseModel):
    id: int
    name: str
    ranked_count: int


class ChallengeResultOut(BaseModel):
    athlete_id: int
    nom: str
    prenom: str
    rank_overall: int | None
    total_time: str | None
    status: str


class ChallengeDetail(BaseModel):
    id: int
    name: str
    event_date: date
    courses: list[ChallengeCourseOut]
    results: list[ChallengeResultOut]
```

`AthleteDetail` : `challenges: list[AthleteChallengeOut] = []`. `CourseSummary` : `challenges: list[CourseChallengeOut] = []`. Importer depuis `app.schemas.challenge`.

- [ ] **Step 4: Service views** (dans `challenge_service.py`)

```python
def _courses(challenge: Challenge) -> list[dict]:
    return sorted(
        ({"id": link.course.id, "name": link.course.name} for link in challenge.links),
        key=lambda c: c["name"],
    )


def for_athlete(db: Session, athlete_id: int) -> list[dict]:
    rows = challenge_repository.list_for_athlete(db, athlete_id)
    counts = challenge_repository.ranked_counts(db, [r.challenge_id for r in rows])
    return [
        {
            "id": r.challenge.id, "name": r.challenge.name, "event_date": r.challenge.event_date,
            "rank_overall": r.rank_overall, "ranked_count": counts.get(r.challenge_id, 0),
            "total_time": r.total_time, "courses": _courses(r.challenge),
        }
        for r in rows
    ]


def for_course(db: Session, course_id: int) -> list[dict]:
    challenges = challenge_repository.list_for_course(db, course_id)
    counts = challenge_repository.ranked_counts(db, [c.id for c in challenges])
    return [{"id": c.id, "name": c.name, "ranked_count": counts.get(c.id, 0)} for c in challenges]


def detail(db: Session, challenge_id: int) -> dict | None:
    challenge = challenge_repository.get(db, challenge_id)
    if challenge is None:
        return None
    results = sorted(
        challenge.results,
        key=lambda r: (r.rank_overall is None, r.rank_overall or 0, r.athlete.nom),
    )
    return {
        "id": challenge.id, "name": challenge.name, "event_date": challenge.event_date,
        "courses": _courses(challenge),
        "results": [
            {"athlete_id": r.athlete_id, "nom": r.athlete.nom, "prenom": r.athlete.prenom,
             "rank_overall": r.rank_overall, "total_time": r.total_time, "status": r.status}
            for r in results
        ],
    }
```

- [ ] **Step 5: Routes**

`athletes.py`, dans `get_athlete` : `return {"athlete": ..., "participations": items, "challenges": challenge_service.for_athlete(db, athlete_id)}`. Les filtres `seasons` et `federal_only` ne s'appliquent pas aux Challenges : le champ rend la carrière entière quelle que soit la requête (le dire en une ligne dans la docstring).

`courses.py`, dans `get_course_summary` : `summary = stats_service.course_summary(db, course_id)` puis `summary["challenges"] = challenge_service.for_course(db, course_id)` avant le `return` (adapter si `course_summary` rend un objet et non un dict).

`backend/app/api/v1/challenges.py` :

```python
"""Classements Challenge (#1008), lecture seule."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.schemas.challenge import ChallengeDetail
from app.services import challenge_service

router = APIRouter(tags=["challenges"])


@router.get("/challenges/{challenge_id}", response_model=ChallengeDetail)
def get_challenge(challenge_id: int, db: Session = Depends(get_db)):
    found = challenge_service.detail(db, challenge_id)
    if found is None:
        raise NotFoundError("Challenge introuvable")
    return found
```

`router.py` : ajouter `challenges` à l'import groupé et l'inclure comme `courses` (gardé par `require_site_access`, donc **pas** dans `_EXEMPTES_DE_LA_GARDE_SITE`). Si `tests/test_api/test_response_models.py` ou un test d'inventaire des routes liste les routes attendues, y ajouter `/challenges/{challenge_id}`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest -m "not integration" tests/test_api -v` puis `uv run ruff check .`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas backend/app/api/v1 backend/app/services/challenge_service.py backend/tests/test_api
git commit -m "feat(api): expose challenge rankings on athlete, course and challenge routes (#1008)"
```

---

### Task 8: Front (types, fiche athlète, page d'épreuve, page de classement)

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api/server.ts`
- Create: `frontend/components/challenges/AthleteChallenges.tsx` + `.test.tsx`
- Create: `frontend/components/challenges/CourseChallengesNote.tsx` + `.test.tsx`
- Create: `frontend/app/(public_restricted)/challenges/[id]/page.tsx` + `page.test.tsx`
- Modify: `frontend/app/(public_restricted)/athletes/[id]/page.tsx` (sous `EventsTable`)
- Modify: `frontend/app/(public_restricted)/courses/[id]/page.tsx` (après la grille de cartes, avant `RaceFinishers`)

**Interfaces:**
- Consumes: JSON de la Task 7.
- Produces: `AthleteChallenges({ challenges })`, `CourseChallengesNote({ challenges })`, `apiServer.getChallenge(id)`.

Lire d'abord `frontend/AGENTS.md` (patron des tableaux `.tcn-table`, liens soulignés, composants `components/tcn`) et un test de page existant (`app/(public_restricted)/courses/[id]/page.test.tsx`) pour le mock de `apiServer`.

- [ ] **Step 1: Types and client**

`lib/types.ts` :

```ts
/** Épreuve liée à un classement Challenge (#1008). */
export interface ChallengeCourse {
  id: number;
  name: string;
}

/** Ligne Challenge de la fiche athlète : `GET /athletes/{id}` → `challenges`. */
export interface AthleteChallenge {
  id: number;
  name: string;
  event_date: string;
  rank_overall: number | null;
  ranked_count: number;
  total_time: string | null;
  courses: ChallengeCourse[];
}

/** Challenge auquel compte une épreuve : `GET /courses/{id}/summary` → `challenges`. */
export interface CourseChallenge {
  id: number;
  name: string;
  ranked_count: number;
}

export interface ChallengeResult {
  athlete_id: number;
  nom: string;
  prenom: string;
  rank_overall: number | null;
  total_time: string | null;
  status: string;
}

/** `GET /challenges/{id}`. */
export interface ChallengeDetail {
  id: number;
  name: string;
  event_date: string;
  courses: ChallengeCourse[];
  results: ChallengeResult[];
}
```

Ajouter `challenges: AthleteChallenge[];` à `AthleteDetail` et `challenges: CourseChallenge[];` à `CourseSummary`. Corriger les fixtures de test qui construisent ces deux types (`npx tsc --noEmit` les liste) en y ajoutant `challenges: []`.

`lib/api/server.ts`, à côté de `getCourseSummary` :

```ts
  getChallenge: (id: number) => serverFetch<ChallengeDetail>(`/challenges/${id}`),
```

- [ ] **Step 2: Write the failing component tests**

`components/challenges/AthleteChallenges.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AthleteChallenges } from "./AthleteChallenges";

const CHALLENGE = {
  id: 7,
  name: "MEDOC 2026 - START CHALLENGE (XS - M - L)",
  event_date: "2026-05-13",
  rank_overall: 1,
  ranked_count: 52,
  total_time: "06:50:33",
  courses: [{ id: 284, name: "MEDOC 2026 - XS" }],
};

describe("AthleteChallenges", () => {
  it("ne rend rien sans challenge", () => {
    const { container } = render(<AthleteChallenges challenges={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("affiche le rang, l'effectif, le temps cumulé et les liens", () => {
    render(<AthleteChallenges challenges={[CHALLENGE]} />);
    expect(screen.getByRole("heading", { name: "Challenges" })).toBeInTheDocument();
    expect(screen.getByText(/1er \/ 52/)).toBeInTheDocument();
    expect(screen.getByText("06:50:33")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: CHALLENGE.name })).toHaveAttribute("href", "/challenges/7");
    expect(screen.getByRole("link", { name: "MEDOC 2026 - XS" })).toHaveAttribute("href", "/courses/284");
  });
});
```

`components/challenges/CourseChallengesNote.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CourseChallengesNote } from "./CourseChallengesNote";

describe("CourseChallengesNote", () => {
  it("ne rend rien sans challenge", () => {
    const { container } = render(<CourseChallengesNote challenges={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("nomme les challenges et leur effectif", () => {
    render(<CourseChallengesNote challenges={[{ id: 7, name: "START CHALLENGE", ranked_count: 52 }]} />);
    expect(screen.getByText(/Cette épreuve compte pour/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "START CHALLENGE" })).toHaveAttribute("href", "/challenges/7");
    expect(screen.getByText(/52 classés/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run to verify they fail**

Run: `npm test -- components/challenges`
Expected: FAIL (modules absents).

- [ ] **Step 4: Implement the components**

`components/challenges/AthleteChallenges.tsx` :

```tsx
import Link from "next/link";
import { Card } from "@/components/tcn";
import { formatDate } from "@/lib/utils/date";
import { ordinalFr } from "@/lib/utils/format";
import type { AthleteChallenge } from "@/lib/types";

/**
 * Classements Challenge de l'athlète (#1008) : un cumul sur plusieurs épreuves
 * du même jour. Hors de toute tuile et de tout graphique, qui ne lisent que les
 * participations.
 */
export function AthleteChallenges({ challenges }: { challenges: AthleteChallenge[] }) {
  if (challenges.length === 0) return null;
  return (
    <Card>
      <h2 id="titre-challenges" style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, fontWeight: 400, margin: 0, marginBottom: 14 }}>
        Challenges
      </h2>
      <ul aria-labelledby="titre-challenges" className="space-y-3">
        {challenges.map((challenge) => (
          <li key={challenge.id}>
            <Link href={`/challenges/${challenge.id}`} className="underline underline-offset-2">
              {challenge.name}
            </Link>
            <span> ({formatDate(challenge.event_date)})</span>
            <div>
              {challenge.rank_overall !== null && (
                <span>{ordinalFr(challenge.rank_overall)} / {challenge.ranked_count}, </span>
              )}
              {challenge.total_time && <span>{challenge.total_time}</span>}
            </div>
            {challenge.courses.length > 0 && (
              <div>
                Épreuves :{" "}
                {challenge.courses.map((course, index) => (
                  <span key={course.id}>
                    {index > 0 && ", "}
                    <Link href={`/courses/${course.id}`} className="underline underline-offset-2">
                      {course.name}
                    </Link>
                  </span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
```

Vérifier le rendu exact de `ordinalFr(1)` (`grep -n "export function ordinalFr" -A 6 lib/utils/format.ts`) : si elle rend « 1er » le test passe ; sinon aligner le test sur sa sortie réelle. Aligner les styles de titre sur ceux des autres `Card` de la page (même `h2` que le bloc « Top clubs » de la page d'épreuve) plutôt que d'en inventer.

`components/challenges/CourseChallengesNote.tsx` :

```tsx
import Link from "next/link";
import { Card } from "@/components/tcn";
import type { CourseChallenge } from "@/lib/types";

/** Les classements Challenge auxquels compte l'épreuve (#1008). */
export function CourseChallengesNote({ challenges }: { challenges: CourseChallenge[] }) {
  if (challenges.length === 0) return null;
  return (
    <Card>
      <p style={{ margin: 0 }}>
        Cette épreuve compte pour :{" "}
        {challenges.map((challenge, index) => (
          <span key={challenge.id}>
            {index > 0 && ", "}
            <Link href={`/challenges/${challenge.id}`} className="underline underline-offset-2">
              {challenge.name}
            </Link>{" "}
            ({challenge.ranked_count} classés)
          </span>
        ))}
      </p>
    </Card>
  );
}
```

- [ ] **Step 5: Run component tests**

Run: `npm test -- components/challenges`
Expected: PASS.

- [ ] **Step 6: Wire the pages and write the challenge page**

Fiche athlète : `const { athlete, participations, challenges } = ...` (selon la destructuration en place) et, juste après `<EventsTable ... />`, `<AthleteChallenges challenges={challenges} />`.

Page d'épreuve : juste avant `<RaceFinishers`, `<CourseChallengesNote challenges={summary.challenges} />`.

`app/(public_restricted)/challenges/[id]/page.tsx`, sur le patron de la page d'épreuve (`idDeRoute`, `rendreNullSi404`, `notFound`, `PageShell`, `PageHeader`) :

```tsx
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { rendreNullSi404 } from "@/lib/api/null-si-404";
import { idDeRoute } from "@/lib/utils/id-de-route";
import { formatDate } from "@/lib/utils/date";
import { Card } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";

export const metadata: Metadata = { title: "Classement Challenge" };

export default async function ChallengePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const challenge = await apiServer.getChallenge(idDeRoute(id)).catch(rendreNullSi404);
  if (!challenge) notFound();

  return (
    <PageShell>
      <PageHeader title={challenge.name} />
      <div className="space-y-6">
        <Card>
          <p style={{ margin: 0 }}>
            {formatDate(challenge.event_date)}. Cumul des épreuves :{" "}
            {challenge.courses.map((course, index) => (
              <span key={course.id}>
                {index > 0 && ", "}
                <Link href={`/courses/${course.id}`} className="underline underline-offset-2">{course.name}</Link>
              </span>
            ))}
          </p>
        </Card>
        <Card>
          <table className="w-full" aria-label="Classement du challenge">
            <thead>
              <tr>
                <th scope="col" className="text-left">Rang</th>
                <th scope="col" className="text-left">Athlète</th>
                <th scope="col" className="text-right">Temps cumulé</th>
              </tr>
            </thead>
            <tbody>
              {challenge.results.map((row) => (
                <tr key={row.athlete_id}>
                  <td>{row.rank_overall ?? row.status}</td>
                  <td>
                    <Link href={`/athletes/${row.athlete_id}`} className="underline underline-offset-2">
                      {row.prenom} {row.nom}
                    </Link>
                  </td>
                  <td className="text-right">{row.total_time ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </PageShell>
  );
}
```

Adapter les props de `PageHeader` et `PageShell` à leur signature réelle (les lire), et la métadonnée au patron `generateMetadata` des autres pages si elles en ont un.

`app/(public_restricted)/challenges/[id]/page.test.tsx`, sur le patron du test de la page d'épreuve (même mock de `@/lib/api/server`) : rend le titre, une ligne par résultat dans l'ordre reçu, un lien `/athletes/{id}`, et appelle `notFound` quand `getChallenge` rejette un 404.

- [ ] **Step 7: Run all front checks**

Run: `npm test`, `npm run lint`, `npm run build`
Expected: tout vert.

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "feat(front): show challenge rankings on athlete, course and challenge pages (#1008)"
```

---

### Task 9: Documentation et fusion d'athlètes

**Files:**
- Modify: `backend/app/models/AGENTS.md` (section courte « Challenge » : tables, exclusion par construction, jamais créateur d'athlète)
- Modify: `docs/modele-donnees.md` (les trois tables, la ligne d'historique de migration)
- Modify: `backend/app/scrapers/AGENTS.md` (mention de `heat_is_challenge` à côté de `heat_is_relay`)
- Modify (conditionnel): `backend/app/services/athlete_merge.py`

- [ ] **Step 1: Docs**

Rédiger les trois ajouts en français, sans tiret de ponctuation, en renvoyant vers la spec `docs/superpowers/specs/2026-10-02-challenge-rankings-design.md`.

- [ ] **Step 2: Athlete merge (#1176)**

`git fetch origin && git log origin/main --oneline -- backend/app/services/athlete_merge.py`.
- Si le fichier existe sur `origin/main` : rebaser la branche (`git rebase origin/main`), écrire d'abord un test dans le fichier de test de la fusion (`grep -rln "athlete_merge" backend/tests`) qui crée une ligne Challenge sur la fiche absorbée et vérifie qu'après fusion elle pointe vers la fiche conservée, le voir échouer, puis ajouter dans la fonction de fusion la réattribution `for row in challenge_repository.list_for_athlete_ids(db, absorbed_id): row.athlete_id = kept_id` (noms des variables à aligner sur le code), avant la suppression de la fiche absorbée.
- Sinon : ne rien coder ; consigner dans la description de PR qu'il faudra ajouter cette réattribution à #1176, et poster un commentaire sur #1176 : `gh pr comment 1176 --body "La fusion d'athlètes doit aussi réattribuer les lignes \`challenge_results\` (#1008, FK RESTRICT) : \`challenge_repository.list_for_athlete_ids(db, absorbed_id)\` puis \`row.athlete_id = kept_id\`, avant la suppression de la fiche absorbée."` (à faire seulement si l'utilisateur a validé la publication de la PR #1008).

- [ ] **Step 3: Full verification**

Backend : `uv run pytest -m "not integration"`, `uv run ruff check .`, `uv run alembic upgrade head && uv run alembic check`. Front : `npm test`, `npm run lint`, `npm run build`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/AGENTS.md docs/modele-donnees.md backend/app/scrapers/AGENTS.md backend/app/services backend/tests
git commit -m "docs(challenges): document challenge rankings model and detection (#1008)"
```
