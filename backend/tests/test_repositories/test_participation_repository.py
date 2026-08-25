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


def test_list_pending_ne_rend_que_les_resultats_en_attente(db_session):
    """#271 — tous clubs confondus, aucun filtre `tcn_clause` (research.md §D5)."""
    athlete, course = _setup(db_session)
    autre = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    pendante = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", is_pending_validation=True,
    )
    pendante_autre_club = participation_repository.create(
        db_session, athlete_id=autre.id, course_id=course.id, bib_number="2",
        club="ASPTT", is_pending_validation=True,
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="3",
        club="TCN", is_pending_validation=False,
    )
    db_session.flush()

    en_attente = participation_repository.list_pending(db_session)

    assert {p.id for p in en_attente} == {pendante.id, pendante_autre_club.id}


def test_list_pending_vide_sans_resultat_en_attente(db_session):
    assert participation_repository.list_pending(db_session) == []


def test_has_pending_for_course_vrai_si_au_moins_un_resultat_en_attente(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", is_pending_validation=True,
    )
    db_session.flush()

    assert participation_repository.has_pending_for_course(db_session, course.id) is True


def test_has_pending_for_course_faux_si_tout_est_valide(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", is_pending_validation=False,
    )
    db_session.flush()

    assert participation_repository.has_pending_for_course(db_session, course.id) is False


def test_has_pending_for_course_faux_sur_epreuve_inconnue(db_session):
    assert participation_repository.has_pending_for_course(db_session, 4242) is False


def test_has_pending_for_course_faux_si_toutes_rejetees(db_session):
    """#437 : une épreuve dont l'unique résultat en attente a été rejeté
    n'a plus de raison d'être renommable depuis la page bénévoles."""
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    assert participation_repository.has_pending_for_course(db_session, course.id) is False


def test_list_pending_exclut_une_rejetee(db_session):
    """#437 : une entrée rejetée reste is_pending_validation=True mais ne
    doit plus apparaître dans la file bénévoles."""
    course = course_repository.get_or_create(
        db_session, name="Tri Rejet", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    pendante = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    rejetee = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="2",
        is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    assert [p.id for p in participation_repository.list_pending(db_session)] == [pendante.id]
    assert [p.id for p in participation_repository.list_rejected(db_session)] == [rejetee.id]


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

    by_full_name = participation_repository.list_participations(db_session, name="Jean Dupont")
    assert [p.athlete.nom for p in by_full_name] == ["DUPONT"]


def test_list_avec_terme_tout_espaces_ne_rend_rien(db_session):
    """`name="   "` ne doit pas dégénérer en absence de filtre (revue #365)."""
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    assert participation_repository.list_participations(db_session, name="   ") == []


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


def test_stats_by_type_filtre_par_saison_unique(db_session):
    """`for_stats` a été remplacée par cinq fonctions dédiées (#580) ; `seasons`
    est un filtre commun aux cinq, vérifié ici sur l'une d'elles."""
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

    only_2025 = participation_repository.stats_by_type(db_session, seasons=[2025])
    assert only_2025 == [("triathlon-m", 1)]  # "Tri Z" est de ce type, "Tri Automne" est exclue


def test_stats_totals_multi_saisons_non_contigues(db_session):
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

    total, _athletes, events = participation_repository.stats_totals(
        db_session, seasons=[2025, 2023]
    )
    assert (total, events) == (2, 2)  # "Tri Z" (2025) + "Tri 2023" — "Tri 2024" exclue


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


def test_events_page_meme_nom_meme_date_pagine_sans_doublon_ni_manque(db_session):
    """#567 point 3 — cas Mesquer : deux `Course` de même `name` et `event_date`
    (identité `(name, event_date, event_type, is_relay)` distincte par
    `event_type`, cf. `course_repository.get_or_create`) sont entièrement à
    égalité sous `date_desc` faute de clé de départage unique. Feuilletées en
    `page_size=1`, elles doivent apparaître exactement une fois chacune, sans
    répétition ni absence — l'instabilité que `LIMIT/OFFSET` introduirait sur
    des lignes ex æquo."""
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    a = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 6, 1), event_type="triathlon-m"
    )
    b = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 6, 1), event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=a.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=b.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    seen: list[int] = []
    page = 1
    while True:
        result = participation_repository.events_page(db_session, page=page, page_size=1)
        if not result["items"]:
            break
        seen.extend(row.course_id for row in result["items"])
        page += 1
        if page > 10:  # garde-fou anti-boucle infinie si la pagination reste cassée
            break

    assert sorted(seen) == sorted([a.id, b.id])


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
    # Plus de `source_url=` au constructeur : c'est une propriété dérivée depuis
    # #279, et elle refuse l'affectation. Ce test ne la lit pas — l'URL n'était
    # ici que du remplissage.
    course = Course(name="Triathlon de Nantes", event_type="triathlon-m")
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


