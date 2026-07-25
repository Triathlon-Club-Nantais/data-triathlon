# Identification du club TCN et disciplines hors fédération — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ne compter comme membre du TCN que les vrais membres, et sortir les
disciplines hors fédération triathlon des compteurs du club.

**Architecture:** `app/core/club.py` devient l'unique définition de
« appartient au TCN » (liste blanche de libellés normalisés, match à l'égalité),
exposée aux clients via un booléen `is_tcn` dans le DTO ; le paramètre d'API
`club` (texte libre en sous-chaîne) est remplacé par `scope=club`. En parallèle,
`app/core/discipline.py` définit les disciplines hors fédération et un paramètre
`federal_only` les retire des compteurs quand l'écran le demande.

**Tech Stack:** Python 3.13 / uv / FastAPI / SQLAlchemy 2.0 / pytest — Next.js 16
/ TypeScript / Vitest.

Spec : `docs/superpowers/specs/2026-07-25-identification-club-tcn-design.md`
Issue : [#76](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/76)

## Global Constraints

- Commandes backend depuis `backend/`, toujours via `uv run` (aucun venv à activer).
- Tests unitaires **sans réseau** : `uv run pytest -m "not integration"`.
- Lint : `uv run ruff check .` doit passer à chaque commit.
- Frontend depuis `frontend/` : `npm test` (Vitest) et `npm run build`.
- UI, commentaires et messages d'erreur en **français avec accents**.
- Commits en Conventional Commits, suffixés ` (#76)`.
- **Aucune migration Alembic** : ce plan ne touche à aucun modèle SQLAlchemy.
- Le flux ne traverse qu'une direction : `api → services → repositories → DB`.
  Seuls les repositories touchent la `Session`.
- CLI : **stdout reste parsable**. Avec `--json`, stdout ne porte que la ligne JSON.
- Libellés canoniques du club, forme normalisée, valables pour tout le plan :
  `triathlon club nantais`, `tri club nantais`, `tcn`.
- Slugs hors fédération, valables pour tout le plan : `trail`, `cyclisme`,
  `cyclisme-route`, `cyclisme-clm`, `course-a-pied`, `course-a-pied-5k`,
  `course-a-pied-10k`, `course-a-pied-semi`, `course-a-pied-marathon`.

**Écart assumé par rapport à la spec :** la spec annonce `federal_only` « sur les
mêmes endpoints que `scope` ». Le plan le restreint aux endpoints qui alimentent
réellement des compteurs ou des listes consommées par le front : `/participations`,
`/courses/events`, `/stats`, `/stats/seasons`, `/stats/events-geo`. `/courses`
(liste brute) et `/athletes` reçoivent `scope` — c'est le renommage d'un
paramètre existant — mais pas `federal_only` : aucun écran ne les appelle, et un
paramètre non consommé est du code mort à maintenir.

---

### Task 1: Le prédicat club, source unique

**Files:**
- Modify: `backend/app/core/club.py` (réécriture complète)
- Create: `backend/tests/club_corpus.py`
- Create: `backend/tests/test_core/test_club.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `app.core.club.TCN_CLUB_LABELS: frozenset[str]`
  - `app.core.club.SCOPE_CLUB: str` (vaut `"club"`)
  - `app.core.club.normalize_club(club: str | None) -> str`
  - `app.core.club.is_tcn(club: str | None) -> bool`
  - `app.core.club.tcn_clause(column) -> ColumnElement[bool]`
  - `app.core.club.is_club_scope(scope: str | None) -> bool`
  - `tests.club_corpus.CORPUS: list[tuple[str | None, bool]]`
- Retiré : `TCN_KEYWORDS`, `club_keyword_filter`. Les appelants sont migrés en
  Task 2 — **la suite de tests est rouge entre les deux commits**, c'est prévu.

- [ ] **Step 1: Écrire le corpus de libellés partagé**

Créer `backend/tests/club_corpus.py` :

```python
"""Corpus de libellés de club, partagé par les tests du prédicat.

Tiré des données de prod du 25/07/2026 (issue #76). C'est le **contrat** du
filtre club : il est passé à la fois dans `is_tcn()` (Python) et dans une requête
filtrée par `tcn_clause()` (SQL), et les deux doivent rendre le même verdict.

Ajouter un cas ici, c'est l'exiger des deux implémentations à la fois.
"""

#: (libellé brut, appartient au TCN)
CORPUS: list[tuple[str | None, bool]] = [
    # Vrais libellés du club, dans les casses réellement observées.
    ("TRIATHLON CLUB NANTAIS", True),
    ("TRI CLUB NANTAIS", True),
    ("Triathlon Club Nantais", True),
    ("TCN", True),
    # Bords et espaces internes : la normalisation les aplatit.
    ("  TRI CLUB NANTAIS  ", True),
    ("TRI  CLUB   NANTAIS", True),
    # Les faux positifs de #76 : des clubs nantais, mais pas le nôtre.
    ("ASSOCIATION SPORTIVE  MARATHONIENS NANTAIS", False),
    ("S/L STADE NANTAIS AC", False),
    ("RACING CLUB NANTAIS *", False),
    # Breizh Chrono met parfois la ville dans la colonne club.
    ("NANTES (44200)", False),
    ("LE LANDREAU (44430)", False),
    # L'égalité est stricte : un libellé qui contient le nôtre n'est pas le nôtre.
    ("TRIATHLON CLUB NANTAIS SUD", False),
    ("TCN ATHLETISME", False),
    # Absence d'information.
    ("", False),
    (None, False),
]

#: Sous-ensemble insérable en base (SQL ne voit jamais de `None` utile ici).
CORPUS_SQL: list[tuple[str, bool]] = [
    (libelle, attendu) for libelle, attendu in CORPUS if libelle
]
```

- [ ] **Step 2: Écrire le test du prédicat Python**

Créer `backend/tests/test_core/test_club.py` :

```python
import pytest

from app.core.club import TCN_CLUB_LABELS, is_club_scope, is_tcn, normalize_club
from tests.club_corpus import CORPUS


@pytest.mark.parametrize("libelle,attendu", CORPUS)
def test_is_tcn_sur_le_corpus(libelle, attendu):
    assert is_tcn(libelle) is attendu


def test_normalize_club_aplatit_casse_bords_et_espaces():
    assert normalize_club("  TRI   CLUB  NANTAIS ") == "tri club nantais"
    assert normalize_club(None) == ""
    assert normalize_club("") == ""


def test_les_libelles_de_reference_sont_deja_normalises():
    """La liste blanche est comparée à des formes normalisées : elle doit l'être."""
    for label in TCN_CLUB_LABELS:
        assert normalize_club(label) == label


def test_is_club_scope():
    assert is_club_scope("club") is True
    assert is_club_scope(None) is False
    assert is_club_scope("tous") is False
```

- [ ] **Step 3: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_core/test_club.py -q`
Expected: FAIL — `ImportError: cannot import name 'is_club_scope' from 'app.core.club'`

- [ ] **Step 4: Réécrire `app/core/club.py`**

Remplacer **tout** le contenu de `backend/app/core/club.py` par :

```python
"""
Appartenance au Triathlon Club Nantais — **définition unique**.

Le prédicat a longtemps existé en trois exemplaires divergents (ici, dans le
front, dans le scraper Breizh Chrono), le plus permissif faisant autorité sur les
compteurs : tout libellé contenant « nantais » était compté comme TCN, ce qui
ramassait les clubs d'athlétisme nantais (issue #76). Il n'y a plus qu'une
définition, et elle vit ici.

Le match se fait à l'**égalité** sur une forme normalisée, jamais en
sous-chaîne : « RACING CLUB NANTAIS » est un club nantais, pas le nôtre.
"""
import re

from sqlalchemy import func

#: Libellés du club, sous leur forme normalisée (cf. `normalize_club`).
#: Ajouter une variante ici est le geste prévu — `python -m app.cli club-labels`
#: sert justement à repérer celles qui manquent.
TCN_CLUB_LABELS: frozenset[str] = frozenset({
    "triathlon club nantais",
    "tri club nantais",
    "tcn",
})

#: Valeur du paramètre d'API `scope` restreignant une réponse aux membres du club.
SCOPE_CLUB = "club"

_ESPACES = re.compile(r"\s+")


def normalize_club(club: str | None) -> str:
    """Forme comparable d'un libellé : minuscules, bords et espaces internes aplatis.

    Miroir Python de `_normalise_sql`. Les deux doivent rendre le même verdict —
    c'est ce que verrouille `tests/test_repositories/test_club_filter.py`.
    """
    return _ESPACES.sub(" ", (club or "").strip()).lower()


def is_tcn(club: str | None) -> bool:
    """Vrai si `club` désigne le Triathlon Club Nantais."""
    return normalize_club(club) in TCN_CLUB_LABELS


def is_club_scope(scope: str | None) -> bool:
    """Vrai si le paramètre d'API `scope` demande la portée club."""
    return scope == SCOPE_CLUB


def _normalise_sql(column):
    """Miroir SQL de `normalize_club`, portable SQLite (dev) et Postgres (prod).

    Trois `replace` imbriqués aplatissent jusqu'à huit espaces consécutifs. Au
    delà, le libellé sort du filtre : le pire cas est un oubli, jamais un faux
    positif — et `club-labels` le rendra visible.
    """
    expr = func.lower(func.trim(column))
    for _ in range(3):
        expr = func.replace(expr, "  ", " ")
    return expr


def tcn_clause(column):
    """Clause SQLAlchemy : `column` porte un libellé du club.

    `column` est passée en paramètre pour couvrir aussi bien `Participation.club`
    (le club inscrit sur la ligne de résultat) que `Athlete.club`.
    """
    return _normalise_sql(column).in_(sorted(TCN_CLUB_LABELS))
```

- [ ] **Step 5: Lancer le test et vérifier qu'il passe**

Run: `cd backend && uv run pytest tests/test_core/test_club.py -q`
Expected: PASS — 18 tests (15 cas du corpus + 3 tests nommés)

- [ ] **Step 6: Lint**

Run: `cd backend && uv run ruff check app/core/club.py tests/test_core/test_club.py tests/club_corpus.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/club.py backend/tests/test_core/test_club.py backend/tests/club_corpus.py
git commit -m "feat(club): liste blanche de libellés à la place du filtre par sous-chaîne (#76)"
```

---

### Task 2: Bascule du paramètre `club` vers `scope`

Cette tâche est indivisible : retirer `club_keyword_filter` casse simultanément
les trois repositories et les quatre routers qui l'utilisent. Elle rend la suite
verte, laissée rouge par la Task 1.

**Files:**
- Modify: `backend/app/repositories/participation_repository.py`
- Modify: `backend/app/repositories/athlete_repository.py`
- Modify: `backend/app/repositories/course_repository.py:85-111`
- Modify: `backend/app/services/stats_service.py:14, 62`
- Modify: `backend/app/api/v1/participations.py:62-88`
- Modify: `backend/app/api/v1/courses.py:27-67`
- Modify: `backend/app/api/v1/athletes.py:14-22`
- Modify: `backend/app/api/v1/stats.py`
- Create: `backend/tests/test_repositories/test_club_filter.py`
- Modify: `backend/tests/test_repositories/test_participation_repository.py:61`
- Modify: `backend/tests/test_api/test_participations_api.py:65-67`
- Modify: `backend/tests/test_services/test_stats_service.py:31`

**Interfaces:**
- Consumes: `app.core.club.tcn_clause`, `is_club_scope`, `SCOPE_CLUB` (Task 1).
- Produces:
  - Repositories et services : paramètre `club_only: bool = False` en lieu et
    place de `club: str | None = None`, partout où il existait.
  - HTTP : paramètre de requête `scope` (seule valeur reconnue : `club`) en lieu
    et place de `club`.
  - `participation_repository.tcn_filter()` est **supprimé** (remplacé par
    `tcn_clause(Participation.club)` en appel direct).

**Note de vocabulaire :** `scope` est le nom du paramètre **HTTP** ; sous la
couche API on manipule un booléen `club_only`. Un booléen se lit mieux qu'une
chaîne magique dans une signature de repository, et la traduction se fait en un
seul endroit, dans chaque router.

- [ ] **Step 1: Écrire le test d'équivalence SQL ≡ Python**

C'est le test central du plan : il interdit à la version SQL du prédicat de
diverger de la version Python.

Créer `backend/tests/test_repositories/test_club_filter.py` :

```python
"""Le filtre SQL et le prédicat Python doivent rendre le même verdict.

Le prédicat existe nécessairement deux fois : en Python pour le champ `is_tcn`
du DTO et pour les scrapers, en SQL pour filtrer et paginer sans charger toute
la table. Deux implémentations, un seul contrat — celui de `tests/club_corpus.py`.
Sans ce test, un badge affiché « TCN » pourrait sortir du compteur « TCN ».
"""
from datetime import date

from app.core.club import is_tcn, tcn_clause
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository
from tests.club_corpus import CORPUS_SQL


def _peupler(db_session):
    """Une participation par libellé du corpus, sur une seule épreuve."""
    course = course_repository.get_or_create(
        db_session, name="Tri des libellés", event_date=date(2026, 5, 16),
        event_type="triathlon-m",
    )
    for index, (libelle, _) in enumerate(CORPUS_SQL):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"NOM{index}", prenom="Test"
        )
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=str(index),
            club=libelle,
        )
    db_session.flush()
    return course


def test_le_filtre_sql_retient_exactement_ce_que_retient_le_predicat(db_session):
    _peupler(db_session)

    retenus = {
        p.club
        for p in db_session.query(Participation).filter(tcn_clause(Participation.club)).all()
    }
    attendus = {libelle for libelle, attendu in CORPUS_SQL if attendu}

    assert retenus == attendus


def test_le_predicat_python_est_d_accord_avec_le_corpus():
    """Garde-fou : le corpus décrit bien ce que fait `is_tcn`, pas autre chose."""
    for libelle, attendu in CORPUS_SQL:
        assert is_tcn(libelle) is attendu


def test_la_liste_filtree_par_scope_club_ne_rend_que_le_club(db_session):
    """Régression directe de #76 : 6 libellés « nantais », 3 seulement sont TCN."""
    _peupler(db_session)

    rows = participation_repository.list_participations(
        db_session, club_only=True, page_size=100
    )

    assert {r.club for r in rows} == {
        libelle for libelle, attendu in CORPUS_SQL if attendu
    }
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_repositories/test_club_filter.py -q`
Expected: FAIL — `TypeError: list_participations() got an unexpected keyword argument 'club_only'`

- [ ] **Step 3: Migrer `participation_repository.py`**

Remplacer l'import ligne 7 :

```python
from app.core.club import tcn_clause
```

Dans `_apply_filters` (ligne 95), renommer le paramètre `club` en `club_only` et
remplacer le bloc des lignes 117-119 par :

```python
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
```

Supprimer entièrement la fonction `tcn_filter()` (lignes 192-194) et, dans
`_grouped_events_query` ligne 232, remplacer son appel :

```python
        func.sum(case((tcn_clause(Participation.club), 1), else_=0)).label("tcn_count"),
```

Dans `for_stats` (ligne 197), remplacer la signature et le bloc de filtrage :

```python
def for_stats(
    db: Session, *, club_only: bool = False, seasons: list[int] | None = None
) -> list[Participation]:
    """Charge les participations (avec course + athlète) pour les agrégations stats."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    )
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if seasons:
        q = q.join(Course, Participation.course_id == Course.id).filter(_season_clause(seasons))
    return q.all()
```

Dans `distinct_seasons` (ligne 354), remplacer la signature et le bloc :

```python
def distinct_seasons(db: Session, *, club_only: bool = False) -> list[dict]:
```

```python
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
```

Enfin, quatre fonctions portent encore le paramètre dans leur signature :
`list_participations` (ligne 139), `_grouped_events_query` (ligne 219),
`events_with_counts` (ligne 261) et `events_page` (ligne 304). Dans chacune,
remplacer la ligne

```python
    club: str | None = None,
```

par

```python
    club_only: bool = False,
```

(dans `_grouped_events_query`, la forme est `club=None,` sans annotation →
`club_only=False,`), et remplacer dans leur corps chaque argument `club=club,`
passé à `_apply_filters` ou `_grouped_events_query` par `club_only=club_only,` —
il y en a cinq. Les numéros de ligne cités valent pour le fichier d'origine et
se décalent au fil des remplacements : se fier aux noms de fonctions.

Vérification : `grep -n "club" app/repositories/participation_repository.py` ne
doit plus renvoyer que des occurrences de `Participation.club`, `club_only` et
`tcn_clause`.

- [ ] **Step 4: Migrer `athlete_repository.py` et `course_repository.py`**

Dans `backend/app/repositories/athlete_repository.py`, remplacer l'import ligne 7
par `from app.core.club import tcn_clause`, puis dans `search` (ligne 59)
remplacer le paramètre `club: str | None = None` par `club_only: bool = False` et
les lignes 73-75 par :

```python
    if club_only:
        q = q.filter(tcn_clause(Athlete.club))
```

Dans `backend/app/repositories/course_repository.py`, remplacer l'import ligne 6
par `from app.core.club import tcn_clause`, puis dans `list_all` remplacer le
paramètre `club: str | None = None` par `club_only: bool = False` et les lignes
98-104 par :

```python
    if club_only:
        q = (
            q.join(Participation, Participation.course_id == Course.id)
            .filter(tcn_clause(Participation.club))
            .distinct()
        )
```

- [ ] **Step 5: Migrer `stats_service.py`**

Deux signatures à ouvrir sur `club_only` (lignes 14 et 62) :

```python
def get_stats(
    db: Session, *, club_only: bool = False, seasons: list[int] | None = None
) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(db, club_only=club_only, seasons=seasons)
```

```python
def list_seasons(db: Session, *, club_only: bool = False) -> list[dict]:
```

et dans son corps, ligne 68 :

```python
    rows = participation_repository.distinct_seasons(db, club_only=club_only)
```

- [ ] **Step 6: Migrer les quatre routers**

Dans chaque router, le paramètre HTTP `club: str | None = Query(None)` devient
`scope: str | None = Query(None, description="« club » restreint aux membres du TCN.")`,
et l'appel passe `club_only=is_club_scope(scope)`.

`backend/app/api/v1/participations.py` — ajouter `from app.core.club import is_club_scope`
en tête, puis dans `list_participations` remplacer `club: str | None = Query(None),`
par la ligne `scope` ci-dessus et `club=club,` par `club_only=is_club_scope(scope),`.

`backend/app/api/v1/courses.py` — même import ; appliquer la substitution dans
`list_events` **et** dans `list_courses`.

`backend/app/api/v1/athletes.py` — même import ; substitution dans la recherche
d'athlètes (`club=club` → `club_only=is_club_scope(scope)`).

`backend/app/api/v1/stats.py` — même import, puis :

```python
@router.get("/stats")
def get_stats(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    seasons: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Stats agrégées du club, filtrables par saison(s) (CSV d'années)."""
    return stats_service.get_stats(
        db, club_only=is_club_scope(scope), seasons=parse_seasons(seasons)
    )


@router.get("/stats/seasons", response_model=list[SeasonOut])
def list_seasons(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    db: Session = Depends(get_db),
):
    """Saisons disponibles pour le sélecteur (avec saison en cours forcée)."""
    return stats_service.list_seasons(db, club_only=is_club_scope(scope))


@router.get("/stats/events-geo")
def get_events_geo(
    scope: str | None = Query(None, description="« club » restreint aux membres du TCN."),
    db: Session = Depends(get_db),
):
    """Épreuves géocodées (lat/lon) pour la carte. Géocodage caché en mémoire."""
    rows = participation_repository.events_with_counts(db, club_only=is_club_scope(scope))
```

- [ ] **Step 7: Adapter les trois tests existants qui passaient un texte libre**

`backend/tests/test_repositories/test_participation_repository.py` ligne 61 :

```python
    by_club = participation_repository.list_participations(db_session, club_only=True)
```

`backend/tests/test_api/test_participations_api.py` lignes 65-67 :

```python
    by_club = client.get("/api/v1/participations", params={"scope": "club"})
    assert by_club.status_code == 200
    assert by_club.json()[0]["club"] == "TCN"
```

`backend/tests/test_services/test_stats_service.py` ligne 31 :

```python
    stats = stats_service.get_stats(db_session, club_only=True)
```

- [ ] **Step 8: Lancer toute la suite backend**

Run: `cd backend && uv run pytest -m "not integration" -q`
Expected: PASS — aucun échec, aucun `ImportError` résiduel sur `club_keyword_filter`

- [ ] **Step 9: Lint**

Run: `cd backend && uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add backend/app backend/tests
git commit -m "refactor(api): remplace le filtre club texte libre par scope=club (#76)"
```

---

### Task 3: `is_tcn` dans le DTO de participation

**Files:**
- Modify: `backend/app/schemas/participation.py:10-28`
- Modify: `backend/tests/test_api/test_participations_api.py`

**Interfaces:**
- Consumes: `app.core.club.is_tcn` (Task 1).
- Produces: `ParticipationOut.is_tcn: bool` — champ calculé, présent dans toutes
  les réponses qui sérialisent une participation (`/participations`,
  `/participations/{id}`, `/courses/{id}`). C'est ce champ que le front lira en
  Task 8.

- [ ] **Step 1: Écrire le test**

Ajouter à la fin de `backend/tests/test_api/test_participations_api.py` :

```python
def test_is_tcn_expose_le_verdict_du_backend(client):
    """Le front n'a plus à deviner : le backend tranche et le dit."""
    client.post("/api/v1/participations", json=_payload(bib="1", nom="DUPONT", club="TRI CLUB NANTAIS"))
    client.post("/api/v1/participations", json=_payload(bib="2", nom="MARTIN", club="RACING CLUB NANTAIS *"))

    rows = client.get("/api/v1/participations").json()
    par_club = {r["club"]: r["is_tcn"] for r in rows}

    assert par_club["TRI CLUB NANTAIS"] is True
    assert par_club["RACING CLUB NANTAIS *"] is False
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_api/test_participations_api.py::test_is_tcn_expose_le_verdict_du_backend -q`
Expected: FAIL — `KeyError: 'is_tcn'`

- [ ] **Step 3: Ajouter le champ calculé au schéma**

Dans `backend/app/schemas/participation.py`, ajouter l'import et le champ :

```python
from pydantic import BaseModel, ConfigDict, computed_field

from app.core.club import is_tcn as _is_tcn
```

puis, à la fin de la classe `ParticipationOut` (après `created_at`) :

```python
    @computed_field
    @property
    def is_tcn(self) -> bool:
        """Appartenance au club, tranchée par le backend.

        Exposée pour que le front n'ait pas à réimplémenter le prédicat : c'est
        cette duplication qui avait divergé et laissé passer les faux positifs
        de l'issue #76.
        """
        return _is_tcn(self.club)
```

- [ ] **Step 4: Lancer le test et vérifier qu'il passe**

Run: `cd backend && uv run pytest tests/test_api/ -q`
Expected: PASS

- [ ] **Step 5: Lint et commit**

```bash
cd backend && uv run ruff check .
git add backend/app/schemas/participation.py backend/tests/test_api/test_participations_api.py
git commit -m "feat(api): expose is_tcn dans le DTO de participation (#76)"
```

---

### Task 4: Les disciplines hors fédération

**Files:**
- Create: `backend/app/core/discipline.py`
- Create: `backend/tests/test_core/test_discipline.py`

**Interfaces:**
- Consumes: `app.scrapers.classify.CANONICAL_TYPES` (lecture, pour le test de cohérence).
- Produces:
  - `app.core.discipline.NON_FEDERAL_TYPES: frozenset[str]`
  - `app.core.discipline.is_federal(event_type: str | None) -> bool`
  - `app.core.discipline.federal_clause(column) -> ColumnElement[bool]`

**Pourquoi une liste de slugs exacts et non un préfixe de sport :** comparer des
slugs entiers des deux côtés (`in_` en SQL, `in` en Python) rend la divergence
SQL/Python **structurellement impossible**, là où un `LIKE 'trail%'` classerait
un hypothétique `trailrun` autrement que le Python. Et un slug inconnu — legacy
non re-classé, discipline future — est fédéral des deux côtés.

- [ ] **Step 1: Écrire le test**

Créer `backend/tests/test_core/test_discipline.py` :

```python
import pytest

from app.core.discipline import NON_FEDERAL_TYPES, is_federal
from app.scrapers.classify import CANONICAL_TYPES

FEDERALES = [
    "triathlon", "triathlon-s", "triathlon-m", "triathlon-xl",
    "duathlon", "duathlon-l", "swimrun", "swimrun-m",
    "aquathlon", "aquarun", "bike-run",
]
HORS_FEDERATION = [
    "trail", "cyclisme", "cyclisme-route", "cyclisme-clm",
    "course-a-pied", "course-a-pied-5k", "course-a-pied-10k",
    "course-a-pied-semi", "course-a-pied-marathon",
]


@pytest.mark.parametrize("event_type", FEDERALES)
def test_disciplines_federales(event_type):
    assert is_federal(event_type) is True


@pytest.mark.parametrize("event_type", HORS_FEDERATION)
def test_disciplines_hors_federation(event_type):
    assert is_federal(event_type) is False


@pytest.mark.parametrize("event_type", ["", None, "Trail L", "sport-inconnu"])
def test_un_type_non_canonique_est_federal_par_defaut(event_type):
    """Liste d'exclusion : l'inconnu reste dans les compteurs plutôt que d'en sortir en silence."""
    assert is_federal(event_type) is True


def test_les_types_hors_federation_sont_des_slugs_canoniques():
    """Une faute de frappe dans la liste la rendrait inopérante sans rien casser."""
    assert NON_FEDERAL_TYPES <= CANONICAL_TYPES


def test_la_partition_couvre_tous_les_slugs_canoniques():
    """Tout slug canonique tombe d'un côté ou de l'autre, aucun n'est orphelin."""
    federaux = {t for t in CANONICAL_TYPES if is_federal(t)}
    assert federaux | NON_FEDERAL_TYPES == CANONICAL_TYPES
    assert federaux & NON_FEDERAL_TYPES == set()


def test_la_liste_du_test_et_celle_du_module_coincident():
    """Le test doit tomber si quelqu'un élargit la liste sans y réfléchir ici."""
    assert set(HORS_FEDERATION) == NON_FEDERAL_TYPES
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_core/test_discipline.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.discipline'`

- [ ] **Step 3: Créer `app/core/discipline.py`**

```python
"""
Disciplines fédérales triathlon, et les autres.

Un club de triathlon importe aussi des trails et des courses sur route de ses
membres : légitime à conserver, mais ces résultats gonflent des compteurs qu'on
lit comme des compteurs de triathlon (issue #76). D'où la partition.

**Liste d'exclusion, pas d'inclusion** : est fédéral tout ce qui n'est pas
explicitement listé ici. Une discipline future entre donc dans les compteurs par
défaut, comme le repli du classifieur retombe déjà sur `triathlon`
(`app/scrapers/classify.py`). Le contraire ferait disparaître des résultats sans
que personne ne s'en aperçoive.

Les slugs sont comparés **entiers** des deux côtés (Python et SQL), ce qui rend
les deux implémentations incapables de diverger.
"""

#: Slugs canoniques (cf. `classify.CANONICAL_TYPES`) hors fédération triathlon.
NON_FEDERAL_TYPES: frozenset[str] = frozenset({
    "trail",
    "cyclisme",
    "cyclisme-route",
    "cyclisme-clm",
    "course-a-pied",
    "course-a-pied-5k",
    "course-a-pied-10k",
    "course-a-pied-semi",
    "course-a-pied-marathon",
})


def is_federal(event_type: str | None) -> bool:
    """Vrai si `event_type` relève d'une discipline de la fédération triathlon."""
    return (event_type or "") not in NON_FEDERAL_TYPES


def federal_clause(column):
    """Clause SQLAlchemy : `column` (un `event_type`) est une discipline fédérale."""
    return column.notin_(sorted(NON_FEDERAL_TYPES))
```

- [ ] **Step 4: Lancer le test et vérifier qu'il passe**

Run: `cd backend && uv run pytest tests/test_core/test_discipline.py -q`
Expected: PASS

- [ ] **Step 5: Lint et commit**

```bash
cd backend && uv run ruff check .
git add backend/app/core/discipline.py backend/tests/test_core/test_discipline.py
git commit -m "feat(core): distingue les disciplines fédérales des autres (#76)"
```

---

### Task 5: Le paramètre `federal_only`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py`
- Modify: `backend/app/services/stats_service.py`
- Modify: `backend/app/api/v1/participations.py`
- Modify: `backend/app/api/v1/courses.py` (`list_events` uniquement)
- Modify: `backend/app/api/v1/stats.py`
- Create: `backend/tests/test_api/test_federal_only.py`

**Interfaces:**
- Consumes: `app.core.discipline.federal_clause` (Task 4), `club_only` (Task 2).
- Produces: paramètre `federal_only: bool = False` sur
  `list_participations`, `for_stats`, `distinct_seasons`, `events_with_counts`,
  `events_page`, `_apply_filters`, `_grouped_events_query`,
  `stats_service.get_stats`, `stats_service.list_seasons`, et sur les endpoints
  `/participations`, `/courses/events`, `/stats`, `/stats/seasons`,
  `/stats/events-geo`.

**Le défaut est `False` — c'est-à-dire aucun filtrage.** L'exclusion des autres
disciplines est un défaut d'**écran** (dashboard, page club, Task 9), pas d'API :
un défaut à `True` amputerait silencieusement tout futur appelant, ce qui est
précisément le travers que #76 corrige.

- [ ] **Step 1: Écrire le test**

Créer `backend/tests/test_api/test_federal_only.py` :

```python
"""`federal_only` sort les disciplines hors fédération des compteurs (#76)."""


def _payload(bib: str, nom: str, event_name: str, event_type: str) -> dict:
    return {
        "athlete_name": nom,
        "athlete_firstname": "Test",
        "club": "TRI CLUB NANTAIS",
        "bib_number": bib,
        "event_name": event_name,
        "event_date": "2026-05-31",
        "event_type": event_type,
        "total_time": "01:30:00",
        "provider": "manuel",
    }


def _peupler(client):
    client.post("/api/v1/participations", json=_payload("1", "DUPONT", "Tri M", "triathlon-m"))
    client.post("/api/v1/participations", json=_payload("2", "MARTIN", "Urban Trail", "trail"))
    client.post("/api/v1/participations", json=_payload("3", "DURAND", "10 km", "course-a-pied-10k"))


def test_sans_le_parametre_rien_n_est_filtre(client):
    """L'API reste neutre par défaut : c'est l'écran qui décide, pas le backend."""
    _peupler(client)
    rows = client.get("/api/v1/participations", params={"scope": "club"}).json()
    assert len(rows) == 3


def test_federal_only_retire_trail_et_course_a_pied(client):
    _peupler(client)
    rows = client.get(
        "/api/v1/participations", params={"scope": "club", "federal_only": "true"}
    ).json()
    assert [r["course"]["event_type"] for r in rows] == ["triathlon-m"]


def test_les_stats_suivent_le_meme_filtre(client):
    _peupler(client)

    tout = client.get("/api/v1/stats", params={"scope": "club"}).json()
    federal = client.get(
        "/api/v1/stats", params={"scope": "club", "federal_only": "true"}
    ).json()

    assert tout["total"] == 3
    assert tout["events"] == 3
    assert federal["total"] == 1
    assert federal["events"] == 1
    assert set(federal["by_type"]) == {"triathlon-m"}


def test_les_epreuves_agregees_suivent_le_meme_filtre(client):
    _peupler(client)

    tout = client.get("/api/v1/courses/events", params={"scope": "club"}).json()
    federal = client.get(
        "/api/v1/courses/events", params={"scope": "club", "federal_only": "true"}
    ).json()

    assert tout["total_events"] == 3
    assert federal["total_events"] == 1
    assert federal["total_participations"] == 1
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_api/test_federal_only.py -q`
Expected: FAIL — `test_federal_only_retire_trail_et_course_a_pied` renvoie 3 lignes au lieu d'1
(le paramètre inconnu est ignoré par FastAPI, aucun filtrage n'a lieu)

- [ ] **Step 3: Threader `federal_only` dans le repository**

Dans `backend/app/repositories/participation_repository.py`, ajouter l'import :

```python
from app.core.discipline import federal_clause
```

Dans `_apply_filters`, ajouter le paramètre `federal_only=False` à la signature
et, juste après le bloc `if seasons:` :

```python
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
```

Dans `for_stats`, ajouter `federal_only: bool = False` à la signature. La
jointure sur `Course` y est conditionnelle (elle n'existe que si `seasons`), il
faut donc la rendre inconditionnelle dès que l'un des deux filtres est demandé :

```python
def for_stats(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[Participation]:
    """Charge les participations (avec course + athlète) pour les agrégations stats."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    )
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    if seasons:
        q = q.filter(_season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.all()
```

Dans `distinct_seasons`, ajouter `federal_only: bool = False` à la signature et,
après le bloc `if club_only:` :

```python
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
```

Enfin, ajouter la ligne

```python
    federal_only: bool = False,
```

aux signatures de `list_participations`, `_grouped_events_query`,
`events_with_counts` et `events_page` — juste après leur `club_only` — et
propager `federal_only=federal_only,` à chacun de leurs appels internes à
`_apply_filters` ou `_grouped_events_query` (les cinq mêmes sites que
`club_only` en Task 2).

Vérification : `grep -n "federal_only" app/repositories/participation_repository.py`
doit montrer, pour chaque fonction publique du fichier qui accepte déjà
`club_only`, à la fois le paramètre **et** sa propagation ou son filtre. Un
paramètre déclaré mais non propagé est le mode de panne typique de ce genre de
threading : le test `test_les_epreuves_agregees_suivent_le_meme_filtre` l'attrape.

- [ ] **Step 4: Threader `federal_only` dans `stats_service`**

```python
def get_stats(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )
```

```python
def list_seasons(db: Session, *, club_only: bool = False, federal_only: bool = False) -> list[dict]:
```

et dans son corps :

```python
    rows = participation_repository.distinct_seasons(
        db, club_only=club_only, federal_only=federal_only
    )
```

`list_events` relaie déjà `**filters` : rien à y changer.

- [ ] **Step 5: Exposer le paramètre sur les cinq endpoints**

Dans chacun, ajouter le paramètre de requête et le propager :

```python
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
```

- `participations.list_participations` → `federal_only=federal_only`
- `courses.list_events` → `federal_only=federal_only`
- `stats.get_stats` → `federal_only=federal_only`
- `stats.list_seasons` → `federal_only=federal_only`
- `stats.get_events_geo` → `participation_repository.events_with_counts(db, club_only=…, federal_only=federal_only)`

- [ ] **Step 6: Lancer le test et vérifier qu'il passe**

Run: `cd backend && uv run pytest tests/test_api/test_federal_only.py -q`
Expected: PASS (4 tests)

- [ ] **Step 7: Lancer toute la suite, lint, commit**

```bash
cd backend && uv run pytest -m "not integration" -q && uv run ruff check .
git add backend/app backend/tests
git commit -m "feat(api): federal_only exclut les disciplines hors fédération des compteurs (#76)"
```

---

### Task 6: La commande CLI `club-labels`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (ajout de `club_label_counts`)
- Create: `backend/app/cli/commands/club_labels.py`
- Modify: `backend/app/cli/reports.py`
- Modify: `backend/app/cli/__init__.py:20-25`
- Create: `backend/tests/test_cli/test_club_labels.py`

**Interfaces:**
- Consumes: `app.core.club.is_tcn` (Task 1).
- Produces:
  - `participation_repository.club_label_counts(db, *, like: str | None = None) -> list[tuple[str, int]]`
  - `reports.render_club_labels_report(labels: list[dict]) -> str`
  - `reports.emit_report(rapport: str, payload: dict, *, json_output: bool) -> None`
  - commande `python -m app.cli club-labels [--like FRAGMENT] [--json]`

- [ ] **Step 1: Écrire le test**

Créer `backend/tests/test_cli/test_club_labels.py` :

```python
"""La commande `club-labels` : le filet contre l'oubli silencieux d'une variante (#76)."""
import json
from contextlib import contextmanager
from datetime import date

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import club_labels as cmd
from app.repositories import athlete_repository, course_repository, participation_repository

runner = CliRunner()


def _peupler(db):
    course = course_repository.get_or_create(
        db, name="Tri Z", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    libelles = [
        "TRI CLUB NANTAIS", "TRI CLUB NANTAIS", "TRI CLUB NANTAIS",
        "RACING CLUB NANTAIS *", "RACING CLUB NANTAIS *",
        "ASPTT RENNES",
    ]
    for index, libelle in enumerate(libelles):
        athlete = athlete_repository.get_or_create(db, nom=f"NOM{index}", prenom="Test")
        participation_repository.create(
            db, athlete_id=athlete.id, course_id=course.id,
            bib_number=str(index), club=libelle,
        )
    db.flush()


def _brancher_session(monkeypatch, db_session):
    _peupler(db_session)

    @contextmanager
    def _session():
        yield db_session

    monkeypatch.setattr(cmd, "session_scope", _session)


def test_rapport_texte_trie_et_marque_les_libelles(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    result = runner.invoke(app, ["club-labels"])

    assert result.exit_code == 0
    lignes = [ligne for ligne in result.stdout.splitlines() if "NANTAIS" in ligne or "RENNES" in ligne]
    assert "3  ✓  TRI CLUB NANTAIS" in lignes[0]
    assert "2  ✗  RACING CLUB NANTAIS *" in lignes[1]
    assert "1  ✗  ASPTT RENNES" in lignes[2]


def test_like_restreint_aux_libelles_contenant_le_fragment(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    result = runner.invoke(app, ["club-labels", "--like", "rennes"])

    assert result.exit_code == 0
    assert "ASPTT RENNES" in result.stdout
    assert "NANTAIS" not in result.stdout


def test_json_ne_met_que_le_json_sur_stdout(monkeypatch, db_session):
    _brancher_session(monkeypatch, db_session)

    result = runner.invoke(app, ["club-labels", "--json"])

    assert result.exit_code == 0
    charge = json.loads(result.stdout.strip())
    assert charge["total_labels"] == 3
    assert charge["tcn_labels"] == 1
    assert charge["tcn_participations"] == 3
    assert charge["labels"][0] == {
        "club": "TRI CLUB NANTAIS", "participations": 3, "is_tcn": True
    }
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_cli/test_club_labels.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli.commands.club_labels'`

- [ ] **Step 3: Ajouter l'agrégation au repository**

À la fin de `backend/app/repositories/participation_repository.py` :

```python
def club_label_counts(db: Session, *, like: str | None = None) -> list[tuple[str, int]]:
    """Libellés de club distincts et leur nombre de participations, décroissant.

    Alimente `python -m app.cli club-labels`. Les libellés vides sont écartés :
    ils ne disent rien de l'appartenance à un club.
    """
    q = db.query(Participation.club, func.count(Participation.id)).filter(
        Participation.club.isnot(None), Participation.club != ""
    )
    if like:
        q = q.filter(Participation.club.ilike(f"%{like}%"))
    rows = q.group_by(Participation.club).all()
    return sorted(((club, int(count)) for club, count in rows), key=lambda r: (-r[1], r[0]))
```

- [ ] **Step 4: Ajouter le rendu et l'émission dans `reports.py`**

Ajouter à `backend/app/cli/reports.py`, après `render_rescrape_report` :

```python
def render_club_labels_report(labels: list[dict]) -> str:
    """Inventaire des libellés de club, marqués reconnus (✓) ou non (✗).

    Le filtre club match à l'égalité sur une liste blanche : une variante non
    répertoriée sort des compteurs **sans aucun signal**. Ce rapport est le
    filet — il rend visible ce que le filtre ne voit pas.
    """
    lignes = ["=== LIBELLÉS CLUB ==="]
    if not labels:
        lignes.append("Aucun libellé de club en base.")
        return "\n".join(lignes)

    largeur = max(len(str(row["participations"])) for row in labels)
    for row in labels:
        marque = "✓" if row["is_tcn"] else "✗"
        lignes.append(f"  {row['participations']:>{largeur}}  {marque}  {row['club']}")

    lignes.append("")
    lignes.append(_ligne("Libellés distincts", len(labels)))
    lignes.append(_ligne("Libellés du club", sum(1 for row in labels if row["is_tcn"])))
    lignes.append(
        _ligne(
            "Participations du club",
            sum(row["participations"] for row in labels if row["is_tcn"]),
        )
    )
    return "\n".join(lignes)
```

et, après `emit_outcome` :

```python
def emit_report(rapport: str, payload: dict, *, json_output: bool) -> None:
    """Émet un rapport d'inventaire, sans code de sortie à porter.

    Pendant de `emit_outcome` pour les commandes qui ne pilotent pas de batch :
    même règle sur stdout (`--json` le garde pur), mais rien à signaler par le
    code de retour — un inventaire ne peut pas « échouer partiellement ».
    """
    emis = _echo(rapport, err=json_output)
    if json_output:
        _echo(json.dumps(payload, ensure_ascii=False))
    elif not emis:
        _echo(rapport, err=True)  # stdout coupé : le rapport se replie sur stderr
```

- [ ] **Step 5: Écrire la commande**

Créer `backend/app/cli/commands/club_labels.py` :

```python
"""Commande `club-labels` : inventaire des libellés de club vus en base. Zéro logique métier."""
import typer

from app.cli.reports import emit_report, render_club_labels_report
from app.core.club import is_tcn
from app.core.database import session_scope
from app.repositories import participation_repository


def club_labels(
    like: str | None = typer.Option(
        None, "--like", help="Ne montre que les libellés contenant ce fragment."
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Liste les libellés de club distincts, en marquant ceux reconnus comme TCN.

    Le filtre club match à l'égalité sur une liste blanche (`core/club.py`). Une
    variante non répertoriée — « TCN TRIATHLON », « T.C.N. » — fait donc sortir
    un membre des compteurs sans le moindre signal. Cette commande est le filet :

        uv run python -m app.cli club-labels --like nant
    """
    with session_scope() as db:
        rows = participation_repository.club_label_counts(db, like=like)

    labels = [
        {"club": club, "participations": count, "is_tcn": is_tcn(club)}
        for club, count in rows
    ]
    payload = {
        "labels": labels,
        "total_labels": len(labels),
        "tcn_labels": sum(1 for row in labels if row["is_tcn"]),
        "tcn_participations": sum(row["participations"] for row in labels if row["is_tcn"]),
    }
    emit_report(render_club_labels_report(labels), payload, json_output=json_output)
```

- [ ] **Step 6: Enregistrer la commande**

Dans `backend/app/cli/__init__.py`, ajouter l'import et l'enregistrement :

```python
from app.cli.commands.club_labels import club_labels
from app.cli.commands.import_sheet import import_sheet
from app.cli.commands.rescrape_db import rescrape_db
```

```python
app.command("club-labels")(club_labels)
app.command("import-sheet")(import_sheet)
app.command("rescrape-db")(rescrape_db)
```

- [ ] **Step 7: Lancer le test et vérifier qu'il passe**

Run: `cd backend && uv run pytest tests/test_cli/ -q`
Expected: PASS

- [ ] **Step 8: Lint et commit**

```bash
cd backend && uv run ruff check .
git add backend/app backend/tests
git commit -m "feat(cli): commande club-labels pour inventorier les libellés de club (#76)"
```

---

### Task 7: Le scraper Breizh Chrono réutilise le prédicat

**Files:**
- Modify: `backend/app/scrapers/breizhchrono.py:258-277`
- Modify: `backend/app/scrapers/klikego.py:302-303` (suppression de `_TCN_KEYWORDS`)
- Modify: `backend/tests/test_breizhchrono.py`

**Interfaces:**
- Consumes: `app.core.club.is_tcn` (Task 1).
- Produces: `klikego._TCN_KEYWORDS` n'existe plus. Un scraper qui importe
  `app.core.club` reste conforme aux couches (`core` est la base) ; c'est
  l'import croisé `breizhchrono → klikego._TCN_KEYWORDS` qui contournait.

**Ici la permissivité ne coûtait qu'en requêtes HTTP inutiles**, pas en
exactitude : les splits fins étaient récupérés pour 13 coureurs hors club sur la
course 15. Le resserrement est donc un gain accessoire, pas une correction de bug.

- [ ] **Step 1: Écrire le test**

Ajouter à `backend/tests/test_breizhchrono.py` :

```python
def test_les_splits_fins_ne_sont_cherches_que_pour_le_club(monkeypatch):
    """Un club nantais qui n'est pas le nôtre ne déclenche plus de requête (#76)."""
    import httpx

    from app.scrapers import breizhchrono
    from app.scrapers.base import ScrapedResult

    demandes: list[str] = []

    class _Client:
        def get(self, url: str):
            demandes.append(url)
            return httpx.Response(404, request=httpx.Request("GET", url))

    # `source_url` et `provider` sont les deux champs sans valeur par défaut.
    def _resultat(club: str, bib: str) -> ScrapedResult:
        return ScrapedResult(
            source_url="https://live.breizhchrono.com/evt",
            provider="breizhchrono",
            club=club,
            bib_number=bib,
        )

    results = [
        _resultat("TRI CLUB NANTAIS", "1"),
        _resultat("RACING CLUB NANTAIS *", "2"),
        _resultat("ASPTT RENNES", "3"),
    ]

    breizhchrono._fetch_tcn_fine_splits(
        "https://live.breizhchrono.com", "evt", "heat", results, _Client()
    )

    assert len(demandes) == 1
    assert "dossard=1" in demandes[0]
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_breizhchrono.py::test_les_splits_fins_ne_sont_cherches_que_pour_le_club -q`
Expected: FAIL — `assert 2 == 1` (« RACING CLUB NANTAIS * » déclenche encore une requête)

- [ ] **Step 3: Remplacer la liste maison par le prédicat**

Dans `backend/app/scrapers/breizhchrono.py`, remplacer le corps de
`_fetch_tcn_fine_splits` (lignes 266-277) :

```python
    from app.core.club import is_tcn
    from app.scrapers.klikego import _parse_detail
    for r in results:
        if is_tcn(r.club):
```

(le reste de la boucle est inchangé)

Dans `backend/app/scrapers/klikego.py`, supprimer les lignes 302-303 :

```python
# Mots-clés d'appartenance TCN, réutilisés par le scraper Breizh Chrono.
_TCN_KEYWORDS = ("nantais", "tcn", "tri club nant", "triathlon club nant")
```

- [ ] **Step 4: Lancer les tests scrapers et vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_breizhchrono.py tests/test_klikego.py -q`
Expected: PASS

- [ ] **Step 5: Lint et commit**

```bash
cd backend && uv run pytest -m "not integration" -q && uv run ruff check .
git add backend/app/scrapers backend/tests/test_breizhchrono.py
git commit -m "refactor(scrapers): Breizh Chrono réutilise le prédicat club unique (#76)"
```

---

### Task 8: Front — `scope` et `is_tcn`

**Files:**
- Delete: `frontend/lib/club-constants.ts`
- Delete: `frontend/lib/utils/club.ts`
- Delete: `frontend/lib/utils/club.test.ts`
- Modify: `frontend/lib/scope.ts`
- Modify: `frontend/lib/scope.test.ts`
- Modify: `frontend/lib/types.ts:28-45, 159-172`
- Modify: `frontend/lib/api/client.ts:72-77`
- Modify: `frontend/lib/api/server.ts:45-48`
- Modify: `frontend/app/resultats/page.tsx:23`
- Modify: `frontend/app/carte/page.tsx:8, 19, 29`
- Modify: `frontend/components/map/MapView.tsx:28-43`
- Modify: `frontend/app/dashboard/page.tsx:3, 30, 36-41`
- Modify: `frontend/app/dashboard/page.test.tsx`
- Modify: `frontend/app/club/page.tsx`
- Modify: `frontend/app/courses/[id]/page.tsx:9, 38, 65-71, 143`
- Modify: `frontend/components/results/RaceFinishers.tsx:5, 26, 63`
- Modify: `frontend/components/results/Leaderboard.tsx:15, 49`

**Interfaces:**
- Consumes: `scope=club`, `Participation.is_tcn` (Tasks 2 et 3).
- Produces:
  - `lib/scope.ts` : `SCOPE_PARAM`, `SCOPE_CLUB`, `scopeFromParam(scope?: string | null): "club" | undefined`,
    `isClubScope(scope?: string | null): boolean`. `clubFromScope` est supprimé.
  - `ParticipationFilters.scope?: "club"` remplace `club?: string`.
  - `Participation.is_tcn: boolean`.
  - `apiClient.getStats` / `getSeasons` / `getEventsGeo` prennent désormais un
    objet d'options (voir Step 4) — trois paramètres positionnels optionnels
    devenaient illisibles.

`frontend/lib/club-constants.ts` disparaît en entier : `TCN_CLUB_FILTER` n'a plus
de raison d'être, et `CLUB_COOKIE` qu'il exporte aussi n'est référencé nulle part
(vestige de l'ancien toggle global).

- [ ] **Step 1: Écrire les tests**

Remplacer `frontend/lib/scope.test.ts` par :

```ts
import { describe, expect, it } from "vitest";
import { SCOPE_CLUB, isClubScope, scopeFromParam } from "./scope";

describe("scopeFromParam", () => {
  it("rend la portée club quand le paramètre la demande", () => {
    expect(scopeFromParam("club")).toBe(SCOPE_CLUB);
  });

  it("rend undefined sinon, pour que le filtre soit simplement absent", () => {
    expect(scopeFromParam(undefined)).toBeUndefined();
    expect(scopeFromParam(null)).toBeUndefined();
    expect(scopeFromParam("tous")).toBeUndefined();
  });
});

describe("isClubScope", () => {
  it("reconnaît la portée club", () => {
    expect(isClubScope("club")).toBe(true);
    expect(isClubScope(undefined)).toBe(false);
  });
});
```

Dans `frontend/app/dashboard/page.test.tsx`, trois choses changent.

Supprimer l'import ligne 3 (`import { TCN_CLUB_FILTER } … `).

Adapter le mock (lignes 10-17) : `getStats` et `listSeasons` prennent désormais
un objet d'options, plus une chaîne.

```ts
vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (opts: unknown) => getStats(opts),
    listEvents: (filters: unknown) => listEvents(filters),
    listParticipations: (filters: unknown) => listParticipations(filters),
    listSeasons: (opts: unknown) => listSeasons(opts),
  },
}));
```

Remplacer les cinq assertions référençant `TCN_CLUB_FILTER` (lignes 59, 61, 64,
71, 85) par leur équivalent en portée :

```ts
    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
    expect(listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
    );
    expect(listParticipations).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "club" }),
    );
