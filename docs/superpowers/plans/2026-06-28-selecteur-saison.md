# Sélecteur de saison sur le tableau de bord — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre, sur le tableau de bord, d'arriver par défaut sur la saison en cours et de sélectionner une ou plusieurs autres saisons (uniquement celles ayant des résultats), avec recalcul de toutes les cartes/agrégats.

**Architecture :** Filtrage par « saison » (1ᵉʳ sept → 31 août) dérivé de `Course.event_date`, sans migration. Backend : helpers purs `core/season.py`, filtre `seasons` (OU de plages de dates) propagé `api → service → repository`, nouvel endpoint `/stats/seasons`. Frontend : helpers miroir `lib/utils/season.ts`, état dans l'URL (`?seasons=2025,2023`), composant client `SeasonSelector`, page dashboard (Server Component) qui lit l'URL et propage `seasons` aux trois appels existants.

**Tech Stack :** Backend FastAPI 0.115 + SQLAlchemy 2.0 (sync) + Pydantic v2, tests pytest, lint ruff. Frontend Next.js 16 (App Router) + TypeScript strict + composants `components/tcn` + `components/ui` (Popover base-ui), tests Vitest + RTL.

## Global Constraints

- **Définition de saison :** saison d'année de début `Y` couvre `[Y-09-01, (Y+1)-08-31]`, libellé `"Saison Y — Y+1"`. Bascule : `season_of(d)` = `d.year` si `d.month >= 9`, sinon `d.year - 1`.
- **Défaut :** aucun paramètre `seasons` → **saison en cours uniquement** (calculée côté serveur).
- **Identifiant de saison :** entier = année de début. Filtre `seasons` = CSV d'années de début dans l'URL et les query params (ex. `2025,2023`).
- **Sélection multiple non contiguë :** plusieurs saisons → **OU** de plages de dates (jamais une plage unique englobante).
- **Épreuves sans date** (`Course.event_date IS NULL`) : exclues de toute vue filtrée par saison et d'aucun décompte de saison (naturellement, par les comparaisons `>=`/`<=`).
- **Options du sélecteur :** saisons ayant ≥ 1 participation sur une épreuve datée, **plus** la saison en cours toujours présente (même à 0), triées par année de début **décroissante**.
- **Aucune migration Alembic.**
- **Langue :** UI, commentaires et messages en **français** (avec accents).
- **Tests unitaires sans réseau.** Commits en Conventional Commits.
- **Horloge centralisée :** côté backend, ne jamais appeler `date.today()` directement ; passer par `app.core.time.utcnow()` (seule fonction existante de `app/core/time.py`) pour rester figeable en test.
- **Réponses API inchangées** pour `/stats`, `/courses/events`, `/participations` (seul le sous-ensemble filtré change). Seul ajout : `GET /stats/seasons`.

---

## File Structure

**Backend (`backend/`)**
- `app/core/season.py` *(nouveau)* — helpers purs de saison (aucune dépendance DB).
- `app/repositories/participation_repository.py` *(modifié)* — clause `seasons` dans `_apply_filters`, propagation, `for_stats`, nouveau `distinct_seasons`.
- `app/services/stats_service.py` *(modifié)* — `get_stats(..., seasons)`, nouveau `list_seasons`.
- `app/schemas/season.py` *(nouveau)* — `SeasonOut`.
- `app/api/v1/stats.py` *(modifié)* — `seasons` sur `/stats`, nouveau `/stats/seasons`.
- `app/api/v1/courses.py` *(modifié)* — `seasons` sur `/courses/events`.
- `app/api/v1/participations.py` *(modifié)* — `seasons` sur `/participations`.
- Tests : `tests/test_core/test_season.py` *(nouveau)*, `tests/test_repositories/test_participation_repository.py` *(modifié)*, `tests/test_services/test_stats_service.py` *(modifié)*, `tests/test_api/test_other_api.py` *(modifié)*.

**Frontend (`frontend/`)**
- `lib/utils/season.ts` *(nouveau)* — helpers miroir.
- `lib/utils/season.test.ts` *(nouveau)*.
- `lib/types.ts` *(modifié)* — type `Season`, `seasons?: number[]` dans `ParticipationFilters`.
- `lib/api/client.ts` + `lib/api/server.ts` *(modifiés)* — `toQuery` (CSV des tableaux), `listSeasons`.
- `components/dashboard/SeasonSelector.tsx` *(nouveau, client)* + `SeasonSelector.test.tsx` *(nouveau)*.
- `app/dashboard/page.tsx` *(modifié)* — lecture URL, `listSeasons`, propagation, titre dynamique, insertion du sélecteur.

---

## Task 1 : Helpers de saison backend — `app/core/season.py`

**Files:**
- Create: `backend/app/core/season.py`
- Create: `backend/tests/test_core/__init__.py`
- Test: `backend/tests/test_core/test_season.py`

**Interfaces:**
- Consumes : `app.core.time.utcnow`.
- Produces :
  - `season_of(d: date) -> int`
  - `season_bounds(start_year: int) -> tuple[date, date]`
  - `current_season() -> int`
  - `season_label(start_year: int) -> str`
  - `parse_seasons(raw: str | None) -> list[int]`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_core/__init__.py` (fichier vide) puis `backend/tests/test_core/test_season.py` :

```python
from datetime import date

import pytest

from app.core import season


def test_season_of_borne_31_aout_appartient_saison_precedente():
    assert season.season_of(date(2026, 8, 31)) == 2025


def test_season_of_borne_1er_septembre_ouvre_nouvelle_saison():
    assert season.season_of(date(2026, 9, 1)) == 2026


def test_season_of_janvier_appartient_saison_de_l_annee_precedente():
    assert season.season_of(date(2026, 1, 15)) == 2025


def test_season_bounds():
    assert season.season_bounds(2025) == (date(2025, 9, 1), date(2026, 8, 31))


def test_season_label():
    assert season.season_label(2025) == "Saison 2025 — 2026"


def test_current_season_utilise_horloge_figee(monkeypatch):
    from datetime import datetime

    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 6, 27, 10, 0, 0))
    assert season.current_season() == 2025


def test_parse_seasons_nominal():
    assert season.parse_seasons("2025,2023") == [2025, 2023]


def test_parse_seasons_tolere_espaces_dedoublonne_ignore_non_entiers():
    assert season.parse_seasons(" 2025 , 2025, abc, 2023 ") == [2025, 2023]


