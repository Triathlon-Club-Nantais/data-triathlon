from datetime import date

import pytest

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import athlete_repository, course_repository, participation_repository


def _setup(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri Z", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    return athlete, course


def test_create_and_dedup_by_bib(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="42",
        club="TCN",
        total_time="01:59:00",
    )
    assert participation_repository.exists_for_bib(db_session, course.id, "42") is True
    assert participation_repository.exists_for_bib(db_session, course.id, "99") is False
    assert participation_repository.existing_bibs_for_course(db_session, course.id) == {"42"}


def test_count_for_course_inclut_les_participations_sans_dossard(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="42", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number=None, club="TCN"
    )
    db_session.flush()

    assert participation_repository.count_for_course(db_session, course.id) == 2
    assert participation_repository.existing_bibs_for_course(db_session, course.id) == {"42"}


def test_count_for_athlete_compte_sur_toutes_les_epreuves(db_session):
    """Le poids d'une fiche coureur, sans hydrater sa collection de résultats."""
    athlete, course = _setup(db_session)
    autre_epreuve = course_repository.get_or_create(
        db_session, name="Tri Y", event_date=date(2026, 6, 20), event_type="triathlon-s"
    )
    voisin = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    for epreuve in (course, autre_epreuve):
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=epreuve.id, bib_number="42", club="TCN"
        )
    participation_repository.create(
        db_session, athlete_id=voisin.id, course_id=course.id, bib_number="43", club="TCN"
    )
    db_session.flush()

    assert participation_repository.count_for_athlete(db_session, athlete.id) == 2
    assert participation_repository.count_for_athlete(db_session, voisin.id) == 1


def test_list_filters_by_name_and_club(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number="2", club="ASPTT"
    )
    db_session.flush()

    by_name = participation_repository.list_participations(db_session, name="dupont")
    assert len(by_name) == 1
    assert by_name[0].athlete.nom == "DUPONT"

    by_club = participation_repository.list_participations(db_session, club_only=True)
    assert len(by_club) == 1
    assert by_club[0].club == "TCN"