```
```ts
    expect(listSeasons).toHaveBeenCalledWith(expect.objectContaining({ scope: "club" }));
```

- [ ] **Step 2: Lancer les tests et vérifier qu'ils échouent**

Run: `cd frontend && npm test`
Expected: FAIL — `scope.test.ts` ne trouve pas `scopeFromParam`

- [ ] **Step 3: Réécrire `lib/scope.ts` et supprimer les deux modules morts**

```ts
/** Nom du paramètre d'URL pilotant la portée club (par page). */
export const SCOPE_PARAM = "scope";

/** Valeur du paramètre quand seul le club est affiché. */
export const SCOPE_CLUB = "club";

/**
 * Convertit le paramètre d'URL en valeur de `scope` pour l'API.
 * `?scope=club` → `"club"` ; sinon `undefined` (aucun filtre, tous les athlètes).
 *
 * Le front n'a plus d'opinion sur ce qu'est un membre du club : il transmet une
 * portée, le backend tranche (cf. `app/core/club.py`, issue #76).
 */
export function scopeFromParam(scope?: string | null): typeof SCOPE_CLUB | undefined {
  return scope === SCOPE_CLUB ? SCOPE_CLUB : undefined;
}

/** true si la portée club est active. */
export function isClubScope(scope?: string | null): boolean {
  return scope === SCOPE_CLUB;
}
```

```bash
cd frontend && rm lib/club-constants.ts lib/utils/club.ts lib/utils/club.test.ts
```

- [ ] **Step 4: Mettre à jour les types et les deux clients d'API**

Dans `frontend/lib/types.ts`, ajouter à l'interface `Participation` (après `club`) :

```ts
  /** Appartenance au club, tranchée par le backend (jamais recalculée ici). */
  is_tcn: boolean;