@pytest.mark.parametrize("raw", [None, "", "   ", ","])
def test_parse_seasons_vide(raw):
    assert season.parse_seasons(raw) == []
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `cd backend && pytest tests/test_core/test_season.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'app.core.season').

- [ ] **Step 3 : Écrire l'implémentation**

Créer `backend/app/core/season.py` :

```python
"""Helpers de saison sportive : du 1ᵉʳ septembre Y au 31 août Y+1.

Module pur (aucune dépendance DB). L'identifiant d'une saison est son année de
début Y. La saison Y couvre [Y-09-01, (Y+1)-08-31] et s'affiche « Saison Y — Y+1 ».
"""
from datetime import date

from app.core.time import utcnow


def season_of(d: date) -> int:
    """Année de début de la saison contenant `d` (bascule au 1ᵉʳ septembre)."""
    return d.year if d.month >= 9 else d.year - 1


def season_bounds(start_year: int) -> tuple[date, date]:
    """Bornes incluses (date_from, date_to) de la saison d'année de début `start_year`."""
    return date(start_year, 9, 1), date(start_year + 1, 8, 31)


def current_season() -> int:
    """Saison en cours, calculée depuis l'horloge centralisée (figeable en test)."""
    return season_of(utcnow().date())


def season_label(start_year: int) -> str:
    """Libellé d'affichage « Saison Y — Y+1 »."""
    return f"Saison {start_year} — {start_year + 1}"


def parse_seasons(raw: str | None) -> list[int]:
    """Parse un CSV d'années de début (« 2025,2023 ») → liste d'entiers.

    Tolère les espaces, ignore les valeurs non entières, dédoublonne en
    conservant l'ordre d'apparition.
    """
    if not raw:
        return []
    out: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            year = int(token)
        except ValueError:
            continue
        if year not in out:
            out.append(year)
    return out
```

- [ ] **Step 4 : Lancer les tests pour vérifier le succès**

Run: `cd backend && pytest tests/test_core/test_season.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5 : Lint**

Run: `cd backend && ruff check app/core/season.py tests/test_core/test_season.py`
Expected: `All checks passed!`

- [ ] **Step 6 : Commit**

```bash
git add backend/app/core/season.py backend/tests/test_core/
git commit -m "feat(backend): helpers purs de saison (core/season.py)"
```

---

## Task 2 : Filtrage par saisons dans le repository

**Files:**
- Modify: `backend/app/repositories/participation_repository.py`
- Test: `backend/tests/test_repositories/test_participation_repository.py`

**Interfaces:**
- Consumes : `app.core.season.season_bounds`.
- Produces (signatures étendues, `seasons: list[int] | None = None` ajouté) :
  - `_apply_filters(q, db, *, name, event_type, event_name, club, date_from, date_to, course_id=None, seasons=None)`
  - `list_participations(..., seasons: list[int] | None = None)`
  - `events_with_counts(..., seasons: list[int] | None = None)`
  - `events_page(..., seasons: list[int] | None = None)`
  - `for_stats(db, club=None, seasons: list[int] | None = None)`
  - `_season_clause(seasons: list[int]) -> ColumnElement` *(privé)*

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_repositories/test_participation_repository.py` :

```python
def test_for_stats_filtre_par_saison_unique(db_session):
    athlete, _ = _setup(db_session)  # course "Tri Z" le 2026-05-16 → saison 2025
    c_autre = course_repository.get_or_create(
        db_session, name="Tri Automne", event_date=date(2024, 10, 1), event_type="triathlon-s"
    )  # saison 2024
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=_setup(db_session)[1].id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_autre.id, bib_number="2", club="TCN"
    )
    db_session.flush()

    only_2025 = participation_repository.for_stats(db_session, seasons=[2025])
    assert {p.course.name for p in only_2025} == {"Tri Z"}


def test_for_stats_multi_saisons_non_contigues(db_session):
    athlete, course_2025 = _setup(db_session)  # "Tri Z" 2026-05-16 → saison 2025
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )  # saison 2023
    c_2024 = course_repository.get_or_create(
        db_session, name="Tri 2024", event_date=date(2024, 10, 1), event_type="triathlon-s"
    )  # saison 2024
    for i, c in enumerate((course_2025, c_2023, c_2024)):
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=c.id, bib_number=str(i), club="TCN"
        )
    db_session.flush()

    rows = participation_repository.for_stats(db_session, seasons=[2025, 2023])
    assert {p.course.name for p in rows} == {"Tri Z", "Tri 2023"}


def test_events_page_filtre_par_saison_exclut_sans_date(db_session):
    athlete, course_2025 = _setup(db_session)  # "Tri Z" → saison 2025
    c_sans_date = course_repository.get_or_create(
        db_session, name="Sans Date", event_date=None, event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course_2025.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_sans_date.id, bib_number="2", club="TCN"
    )
    db_session.flush()

    page = participation_repository.events_page(db_session, seasons=[2025])
    assert page["total_events"] == 1
    assert page["items"][0].event_name == "Tri Z"


def test_distinct_seasons_compte_et_force_aucune_saison_courante(db_session):
    athlete, course_2025 = _setup(db_session)  # saison 2025
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )
    c_sans_date = course_repository.get_or_create(
        db_session, name="Sans Date", event_date=None, event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course_2025.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_2023.id, bib_number="2", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_sans_date.id, bib_number="3", club="TCN"
    )
    db_session.flush()

    rows = participation_repository.distinct_seasons(db_session)
    by_year = {r["start_year"]: r for r in rows}
    assert set(by_year) == {2025, 2023}  # épreuve sans date exclue
    assert by_year[2025]["event_count"] == 1
    assert by_year[2025]["participation_count"] == 1
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `cd backend && pytest tests/test_repositories/test_participation_repository.py -v`
Expected: FAIL (`TypeError: ... unexpected keyword argument 'seasons'` puis `AttributeError: ... 'distinct_seasons'`).

- [ ] **Step 3 : Écrire l'implémentation**

Dans `backend/app/repositories/participation_repository.py` :

a) Ajouter l'import de `and_` et du helper de saison (haut du fichier) :

```python
from sqlalchemy import and_, case, func, or_
```

```python
from app.core.season import season_bounds
```

b) Ajouter le helper privé juste avant `_apply_filters` :

