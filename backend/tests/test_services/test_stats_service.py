from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import stats_service


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
