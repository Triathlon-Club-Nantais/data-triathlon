from collections import Counter
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import joinedload

from app.core.club import tcn_clause
from app.core.discipline import federal_clause
from app.core.validation import validated_clause
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository
from app.repositories.participation_repository import season_clause
from app.services import stats_service
from app.services.stats_service import _accumule, _bucket, _meilleur_rang


def _seed(db):
    a1 = athlete_repository.get_or_create(db, nom="DUPONT", prenom="Jean", club="TCN")
    a2 = athlete_repository.get_or_create(db, nom="MARTIN", prenom="Paul", club="ASPTT")
    c = course_repository.get_or_create(
        db, name="Tri de Nantes", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(db, athlete_id=a1.id, course_id=c.id, bib_number="1", club="TCN")
    participation_repository.create(db, athlete_id=a2.id, course_id=c.id, bib_number="2", club="ASPTT")
    db.flush()


def test_get_stats_global(db_session):
    _seed(db_session)
    stats = stats_service.get_stats(db_session)
    assert stats["total"] == 2
    assert stats["athletes"] == 2
    assert stats["events"] == 1
    assert stats["by_type"] == {"triathlon-m": 2}
    assert stats["by_month"] == {"2026-05": 2}
    assert len(stats["recent"]) == 2


def test_get_stats_filtered_by_club(db_session):
    _seed(db_session)
    stats = stats_service.get_stats(db_session, club_only=True)
    assert stats["total"] == 1
    assert stats["athletes"] == 1


def test_get_stats_ignore_une_participation_pendante(db_session):
    """#270, FR-021 — au niveau service, pas seulement au niveau repository."""
    _seed(db_session)
    avant = stats_service.get_stats(db_session)

    autre = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Léa", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri de Nantes", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=autre.id, course_id=course.id, bib_number="99",
        club="TCN", is_pending_validation=True,
    )
    db_session.flush()

    apres = stats_service.get_stats(db_session)
    assert apres["total"] == avant["total"]
    assert apres["athletes"] == avant["athletes"]


def test_list_events_counts_tcn(db_session):
    _seed(db_session)
    page = stats_service.list_events(db_session)
    assert page["total_events"] == 1
    assert page["total_participations"] == 2
    assert len(page["items"]) == 1
    event = page["items"][0]
    assert event["total"] == 2
    assert event["tcn_count"] == 1
    assert event["id"] > 0
    assert event["is_relay"] is False


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


def _participation_rang(
    db, *, athlete_gender="", rank_overall=None, rank_category=None, rank_gender=None
):
    """Une participation isolée, sur sa propre épreuve, pour ne pas polluer les
    autres tests de rang (chaque appel crée son propre athlète/course)."""
    unique = f"{rank_overall}-{rank_category}-{rank_gender}-{athlete_gender}-{id(object())}"
    athlete = athlete_repository.get_or_create(
        db, nom="RANG", prenom=unique, gender=athlete_gender, club="TCN"
    )
    course = course_repository.get_or_create(
        db, name=f"Course rang {unique}", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        club="TCN",
        rank_overall=rank_overall,
        rank_category=rank_category,
        rank_gender=rank_gender,
    )
    db.flush()


def test_get_stats_rank_counters_vide_sans_participation(db_session):
    stats = stats_service.get_stats(db_session)
    assert stats["rank_counters"] == {
        "scratch": {"victories": 0, "podiums": 0, "top10": 0},
        "category": {"victories": 0, "podiums": 0, "top10": 0},
        "all": {"victories": 0, "podiums": 0, "top10": 0},
        "gender": {
            "women": {"victories": 0, "podiums": 0, "top10": 0},
            "men": {"victories": 0, "podiums": 0, "top10": 0},
        },
    }


def test_get_stats_rank_counters_scratch_et_category_independants(db_session):
    # Victoire scratch (rank_overall=1) mais hors top10 en catégorie (rank_category=15).
    _participation_rang(db_session, rank_overall=1, rank_category=15)
    # Podium en catégorie (rank_category=3) mais hors classement scratch (rank_overall=None).
    _participation_rang(db_session, rank_category=3)

    stats = stats_service.get_stats(db_session)
    rc = stats["rank_counters"]

    assert rc["scratch"] == {"victories": 1, "podiums": 1, "top10": 1}
    assert rc["category"] == {"victories": 0, "podiums": 1, "top10": 1}