```

et dans `ParticipationFilters`, remplacer `club?: string;` par :

```ts
  scope?: "club";
  federal_only?: boolean;
```

Dans `frontend/lib/api/client.ts`, remplacer les trois méthodes (lignes 72-77) :

```ts
  getStats: (opts: { scope?: string; seasons?: number[]; federal_only?: boolean } = {}) =>
    request<Stats>(`/stats${toQuery(opts)}`),
  listSeasons: (opts: { scope?: string; federal_only?: boolean } = {}) =>
    request<Season[]>(`/stats/seasons${toQuery(opts)}`),
  getEventsGeo: (opts: { scope?: string; federal_only?: boolean } = {}) =>
    request<GeoEvent[]>(`/stats/events-geo${toQuery(opts)}`),
```

Dans `frontend/lib/api/server.ts`, remplacer les deux méthodes (lignes 45-48) :

```ts
  getStats: (opts: { scope?: string; seasons?: number[]; federal_only?: boolean } = {}) =>
    serverFetch<Stats>(`/stats${toQuery(opts)}`),
  listSeasons: (opts: { scope?: string; federal_only?: boolean } = {}) =>
    serverFetch<Season[]>(`/stats/seasons${toQuery(opts)}`),
```

`toQuery` ignore déjà `undefined` et `false` n'a pas à être envoyé : passer
`federal_only: undefined` plutôt que `false` quand le toggle est inactif.

- [ ] **Step 5: Migrer les pages qui passaient `club`**

`frontend/app/resultats/page.tsx` ligne 23 — remplacer l'import
`import { clubFromScope } from "@/lib/scope";` par
`import { scopeFromParam } from "@/lib/scope";` et la ligne du filtre :

```ts
    scope: scopeFromParam(sp.scope),