```python
def _season_clause(seasons: list[int]):
    """OU de plages de dates pour les saisons demandées (event_date NULL exclu)."""
    bounds = [season_bounds(y) for y in seasons]
    return or_(
        *[and_(Course.event_date >= start, Course.event_date <= end) for start, end in bounds]
    )
```

c) Étendre `_apply_filters` — ajouter le paramètre et la clause (après le bloc `date_to`) :

```python
def _apply_filters(
    q,
    db,
    *,
    name,
    event_type,
    event_name,
    club,
    date_from,
    date_to,
    course_id=None,
    seasons=None,
):
    """Joint Athlete + Course et applique les filtres communs (liste + épreuves)."""
    q = q.join(Athlete, Participation.athlete_id == Athlete.id).join(
        Course, Participation.course_id == Course.id
    )
    if course_id is not None:
        q = q.filter(Participation.course_id == course_id)
    if name:
        pattern = f"%{name}%"
        q = q.filter(or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern)))
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if event_name:
        q = q.filter(_course_name_filter(db, event_name))
    if date_from:
        q = q.filter(Course.event_date >= date_from)
    if date_to:
        q = q.filter(Course.event_date <= date_to)
    if seasons:
        q = q.filter(_season_clause(seasons))
    return q
```

d) Propager `seasons` dans `list_participations` — ajouter le paramètre et le passer à `_apply_filters` :

```python
def list_participations(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    course_id: int | None = None,
    seasons: list[int] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Participation]:
    q = db.query(Participation).options(
        joinedload(Participation.athlete), joinedload(Participation.course)
    )
    q = _apply_filters(
        q,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
        course_id=course_id,
        seasons=seasons,
    )
    offset = (page - 1) * page_size
    order = (
        (Participation.rank_overall.is_(None), Participation.rank_overall)
        if course_id
        else (Participation.created_at.desc(),)
    )
    return q.order_by(*order).offset(offset).limit(page_size).all()
```

e) Étendre `for_stats` — ajouter `seasons` ; quand fourni, joindre `Course` et appliquer la clause :

```python
def for_stats(
    db: Session, club: str | None = None, seasons: list[int] | None = None
) -> list[Participation]:
    """Charge les participations (avec course + athlète) pour les agrégations stats."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    )
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
    if seasons:
        q = q.join(Course, Participation.course_id == Course.id).filter(_season_clause(seasons))
    return q.all()
```

f) Propager `seasons` dans `_grouped_events_query`, `events_with_counts`, `events_page` — ajouter `seasons=None` à chaque signature et le passer à `_apply_filters` / à l'appel imbriqué. Dans `_grouped_events_query` :

```python
def _grouped_events_query(
    db: Session,
    *,
    name=None,
    event_type=None,
    event_name=None,
    club=None,
    date_from=None,
    date_to=None,
    seasons=None,
):
    """Requête de base : une ligne par épreuve (course) avec compteurs total + TCN."""
    q = db.query(
        Course.id.label("course_id"),
        Course.name.label("event_name"),
        Course.event_date.label("event_date"),
        Course.event_type.label("event_type"),
        Course.is_relay.label("is_relay"),
        Course.distance_km.label("distance_km"),
        func.count(Participation.id).label("total"),
        func.sum(case((tcn_filter(), 1), else_=0)).label("tcn_count"),
    )
    q = _apply_filters(
        q,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
    )
    return q.group_by(
        Course.id,
        Course.name,
        Course.event_date,
        Course.event_type,
        Course.is_relay,
        Course.distance_km,
    )
```

Dans `events_with_counts` : ajouter `seasons: list[int] | None = None` à la signature et `seasons=seasons,` dans l'appel à `_grouped_events_query`.

Dans `events_page` : ajouter `seasons: list[int] | None = None` à la signature, et `seasons=seasons,` dans **les deux** appels (`_grouped_events_query` et le `_apply_filters` du décompte `parts`).

g) Ajouter `distinct_seasons` (par exemple après `events_page`) :

```python
def distinct_seasons(db: Session, club: str | None = None) -> list[dict]:
    """Saisons présentes (≥ 1 participation sur une épreuve datée), repliées en Python.

    Repli Python plutôt que SQL pour rester portable SQLite/Postgres sans
    fonctions de date spécifiques. Volume de données modeste.
    """
    q = (
        db.query(
            Course.event_date.label("event_date"),
            func.count(Participation.id).label("part_count"),
        )
        .join(Participation, Participation.course_id == Course.id)
        .filter(Course.event_date.isnot(None))
    )
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
    rows = q.group_by(Course.id, Course.event_date).all()

    agg: dict[int, dict] = {}
    for event_date, part_count in rows:
        year = season_of(event_date)
        entry = agg.setdefault(
            year, {"start_year": year, "event_count": 0, "participation_count": 0}
        )
        entry["event_count"] += 1
        entry["participation_count"] += int(part_count or 0)
    return list(agg.values())
```

Et compléter l'import de saison (en-tête du fichier) :

```python
from app.core.season import season_bounds, season_of
```

- [ ] **Step 4 : Lancer les tests pour vérifier le succès**

Run: `cd backend && pytest tests/test_repositories/test_participation_repository.py -v`
Expected: PASS (tous, dont les 4 nouveaux).

- [ ] **Step 5 : Non-régression du repository**

Run: `cd backend && pytest tests/test_repositories -q`
Expected: PASS.

- [ ] **Step 6 : Lint**

Run: `cd backend && ruff check app/repositories/participation_repository.py`
Expected: `All checks passed!`

- [ ] **Step 7 : Commit**

```bash
git add backend/app/repositories/participation_repository.py backend/tests/test_repositories/test_participation_repository.py
git commit -m "feat(backend): filtre seasons (OU de plages) + distinct_seasons dans le repo"
```

---

## Task 3 : Service stats — `seasons` + `list_seasons`

**Files:**
- Modify: `backend/app/services/stats_service.py`
- Test: `backend/tests/test_services/test_stats_service.py`

**Interfaces:**
- Consumes : `participation_repository.for_stats(..., seasons)`, `participation_repository.distinct_seasons`, `app.core.season.current_season`, `season_label`.
- Produces :
  - `get_stats(db, club=None, seasons: list[int] | None = None) -> dict`
  - `list_seasons(db, club=None) -> list[dict]` — chaque entrée : `{start_year, event_count, participation_count, label, is_current}`, triée par `start_year` décroissant, saison en cours forcée (à 0 si absente).

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_services/test_stats_service.py` (l'import `date` y est déjà) :

```python
def test_get_stats_filtre_par_saison(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    c_2025 = course_repository.get_or_create(
        db_session, name="Tri 2025", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )  # saison 2025
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )  # saison 2023
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2025.id, bib_number="1", club="TCN")
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2023.id, bib_number="2", club="TCN")
    db_session.flush()

    stats = stats_service.get_stats(db_session, seasons=[2025])
    assert stats["total"] == 1
    assert stats["by_type"] == {"triathlon-m": 1}