def test_list_filters_by_course_id(db_session):
    athlete, course = _setup(db_session)
    other_course = course_repository.get_or_create(
        db_session, name="Tri Y", event_date=date(2026, 6, 1), event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=other_course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    only = participation_repository.list_participations(db_session, course_id=course.id)
    assert len(only) == 1
    assert only[0].course_id == course.id


def test_event_name_filter_substring_sqlite(db_session):
    """En SQLite (dev) la recherche course reste un ILIKE sous-chaîne."""
    athlete, course = _setup(db_session)  # "Tri Z"
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    page = participation_repository.events_page(db_session, event_name="tri")
    assert page["total_events"] == 1
    assert page["items"][0].event_name == "Tri Z"

    empty = participation_repository.events_page(db_session, event_name="marathon")
    assert empty["total_events"] == 0


def test_events_page_pagination_and_sort(db_session):
    athlete, _ = _setup(db_session)
    c_old = course_repository.get_or_create(
        db_session, name="Alpha", event_date=date(2025, 1, 1), event_type="triathlon-s"
    )
    c_new = course_repository.get_or_create(
        db_session, name="Beta", event_date=date(2026, 1, 1), event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_old.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=c_new.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    first = participation_repository.events_page(db_session, page=1, page_size=1)
    assert first["total_events"] == 2
    assert len(first["items"]) == 1
    # Tri par défaut date_desc → la plus récente en premier.
    assert first["items"][0].event_name == "Beta"

    by_name = participation_repository.events_page(db_session, sort="name")
    assert [r.event_name for r in by_name["items"]] == ["Alpha", "Beta"]


def test_events_page_sort_imported_desc_ordonne_par_date_import(db_session):
    """« Derniers résultats enregistrés » (#201) : la plus récemment importée en tête.

    L'épreuve ancienne (event_date passé) doit remonter au-dessus d'une épreuve
    à venir déjà en base si elle a été enregistrée plus récemment — c'est le
    point qui distingue ce tri de `date_desc`.
    """
    from datetime import timedelta

    from app.core.time import utcnow

    athlete = athlete_repository.get_or_create(db_session, nom="X", prenom="Y", club="TCN")
    ancien = course_repository.get_or_create(
        db_session, name="Ancien Tri", event_date=date(2020, 6, 1), event_type="triathlon-s"
    )
    futur = course_repository.get_or_create(
        db_session, name="Futur Tri", event_date=date(2027, 6, 1), event_type="triathlon-s"
    )
    # Le futur a été importé AVANT l'ancien : c'est l'ancien qu'on veut voir en tête.
    now = utcnow()
    futur.created_at = now - timedelta(days=10)
    ancien.created_at = now
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=ancien.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=futur.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    by_import = participation_repository.events_page(db_session, sort="imported_desc")
    assert [r.event_name for r in by_import["items"]] == ["Ancien Tri", "Futur Tri"]

    # Contrôle : le tri date_desc rend l'inverse (comportement inchangé pour /resultats).
    by_date = participation_repository.events_page(db_session, sort="date_desc")
    assert [r.event_name for r in by_date["items"]] == ["Futur Tri", "Ancien Tri"]


def test_for_stats_filtre_par_saison_unique(db_session):
    athlete, course_2025 = _setup(db_session)  # course "Tri Z" le 2026-05-16 → saison 2025
    c_autre = course_repository.get_or_create(
        db_session, name="Tri Automne", event_date=date(2024, 10, 1), event_type="triathlon-s"
    )  # saison 2024
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course_2025.id, bib_number="1", club="TCN"
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


def test_distinct_seasons_compte_et_exclut_epreuves_sans_date(db_session):
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


def _athlete_course(db):
    athlete = Athlete(nom="DUPONT", prenom="Jean")
    course = Course(name="Triathlon de Nantes", event_type="triathlon-m", source_url="http://x")
    db.add_all([athlete, course])
    db.flush()
    return athlete, course


def test_update_ecrit_les_champs_fournis(db_session):
    athlete, course = _athlete_course(db_session)
    p = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id,
        bib_number="1", total_time="01:00:00", status="finisher",
    )

    participation_repository.update(db_session, p, total_time="00:59:00", rank_overall=3)

    refreshed = participation_repository.get(db_session, p.id)
    assert refreshed.total_time == "00:59:00"
    assert refreshed.rank_overall == 3
    assert refreshed.bib_number == "1"  # champ non fourni → inchangé


def test_finishers_count_by_group_separe_solos_et_relais(db_session):
    athlete, course = _setup(db_session)
    relayeur = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", club="TCN"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        status="finisher",
        rank_overall=1,
        is_relay=False,
    )
    participation_repository.create(
        db_session,
        athlete_id=relayeur.id,
        course_id=course.id,
        bib_number="2",
        status="finisher",
        rank_overall=1,
        is_relay=True,
    )
    db_session.flush()

    counts = participation_repository.finishers_count_by_group(db_session, [course.id])

    assert counts == {(course.id, False): 1, (course.id, True): 1}


def test_finishers_count_by_group_exclut_non_finishers_et_non_classes(db_session):
    athlete, course = _setup(db_session)
    abandon = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", club="TCN"
    )
    sans_rang = athlete_repository.get_or_create(
        db_session, nom="DURAND", prenom="Luc", club="TCN"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        status="finisher",
        rank_overall=1,
        is_relay=False,
    )
    participation_repository.create(
        db_session,
        athlete_id=abandon.id,
        course_id=course.id,
        bib_number="2",
        status="DNF",
        rank_overall=None,
        is_relay=False,
    )
    participation_repository.create(
        db_session,
        athlete_id=sans_rang.id,
        course_id=course.id,
        bib_number="3",
        status="finisher",
        rank_overall=None,
        is_relay=False,
    )
    db_session.flush()

    counts = participation_repository.finishers_count_by_group(db_session, [course.id])

    assert counts == {(course.id, False): 1}


def test_finishers_count_by_group_sans_finisher_classe_ne_produit_pas_de_cle(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        status="DNS",
        rank_overall=None,
        is_relay=False,
    )
    db_session.flush()

    assert participation_repository.finishers_count_by_group(db_session, [course.id]) == {}


def test_finishers_count_by_group_sans_ids_renvoie_un_dict_vide(db_session):
    assert participation_repository.finishers_count_by_group(db_session, []) == {}


# ── Ordre d'affichage, tranche et recherche (issue #163) ──────────────────────
#
# L'ordre d'affichage vivait en JavaScript (`orderParticipations`) pendant que la
# requête triait sur `rank_overall` seul. Invisible tant que le classement entier
# arrivait d'un coup ; paginé, la tranche servie n'est plus celle attendue. Ces
# tests figent l'ordre en base comme unique définition.