```

`frontend/app/carte/page.tsx` — même substitution d'import, puis :

```ts
  const scope = scopeFromParam(sp.get("scope"));
```
```tsx
        <MapView scope={scope} />
```

`frontend/components/map/MapView.tsx` — renommer la prop et la dépendance :

```tsx
export function MapView({ scope }: { scope?: string }) {
```
```ts
      .getEventsGeo({ scope })
```
```ts
  }, [scope]);
```

`frontend/app/club/page.tsx` — remplacer l'import de `TCN_CLUB_FILTER` par
`import { SCOPE_CLUB } from "@/lib/scope";` et les deux appels :

```ts
  const [stats, participations] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, page_size: 1000 }),
  ]);
```

`frontend/app/dashboard/page.tsx` — remplacer l'import de `TCN_CLUB_FILTER` par
`import { SCOPE_CLUB } from "@/lib/scope";`, supprimer la ligne 30
(`const club = TCN_CLUB_FILTER;`) et remplacer le bloc d'appels :

```ts
  const [stats, eventsPage, participations, seasons] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected }),
    apiServer.listEvents({ scope: SCOPE_CLUB, seasons: selected, page_size: 200 }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, seasons: selected, page_size: 5000 }),
    apiServer.listSeasons({ scope: SCOPE_CLUB }),
  ]);