def test_get_stats_rank_counters_emboitement_victoires_podiums_top10(db_session):
    """victoires ≤ podiums ≤ top10, même invariant que côté front (issue #77)."""
    _participation_rang(db_session, rank_overall=1)
    _participation_rang(db_session, rank_overall=3)
    _participation_rang(db_session, rank_overall=10)
    _participation_rang(db_session, rank_overall=200)

    scratch = stats_service.get_stats(db_session)["rank_counters"]["scratch"]
    assert scratch == {"victories": 1, "podiums": 2, "top10": 3}


def test_get_stats_rank_counters_all_prend_le_min_des_trois(db_session):
    # rank_overall=50 mais rank_category=1 : le mode "all" doit capter la victoire.
    _participation_rang(db_session, rank_overall=50, rank_category=1, rank_gender=20)

    rc = stats_service.get_stats(db_session)["rank_counters"]
    assert rc["all"] == {"victories": 1, "podiums": 1, "top10": 1}
    assert rc["scratch"] == {"victories": 0, "podiums": 0, "top10": 0}


def test_get_stats_rank_counters_gender_ventile_f_h(db_session):
    _participation_rang(db_session, athlete_gender="F", rank_gender=1)
    _participation_rang(db_session, athlete_gender="M", rank_gender=2)
    _participation_rang(db_session, athlete_gender="f", rank_gender=8)  # casse ignorée

    rc = stats_service.get_stats(db_session)["rank_counters"]["gender"]
    assert rc["women"] == {"victories": 1, "podiums": 1, "top10": 2}
    assert rc["men"] == {"victories": 0, "podiums": 1, "top10": 1}


def test_get_stats_rank_counters_gender_ignore_les_genres_non_f_m(db_session):
    """Comportement préservé du front (`club-aggregate.ts`) : seuls "F"/"M"
    comptent, un athlète "H" n'entre dans aucun des deux compteurs."""
    _participation_rang(db_session, athlete_gender="H", rank_gender=1)

    rc = stats_service.get_stats(db_session)["rank_counters"]["gender"]
    assert rc["women"] == {"victories": 0, "podiums": 0, "top10": 0}
    assert rc["men"] == {"victories": 0, "podiums": 0, "top10": 0}


def test_get_stats_rank_counters_ignore_les_rangs_nuls_ou_absents(db_session):
    _participation_rang(db_session, rank_overall=None)
    _participation_rang(db_session, rank_overall=0)  # jamais valide, garde `>= 1`

    rc = stats_service.get_stats(db_session)["rank_counters"]["scratch"]
    assert rc == {"victories": 0, "podiums": 0, "top10": 0}


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


# ── Synthèse d'épreuve (issue #163) ──────────────────────────────────────────
#
# Les six blocs de la page d'épreuve étaient calculés dans le navigateur sur le
# classement entier. Ils passent au backend, qui doit rendre exactement les
# mêmes valeurs — limites d'affichage et découpage d'histogramme compris.


def _epreuve(db, lignes):
    """`lignes` : (nom, prenom, gender, club, category, status, total_time, splits)."""
    course = course_repository.get_or_create(
        db, name="Tri Synthèse", event_date=date(2026, 7, 4), event_type="triathlon-m"
    )
    for index, (nom, prenom, gender, club, categorie, status, temps, splits) in enumerate(lignes):
        athlete = athlete_repository.get_or_create(
            db, nom=nom, prenom=prenom, gender=gender, club=club
        )
        participation_repository.create(
            db,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=str(index),
            club=club,
            category=categorie,
            status=status,
            total_time=temps,
            splits=splits,
        )
    db.flush()
    return course


