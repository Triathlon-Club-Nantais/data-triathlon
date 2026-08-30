"""Le point unique d'exclusion des résultats non vérifiés (#270, FR-021/FR-022).

Comportemental plutôt qu'AST : la règle traverse onze fonctions publiques,
réparties sur trois repositories, via des helpers partagés (`_apply_filters`
notamment), qu'un lecteur d'appels statique attribuerait mal. Un test par
fonction publique, sur une participation pendante et une validée, vaut mieux
ici qu'un motif de code — sur le principe de `test_core/test_discipline.py`,
pas sur la forme de `test_permissions_catalogue.py`.

Les six fonctions de `participation_repository.py` qui ne filtrent **pas** —
`list_for_athlete` (la surface voulue par FR-019), `list_for_course` (chemin
d'import), `count_for_athlete`, `count_for_course`/`delete_for_course`
(gestes d'administration), `count_bibs_absent_from` (aperçu de fusion) et
`existing_bibs_for_course` (dédoublonnage d'import) — sont couvertes
ailleurs : `list_for_athlete` dans `test_participation_repository.py`, les
autres n'ont pas été modifiées et restent sous leurs tests existants.

#562 a ajouté quatre fonctions à la carte, sur deux autres repositories :
`distinct_seasons` (`participation_repository.py`, angle mort de la carte
initiale), `course_repository._filtered` (branche `club_only`), et
`athlete_repository.list_with_season_participation_count`/
`.search_by_relevance`. Ces deux derniers fichiers n'importaient pas
`app.core.validation` avant #562.

#581 en ajoute deux de plus, sur deux repositories (`athlete_repository` et
`participation_repository`) : `club_roster` et `club_podiums`, agrégations de
synthèse d'un club pour la page `/club` (SSR côté frontend).
"""
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def _duo(db_session, event_type="triathlon-m"):
    """Une épreuve, une participation pendante et une validée."""
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri Validation", event_date=date(2026, 5, 16), event_type=event_type
    )
    pendante = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=True,
    )
    validee = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="2",
        club="TCN", status="finisher", rank_overall=2, total_time="01:10:00",
        is_pending_validation=False,
    )
    # Compteurs dénormalisés (#623) : cette fixture crée les participations
    # directement, hors du chemin d'import qui les tient à jour d'ordinaire
    # (`_Persister.finalize`) — même patron que `is_reliable_computed`/
    # `quality_issues` (#486), posés directement par les fixtures qui en ont
    # besoin plutôt que rejoués par un import complet. Seule `validee` compte.
    course_repository.set_counts(db_session, course, participation_count=1, tcn_count=1)
    db_session.flush()
    return course, pendante, validee


def test_is_rejected_est_un_champ_reel_persiste(db_session):
    """#437 : is_rejected est mappé au modèle et persiste en base."""
    course, pendante, _ = _duo(db_session)
    assert pendante.is_rejected is False  # défaut
    pendante.is_rejected = True
    db_session.flush()
    db_session.expire(pendante)
    assert participation_repository.get(db_session, pendante.id).is_rejected is True


def test_list_participations_exclut_une_pendante(db_session):
    course, _, validee = _duo(db_session)
    rows = participation_repository.list_participations(db_session, course_id=course.id)
    assert [p.id for p in rows] == [validee.id]


def test_events_with_counts_ne_compte_pas_les_pendantes(db_session):
    course, _, _ = _duo(db_session)
    row = next(r for r in participation_repository.events_with_counts(db_session) if r.course_id == course.id)
    assert row.total == 1
    assert row.tcn_count == 1


def test_events_page_ne_compte_pas_les_pendantes(db_session):
    _duo(db_session)
    page = participation_repository.events_page(db_session)
    assert page["total_participations"] == 1


def test_stats_totals_exclut_une_pendante(db_session):
    """`for_stats` a été remplacée par cinq fonctions dédiées (#580) : chacune
    reprend l'exclusion à son compte plutôt que de la déléguer à une fonction
    commune, d'où un test par fonction plutôt qu'un seul pour `for_stats`."""
    _duo(db_session)
    total, athletes, events = participation_repository.stats_totals(db_session)
    assert (total, athletes, events) == (1, 1, 1)


def test_stats_by_type_exclut_une_pendante(db_session):
    _duo(db_session)
    rows = participation_repository.stats_by_type(db_session)
    assert rows == [("triathlon-m", 1)]


def test_stats_by_month_rows_exclut_une_pendante(db_session):
    _duo(db_session)
    rows = participation_repository.stats_by_month_rows(db_session)
    assert [count for _event_date, count in rows] == [1]


def test_stats_recent_rows_exclut_une_pendante(db_session):
    _, _, validee = _duo(db_session)
    rows = participation_repository.stats_recent_rows(db_session)
    assert [row[0] for row in rows] == [validee.id]


def test_stats_rank_rows_exclut_une_pendante(db_session):
    _duo(db_session)
    rows = participation_repository.stats_rank_rows(db_session)
    assert [rank_overall for rank_overall, *_ in rows] == [2]  # rang de la validée