def _classement(db_session):
    """Épreuve couvrant les quatre groupes de statut et les temps absents."""
    course = course_repository.get_or_create(
        db_session, name="Tri Ordre", event_date=date(2026, 6, 1), event_type="triathlon-m"
    )

    def ajoute(nom, prenom, status, rank, temps, club="ASPTT", gender=""):
        athlete = athlete_repository.get_or_create(
            db_session, nom=nom, prenom=prenom, club=club, gender=gender
        )
        return participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=f"{nom}{prenom}",
            club=club,
            status=status,
            rank_overall=rank,
            total_time=temps,
        )

    lignes = {
        "rang1": ajoute("BBB", "Un", "finisher", 1, "01:00:00", club="TCN"),
        "rang2": ajoute("AAA", "Deux", "finisher", 2, "01:10:00"),
        "sansrang_a": ajoute("AAA", "Trois", "finisher", None, None),
        "sansrang_c": ajoute("CCC", "Quatre", "finisher", None, "01:20:00"),
        "dnf_temps": ajoute("ZZZ", "Cinq", "DNF", None, "02:00:00"),
        "dnf_sans": ajoute("AAA", "Six", "DNF", None, ""),
        "dsq": ajoute("DDD", "Sept", "DSQ", None, "01:30:00"),
        "dns": ajoute("EEE", "Huit", "DNS", None, "00:00:00"),
    }
    db_session.flush()
    return course, lignes


def test_ordre_affichage_groupes_puis_rang_puis_temps(db_session):
    course, lignes = _classement(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None
    )

    assert total == 8
    assert [p.id for p in rows] == [
        lignes["rang1"].id,  # finisher rang 1
        lignes["rang2"].id,  # finisher rang 2
        lignes["sansrang_a"].id,  # finishers sans rang, départagés par nom
        lignes["sansrang_c"].id,
        lignes["dnf_temps"].id,  # DNF, temps renseigné d'abord
        lignes["dnf_sans"].id,
        lignes["dsq"].id,  # puis DSQ
        lignes["dns"].id,  # puis DNS
    ]


def test_ordre_affichage_temps_absent_en_fin_de_groupe(db_session):
    """`00:00:00` et la chaîne vide valent temps absent, comme `NULL`."""
    course, lignes = _classement(db_session)

    rows, _ = participation_repository.list_page_for_course(db_session, course.id, page_size=None)
    ids = [p.id for p in rows]

    assert ids.index(lignes["dnf_temps"].id) < ids.index(lignes["dnf_sans"].id)


def test_ordre_affichage_non_classes_apres_les_classes_parmi_les_finishers(db_session):
    """Garde-fou SQLite (`NULL` en tête) / PostgreSQL (`NULL` en queue).

    La restriction aux finishers compte : un DNF sans rang passe, lui, **avant**
    un finisher sans rang — c'est le groupe qui prime, pas le rang.
    """
    course, lignes = _classement(db_session)

    rows, _ = participation_repository.list_page_for_course(db_session, course.id, page_size=None)
    ids = [p.id for p in rows]

    assert ids.index(lignes["rang2"].id) < ids.index(lignes["sansrang_a"].id)
    assert ids.index(lignes["sansrang_a"].id) < ids.index(lignes["dnf_temps"].id)


def _classement_accents(db_session):
    course = course_repository.get_or_create(
        db_session, name="Tri Accents", event_date=date(2026, 6, 2), event_type="triathlon-m"
    )

    def ajoute(nom, prenom, club, categorie, dossard):
        athlete = athlete_repository.get_or_create(
            db_session, nom=nom, prenom=prenom, club=club
        )
        return participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=dossard,
            club=club,
            category=categorie,
            status="finisher",
            rank_overall=None,
            total_time="01:00:00",
        )

    lignes = {
        "lemee": ajoute("LEMÉE", "Loïc", "ASPTT NANTES", "SEM", "101"),
        "leguen": ajoute("Le Guen", "Anne", "Triathlon Club Nantais", "SEF", "202"),
        "durand": ajoute("DURAND", "Hervé", "ASPTT NANTES", "V1H", "303"),
    }
    db_session.flush()
    return course, lignes


def test_recherche_par_nom_en_sous_chaine(db_session):
    course, lignes = _classement_accents(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="guen"
    )

    assert total == 1
    assert [p.id for p in rows] == [lignes["leguen"].id]


def test_recherche_insensible_aux_accents_et_a_la_casse(db_session):
    """`lower('LEMÉE') LIKE '%lemee%'` est faux sur SQLite **et** PostgreSQL."""
    course, lignes = _classement_accents(db_session)

    sans_accent = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="lemee"
    )
    avec_accent = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="LEMÉE"
    )

    assert sans_accent[1] == avec_accent[1] == 1
    assert [p.id for p in sans_accent[0]] == [lignes["lemee"].id]
    assert [p.id for p in avec_accent[0]] == [lignes["lemee"].id]