```

- [ ] **Step 6: Migrer les trois consommateurs de `isTCN`**

`frontend/components/results/Leaderboard.tsx` — supprimer l'import ligne 15,
puis ligne 49 :

```ts
            const tcn = p.is_tcn;
```

`frontend/components/results/RaceFinishers.tsx` — supprimer l'import ligne 5,
puis lignes 26 et 63 :

```ts
  const filtered = filter === "tcn" ? participations.filter((p) => p.is_tcn) : participations;
```
```ts
            const own = p.is_tcn;
```

`frontend/app/courses/[id]/page.tsx` — supprimer l'import ligne 9, puis :

```ts
  const tcnCount = participations.filter((p) => p.is_tcn).length;
```

et l'agrégation « Top clubs » (lignes 65-71), qui doit désormais porter le
drapeau du backend plutôt que le recalculer :

```ts
  // ── Top clubs ──
  // Le drapeau TCN vient du backend : il est fonction du seul libellé, donc
  // identique pour toutes les participations d'un même groupe (issue #76).
  const clubMap = new Map<string, { count: number; isTcn: boolean }>();
  for (const p of participations) {
    const club = p.club?.trim();
    if (!club) continue;
    const entry = clubMap.get(club) ?? { count: 0, isTcn: p.is_tcn };
    entry.count += 1;
    clubMap.set(club, entry);
  }
  const clubs = [...clubMap.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 9);
