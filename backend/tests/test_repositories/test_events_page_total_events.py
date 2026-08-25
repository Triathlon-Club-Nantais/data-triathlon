"""Égalité entre les deux formules de `total_events` (#584).

`_grouped_events_query` regroupe `participations` par `Course.id` — une ligne
par épreuve retenue. Compter les lignes de ce résultat (`COUNT` sur la
sous-requête groupée, la formule en place) et compter les `course_id`
distincts parmi les participations qui satisfont les mêmes filtres
(`COUNT(DISTINCT participations.course_id)`, la formule de remplacement)
tiennent le même nombre : `_apply_filters` est la clause partagée des deux
requêtes, et aucune épreuve ne peut exister dans l'une sans l'autre — une
`Course` sans participation filtrée n'a pas de ligne groupée, et réciproquement.

Préalable explicite de la mesure de #584 avant de remplacer la formule dans
`events_page` : douze fois plus cher, même valeur (150 sur le jeu de sondage).
Ce test croise les quatre familles de filtre citées par la mesure — portée
club, dates, recherche, `federal_only` — plus les saisons et un doublon
nom+date (cas Mesquer, #567), pour couvrir les endroits où deux `COUNT`
pourraient diverger : dates absentes, participations en attente de
validation, épreuves à égalité de nom.
"""
from datetime import date

import pytest
from sqlalchemy import func

from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository
from app.repositories.participation_repository import _apply_filters, _grouped_events_query

_DEFAULT_FILTERS = {
    "name": None,
    "event_type": None,
    "event_name": None,
    "club_only": False,
    "date_from": None,
    "date_to": None,
    "seasons": None,
    "federal_only": False,
}


def _old_total_events(db, **filters) -> int:
    """Formule en place : COUNT sur la sous-requête groupée (~70 ms mesurés / 31k lignes)."""
    grouped = _grouped_events_query(db, **{**_DEFAULT_FILTERS, **filters})
    return db.query(func.count()).select_from(grouped.subquery()).scalar() or 0


def _new_total_events(db, **filters) -> int:
    """Formule de remplacement : COUNT(DISTINCT course_id) filtré (~6 ms mesurés)."""
    q = _apply_filters(db.query(Participation), db, **{**_DEFAULT_FILTERS, **filters})
    return q.with_entities(func.count(func.distinct(Participation.course_id))).scalar() or 0


@pytest.fixture
def jeu_realiste(db_session):
    """Dix épreuves croisant saison, discipline fédérale/non, portée club, date
    absente et doublon nom+date — plus une épreuve entièrement en attente."""
    db = db_session
    tcn = athlete_repository.get_or_create(db, nom="DUPONT", prenom="Jean", club="TCN")
    tcn2 = athlete_repository.get_or_create(
        db, nom="MARTIN", prenom="Alice", club="Triathlon Club Nantais"
    )
    autre = athlete_repository.get_or_create(db, nom="DURAND", prenom="Paul", club="ASPTT Rennes")

    courses = {
        "nantes_m": course_repository.get_or_create(
            db, name="Triathlon de Nantes", event_date=date(2025, 6, 1), event_type="triathlon-m"
        ),
        # Doublon nom+date, event_type différent (cas Mesquer, #567).
        "nantes_s": course_repository.get_or_create(
            db, name="Triathlon de Nantes", event_date=date(2025, 6, 1), event_type="triathlon-s"
        ),
        "trail_dunes": course_repository.get_or_create(
            db, name="Trail des Dunes", event_date=date(2025, 7, 1), event_type="trail"
        ),
        "marathon_paris": course_repository.get_or_create(
            db,
            name="Marathon de Paris",
            event_date=date(2025, 4, 1),
            event_type="course-a-pied-marathon",
        ),
        "ironman_nice": course_repository.get_or_create(
            db, name="Ironman Nice", event_date=date(2024, 8, 15), event_type="triathlon-l"
        ),
        "duathlon_vendee": course_repository.get_or_create(
            db, name="Duathlon Vendée", event_date=date(2023, 9, 10), event_type="duathlon"
        ),
        "sans_date": course_repository.get_or_create(
            db, name="Triathlon Sans Date", event_date=None, event_type="triathlon-s"
        ),
        "cyclisme": course_repository.get_or_create(
            db, name="Cyclisme Challenge", event_date=date(2025, 5, 1), event_type="cyclisme-route"
        ),
        "xl_futur": course_repository.get_or_create(
            db, name="Triathlon XL", event_date=date(2026, 1, 1), event_type="triathlon-m"
        ),
        "swimrun": course_repository.get_or_create(
            db, name="Swimrun Ocean", event_date=date(2025, 3, 1), event_type="swimrun"
        ),
    }

    bib = 0
    for course in courses.values():
        bib += 1
        participation_repository.create(
            db, athlete_id=tcn.id, course_id=course.id, bib_number=str(bib), club="TCN"
        )
        bib += 1
        participation_repository.create(
            db,
            athlete_id=tcn2.id,
            course_id=course.id,
            bib_number=str(bib),
            club="Triathlon Club Nantais",
        )
        bib += 1
        participation_repository.create(
            db, athlete_id=autre.id, course_id=course.id, bib_number=str(bib), club="ASPTT Rennes"
        )

    # Une épreuve dont l'unique résultat est en attente : ne doit compter dans
    # aucune des deux formules — sans quoi la sous-requête groupée (INNER JOIN)
    # et le COUNT DISTINCT filtré divergeraient sur ce cas précis.
    pending_only = course_repository.get_or_create(
        db, name="Trail En Attente", event_date=date(2025, 8, 1), event_type="trail"
    )
    participation_repository.create(
        db,
        athlete_id=autre.id,
        course_id=pending_only.id,
        bib_number="900",
        club="ASPTT Rennes",
        is_pending_validation=True,
    )
    # Une participation en attente sur une épreuve par ailleurs validée : ne
    # doit rien ajouter au compte de cette épreuve (déjà comptée une fois).
    participation_repository.create(
        db,
        athlete_id=tcn.id,
        course_id=courses["nantes_m"].id,
        bib_number="901",
        club="TCN",
        is_pending_validation=True,
    )
    db.flush()
    return courses