def test_feuilletage_page_size_1_stable_avec_deux_homonymes_exacts(db_session):
    """Deux athlètes distincts, mêmes nom/prénom, même groupe/rang/temps : rien
    ne les distingue avant la clé finale de `_ordre_affichage`. Sur cette
    épreuve figée (aucune écriture concurrente entre les pages), SQLite rend un
    plan stable même sans clé finale — ce test ne peut donc pas, à lui seul,
    reproduire le doublon/l'oubli en feuilletant (le défaut est un plan de
    requête non garanti, cf. docstring de `summary_rows_for_course` sur
    PostgreSQL : « l'ordre du tas n'est pas stable (UPDATE, VACUUM) »). Il fige
    quand même le contrat observable : chaque page est disjointe des autres et
    leur réunion couvre tout le classement.
    """
    course = course_repository.get_or_create(
        db_session, name="Tri Homonymes", event_date=date(2026, 6, 3), event_type="triathlon-m"
    )
    # Deux athlètes distincts (dates de naissance différentes) mais nom et
    # prénom identiques — et la même absence de rang/temps : rien ne les
    # distingue avant la clé finale.
    homonyme_1 = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Alex", birth_date=date(1990, 1, 1)
    )
    homonyme_2 = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Alex", birth_date=date(1995, 6, 15)
    )
    autre = athlete_repository.get_or_create(db_session, nom="ZOLA", prenom="Bertrand")

    lignes = [
        participation_repository.create(
            db_session, athlete_id=homonyme_1.id, course_id=course.id, bib_number="1",
            status="finisher", rank_overall=None, total_time=None,
        ),
        participation_repository.create(
            db_session, athlete_id=homonyme_2.id, course_id=course.id, bib_number="2",
            status="finisher", rank_overall=None, total_time=None,
        ),
        participation_repository.create(
            db_session, athlete_id=autre.id, course_id=course.id, bib_number="3",
            status="finisher", rank_overall=None, total_time=None,
        ),
    ]
    db_session.flush()
    ids_attendus = {p.id for p in lignes}

    vues: list[int] = []
    for page in range(1, len(lignes) + 1):
        rows, total = participation_repository.list_page_for_course(
            db_session, course.id, page=page, page_size=1
        )
        assert total == len(lignes)
        vues.extend(p.id for p in rows)

    assert len(vues) == len(ids_attendus)  # aucune ligne vue deux fois
    assert set(vues) == ids_attendus  # aucune ligne manquante


def test_ordre_affichage_departage_sur_l_id_en_dernier_recours(db_session):
    """La garantie réelle derrière le test de feuilletage ci-dessus : la requête
    SQL elle-même porte une clé de départage unique. `Participation.id` est
    l'unique clé qui ne peut jamais être à égalité entre deux lignes — c'est
    elle qui doit fermer `_ordre_affichage`, comme `summary_rows_for_course`
    le fait déjà via `.order_by(Participation.id)`.
    """
    derniere_cle = participation_repository._ordre_affichage()[-1]
    compiled = derniere_cle.compile(db_session.bind, compile_kwargs={"literal_binds": True})

    assert str(compiled) == "participations.id"


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


def test_recherche_par_prenom_nom(db_session):
    """« prénom nom » : chaque mot matche nom **ou** prénom, dans l'ordre voulu (#357)."""
    course, lignes = _classement_accents(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="Herve Durand"
    )

    assert total == 1
    assert [p.id for p in rows] == [lignes["durand"].id]


def test_recherche_par_nom_prenom(db_session):
    """L'ordre des mots ne compte pas : « nom prénom » trouve aussi."""
    course, lignes = _classement_accents(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="Durand Herve"
    )

    assert total == 1
    assert [p.id for p in rows] == [lignes["durand"].id]