```

et le rendu ligne 142-143 :

```tsx
            clubs.map(([name, { count, isTcn: own }]) => {
              return (
```

- [ ] **Step 7: Lancer les tests, le lint et le build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS — aucune référence résiduelle à `isTCN` ni à `TCN_CLUB_FILTER`
(le build échouerait sur l'import manquant)

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "refactor(front): lit is_tcn du backend et parle scope=club (#76)"
```

---

### Task 9: Front — le toggle des disciplines

**Files:**
- Modify: `frontend/lib/scope.ts`
- Modify: `frontend/lib/scope.test.ts`
- Create: `frontend/components/layout/DisciplineToggle.tsx`
- Modify: `frontend/app/dashboard/page.tsx`
- Modify: `frontend/app/dashboard/page.test.tsx`
- Modify: `frontend/app/club/page.tsx`

**Interfaces:**
- Consumes: `federal_only` (Task 5), `ParticipationFilters.federal_only` (Task 8).
- Produces:
  - `lib/scope.ts` : `SPORTS_PARAM = "sports"`, `SPORTS_ALL = "all"`,
    `federalOnlyFromParam(sports?: string | null): true | undefined`
  - `components/layout/DisciplineToggle.tsx` : composant client sans props.

**Le paramètre d'URL est en positif (`?sports=all` = tout afficher) alors que
l'API est en négatif (`federal_only=true` = filtrer).** L'URL décrit ce que
l'utilisateur voit, l'API ce qu'elle retire ; et l'absence de paramètre — le cas
par défaut, le plus fréquent — laisse l'URL propre.

- [ ] **Step 1: Écrire le test**

Ajouter à `frontend/lib/scope.test.ts` :

```ts
import { federalOnlyFromParam } from "./scope";

describe("federalOnlyFromParam", () => {
  it("filtre les autres disciplines par défaut", () => {
    expect(federalOnlyFromParam(undefined)).toBe(true);
    expect(federalOnlyFromParam(null)).toBe(true);
  });

  it("rend undefined quand l'utilisateur demande tout, pour ne rien envoyer à l'API", () => {
    expect(federalOnlyFromParam("all")).toBeUndefined();
  });
});
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

Run: `cd frontend && npm test -- scope`
Expected: FAIL — `federalOnlyFromParam is not a function`

- [ ] **Step 3: Compléter `lib/scope.ts`**

Ajouter à la fin du fichier :

```ts
/** Nom du paramètre d'URL ouvrant les compteurs aux disciplines hors fédération. */
export const SPORTS_PARAM = "sports";

/** Valeur du paramètre quand toutes les disciplines sont affichées. */
export const SPORTS_ALL = "all";

/**
 * Traduit le paramètre d'URL en filtre pour l'API.
 *
 * L'URL est en positif (`?sports=all` = tout montrer), l'API en négatif
 * (`federal_only=true` = retirer trail, course à pied et cyclisme) : l'URL dit
 * ce qu'on voit, l'API ce qu'elle enlève. Le défaut — filtrer — est un défaut
 * d'écran, pas d'API ; c'est ici qu'il est décidé.
 */
export function federalOnlyFromParam(sports?: string | null): true | undefined {
  return sports === SPORTS_ALL ? undefined : true;
}
```

- [ ] **Step 4: Écrire le composant**

Créer `frontend/components/layout/DisciplineToggle.tsx` :

```tsx
"use client";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";

import { SPORTS_ALL, SPORTS_PARAM } from "@/lib/scope";

/**
 * Ouvre les compteurs aux disciplines hors fédération triathlon.
 *
 * Par défaut, trail, course à pied et cyclisme sont exclus des compteurs du
 * club : ils restent consultables ailleurs, mais ne se lisent pas comme des
 * résultats de triathlon (issue #76).
 */
export function DisciplineToggle() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [pending, startTransition] = useTransition();
  const toutesDisciplines = sp.get(SPORTS_PARAM) === SPORTS_ALL;

  function basculer(toutes: boolean) {
    const params = new URLSearchParams(sp.toString());
    if (toutes) params.set(SPORTS_PARAM, SPORTS_ALL);
    else params.delete(SPORTS_PARAM);
    const qs = params.toString();
    startTransition(() => router.push(`${pathname}${qs ? `?${qs}` : ""}`));
  }

  return (
    <label
      data-pending={pending || undefined}
      className="inline-flex cursor-pointer items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground data-pending:opacity-70"
    >
      <input
        type="checkbox"
        checked={toutesDisciplines}
        onChange={(e) => basculer(e.target.checked)}
        className="size-3.5 accent-[var(--tcn-orange)]"
      />
      Inclure les autres disciplines
    </label>
  );
}
```

- [ ] **Step 5: Brancher le dashboard**

Dans `frontend/app/dashboard/page.tsx`, ajouter les imports :

```ts
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
```

lire le paramètre après `const sp = await searchParams;` :

```ts
  const federal_only = federalOnlyFromParam(sp.sports);
```

propager aux quatre appels :

```ts
  const [stats, eventsPage, participations, seasons] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: selected, federal_only }),
    apiServer.listEvents({ scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 200 }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, seasons: selected, federal_only, page_size: 5000 }),
    apiServer.listSeasons({ scope: SCOPE_CLUB, federal_only }),
  ]);