def test_course_summary_ventile_les_statuts(db_session):
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "TCN", "SEM", "finisher", "01:00:00", None),
            ("B", "Deux", "F", "ASPTT", "SEF", "DNF", None, None),
            ("C", "Trois", "M", "ASPTT", "SEM", "DSQ", None, None),
            ("D", "Quatre", "F", "ASPTT", "V1F", "DNS", None, None),
            ("E", "Cinq", "", "ASPTT", None, "", None, None),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["total"] == 5
    assert synthese["finishers"] == 1
    assert synthese["non_finishers"] == 3
    assert synthese["unknown"] == 1
    # Invariant : les trois compteurs somment toujours au total (#23).
    assert (
        synthese["finishers"] + synthese["non_finishers"] + synthese["unknown"]
        == synthese["total"]
    )
    # `non_finishers` agrégeait trois statuts distincts sous un seul chiffre,
    # trompeur : un DNS n'a jamais couru, un DSQ a fini disqualifié (#331).
    assert synthese["dnf"] == 1
    assert synthese["dsq"] == 1
    assert synthese["dns"] == 1
    assert synthese["dnf"] + synthese["dsq"] + synthese["dns"] == synthese["non_finishers"]


def test_course_summary_genre_ignore_les_lignes_sans_genre_lisible(db_session):
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", None, "finisher", None, None),
            ("B", "Deux", "H", "ASPTT", None, "finisher", None, None),
            ("C", "Trois", "F", "ASPTT", None, "finisher", None, None),
            ("D", "Quatre", "W", "ASPTT", None, "finisher", None, None),
            ("E", "Cinq", "U", "ASPTT", None, "finisher", None, None),
            ("F", "Six", "", "ASPTT", None, "finisher", None, None),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert (synthese["male"], synthese["female"]) == (2, 2)
    # `U` et vide ne sont comptés d'aucun côté : la somme ne fait pas le total.
    assert synthese["male"] + synthese["female"] < synthese["total"]


def test_course_summary_club_et_compteur_tcn(db_session):
    """Les variantes de libellé TCN (issue #200) sont fusionnées sous un nom canonique.

    Les chronométreurs saisissent le club en verbatim : `TRI CLUB NANTAIS`,
    `Triathlon club nantais`, `TCN` cohabitent en base (146/38/1 fois mesurés
    sur la prod). Les compter séparément dans « Top clubs » produit deux à
    trois lignes pour le même club — ce que corrige la fusion.
    """
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "Triathlon Club Nantais", None, "finisher", None, None),
            ("B", "Deux", "M", "TCN", None, "finisher", None, None),
            ("C", "Trois", "M", "TRI CLUB NANTAIS", None, "finisher", None, None),
            ("D", "Quatre", "M", "ASPTT", None, "finisher", None, None),
            ("E", "Cinq", "M", None, None, "finisher", None, None),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["tcn_count"] == 3
    clubs_par_nom = {c["name"]: c for c in synthese["clubs"]}
    # Un club vide n'entre pas dans le classement des clubs.
    assert set(clubs_par_nom) == {"Triathlon Club Nantais", "ASPTT"}
    # Les 3 lignes TCN sont fusionnées sous le libellé canonique.
    assert clubs_par_nom["Triathlon Club Nantais"]["is_tcn"] is True
    assert clubs_par_nom["Triathlon Club Nantais"]["count"] == 3
    assert clubs_par_nom["ASPTT"]["is_tcn"] is False
    assert clubs_par_nom["ASPTT"]["count"] == 1


def test_course_summary_borne_categories_a_8_et_clubs_a_9(db_session):
    lignes = []
    for index in range(12):
        # Effectifs décroissants : la catégorie 0 est la plus nombreuse.
        for occurrence in range(12 - index):
            lignes.append(
                (
                    f"N{index}",
                    f"P{occurrence}",
                    "M",
                    f"CLUB{index}",
                    f"CAT{index}",
                    "finisher",
                    None,
                    None,
                )
            )
    course = _epreuve(db_session, lignes)

    synthese = stats_service.course_summary(db_session, course.id)

    assert len(synthese["categories"]) == 8
    assert len(synthese["clubs"]) == 9
    assert [c["name"] for c in synthese["categories"]][:2] == ["CAT0", "CAT1"]
    assert [c["count"] for c in synthese["categories"]] == sorted(
        [c["count"] for c in synthese["categories"]], reverse=True
    )