_FILTER_COMBOS = [
    pytest.param({}, id="sans_filtre"),
    pytest.param({"club_only": True}, id="portee_club"),
    pytest.param({"date_from": date(2025, 1, 1)}, id="date_from"),
    pytest.param({"date_to": date(2024, 12, 31)}, id="date_to"),
    pytest.param(
        {"date_from": date(2025, 1, 1), "date_to": date(2025, 6, 30)}, id="plage_de_dates"
    ),
    pytest.param({"event_name": "tri"}, id="recherche_nom_epreuve"),
    pytest.param({"event_name": "Nantes"}, id="recherche_nom_epreuve_doublon"),
    pytest.param({"name": "DUPONT"}, id="recherche_nom_athlete"),
    pytest.param({"federal_only": True}, id="federal_only"),
    pytest.param({"seasons": [2025]}, id="une_saison"),
    pytest.param({"seasons": [2023, 2025]}, id="saisons_non_contigues"),
    pytest.param(
        {"club_only": True, "federal_only": True, "seasons": [2024]},
        id="combinaison_club_federal_saison",
    ),
    pytest.param(
        {"date_from": date(2025, 1, 1), "federal_only": True, "event_name": "tri"},
        id="combinaison_dates_federal_recherche",
    ),
]


@pytest.mark.parametrize("filters", _FILTER_COMBOS)
def test_total_events_meme_valeur_count_groupe_et_count_distinct(db_session, jeu_realiste, filters):
    old = _old_total_events(db_session, **filters)
    new = _new_total_events(db_session, **filters)
    assert old == new
    # Sanity : chaque combinaison choisie garde au moins une épreuve, sinon
    # l'égalité 0 == 0 ne prouverait rien de la formule elle-même.
    assert old > 0


def test_total_events_zero_des_deux_cotes_sur_filtre_sans_resultat(db_session, jeu_realiste):
    """Un filtre qui n'attrape rien rend 0 des deux côtés, jamais une erreur."""
    old = _old_total_events(db_session, event_name="ne-matche-rien-xyz")
    new = _new_total_events(db_session, event_name="ne-matche-rien-xyz")
    assert old == new == 0


def test_total_events_epreuve_entierement_en_attente_exclue_des_deux_cotes(db_session, jeu_realiste):
    """L'épreuve dont l'unique résultat est en attente (#270) ne compte nulle part."""
    old = _old_total_events(db_session, event_name="En Attente")
    new = _new_total_events(db_session, event_name="En Attente")
    assert old == new == 0