```

et afficher le contrôle à côté du sélecteur de saison (ligne 59) :

```tsx
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <DisciplineToggle />
          <SeasonSelector seasons={seasons} />
        </div>
```

- [ ] **Step 6: Brancher la page club**

`frontend/app/club/page.tsx` ne lisait aucun paramètre d'URL : il faut lui en
donner un.

```tsx
import { apiServer } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { DisciplineToggle } from "@/components/layout/DisciplineToggle";
import { ClubDashboard } from "@/components/club/ClubDashboard";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";

// La page Club est TOUJOURS filtrée sur le club, indépendamment de toute portée.
export default async function ClubPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);

  const [stats, participations] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, federal_only }),
    apiServer.listParticipations({ scope: SCOPE_CLUB, federal_only, page_size: 1000 }),
  ]);

  return (
    <PageShell>
      <div className="space-y-8">
        <PageHeader
          eyebrow="Triathlon Club Nantais"
          title="Espace club"
          description="Synthèse, podiums et athlètes du Triathlon Club Nantais."
          actions={<DisciplineToggle />}
        />
        <ClubDashboard stats={stats} participations={participations} />
      </div>
    </PageShell>
  );
}
```

Vérifier au passage que `PageHeader` accepte bien une prop `actions` — la page
Résultats l'utilise déjà (`frontend/app/resultats/page.tsx:41`).

- [ ] **Step 7: Compléter le test du dashboard**

Ajouter à `frontend/app/dashboard/page.test.tsx` un cas couvrant les deux états :

```ts
  it("exclut les autres disciplines par défaut et les inclut sur demande", async () => {
    await renderDashboard({});
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: true }),
    );

    vi.clearAllMocks();
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue(EVENTS_PAGE);
    listParticipations.mockResolvedValue(PARTICIPATIONS);
    listSeasons.mockResolvedValue(SEASONS);

    await renderDashboard({ sports: "all" });
    expect(getStats).toHaveBeenCalledWith(
      expect.objectContaining({ federal_only: undefined }),
    );
  });