def test_course_summary_split_keys_vues_sur_au_moins_une_participation(db_session):
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", None, "finisher", "01:00:00", {"swim": "00:20:00"}),
            ("B", "Deux", "M", "ASPTT", None, "finisher", "01:10:00", {"swim": "", "bike": "00:30:00"}),
            ("C", "Trois", "M", "ASPTT", None, "finisher", "01:20:00", None),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    # Ordre d'apparition, et une clé à valeur vide ne compte pas.
    assert synthese["split_keys"] == ["swim", "bike"]


def test_course_summary_ne_charge_que_les_colonnes_utiles(db_session):
    """FR-022 : pas d'objet ORM hydraté, pas de relation chargée, une requête.

    Sans ce garde, un `joinedload` réintroduit un jour ferait retomber la
    synthèse dans le coût que la feature #163 supprime, sans rien signaler.
    """
    from sqlalchemy import event

    course = _epreuve(
        db_session,
        [("A", "Un", "M", "ASPTT", "SEM", "finisher", "01:00:00", None)],
    )
    db_session.flush()

    lignes = participation_repository.summary_rows_for_course(db_session, course.id)
    assert lignes and not hasattr(lignes[0], "__mapper__")
    assert len(lignes[0]) == 6

    requetes = []

    def _mouchard(conn, cursor, statement, *reste):
        requetes.append(statement)

    # On instrumente `course_summary` et non la seule lecture : un lazy-load
    # réintroduit dans la boucle d'agrégation resterait invisible sinon.
    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _mouchard)
    try:
        stats_service.course_summary(db_session, course.id)
    finally:
        event.remove(engine, "before_cursor_execute", _mouchard)
    assert len(requetes) == 1, requetes


def test_course_summary_histogramme_meme_decoupage_que_le_front(db_session):
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", None, "finisher", "01:00:00", None),  # 3600 s
            ("B", "Deux", "M", "ASPTT", None, "finisher", "01:04:59", None),  # même tranche
            ("C", "Trois", "M", "ASPTT", None, "finisher", "01:10:00", None),  # +2 tranches
        ],
    )

    histogramme = stats_service.course_summary(db_session, course.id)["histogram"]

    assert histogramme["bucket_sec"] == 300
    assert histogramme["start_sec"] == 3600
    assert histogramme["bars"] == [2, 0, 1]


def test_course_summary_histogramme_ignore_les_temps_absents(db_session):
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", None, "DNF", None, None),
            ("B", "Deux", "M", "ASPTT", None, "DNS", "", None),
            ("C", "Trois", "M", "ASPTT", None, "DSQ", "00:00:00", None),
        ],
    )

    assert stats_service.course_summary(db_session, course.id)["histogram"] is None


def test_course_summary_histogramme_plafonne_a_60_tranches(db_session):
    lignes = [
        ("A", "Un", "M", "ASPTT", None, "finisher", "00:05:00", None),
        ("B", "Deux", "M", "ASPTT", None, "finisher", "12:00:00", None),
    ]
    course = _epreuve(db_session, lignes)

    histogramme = stats_service.course_summary(db_session, course.id)["histogram"]

    assert len(histogramme["bars"]) == 60
    # Le dernier temps retombe dans la dernière tranche, il n'est pas perdu.
    assert sum(histogramme["bars"]) == 2


def test_course_summary_epreuve_vide(db_session):
    course = course_repository.get_or_create(
        db_session, name="Tri Désert", event_date=date(2026, 7, 5), event_type="triathlon-m"
    )
    db_session.flush()

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["total"] == 0
    assert (synthese["finishers"], synthese["non_finishers"], synthese["unknown"]) == (0, 0, 0)
    assert (synthese["male"], synthese["female"], synthese["tcn_count"]) == (0, 0, 0)
    assert synthese["categories"] == []
    assert synthese["clubs"] == []
    assert synthese["split_keys"] == []
    assert synthese["histogram"] is None