def test_recherche_par_prenom_nom_accentue(db_session):
    """Deux mots + nom accentué : « Loic Lemee » trouve « LEMÉE »."""
    course, lignes = _classement_accents(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, q="loic lemee"
    )

    assert total == 1
    assert [p.id for p in rows] == [lignes["lemee"].id]


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


def test_list_for_athlete_inclut_une_participation_pendante(db_session):
    """FR-019 — la fiche athlète est la seule surface qui montre les pendantes."""
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", is_pending_validation=True,
    )
    db_session.flush()

    rows = participation_repository.list_for_athlete(db_session, athlete.id)
    assert len(rows) == 1
    assert rows[0].is_pending_validation is True


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


# --- Non-régression #350 : N+1 sur Course.provider/source_url --------------
#
# `Course.provider`/`.source_url` sont des `hybrid_property` qui lisent
# `course.sources` en mémoire (`_from_active_source`), sans requête — à
# condition que la collection soit déjà chargée. Les trois fonctions
# ci-dessous doivent charger `Course.sources` en un seul aller (`selectinload`
# chaîné derrière `joinedload(Participation.course)`), quel que soit le nombre
# de courses/participations dans la page. Le test porte sur le **nombre** de
# requêtes SQL, pas sur le contenu du résultat — un test qui ne vérifierait
# que `provider`/`source_url` laisserait le N+1 revenir sans jamais le voir.


def _course_avec_source_active(db_session, indice: int) -> Course:
    return course_repository.get_or_create(
        db_session,
        name=f"Tri Source {indice}",
        event_date=date(2026, 5, indice + 1),
        event_type="triathlon-m",
        source_url=f"https://timing.example/{indice}",
        provider="klikego",
    )


def test_list_participations_charge_les_sources_en_un_seul_aller(db_session):
    """Cinq courses distinctes, huit participations : le nombre de requêtes ne
    doit dépendre ni du nombre de courses, ni du nombre de participations."""
    from app.core import sql_observability

    athletes = [
        athlete_repository.get_or_create(db_session, nom=f"NOM{i}", prenom="P", club="TCN")
        for i in range(2)
    ]
    courses = [_course_avec_source_active(db_session, i) for i in range(5)]
    for course in courses:
        participation_repository.create(
            db_session, athlete_id=athletes[0].id, course_id=course.id, bib_number="1", club="TCN"
        )
    # Trois des cinq courses portent un second participant : la source ne doit
    # pas non plus être rechargée par participation.
    for course in courses[:3]:
        participation_repository.create(
            db_session, athlete_id=athletes[1].id, course_id=course.id, bib_number="2", club="TCN"
        )
    db_session.flush()
    # Périme tout ce que la mise en place vient de charger : sans ça, les
    # sources posées par `get_or_create` restent en mémoire sur ces mêmes
    # instances et le test ne verrait jamais le lazy-load qu'il cherche à
    # détecter — comme une nouvelle session le ferait à chaque requête HTTP.
    db_session.expire_all()

    sql_observability.install(db_session.bind, slow_query_ms=0, collect_stats=True)
    try:
        with sql_observability.measure_queries("test list_participations") as stats:
            rows = participation_repository.list_participations(db_session, page_size=50)
            assert len(rows) == 8
            for row in rows:
                assert row.course.provider == "klikego"
                assert row.course.source_url
        # 1 requête principale (Participation + Athlete + Course joints) + 1
        # requête groupée `IN (...)` pour les sources de toutes les courses de
        # la page — jamais une par course distincte.
        assert stats.count == 2
    finally:
        sql_observability.reset_for_tests()


def test_list_for_athlete_charge_les_sources_en_un_seul_aller(db_session):
    """Un même athlète sur quatre courses distinctes : même garde-fou que
    `list_participations`, alimente `/athletes/[id]`."""
    from app.core import sql_observability

    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    courses = [_course_avec_source_active(db_session, i) for i in range(4)]
    for course in courses:
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
        )
    db_session.flush()
    athlete_id = athlete.id  # capturé avant expiration : sinon l'accès à
    # l'attribut après `expire_all()` déclenche lui-même une requête, une de
    # plus que ce que la fonction testée émet réellement.
    db_session.expire_all()

    sql_observability.install(db_session.bind, slow_query_ms=0, collect_stats=True)
    try:
        with sql_observability.measure_queries("test list_for_athlete") as stats:
            rows = participation_repository.list_for_athlete(db_session, athlete_id)
            assert len(rows) == 4
            for row in rows:
                assert row.course.provider == "klikego"
                assert row.course.source_url
        assert stats.count == 2
    finally:
        sql_observability.reset_for_tests()