def test_list_seasons_force_saison_courante_et_tri_decroissant(db_session, monkeypatch):
    from app.core import season as season_module

    # Saison en cours figée à 2025, sans aucun résultat 2025.
    monkeypatch.setattr(season_module, "current_season", lambda: 2025)

    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    c_2023 = course_repository.get_or_create(
        db_session, name="Tri 2023", event_date=date(2023, 10, 1), event_type="triathlon-s"
    )
    c_2022 = course_repository.get_or_create(
        db_session, name="Tri 2022", event_date=date(2022, 10, 1), event_type="triathlon-s"
    )
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2023.id, bib_number="1", club="TCN")
    participation_repository.create(db_session, athlete_id=a1.id, course_id=c_2022.id, bib_number="2", club="TCN")
    db_session.flush()

    seasons = stats_service.list_seasons(db_session)
    years = [s["start_year"] for s in seasons]
    assert years == [2025, 2023, 2022]  # courante forcée en tête, puis décroissant
    current = next(s for s in seasons if s["start_year"] == 2025)
    assert current["is_current"] is True
    assert current["event_count"] == 0
    assert current["label"] == "Saison 2025 — 2026"
    assert seasons[1]["is_current"] is False
```

S'assurer que `participation_repository` est importé dans ce fichier de test (il l'est déjà : `from app.repositories import athlete_repository, course_repository, participation_repository`).

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `cd backend && pytest tests/test_services/test_stats_service.py -v`
Expected: FAIL (`TypeError: get_stats() got an unexpected keyword argument 'seasons'` puis `AttributeError: ... 'list_seasons'`).

- [ ] **Step 3 : Écrire l'implémentation**

Dans `backend/app/services/stats_service.py` :

a) Ajouter l'import en tête :

```python
from app.core import season as season_module
```

b) Étendre `get_stats` — signature + passage de `seasons` :

```python
def get_stats(db: Session, club: str | None = None, seasons: list[int] | None = None) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(db, club, seasons=seasons)
```

(Le reste du corps de `get_stats` est inchangé.)

c) Ajouter `list_seasons` (par exemple après `get_stats`) :

```python
def list_seasons(db: Session, club: str | None = None) -> list[dict]:
    """Saisons disponibles pour le sélecteur.

    Saisons ayant ≥ 1 résultat daté + saison en cours toujours présente (à 0 si
    absente), enrichies de `label`/`is_current`, triées par année décroissante.
    """
    rows = participation_repository.distinct_seasons(db, club)
    by_year = {r["start_year"]: r for r in rows}

    current = season_module.current_season()
    by_year.setdefault(
        current, {"start_year": current, "event_count": 0, "participation_count": 0}
    )

    out = []
    for year in sorted(by_year, reverse=True):
        entry = by_year[year]
        out.append(
            {
                "start_year": year,
                "event_count": entry["event_count"],
                "participation_count": entry["participation_count"],
                "label": season_module.season_label(year),
                "is_current": year == current,
            }
        )
    return out
```

- [ ] **Step 4 : Lancer les tests pour vérifier le succès**

Run: `cd backend && pytest tests/test_services/test_stats_service.py -v`
Expected: PASS (tous, dont les 2 nouveaux).

- [ ] **Step 5 : Lint**

Run: `cd backend && ruff check app/services/stats_service.py`
Expected: `All checks passed!`

- [ ] **Step 6 : Commit**

```bash
git add backend/app/services/stats_service.py backend/tests/test_services/test_stats_service.py
git commit -m "feat(backend): stats_service get_stats(seasons) + list_seasons"
```

---

## Task 4 : Schéma `SeasonOut` + endpoints API

**Files:**
- Create: `backend/app/schemas/season.py`
- Modify: `backend/app/api/v1/stats.py`
- Modify: `backend/app/api/v1/courses.py`
- Modify: `backend/app/api/v1/participations.py`
- Test: `backend/tests/test_api/test_other_api.py`

**Interfaces:**
- Consumes : `app.core.season.parse_seasons`, `stats_service.get_stats(..., seasons)`, `stats_service.list_seasons`, `stats_service.list_events(..., seasons)`, `participation_repository.list_participations(..., seasons)`.
- Produces :
  - `SeasonOut(BaseModel)` : `start_year: int`, `label: str`, `event_count: int`, `participation_count: int`, `is_current: bool`.
  - `GET /stats?seasons=<csv>` ; `GET /stats/seasons?club=` → `list[SeasonOut]` ; `GET /courses/events?seasons=<csv>` ; `GET /participations?seasons=<csv>`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_api/test_other_api.py` (helper `_payload` déjà présent) :

```python
def test_stats_seasons_endpoint_et_filtre(client):
    # Saison 2025 (2026-05-16) et saison 2023 (2023-10-01).
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", nom="MARTIN", club="TCN"), "event_name": "Tri 2023", "event_date": "2023-10-01"},
    )

    seasons = client.get("/api/v1/stats/seasons").json()
    years = [s["start_year"] for s in seasons]
    assert 2025 in years and 2023 in years
    assert years == sorted(years, reverse=True)
    s2025 = next(s for s in seasons if s["start_year"] == 2025)
    assert s2025["label"] == "Saison 2025 — 2026"
    assert "is_current" in s2025

    # Filtre /stats par saison.
    stats_2025 = client.get("/api/v1/stats", params={"seasons": "2025"}).json()
    assert stats_2025["total"] == 1
    stats_multi = client.get("/api/v1/stats", params={"seasons": "2025,2023"}).json()
    assert stats_multi["total"] == 2


def test_courses_events_filtre_par_saison(client):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))  # saison 2025
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", club="TCN"), "event_name": "Tri 2023", "event_date": "2023-10-01"},
    )
    page = client.get("/api/v1/courses/events", params={"seasons": "2025"}).json()
    assert page["total_events"] == 1
    assert page["items"][0]["event_name"] == "Triathlon de Nantes"


def test_participations_filtre_par_saison(client):
    client.post("/api/v1/participations", json=_payload(bib="1", club="TCN"))  # saison 2025
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", club="TCN"), "event_name": "Tri 2023", "event_date": "2023-10-01"},
    )
    rows = client.get("/api/v1/participations", params={"seasons": "2023"}).json()
    assert len(rows) == 1
    assert rows[0]["course"]["event_date"] == "2023-10-01"
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `cd backend && pytest tests/test_api/test_other_api.py -v`
Expected: FAIL (404 sur `/stats/seasons` ; le filtre `seasons` ignoré → `total == 2` au lieu de 1).

- [ ] **Step 3 : Créer le schéma**

Créer `backend/app/schemas/season.py` :

```python
"""Schéma Pydantic d'une saison sportive (sélecteur du tableau de bord)."""
from pydantic import BaseModel