def test_course_summary_departage_les_ex_aequo_par_libelle(db_session):
    """Sinon l'ordre dépend de l'ordre de lecture en base, donc de l'import."""
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ZED TRI", "V2H", "finisher", None, None),
            ("B", "Deux", "M", "ALPHA TRI", "SEM", "finisher", None, None),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert [c["name"] for c in synthese["clubs"]] == ["ALPHA TRI", "ZED TRI"]
    assert [c["name"] for c in synthese["categories"]] == ["SEM", "V2H"]


def test_course_summary_denominateur_des_categories_porte_sur_toutes(db_session):
    """Le dénominateur des pourcentages n'est pas la somme des 8 rendues.

    Sur une épreuve à plus de 8 catégories — le cas nominal d'un triathlon —
    rapporter les barres au seul top 8 les gonfle et les fait sommer à 100 %,
    ce qu'elles ne font pas. Mesuré à 1,28× sur une épreuve à 20 catégories.
    """
    lignes = []
    for index in range(12):
        for occurrence in range(12 - index):
            lignes.append(
                (f"N{index}", f"P{occurrence}", "M", "ASPTT", f"CAT{index}", "finisher", None, None)
            )
    # Une ligne sans catégorie : elle ne compte dans aucun des deux dénominateurs.
    lignes.append(("SANSCAT", "X", "M", "ASPTT", None, "finisher", None, None))
    course = _epreuve(db_session, lignes)

    synthese = stats_service.course_summary(db_session, course.id)

    assert len(synthese["categories"]) == 8
    total_rendues = sum(c["count"] for c in synthese["categories"])
    assert synthese["categories_total"] == 78  # 12 + 11 + … + 1
    assert synthese["categories_total"] > total_rendues
    assert synthese["categories_total"] < synthese["total"]  # la ligne sans catégorie est hors jeu


# ── Non-régression #580 : refonte SQL de get_stats ───────────────────────────
#
# `get_stats` chargeait, via `for_stats`, toutes les participations (avec
# `course`/`athlete` joints) et agrégeait en Python — 724 ms mesurés sur
# 31 280 participations pour des compteurs qu'un `GROUP BY` rend en 8 ms
# (#580). `_legacy_get_stats` ci-dessous est une copie figée de l'algorithme
# d'avant refonte — elle ne dépend plus de `for_stats`, supprimée, ni de
# `stats_service._rank_counters`, dont la signature a changé — et sert
# d'oracle : `stats_service.get_stats`, désormais posé sur cinq requêtes SQL
# agrégées, doit lui rendre un résultat identique au caractère près sur un
# jeu de données couvrant plusieurs types d'épreuve, plusieurs mois, plusieurs
# genres, des rangs variés (dont une égalité et un athlète sans aucun rang),
# et un filtre de saison qui fait disparaître un mois entier du résultat.