def test_list_page_for_course_charge_la_source_en_un_seul_aller(db_session):
    """Le classement d'une épreuve : `contains_eager(Athlete)` déjà en place ne
    doit pas empêcher le chaînage `joinedload(Course).selectinload(sources)`."""
    from app.core import sql_observability

    course = _course_avec_source_active(db_session, 0)
    athletes = [
        athlete_repository.get_or_create(db_session, nom=f"N{i}", prenom="P", club="TCN")
        for i in range(3)
    ]
    for i, athlete in enumerate(athletes):
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id, bib_number=str(i), club="TCN"
        )
    db_session.flush()
    course_id = course.id  # capturé avant expiration, même raison que ci-dessus.
    db_session.expire_all()

    sql_observability.install(db_session.bind, slow_query_ms=0, collect_stats=True)
    try:
        with sql_observability.measure_queries("test list_page_for_course") as stats:
            rows, total = participation_repository.list_page_for_course(db_session, course_id)
            assert total == 3
            for row in rows:
                assert row.course.provider == "klikego"
                assert row.course.source_url
        # count() + tranche paginée (Athlete + Course joints) + IN(...) sources.
        assert stats.count == 3
    finally:
        sql_observability.reset_for_tests()


def test_count_all_compte_toutes_les_participations(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number="2", club="TCN"
    )
    db_session.flush()

    assert participation_repository.count_all(db_session) == 2


def test_delete_all_vide_la_table_sans_toucher_aux_courses(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    efface = participation_repository.delete_all(db_session)

    assert efface == 1
    assert participation_repository.count_all(db_session) == 0
    assert course_repository.get(db_session, course.id) is not None


def test_delete_retire_la_ligne_et_laisse_le_coureur(db_session):
    """#439 — la suppression d'un résultat ne purge pas la fiche devenue vide.

    Divergence assumée avec `reassign_participation`, qui purge : là, la fiche
    orpheline est le résidu d'une erreur de rattachement ; ici, un coureur du
    club dont on retire le seul résultat erroné reste un coureur du club.
    """
    athlete, course = _setup(db_session)
    ligne = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    participation_repository.delete(db_session, ligne)

    assert participation_repository.count_all(db_session) == 0
    assert athlete_repository.get(db_session, athlete.id) is not None


def test_delete_n_emet_aucun_commit(db_session):
    """Principe II — le repository `flush`, la route `commit`."""
    athlete, course = _setup(db_session)
    ligne = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()
    appels: list[str] = []
    original = db_session.commit
    db_session.commit = lambda: appels.append("commit") or original()

    try:
        participation_repository.delete(db_session, ligne)
    finally:
        db_session.commit = original

    assert appels == []


# ── list_for_athlete : filtres saison / discipline (#502) ────────────────────


def _course_pour_filtre(db_session, nom, event_date, event_type):
    course = course_repository.get_or_create(
        db_session, name=nom, event_date=event_date, event_type=event_type
    )
    db_session.flush()
    return course


def _athlete_avec_trois_courses(db_session):
    """Un athlète, trois participations : saison 2025 triathlon, saison 2025
    trail, saison 2024 triathlon. Chaque filtre en retire une différente."""
    athlete = athlete_repository.get_or_create(db_session, nom="FILTRE", prenom="Fanny")
    db_session.flush()
    courses = {
        "tri_2025": _course_pour_filtre(db_session, "Tri 2025", date(2025, 10, 5), "triathlon-m"),
        "trail_2025": _course_pour_filtre(db_session, "Trail 2025", date(2025, 10, 12), "trail"),
        "tri_2024": _course_pour_filtre(db_session, "Tri 2024", date(2024, 10, 5), "triathlon-m"),
    }
    for i, course in enumerate(courses.values(), start=1):
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=str(i),
            club="Triathlon Club Nantais",
        )
    db_session.commit()
    return athlete


def test_list_for_athlete_sans_filtre_rend_tout(db_session):
    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(db_session, athlete.id)

    assert len(lignes) == 3