def test_list_page_for_course_exclut_une_pendante(db_session):
    course, _, validee = _duo(db_session)
    rows, total = participation_repository.list_page_for_course(db_session, course.id)
    assert total == 1
    assert [p.id for p in rows] == [validee.id]


def test_summary_rows_for_course_exclut_une_pendante(db_session):
    course, _, _ = _duo(db_session)
    rows = participation_repository.summary_rows_for_course(db_session, course.id)
    assert len(rows) == 1


def test_finishers_count_by_group_exclut_une_pendante(db_session):
    course, _, _ = _duo(db_session)
    counts = participation_repository.finishers_count_by_group(db_session, [course.id])
    assert counts == {(course.id, False): 1}


# --- Symétrique (T070, FR-022) : une validation après coup entre partout ---


def test_une_participation_validee_apres_coup_entre_dans_les_cinq_sites(db_session):
    course, pendante, _ = _duo(db_session)

    pendante.is_pending_validation = False
    # Compteurs dénormalisés (#623) : ce test bascule le champ directement,
    # hors d'`admin_actions.validate_participation` (le point d'écriture réel
    # qui ajuste les compteurs) — même geste répété ici pour cette fixture.
    course_repository.adjust_counts(db_session, course, participation_delta=1, tcn_delta=1)
    db_session.flush()

    assert len(participation_repository.list_participations(db_session, course_id=course.id)) == 2

    row = next(r for r in participation_repository.events_with_counts(db_session) if r.course_id == course.id)
    assert row.total == 2

    page = participation_repository.events_page(db_session)
    assert page["total_participations"] == 2

    total_stats, _athletes, _events = participation_repository.stats_totals(db_session)
    assert total_stats == 2
    assert len(participation_repository.stats_rank_rows(db_session)) == 2

    _, total = participation_repository.list_page_for_course(db_session, course.id)
    assert total == 2

    assert len(participation_repository.summary_rows_for_course(db_session, course.id)) == 2

    counts = participation_repository.finishers_count_by_group(db_session, [course.id])
    assert counts == {(course.id, False): 2}


# --- #562 : quatre fonctions supplémentaires, sur deux autres repositories ---


def test_distinct_seasons_exclut_une_pendante(db_session):
    _duo(db_session)
    saisons = participation_repository.distinct_seasons(db_session, club_only=True)
    assert saisons == [{"start_year": 2025, "event_count": 1, "participation_count": 1}]


def test_list_all_club_only_exclut_une_epreuve_dont_lunique_participation_club_est_pendante(
    db_session,
):
    course = course_repository.get_or_create(
        db_session, name="Tri Fantome", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    athlete = athlete_repository.get_or_create(db_session, nom="PENDING", prenom="Solo", club="TCN")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=True,
    )
    db_session.flush()
    assert course_repository.list_all(db_session, club_only=True) == []
    assert course_repository.count_all(db_session, club_only=True) == 0


def test_list_with_season_participation_count_exclut_une_pendante(db_session):
    """#709 — `validated_count`/`club_affiliated_count` excluent la pendante,
    `total_count` la compte (FR-001 : même total que `list_for_athlete`)."""
    _, _, validee = _duo(db_session)
    athlete = athlete_repository.get(db_session, validee.athlete_id)
    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=True
    )
    assert resultats == [(athlete, 2, 1, 1)]


def test_list_with_season_participation_count_garde_un_athlete_100pourcent_pendant(db_session):
    """#709 — un athlète du roster (`Athlete.club`) dont l'unique participation
    est pendante n'est plus exclu de la liste (research.md D1) : il apparaît
    avec `total_count=1`, `validated_count=0`, `club_affiliated_count=0`."""
    athlete = athlete_repository.get_or_create(db_session, nom="PENDING", prenom="Solo", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri Solo Deux", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=True,
    )
    db_session.flush()
    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=True
    )
    assert resultats == [(athlete, 1, 0, 0)]


def test_search_by_relevance_ne_compte_pas_la_pendante(db_session):
    _, _, validee = _duo(db_session)
    athlete = athlete_repository.get(db_session, validee.athlete_id)
    resultats = athlete_repository.search_by_relevance(db_session, term="DUPONT")
    assert resultats == [(athlete, 1)]


def test_search_by_relevance_garde_lathlete_dont_lunique_resultat_est_pendant(db_session):
    """Piège #562 : le filtre doit vivre dans la condition du `outerjoin`, pas
    dans le `WHERE` — sinon l'athlète dont l'unique participation est pendante
    disparaît entièrement de la palette ⌘K, au lieu d'y rester à 0 résultat
    validé (comme un athlète qui n'a jamais couru, cf. #484)."""
    athlete = athlete_repository.get_or_create(db_session, nom="SOLOPENDING", prenom="Jean", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="Tri Solo Pendant", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=True,
    )
    db_session.flush()
    resultats = athlete_repository.search_by_relevance(db_session, term="SOLOPENDING")
    assert resultats == [(athlete, 0)]


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