class SeasonOut(BaseModel):
    """Saison disponible : année de début, libellé et compteurs."""

    start_year: int
    label: str
    event_count: int
    participation_count: int
    is_current: bool
```

- [ ] **Step 4 : Étendre `stats.py`**

Remplacer le contenu de `backend/app/api/v1/stats.py` par :

```python
"""Router Stats : agrégations club, saisons disponibles et géolocalisation."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.season import parse_seasons
from app.repositories import participation_repository
from app.schemas.season import SeasonOut
from app.services import geocode_service, stats_service

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(
    club: str | None = Query(None),
    seasons: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return stats_service.get_stats(db, club, seasons=parse_seasons(seasons))


@router.get("/stats/seasons", response_model=list[SeasonOut])
def list_seasons(club: str | None = Query(None), db: Session = Depends(get_db)):
    """Saisons disponibles pour le sélecteur (avec saison en cours forcée)."""
    return stats_service.list_seasons(db, club)


@router.get("/stats/events-geo")
def get_events_geo(club: str | None = Query(None), db: Session = Depends(get_db)):
    """Épreuves géocodées (lat/lon) pour la carte. Géocodage caché en mémoire."""
    rows = participation_repository.events_with_counts(db, club=club)
    geo_events = []
    for r in rows:
        if not r.event_name:
            continue
        coord = geocode_service.geocode(r.event_name)
        if coord:
            geo_events.append({
                "event_name": r.event_name,
                "event_date": r.event_date.isoformat() if r.event_date else None,
                "event_type": r.event_type or "",
                "count": r.total,
                "tcn_count": int(r.tcn_count or 0),
                "lat": coord[0],
                "lon": coord[1],
            })
    return geo_events
```

> Note : `/stats/seasons` est déclaré **avant** `/stats/events-geo` ; l'ordre relatif aux autres routes n'a pas d'incidence (chemins littéraux distincts, aucune collision de pattern).

- [ ] **Step 5 : Étendre `courses.py`**

Dans `backend/app/api/v1/courses.py`, ajouter l'import :

```python
from app.core.season import parse_seasons
```

Puis, dans `list_events`, ajouter le query param et le propager :

```python
@router.get("/courses/events", response_model=EventPage)
def list_events(
    name: str | None = Query(None),
    event_type: str | None = Query(None),
    event_name: str | None = Query(None),
    club: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    seasons: str | None = Query(None),
    sort: str = Query("date_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Page d'épreuves distinctes (scroll infini) avec compteurs participants + TCN."""
    return stats_service.list_events(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        seasons=parse_seasons(seasons),
        sort=sort,
        page=page,
        page_size=page_size,
    )
