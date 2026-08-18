"""Le point unique d'exclusion des résultats non vérifiés (#270, FR-021/FR-022).

Comportemental plutôt qu'AST : la règle traverse cinq fonctions publiques via
un helper partagé (`_apply_filters`), qu'un lecteur d'appels statique
attribuerait mal. Un test par fonction publique, sur une participation
pendante et une validée, vaut mieux ici qu'un motif de code — sur le principe
de `test_core/test_discipline.py`, pas sur la forme de
`test_permissions_catalogue.py`.

Les six fonctions qui ne filtrent **pas** — `list_for_athlete` (la surface
voulue par FR-019), `list_for_course` (chemin d'import), `count_for_athlete`,
`count_for_course`/`delete_for_course` (gestes d'administration),
`count_bibs_absent_from` (aperçu de fusion) et `existing_bibs_for_course`
(dédoublonnage d'import) — sont couvertes ailleurs : `list_for_athlete` dans
`test_participation_repository.py`, les autres n'ont pas été modifiées et
restent sous leurs tests existants.
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


def test_for_stats_exclut_une_pendante(db_session):
    _, _, validee = _duo(db_session)
    rows = participation_repository.for_stats(db_session)
    assert [p.id for p in rows] == [validee.id]


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
    db_session.flush()

    assert len(participation_repository.list_participations(db_session, course_id=course.id)) == 2

    row = next(r for r in participation_repository.events_with_counts(db_session) if r.course_id == course.id)
    assert row.total == 2

    page = participation_repository.events_page(db_session)
    assert page["total_participations"] == 2

    assert len(participation_repository.for_stats(db_session)) == 2

    _, total = participation_repository.list_page_for_course(db_session, course.id)
    assert total == 2

    assert len(participation_repository.summary_rows_for_course(db_session, course.id)) == 2

    counts = participation_repository.finishers_count_by_group(db_session, [course.id])
    assert counts == {(course.id, False): 2}