```

`renderDashboard(searchParams)` est le helper déjà présent dans le fichier
(ligne 50) : il appelle le composant serveur avec
`{ searchParams: Promise.resolve(searchParams) }`. Le re-armement des mocks entre
les deux rendus est nécessaire parce que `beforeEach` ne rejoue pas en cours de test.

- [ ] **Step 8: Lancer les tests, le lint et le build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add frontend
git commit -m "feat(front): toggle « inclure les autres disciplines » sur le dashboard et la page club (#76)"
```

---

### Task 10: Documentation et vérification de bout en bout

**Files:**
- Modify: `AGENTS.md`
- Test: la suite complète, backend et frontend

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: rien de fonctionnel.

- [ ] **Step 1: Documenter la commande et le prédicat dans `AGENTS.md`**

Dans la section « Commandes », sous le bloc « CLI de batch », ajouter :

```
uv run python -m app.cli club-labels --like nant   # libellés club vus en base, marqués TCN ou non
```

Dans la section « Architecture backend », à la ligne décrivant `app/core/`,
ajouter `club.py` et `discipline.py` à l'énumération :

```
- `app/core/` — `config.py` (pydantic-settings), `logging.py`, `database.py`,
  `exceptions.py`, `time.py`, `club.py` (appartenance au TCN : **liste blanche**
  de libellés, match à l'égalité — cf. #76), `discipline.py` (disciplines
  fédérales vs trail / course à pied / cyclisme).
```

Dans la section « Conventions scrapers », remplacer la ligne sur le filtre club :

```
- Identification club : **une seule définition**, `app/core/club.py`
  (`is_tcn` / `tcn_clause`). Ne jamais la réimplémenter ailleurs — front et
  scraper l'avaient fait, les trois listes ont divergé et tout libellé contenant
  « nantais » a été compté comme TCN (#76). Le front lit le champ `is_tcn` du DTO.
```

Ajouter, après la sous-section « Cache TTL », une sous-section :

```
### Portée club et disciplines

Deux paramètres traversent l'API de lecture, sur le même patron que `seasons` :

- `scope=club` — restreint aux membres du TCN. Remplace l'ancien `club`, un
  texte libre cherché en sous-chaîne : c'est lui qui laissait la définition du
  club chez l'appelant, et un `%nantais%` comptait les clubs d'athlétisme
  nantais (#76).
- `federal_only=true` — retire les disciplines hors fédération triathlon
  (`trail`, `course-a-pied*`, `cyclisme*`). **Défaut à `false` : l'API reste
  neutre.** Ce sont le dashboard et la page club qui l'activent, via le toggle
  « Inclure les autres disciplines ». Un défaut à `true` amputerait
  silencieusement tout futur appelant.
```

- [ ] **Step 2: Lancer la suite backend complète**

Run: `cd backend && uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS — la suite comptait ≈ 510 tests avant ce plan, qui en ajoute une
trentaine ; aucun échec, aucun test ignoré.

- [ ] **Step 3: Lancer la suite frontend complète**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 4: Vérifier à la main sur des données réelles**

Démarrer l'API (`cd backend && uv run uvicorn app.main:app --reload --port 8001`)
sur une base contenant la course 15, puis :

```bash
curl -s "http://localhost:8001/api/v1/participations?scope=club&course_id=15" | jq 'length'
# attendu : 2   (15 avant le correctif)

curl -s "http://localhost:8001/api/v1/stats?scope=club" | jq '.total, .events'
# attendu : 236, 12

curl -s "http://localhost:8001/api/v1/stats?scope=club&federal_only=true" | jq '.total, .events'
# attendu : 234, 11

cd backend && uv run python -m app.cli club-labels --like nant
# attendu : ✓ sur TRIATHLON CLUB NANTAIS et TRI CLUB NANTAIS,
#           ✗ sur MARATHONIENS NANTAIS, STADE NANTAIS AC, RACING CLUB NANTAIS *
```

Si les compteurs diffèrent, ne pas ajuster les chiffres attendus : ils viennent
d'une mesure sur la prod du 25/07/2026 (cf. spec). Un écart signale soit une
donnée nouvelle depuis, soit un bug — vérifier avec `club-labels` avant de
conclure.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs: portée club, disciplines et commande club-labels (#76)"
```

---

## Ce que ce plan ne fait pas

Rappelés ici pour qu'ils ne soient pas ajoutés par inadvertance en cours de route :

- **Aucune migration ni nettoyage de données.** Les faux positifs sont calculés
  à la requête, ils disparaissent d'eux-mêmes.
- **Pas de repli sur `Athlete.club`** quand `Participation.club` est vide.
- **Pas de traitement du plafond `page_size=5000`** du dashboard.
- **Pas de blocage d'import** des épreuves hors fédération : elles sont
  importées et restent consultables.