```

(`stats_service.list_events` passe `**filters` à `events_page`, qui accepte désormais `seasons` — aucune autre modif nécessaire.)

- [ ] **Step 6 : Étendre `participations.py`**

Dans `backend/app/api/v1/participations.py`, ajouter l'import :

```python
from app.core.season import parse_seasons
```

Puis, dans `list_participations`, ajouter le query param et le propager :

```python
@router.get("/participations", response_model=list[ParticipationOut])
def list_participations(
    name: str | None = Query(None),
    event_type: str | None = Query(None),
    event_name: str | None = Query(None),
    club: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    seasons: str | None = Query(None),
    course_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    return participation_repository.list_participations(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        seasons=parse_seasons(seasons),
        course_id=course_id,
        page=page,
        page_size=page_size,
    )
```

- [ ] **Step 7 : Lancer les tests pour vérifier le succès**

Run: `cd backend && pytest tests/test_api/test_other_api.py -v`
Expected: PASS (tous, dont les 3 nouveaux).

- [ ] **Step 8 : Suite backend complète + lint**

Run: `cd backend && pytest -m "not integration" -q && ruff check .`
Expected: PASS + `All checks passed!`

- [ ] **Step 9 : Commit**

```bash
git add backend/app/schemas/season.py backend/app/api/v1/stats.py backend/app/api/v1/courses.py backend/app/api/v1/participations.py backend/tests/test_api/test_other_api.py
git commit -m "feat(backend): API seasons (param /stats /courses/events /participations + GET /stats/seasons)"
```

---

## Task 5 : Helpers de saison frontend — `lib/utils/season.ts`

**Files:**
- Create: `frontend/lib/utils/season.ts`
- Test: `frontend/lib/utils/season.test.ts`

**Interfaces:**
- Produces :
  - `currentSeason(now?: Date): number`
  - `seasonOf(iso: string): number`
  - `seasonLabel(startYear: number): string`
  - `parseSeasonsParam(raw?: string | null): number[]`
  - `serializeSeasons(years: number[]): string`
  - `toggleSeason(selected: number[], year: number): number[]`
  - `seasonSelectionLabel(years: number[]): string`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `frontend/lib/utils/season.test.ts` :

```typescript
import { describe, it, expect } from "vitest";
import {
  currentSeason,
  seasonOf,
  seasonLabel,
  parseSeasonsParam,
  serializeSeasons,
  toggleSeason,
  seasonSelectionLabel,
} from "./season";

describe("seasonOf", () => {
  it("31 août appartient à la saison de l'année précédente", () => {
    expect(seasonOf("2026-08-31")).toBe(2025);
  });
  it("1er septembre ouvre une nouvelle saison", () => {
    expect(seasonOf("2026-09-01")).toBe(2026);
  });
  it("janvier appartient à la saison de l'année précédente", () => {
    expect(seasonOf("2026-01-15")).toBe(2025);
  });
});

describe("currentSeason", () => {
  it("calcule depuis une date injectée", () => {
    expect(currentSeason(new Date("2026-06-27T10:00:00Z"))).toBe(2025);
    expect(currentSeason(new Date("2026-09-02T10:00:00Z"))).toBe(2026);
  });
});

describe("seasonLabel", () => {
  it("formate « Saison Y — Y+1 »", () => {
    expect(seasonLabel(2025)).toBe("Saison 2025 — 2026");
  });
});

describe("parseSeasonsParam / serializeSeasons", () => {
  it("parse un CSV, tolère espaces, ignore non entiers, dédoublonne", () => {
    expect(parseSeasonsParam(" 2025 , 2025, abc, 2023 ")).toEqual([2025, 2023]);
  });
  it("renvoie [] pour vide/null", () => {
    expect(parseSeasonsParam(null)).toEqual([]);
    expect(parseSeasonsParam("")).toEqual([]);
  });
  it("sérialise en CSV", () => {
    expect(serializeSeasons([2025, 2023])).toBe("2025,2023");
  });
});

describe("toggleSeason", () => {
  it("ajoute une saison absente", () => {
    expect(toggleSeason([2025], 2023)).toEqual([2025, 2023]);
  });
  it("retire une saison présente", () => {
    expect(toggleSeason([2025, 2023], 2025)).toEqual([2023]);
  });
});

describe("seasonSelectionLabel", () => {
  it("une saison → libellé complet", () => {
    expect(seasonSelectionLabel([2025])).toBe("Saison 2025 — 2026");
  });
  it("plusieurs saisons → décompte", () => {
    expect(seasonSelectionLabel([2025, 2023])).toBe("2 saisons sélectionnées");
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier l'échec**

Run: `cd frontend && npm test -- season`
Expected: FAIL (Cannot find module './season').

- [ ] **Step 3 : Écrire l'implémentation**

Créer `frontend/lib/utils/season.ts` :

```typescript
// Miroir des helpers backend `app/core/season.py`. Saison = 1ᵉʳ sept Y → 31 août Y+1.
// Duplication assumée (le front ne partage pas de code Python) ; couverte par tests de bornes.

/** Année de début de la saison contenant la date ISO « YYYY-MM-DD ». */
export function seasonOf(iso: string): number {
  const year = Number(iso.slice(0, 4));
  const month = Number(iso.slice(5, 7));
  return month >= 9 ? year : year - 1;
}

/** Saison en cours (bascule au 1ᵉʳ septembre). `now` injectable pour les tests. */
export function currentSeason(now: Date = new Date()): number {
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  return month >= 9 ? year : year - 1;
}

/** Libellé d'affichage « Saison Y — Y+1 ». */
export function seasonLabel(startYear: number): string {
  return `Saison ${startYear} — ${startYear + 1}`;
}

/** Parse un CSV d'années (« 2025,2023 ») : tolère espaces, ignore non entiers, dédoublonne. */
export function parseSeasonsParam(raw?: string | null): number[] {
  if (!raw) return [];
  const out: number[] = [];
  for (const token of raw.split(",")) {
    const trimmed = token.trim();
    if (!trimmed) continue;
    const year = Number(trimmed);
    if (!Number.isInteger(year)) continue;
    if (!out.includes(year)) out.push(year);
  }
  return out;
}

/** Sérialise une liste d'années en CSV. */
export function serializeSeasons(years: number[]): string {
  return years.join(",");
}

/** Ajoute/retire une saison de la sélection (toggle). */
export function toggleSeason(selected: number[], year: number): number[] {
  return selected.includes(year)
    ? selected.filter((y) => y !== year)
    : [...selected, year];
}

/** Libellé de l'en-tête : 1 saison → libellé complet ; plusieurs → décompte. */
export function seasonSelectionLabel(years: number[]): string {
  if (years.length === 0) return seasonLabel(currentSeason());
  if (years.length === 1) return seasonLabel(years[0]);
  return `${years.length} saisons sélectionnées`;
}
```

- [ ] **Step 4 : Lancer le test pour vérifier le succès**

Run: `cd frontend && npm test -- season`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add frontend/lib/utils/season.ts frontend/lib/utils/season.test.ts
git commit -m "feat(frontend): helpers de saison (lib/utils/season.ts)"
```

---

## Task 6 : Types & client API frontend

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/api/server.ts`

**Interfaces:**
- Consumes : type `Season` (nouveau, miroir de `SeasonOut`).
- Produces :
  - `Season` : `{ start_year: number; label: string; event_count: number; participation_count: number; is_current: boolean }`.
  - `ParticipationFilters` : ajout `seasons?: number[]`.
  - `apiClient.listSeasons(club?: string): Promise<Season[]>`.
  - `apiServer.listSeasons(club?: string): Promise<Season[]>`.
  - `toQuery` (client + server) sérialise les tableaux en CSV.

- [ ] **Step 1 : Ajouter le type `Season` et `seasons` aux filtres**

Dans `frontend/lib/types.ts`, ajouter après l'interface `Stats` (vers la ligne 88) :

```typescript
// Saison sportive disponible (miroir de SeasonOut backend).
export interface Season {
  start_year: number;
  label: string;
  event_count: number;
  participation_count: number;
  is_current: boolean;
}
```

Et dans `ParticipationFilters`, ajouter le champ `seasons` :

```typescript
export interface ParticipationFilters {
  name?: string;
  event_type?: string;
  event_name?: string;
  club?: string;
  date_from?: string;
  date_to?: string;
  seasons?: number[];
  course_id?: number;
  sort?: string; // "date_desc" | "date_asc" | "name" (épreuves)
  page?: number;
  page_size?: number;
}
```

- [ ] **Step 2 : `toQuery` (client + server) — CSV des tableaux**

Dans `frontend/lib/api/client.ts`, remplacer la fonction `toQuery` par (gère les tableaux → CSV et ignore les tableaux vides) :

```typescript
function toQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) {
      if (v.length > 0) params.set(k, v.join(","));
      return;
    }
    params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}
```

Appliquer la **même** modification à la fonction `toQuery` de `frontend/lib/api/server.ts`.

- [ ] **Step 3 : Ajouter `listSeasons` au client et au server**

Dans `frontend/lib/api/client.ts`, ajouter `Season` à l'import de types et la méthode (après `getStats`) :

```typescript
  listSeasons: (club?: string) =>
    request<Season[]>(`/stats/seasons${toQuery({ club })}`),
```

Import : ajouter `Season` à la liste importée depuis `@/lib/types`.

Dans `frontend/lib/api/server.ts`, ajouter `Season` à l'import et la méthode (après `getStats`) :

```typescript
  listSeasons: (club?: string) =>
    serverFetch<Season[]>(`/stats/seasons${toQuery({ club })}`),
```

- [ ] **Step 4 : Vérifier la compilation et les tests**

Run: `cd frontend && npm test -- date && npm run lint`
Expected: PASS + ESLint propre. (Le test `date` valide qu'aucune régression d'import ; `tsc` est exercé au build en Task 8.)

- [ ] **Step 5 : Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/api/server.ts
git commit -m "feat(frontend): type Season, seasons dans les filtres, listSeasons + toQuery CSV"
```

---

## Task 7 : Composant `SeasonSelector`

**Files:**
- Create: `frontend/components/dashboard/SeasonSelector.tsx`
- Test: `frontend/components/dashboard/SeasonSelector.test.tsx`

**Interfaces:**
- Consumes : `Season` (`@/lib/types`) ; `parseSeasonsParam`, `serializeSeasons`, `toggleSeason`, `currentSeason`, `seasonSelectionLabel` (`@/lib/utils/season`) ; `Badge` (`@/components/tcn`) ; `Popover, PopoverTrigger, PopoverContent` (`@/components/ui/popover`).
- Produces :
  - Composant React `SeasonSelector({ seasons }: { seasons: Season[] })` (client).
  - Helper pur exporté `buildSeasonsHref(selected: number[], scope: string | undefined): string` — chemin `/dashboard` avec `?seasons=` (omis si sélection vide ou = saison en cours), `scope` préservé.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `frontend/components/dashboard/SeasonSelector.test.tsx` :

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SeasonSelector, buildSeasonsHref } from "./SeasonSelector";
import type { Season } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const SEASONS: Season[] = [
  { start_year: 2025, label: "Saison 2025 — 2026", event_count: 0, participation_count: 0, is_current: true },
  { start_year: 2023, label: "Saison 2023 — 2024", event_count: 3, participation_count: 12, is_current: false },
];

describe("buildSeasonsHref", () => {
  it("omet le paramètre quand seule la saison en cours est sélectionnée", () => {
    // saison en cours par défaut → pas de ?seasons
    const href = buildSeasonsHref([2025], undefined);
    expect(href === "/dashboard" || href === "/dashboard?").toBe(true);
    expect(href).not.toContain("seasons=");
  });
  it("sérialise plusieurs saisons et préserve le scope", () => {
    const href = buildSeasonsHref([2025, 2023], "club");
    expect(href).toContain("seasons=2025%2C2023");
    expect(href).toContain("scope=club");
  });
});

describe("SeasonSelector", () => {
  it("affiche par défaut le libellé de la saison en cours", () => {
    render(<SeasonSelector seasons={SEASONS} />);
    expect(screen.getByText(/Saison 2025/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2 : Lancer le test pour vérifier l'échec**

Run: `cd frontend && npm test -- SeasonSelector`
Expected: FAIL (Cannot find module './SeasonSelector').

- [ ] **Step 3 : Écrire l'implémentation**

Créer `frontend/components/dashboard/SeasonSelector.tsx` :

```typescript
"use client";
import { useRouter, useSearchParams } from "next/navigation";
import type { Season } from "@/lib/types";
import { Badge } from "@/components/tcn";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  currentSeason,
  parseSeasonsParam,
  seasonSelectionLabel,
  serializeSeasons,
  toggleSeason,
} from "@/lib/utils/season";

/**
 * Construit l'URL `/dashboard` reflétant la sélection de saisons.
 * Le paramètre `seasons` est omis quand la sélection est vide ou égale à la
 * seule saison en cours (retour implicite au défaut). `scope` est préservé.
 */
export function buildSeasonsHref(selected: number[], scope: string | undefined): string {
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  const isDefault = selected.length === 0 || (selected.length === 1 && selected[0] === currentSeason());
  if (!isDefault) params.set("seasons", serializeSeasons(selected));
  const qs = params.toString();
  return `/dashboard${qs ? `?${qs}` : ""}`;
}

export function SeasonSelector({ seasons }: { seasons: Season[] }) {
  const router = useRouter();
  const sp = useSearchParams();
  const scope = sp.get("scope") ?? undefined;

  const fromUrl = parseSeasonsParam(sp.get("seasons"));
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];

  function apply(next: number[]) {
    router.push(buildSeasonsHref(next, scope));
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <Popover>
        <PopoverTrigger
          aria-label="Choisir les saisons"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            borderRadius: 10,
            border: "1px solid var(--tcn-border)",
            background: "var(--tcn-surface, #fff)",
            color: "var(--tcn-ink)",
            fontWeight: 700,
            fontSize: 14,
            cursor: "pointer",
          }}
        >
          {seasonSelectionLabel(selected)}
        </PopoverTrigger>
        <PopoverContent align="end">
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {seasons.map((s) => {
              const checked = selected.includes(s.start_year);
              return (
                <label
                  key={s.start_year}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "6px 8px",
                    borderRadius: 8,
                    cursor: "pointer",
                    fontSize: 14,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => apply(toggleSeason(selected, s.start_year))}
                  />
                  <span style={{ flex: 1 }}>{s.label}</span>
                  <span style={{ color: "var(--tcn-text-faint)", fontSize: 12 }}>
                    {s.event_count}
                  </span>
                </label>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>

      {selected.length > 1 &&
        selected.map((y) => (
          <Badge key={y} variant="orange">
            {seasons.find((s) => s.start_year === y)?.label ?? `Saison ${y} — ${y + 1}`}
          </Badge>
        ))}
    </div>
  );
}
```

- [ ] **Step 4 : Lancer le test pour vérifier le succès**

Run: `cd frontend && npm test -- SeasonSelector`
Expected: PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add frontend/components/dashboard/SeasonSelector.tsx frontend/components/dashboard/SeasonSelector.test.tsx
git commit -m "feat(frontend): composant SeasonSelector (multi-saisons, URL, chips)"
```

---

## Task 8 : Câblage de la page dashboard

**Files:**
- Modify: `frontend/app/dashboard/page.tsx`

**Interfaces:**
- Consumes : `apiServer.listSeasons`, `apiServer.getStats/listEvents/listParticipations` (avec `seasons`), `SeasonSelector`, `parseSeasonsParam`, `currentSeason`, `seasonSelectionLabel` (`@/lib/utils/season`).
- Produces : page dashboard filtrée par saison, titre dynamique, sélecteur dans l'en-tête.

- [ ] **Step 1 : Modifier la page**

Dans `frontend/app/dashboard/page.tsx` :

a) Ajouter les imports (après les imports existants) :

```typescript
import { SeasonSelector } from "@/components/dashboard/SeasonSelector";
import { currentSeason, parseSeasonsParam, seasonSelectionLabel } from "@/lib/utils/season";
```

b) Après `const club = clubFromScope(sp.scope);`, calculer la sélection :

```typescript
  const fromUrl = parseSeasonsParam(sp.seasons);
  const selected = fromUrl.length > 0 ? fromUrl : [currentSeason()];
```

c) Étendre le `Promise.all` pour récupérer les saisons et propager `seasons` :

```typescript
  const [stats, eventsPage, participations, seasons] = await Promise.all([
    apiServer.getStats(club, selected),
    apiServer.listEvents({ club, seasons: selected, page_size: 200 }),
    apiServer.listParticipations({ club, seasons: selected, page_size: 5000 }),
    apiServer.listSeasons(club),
  ]);
```

> Note : `apiServer.getStats` ne prend aujourd'hui que `club`. Voir step (d) pour étendre sa signature.

d) Dans `frontend/lib/api/server.ts`, étendre `getStats` pour accepter `seasons` (CSV) :