def _legacy_for_stats(db, *, club_only=False, seasons=None, federal_only=False):
    """Copie figée de l'ancienne `participation_repository.for_stats` (#580)."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    ).filter(validated_clause(Participation.is_pending_validation))
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    if seasons:
        q = q.filter(season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.all()


def _legacy_rank_counters(parts):
    """Copie figée de l'ancienne `stats_service._rank_counters` (#580), qui
    bouclait sur des `Participation` entières plutôt que sur des tuples."""
    scratch, category, tous = _bucket(), _bucket(), _bucket()
    genre = {"women": _bucket(), "men": _bucket()}
    for p in parts:
        _accumule(scratch, p.rank_overall)
        _accumule(category, p.rank_category)
        _accumule(tous, _meilleur_rang([p.rank_overall, p.rank_gender, p.rank_category]))
        g = (p.athlete.gender or "").upper() if p.athlete else ""
        if g == "F":
            _accumule(genre["women"], p.rank_gender)
        elif g == "M":
            _accumule(genre["men"], p.rank_gender)
    return {"scratch": scratch, "category": category, "all": tous, "gender": genre}


def _legacy_get_stats(db, *, club_only=False, seasons=None, federal_only=False):
    """Copie figée de l'ancienne `stats_service.get_stats` (#580) — l'oracle
    de non-régression du refactor SQL."""
    parts = _legacy_for_stats(db, club_only=club_only, seasons=seasons, federal_only=federal_only)
    if not parts:
        return {
            "total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": [],
            "rank_counters": _legacy_rank_counters([]),
        }

    athlete_set = {p.athlete_id for p in parts}
    event_set = {p.course_id for p in parts}
    by_type: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    for p in parts:
        course = p.course
        if course and course.event_type:
            by_type[course.event_type] += 1
        if course and course.event_date:
            by_month[str(course.event_date)[:7]] += 1

    recent = sorted(
        (p for p in parts if p.created_at), key=lambda p: p.created_at, reverse=True
    )[:20]

    return {
        "total": len(parts),
        "athletes": len(athlete_set),
        "events": len(event_set),
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
        "recent": [
            {
                "id": p.id,
                "athlete_name": p.athlete.nom if p.athlete else "",
                "athlete_firstname": p.athlete.prenom if p.athlete else "",
                "club": p.club or "",
                "event_name": p.course.name if p.course else "",
                "event_type": p.course.event_type if p.course else "",
                "event_date": p.course.event_date.isoformat()
                if p.course and p.course.event_date
                else None,
                "total_time": p.total_time or "",
                "scraped_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in recent
        ],
        "rank_counters": _legacy_rank_counters(parts),
    }


def _seed_580(db):
    """Jeu de données réaliste : 5 épreuves (4 types, 5 mois, 2 saisons),
    6 athlètes (genres variés, dont un genre ignoré et un vide), 27
    participations validées + 1 pendante, dont une égalité de rang scratch et
    un athlète sans aucun rang. Rend (participations créées, la pendante)."""
    athletes = [
        athlete_repository.get_or_create(db, nom=f"N{i}", prenom=f"P{i}", gender=genre, club=club)
        for i, (genre, club) in enumerate(
            [("M", "TCN"), ("F", "TCN"), ("M", "ASPTT"), ("F", "ASPTT"), ("", "TCN"), ("H", "ASPTT")]
        )
    ]

    c1 = course_repository.get_or_create(
        db, name="Triathlon de Nantes", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )  # saison 2025
    c2 = course_repository.get_or_create(
        db, name="Duathlon de Nantes", event_date=date(2026, 4, 10), event_type="triathlon-s"
    )  # saison 2025
    c3 = course_repository.get_or_create(
        db, name="Trail des Marais", event_date=date(2026, 3, 1), event_type="trail"
    )  # saison 2025, hors fédération
    c4 = course_repository.get_or_create(
        db, name="Cyclosportive Fondo", event_date=date(2025, 10, 5), event_type="cyclisme-route"
    )  # saison 2025, hors fédération
    c5 = course_repository.get_or_create(
        db, name="Triathlon d'Antan", event_date=date(2024, 6, 1), event_type="triathlon-m"
    )  # saison 2023, seule participation de ce mois

    plan = [
        # C1 : égalité scratch (deux rang 1) + un athlète sans aucun rang.
        (c1, [
            (1, 1, 1), (1, 2, 1),
            (2, 1, 2), (3, 3, 2), (4, 2, 3), (5, 4, 3), (6, 5, 4), (7, 6, 4), (8, 7, 5),
            (None, None, None),
            (50, 20, 30), (60, 25, 35),
        ]),
        (c2, [(1, 1, 1), (2, 2, 1), (3, 1, 2), (4, 2, 2), (5, 3, 3), (6, 3, 3)]),
        (c3, [(1, 1, 1), (2, 1, 1), (3, 2, 2), (4, 2, 2)]),
        (c4, [(1, 1, 1), (2, 1, 2), (3, 2, 2)]),
        (c5, [(1, 1, 1), (2, 2, 2)]),
    ]

    created = []
    for course, ranks in plan:
        for i, (r_all, r_cat, r_gen) in enumerate(ranks):
            athlete = athletes[i % len(athletes)]
            club = "TCN" if i % 2 == 0 else "ASPTT"
            p = participation_repository.create(
                db, athlete_id=athlete.id, course_id=course.id, bib_number=str(i),
                club=club, rank_overall=r_all, rank_category=r_cat, rank_gender=r_gen,
                total_time="01:00:00",
            )
            created.append(p)

    # Une pendante, exclue par construction (#270) — même rang que la première
    # victoire de C1, pour vérifier qu'elle ne s'y ajoute pas.
    pendante = participation_repository.create(
        db, athlete_id=athletes[0].id, course_id=c1.id, bib_number="pendante",
        club="TCN", rank_overall=1, rank_category=1, rank_gender=1,
        total_time="01:00:00", is_pending_validation=True,
    )
    db.flush()

    # `created_at` distincts et strictement croissants : sans quoi l'ordre des
    # 20 plus récentes n'est pas comparable entre les deux implémentations.
    base = datetime(2026, 1, 1, 8, 0, 0)
    for i, p in enumerate(created):
        p.created_at = base + timedelta(seconds=i)
    db.flush()

    return created, pendante


def test_get_stats_matches_legacy_implementation_sans_filtre(db_session):
    _seed_580(db_session)
    assert stats_service.get_stats(db_session) == _legacy_get_stats(db_session)


def test_get_stats_matches_legacy_implementation_scope_club(db_session):
    _seed_580(db_session)
    assert stats_service.get_stats(db_session, club_only=True) == _legacy_get_stats(
        db_session, club_only=True
    )


def test_get_stats_matches_legacy_implementation_federal_only(db_session):
    _seed_580(db_session)
    assert stats_service.get_stats(db_session, federal_only=True) == _legacy_get_stats(
        db_session, federal_only=True
    )


def test_get_stats_matches_legacy_implementation_filtre_par_saison(db_session):
    _seed_580(db_session)
    nouveau = stats_service.get_stats(db_session, seasons=[2025])
    assert nouveau == _legacy_get_stats(db_session, seasons=[2025])
    # Cas limite : "Triathlon d'Antan" (saison 2023) est la seule épreuve de
    # 2024-06 — le mois disparaît entièrement du résultat, il n'y figure pas à 0.
    assert "2024-06" not in nouveau["by_month"]


def test_get_stats_matches_legacy_implementation_saison_isolee(db_session):
    """Le mois exclu ci-dessus réapparaît seul quand on cible sa propre saison."""
    _seed_580(db_session)
    nouveau = stats_service.get_stats(db_session, seasons=[2023])
    assert nouveau == _legacy_get_stats(db_session, seasons=[2023])
    assert nouveau["by_month"] == {"2024-06": 2}


def test_get_stats_matches_legacy_implementation_filtres_combines(db_session):
    _seed_580(db_session)
    kwargs = {"club_only": True, "seasons": [2025], "federal_only": True}
    assert stats_service.get_stats(db_session, **kwargs) == _legacy_get_stats(db_session, **kwargs)


def test_get_stats_matches_legacy_implementation_saison_vide(db_session):
    """Chemin de sortie anticipée (`total == 0`) des deux implémentations."""
    _seed_580(db_session)
    kwargs = {"seasons": [2020]}
    nouveau = stats_service.get_stats(db_session, **kwargs)
    assert nouveau == _legacy_get_stats(db_session, **kwargs)
    assert nouveau == {
        "total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": [],
        "rank_counters": {
            "scratch": {"victories": 0, "podiums": 0, "top10": 0},
            "category": {"victories": 0, "podiums": 0, "top10": 0},
            "all": {"victories": 0, "podiums": 0, "top10": 0},
            "gender": {
                "women": {"victories": 0, "podiums": 0, "top10": 0},
                "men": {"victories": 0, "podiums": 0, "top10": 0},
            },
        },
    }


def test_get_stats_recent_est_borne_a_20_et_exclut_la_pendante(db_session):
    _created, pendante = _seed_580(db_session)
    recent = stats_service.get_stats(db_session)["recent"]
    assert len(recent) == 20
    assert pendante.id not in {r["id"] for r in recent}


def test_get_stats_egalite_de_rang_compte_chaque_victoire(db_session):
    """Deux athlètes classés 1ers ex æquo comptent chacun pour une victoire —
    la règle porte sur chaque participation, pas sur une valeur de rang unique."""
    _seed_580(db_session)
    scratch = stats_service.get_stats(db_session)["rank_counters"]["scratch"]
    # Une victoire par épreuve (5 épreuves), plus une seconde sur C1 (égalité).
    assert scratch["victories"] == 6


# ── Écart total / somme des inters (issue #486, RES-10) ──────────────────────
#
# Le point de vérité des seuils est le sondage
# `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`. La synthèse
# publie la **médiane** de l'épreuve, jamais un verdict : c'est l'écran qui
# applique ses seuils d'affichage, ce qui permet de les régler après re-sondage
# sans toucher au contrat.

_INTERS_EXACTS = {
    "swim": "00:15:00",
    "t1": "00:02:00",
    "bike": "00:30:00",
    "t2": "00:03:00",
    "run": "00:10:00",
}


def test_course_summary_publie_la_mediane_des_ecarts(db_session):
    """Deux lignes à 0 %, une à 60 s d'écart : la médiane vaut 0."""
    inters_courts = dict(_INTERS_EXACTS, t1="00:01:00")
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", "S1", "finisher", "01:00:00", _INTERS_EXACTS),
            ("B", "Deux", "M", "ASPTT", "S1", "finisher", "01:00:00", _INTERS_EXACTS),
            ("C", "Trois", "M", "ASPTT", "S1", "finisher", "01:00:00", inters_courts),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["split_gap_median"] == pytest.approx(0.0)