def test_list_for_athlete_filtre_par_saison(db_session):
    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(db_session, athlete.id, seasons=[2025])

    assert sorted(p.course.name for p in lignes) == ["Trail 2025", "Tri 2025"]


def test_list_for_athlete_federal_only_retire_le_trail(db_session):
    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(db_session, athlete.id, federal_only=True)

    assert sorted(p.course.name for p in lignes) == ["Tri 2024", "Tri 2025"]


def test_list_for_athlete_combine_saison_et_discipline(db_session):
    athlete = _athlete_avec_trois_courses(db_session)

    lignes = participation_repository.list_for_athlete(
        db_session, athlete.id, seasons=[2025], federal_only=True
    )

    assert [p.course.name for p in lignes] == ["Tri 2025"]


# ── Filtres club et catégorie du classement (issue #486, RES-11) ─────────────
#
# **Égalité exacte**, et c'est structurant : les valeurs proposées à l'écran sont
# littéralement les chaînes stockées, puisqu'elles viennent d'un `Counter` sur ces
# deux colonnes. Une comparaison partielle ferait diverger le compteur affiché sur
# la carte du total rendu par le classement — le défaut que RES-9 vient de faire
# corriger par le lot #485.


def _classement_filtrable(db_session):
    """Trois clubs, trois catégories, de quoi croiser les filtres."""
    course = course_repository.get_or_create(
        db_session, name="Tri Filtres", event_date=date(2026, 6, 3), event_type="triathlon-m"
    )

    def ajoute(nom, club, categorie):
        athlete = athlete_repository.get_or_create(
            db_session, nom=nom, prenom="Test", club=club, gender="M"
        )
        return participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=nom,
            club=club,
            category=categorie,
            status="finisher",
            rank_overall=1,
            total_time="01:00:00",
        )

    lignes = {
        "blain_v2": ajoute("BLAINV2", "BLAIN TRIATHLON", "V2"),
        "blain_s1": ajoute("BLAINS1", "BLAIN TRIATHLON", "S1"),
        "blain_jeunes": ajoute("JEUNES", "BLAIN TRIATHLON JEUNES", "V2"),
        "tcn_v2": ajoute("TCNV2", "TRIATHLON CLUB NANTAIS", "V2"),
    }
    db_session.flush()
    return course, lignes


def test_le_filtre_club_est_une_egalite_exacte(db_session):
    """« BLAIN TRIATHLON » ne doit pas ramasser « BLAIN TRIATHLON JEUNES »."""
    course, lignes = _classement_filtrable(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, club="BLAIN TRIATHLON"
    )

    assert total == 2
    assert {p.id for p in rows} == {lignes["blain_v2"].id, lignes["blain_s1"].id}


def test_le_filtre_categorie_est_une_egalite_exacte(db_session):
    course, lignes = _classement_filtrable(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, category="V2"
    )

    assert total == 3
    assert lignes["blain_s1"].id not in {p.id for p in rows}


def test_les_deux_filtres_se_cumulent(db_session):
    course, lignes = _classement_filtrable(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, club="BLAIN TRIATHLON", category="V2"
    )

    assert total == 1
    assert [p.id for p in rows] == [lignes["blain_v2"].id]


def test_les_filtres_se_cumulent_avec_la_recherche_et_la_portee_club(db_session):
    course, lignes = _classement_filtrable(db_session)

    _, avec_recherche = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, category="V2", q="BLAINV2"
    )
    assert avec_recherche == 1

    rows, avec_portee = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, category="V2", club_only=True
    )
    assert avec_portee == 1
    assert [p.id for p in rows] == [lignes["tcn_v2"].id]


def test_une_valeur_inconnue_rend_une_selection_vide(db_session):
    course, _ = _classement_filtrable(db_session)

    rows, total = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, club="CLUB INEXISTANT"
    )

    assert rows == []
    assert total == 0


def test_les_filtres_absents_ne_filtrent_rien(db_session):
    """Défaut neutre — Principe V : c'est l'appelant qui active, jamais l'API."""
    course, _ = _classement_filtrable(db_session)

    _, sans = participation_repository.list_page_for_course(db_session, course.id, page_size=None)
    _, avec_none = participation_repository.list_page_for_course(
        db_session, course.id, page_size=None, club=None, category=None
    )

    assert sans == avec_none == 4