```typescript
  getStats: (club?: string, seasons?: number[]) =>
    serverFetch<Stats>(`/stats${toQuery({ club, seasons })}`),
```

Et de façon cohérente, dans `frontend/lib/api/client.ts`, étendre `getStats` de la même manière :

```typescript
  getStats: (club?: string, seasons?: number[]) =>
    request<Stats>(`/stats${toQuery({ club, seasons })}`),
```

e) Remplacer le titre codé en dur (ligne `Saison 2025 — 2026`) par le libellé dynamique et insérer le sélecteur. Remplacer le bloc d'en-tête :

```tsx
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 26 }}>
        <div>
          <Eyebrow>Participations aux courses</Eyebrow>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 40, color: "var(--tcn-ink)", lineHeight: 1, marginTop: 6 }}>{seasonSelectionLabel(selected)}</div>
          <div style={{ fontSize: 15, color: "var(--tcn-text-muted)", marginTop: 8, fontWeight: 500 }}>Vue d&apos;ensemble des performances des athlètes du club</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <SeasonSelector seasons={seasons} />
          <ScopeToggle />
        </div>
      </div>
```

- [ ] **Step 2 : Build (TS strict + RSC)**

Run: `cd frontend && npm run build`
Expected: build OK (compilation TypeScript stricte et RSC sans erreur).