def test_recherche_porte_aussi_sur_le_prenom(db_session):
    course, lignes = _classement_accents(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="herve"
    )

    assert total == 1
    assert [p.id for p in rows] == [lignes["durand"].id]


@pytest.mark.parametrize("terme", ["asptt", "101", "SEM"])
def test_recherche_ne_porte_ni_sur_le_club_ni_sur_le_dossard_ni_sur_la_categorie(
    db_session, terme
):
    """FR-014, borne négative : une exigence non testée dérive au premier champ ajouté."""
    course, _ = _classement_accents(db_session)

    _, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q=terme
    )

    assert total == 0


@pytest.mark.parametrize("terme", ["", "   ", None])
def test_recherche_blanche_equivaut_a_pas_de_recherche(db_session, terme):
    course, _ = _classement_accents(db_session)

    _, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q=terme
    )

    assert total == 3


def test_recherche_et_portee_club_se_composent(db_session):
    course, lignes = _classement_accents(db_session)

    _, tcn_seul = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, club_only=True
    )
    _, les_deux = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, club_only=True, q="lemee"
    )

    assert tcn_seul == 1  # seule « Le Guen » est au TCN
    assert les_deux == 0  # LEMÉE n'y est pas : les deux filtres se cumulent


def test_tranche_ne_perd_ni_ne_duplique_de_ligne(db_session):
    course, _ = _classement_accents(db_session)

    page1, total = participation_repository.list_page_for_course(
        db_session, course.id, page=1, page_size=2
    )
    page2, _ = participation_repository.list_page_for_course(
        db_session, course.id, page=2, page_size=2
    )
    hors_bornes, _ = participation_repository.list_page_for_course(
        db_session, course.id, page=99, page_size=2
    )
    tout, _ = participation_repository.list_page_for_course(db_session, course.id, page_size=None)

    assert total == 3
    assert len(page1) == 2 and len(page2) == 1 and hors_bornes == []
    assert [p.id for p in page1 + page2] == [p.id for p in tout]


@pytest.mark.parametrize("joker", ["%", "_", "%%", "a%"])
def test_recherche_echappe_les_jokers_like(db_session, joker):
    """`q=%` rendait l'épreuve entière, `q=_` n'importe quel caractère.

    Ce n'était pas une injection — le motif est passé en paramètre lié — mais
    un visiteur pouvait contourner sa propre recherche sans le vouloir.
    """
    course, _ = _classement_accents(db_session)

    _, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q=joker
    )

    assert total == 0


def _duo_epreuve_athletes(db_session):
    """Une épreuve, deux coureurs, un seul inscrit."""
    from app.repositories import athlete_repository, course_repository

    course = course_repository.get_or_create(
        db_session, name="Tri reassign", event_date=None, event_type="triathlon-m",
        source_url="https://k/reassign", provider="klikego",
    )
    source = athlete_repository.get_or_create(db_session, nom="SOURCE", prenom="S")
    cible = athlete_repository.get_or_create(db_session, nom="CIBLE", prenom="C")
    db_session.flush()
    ligne = participation_repository.create(
        db_session, athlete_id=source.id, course_id=course.id, bib_number="1"
    )
    db_session.flush()
    return course, source, cible, ligne


def test_exists_for_athlete_on_course_voit_un_deja_classe(db_session):
    """FR-006 — `uq_participation_bib` ne protège pas ce cas : elle porte sur
    (course_id, bib_number), pas sur l'athlète."""
    course, source, cible, _ = _duo_epreuve_athletes(db_session)

    assert participation_repository.exists_for_athlete_on_course(
        db_session, athlete_id=source.id, course_id=course.id
    )
    assert not participation_repository.exists_for_athlete_on_course(
        db_session, athlete_id=cible.id, course_id=course.id
    )


def test_reassign_change_le_rattachement_et_rien_d_autre(db_session):
    course, source, cible, ligne = _duo_epreuve_athletes(db_session)
    ligne.total_time = "01:23:45"
    ligne.rank_overall = 7
    ligne.status = "finisher"
    db_session.flush()

    participation_repository.reassign(db_session, ligne, athlete_id=cible.id)
    db_session.flush()

    relue = participation_repository.get(db_session, ligne.id)
    assert relue.athlete_id == cible.id
    assert relue.course_id == course.id
    assert relue.total_time == "01:23:45"
    assert relue.rank_overall == 7
    assert relue.status == "finisher"