def test_course_summary_mediane_nulle_sans_ligne_evaluable(db_session):
    """Ni splits, ni schéma complet : rien à mesurer, et le produit ne prétend rien."""
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", "S1", "finisher", "01:00:00", None),
            ("B", "Deux", "M", "ASPTT", "S1", "finisher", "01:00:00", {"swim": "00:15:00"}),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["split_gap_median"] is None


def test_course_summary_mediane_ignore_les_lignes_non_evaluables(db_session):
    """La ligne au total illisible ne doit pas tirer la médiane vers zéro."""
    inters_courts = dict(_INTERS_EXACTS, t1="00:01:00")
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", "ASPTT", "S1", "finisher", "01:00:00", inters_courts),
            ("B", "Deux", "M", "ASPTT", "S1", "finisher", None, _INTERS_EXACTS),
            ("C", "Trois", "M", "ASPTT", "S1", "finisher", "01:00:00", inters_courts),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["split_gap_median"] == pytest.approx(60 / 3600)


# ── Ce que les cartes omettent (issue #486, RES-7) ───────────────────────────


def test_course_summary_compte_les_clubs_distincts(db_session):
    """`clubs_total` compte des **clubs**, là où `categories_total` compte des participants.

    Sans lui, le pied « et N autres clubs » n'est pas calculable : la carte ne peut pas
    dire ce qu'elle omet, ce qui est exactement le défaut que RES-7 reproche.
    """
    lignes = []
    for index in range(12):
        for occurrence in range(12 - index):
            lignes.append(
                (f"N{index}", f"P{occurrence}", "M", f"CLUB{index}", "S1", "finisher", None, None)
            )
    course = _epreuve(db_session, lignes)

    synthese = stats_service.course_summary(db_session, course.id)

    assert len(synthese["clubs"]) == 9  # la carte n'en montre que neuf
    assert synthese["clubs_total"] == 12  # …sur douze
    # Et il ne se confond pas avec le compte de participants.
    assert synthese["clubs_total"] != synthese["total"]


def test_course_summary_clubs_total_est_nul_sans_club_renseigne(db_session):
    """Cas réel de la course 47 : 696 lignes, aucun club. L'en-tête doit disparaître."""
    course = _epreuve(
        db_session,
        [
            ("A", "Un", "M", None, "S1", "finisher", None, None),
            ("B", "Deux", "M", "", "S1", "finisher", None, None),
        ],
    )

    synthese = stats_service.course_summary(db_session, course.id)

    assert synthese["clubs"] == []
    assert synthese["clubs_total"] == 0