- [ ] **Step 3 : Lint + suite de tests complète**

Run: `cd frontend && npm run lint && npm test`
Expected: ESLint propre + tous les tests Vitest verts.

- [ ] **Step 4 : Commit**

```bash
git add frontend/app/dashboard/page.tsx frontend/lib/api/server.ts frontend/lib/api/client.ts
git commit -m "feat(frontend): dashboard filtré par saison + titre dynamique + sélecteur"
```

---

## Task 9 : Vérification de bout en bout & documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-06-27-selecteur-saison-design.md` (passage du statut à « implémenté »), optionnel.

- [ ] **Step 1 : Suite backend complète**

Run: `cd backend && pytest -m "not integration" -q && ruff check .`
Expected: tout vert + `All checks passed!`

- [ ] **Step 2 : Suite frontend complète**

Run: `cd frontend && npm test && npm run build && npm run lint`
Expected: Vitest vert, build OK, ESLint propre.

- [ ] **Step 3 : Vérification manuelle (dev)**

Démarrer le backend (`cd backend && uvicorn app.main:app --reload --port 8001`) et le frontend (`cd frontend && npm run dev`), puis vérifier :
- `/dashboard` sans paramètre → titre « Saison <courante> », données de la saison en cours.
- Sélection d'une autre saison → cartes (dossards/victoires/podiums/top 10), disciplines, épreuves préférées recalculées ; URL `?seasons=...`.
- Sélection de deux saisons non contiguës (ex. 2025 + 2023) → union correcte ; chips affichées.
- Le sélecteur ne liste que les saisons avec résultats **plus** la saison en cours.
- Désélection totale → retour implicite à la saison en cours (paramètre retiré de l'URL).

- [ ] **Step 4 : Commit final (si docs mise à jour)**

```bash
git add docs/superpowers/specs/2026-06-27-selecteur-saison-design.md
git commit -m "docs(spec): sélecteur de saison implémenté (issue #7)"
```

---

## Self-Review

**Spec coverage :**
- §1 helpers `core/season.py` → Task 1 ✅
- §2 filtrage repo (`_apply_filters`, propagation, `for_stats`, `distinct_seasons`) → Task 2 ✅
- §3 service (`get_stats` seasons, `list_seasons`) → Task 3 ✅
- §4 API (`/stats` seasons, `/stats/seasons`, `/courses/events`, `/participations`) → Task 4 ✅
- §5 schémas (`SeasonOut`, réponses inchangées) → Task 4 ✅
- §6 migration → aucune (constante globale) ✅
- §7 `lib/utils/season.ts` → Task 5 ✅
- §8 types & client (`Season`, `seasons`, `listSeasons`, `toQuery` CSV) → Task 6 ✅
- §9 `SeasonSelector` → Task 7 ✅
- §10 page dashboard → Task 8 ✅
- Vérification (critères de succès) → Task 9 ✅

**Écart documenté vs spec :** la spec cite `app.core.time.now()`, mais `app/core/time.py` n'expose que `utcnow()`. `current_season()` utilise donc `utcnow().date()` (même intention : horloge centralisée figeable). Comportement et testabilité identiques.

**Cohérence des types :** `seasons: list[int] | None` côté backend (CSV parsé via `parse_seasons`) ; `seasons?: number[]` côté frontend (CSV via `toQuery`). `SeasonOut`/`Season` partagent exactement les 5 champs `start_year, label, event_count, participation_count, is_current`. `distinct_seasons` renvoie `start_year/event_count/participation_count` (sans `label`/`is_current`), enrichis dans `list_seasons` — cohérent.

**Placeholders :** aucun TODO/TBD ; tout le code est fourni intégralement.
