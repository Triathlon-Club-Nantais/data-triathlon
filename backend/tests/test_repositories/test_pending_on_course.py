"""Résultats en attente affichés sur leur épreuve, jamais comptés (#1273).

`list_pending_for_course` liste les lignes en attente non refusées d'une épreuve,
aux mêmes filtres que le classement ; `list_page_for_course` reste le classement
validé. Les comptes restent sous `validated_clause` (`test_pending_exclusion.py`).
"""
from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


def _participation(db, course, nom, bib, *, pending=False, rejected=False, club="ASPTT", category="SEM"):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Test", club=club)
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, club=club,
        category=category, status="finisher", rank_overall=1, total_time="01:00:00",
        is_pending_validation=pending, is_rejected=rejected,
    )


def _epreuve(db, name="Tri Attente"):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 8, 6), event_type="triathlon-m"
    )


def _trio(db):
    """Une épreuve : une validée, deux en attente (ordre de nom inversé), une refusée."""
    course = _epreuve(db)
    validee = _participation(db, course, "ALPHA", "1")
    zulu = _participation(db, course, "ZULU", "2", pending=True)
    bravo = _participation(db, course, "BRAVO", "3", pending=True, club="TCN", category="V2")
    _participation(db, course, "REFUS", "4", pending=True, rejected=True)
    db.flush()
    return course, validee, bravo, zulu


def test_list_pending_for_course_rend_les_en_attente_non_refusees_triees_par_nom(db_session):
    course, _, bravo, zulu = _trio(db_session)
    autre = _epreuve(db_session, name="Autre")
    _participation(db_session, autre, "AILLEURS", "1", pending=True)
    db_session.flush()

    rows = participation_repository.list_pending_for_course(db_session, course.id)

    assert [p.id for p in rows] == [bravo.id, zulu.id]


def test_list_pending_for_course_applique_les_filtres_du_classement(db_session):
    course, _, bravo, zulu = _trio(db_session)

    def ids(**filtres):
        return [p.id for p in participation_repository.list_pending_for_course(db_session, course.id, **filtres)]

    assert ids(q="zulu") == [zulu.id]
    assert ids(club="TCN") == [bravo.id]
    assert ids(category="V2") == [bravo.id]
    assert ids(q="personne") == []


def test_list_pending_for_course_suit_la_portee_club(db_session):
    course, _, bravo, _ = _trio(db_session)
    bravo.counts_for_tcn = True
    db_session.flush()

    rows = participation_repository.list_pending_for_course(db_session, course.id, club_only=True)

    assert [p.id for p in rows] == [bravo.id]


def test_list_page_for_course_ignore_les_lignes_en_attente(db_session):
    course, validee, _, _ = _trio(db_session)

    rows, total = participation_repository.list_page_for_course(db_session, course.id)

    assert total == 1
    assert [p.id for p in rows] == [validee.id]


def test_une_ligne_validee_apres_coup_quitte_les_en_attente_pour_le_classement(db_session):
    course, validee, bravo, zulu = _trio(db_session)
    participation_repository.update(db_session, bravo, is_pending_validation=False)
    db_session.flush()

    rows, total = participation_repository.list_page_for_course(db_session, course.id)

    assert total == 2
    assert {p.id for p in rows} == {validee.id, bravo.id}
    assert [p.id for p in participation_repository.list_pending_for_course(db_session, course.id)] == [zulu.id]


def test_list_pending_for_course_est_plafonnee(db_session):
    """`POST /participations` est ouvert à tout porteur du mot de passe du site :
    des saisies répétées ne doivent pas gonfler chaque réponse sans borne."""
    course = _epreuve(db_session)
    for index in range(participation_repository.PENDING_ROWS_CAP + 1):
        _participation(db_session, course, f"NOM{index:03d}", str(index), pending=True)
    db_session.flush()

    rows = participation_repository.list_pending_for_course(db_session, course.id)

    assert len(rows) == participation_repository.PENDING_ROWS_CAP


def test_list_pending_for_course_ecarte_les_categories_jeunes(db_session):
    """RGPD (#881) : l'import écarte jusqu'à Minime ; une saisie en attente ne
    doit pas les faire apparaître sur la page publique de l'épreuve."""
    course = _epreuve(db_session)
    adulte = _participation(db_session, course, "ADULTE", "1", pending=True)
    _participation(db_session, course, "MINIME", "2", pending=True, category="MIH")
    jeunes = _epreuve(db_session, name="Triathlon Jeunes")
    _participation(db_session, jeunes, "ENFANT", "1", pending=True)
    db_session.flush()

    assert [p.id for p in participation_repository.list_pending_for_course(db_session, course.id)] == [adulte.id]
    assert participation_repository.list_pending_for_course(db_session, jeunes.id) == []


def test_events_page_ne_compte_ni_ne_liste_les_lignes_jeunes_en_attente(db_session):
    course = _epreuve(db_session)
    _participation(db_session, course, "ADULTE", "1", pending=True)
    _participation(db_session, course, "MINIME", "2", pending=True, category="MIH")
    jeunes = _epreuve(db_session, name="Triathlon Jeunes")
    _participation(db_session, jeunes, "ENFANT", "1", pending=True)
    db_session.flush()

    for filtres in [{}, {"club_only": False, "name": "e"}]:
        page = participation_repository.events_page(db_session, **filtres)
        lignes = {r.course_id: r.pending_count for r in page["items"]}
        assert lignes == {course.id: 1}, filtres
        assert page["total_events"] == 1, filtres


# --- Listes d'épreuves : `events_page` (US2) ---


def _trois_epreuves(db):
    """Une épreuve en attente seule, une refusée seule, une mixte (1 validée TCN + 1 en attente)."""
    seule = _epreuve(db, name="Seule en attente")
    attente = _participation(db, seule, "SEUL", "1", pending=True, club="TCN")
    refusee = _epreuve(db, name="Refusee seule")
    _participation(db, refusee, "REFUSE", "1", pending=True, rejected=True, club="TCN")
    mixte = _epreuve(db, name="Mixte")
    validee = _participation(db, mixte, "MIXTE", "1", club="TCN")
    _participation(db, mixte, "MIXTEBIS", "2", pending=True, club="TCN")
    for p in (attente, validee):
        p.counts_for_tcn = True
    course_repository.set_counts(db, mixte, participation_count=1, tcn_count=1)
    db.flush()
    return seule, refusee, mixte


def _lignes(page):
    return {r.course_id: (r.total, r.tcn_count, r.pending_count) for r in page["items"]}




def test_events_page_liste_l_epreuve_en_attente_seule_sans_la_compter(db_session):
    seule, refusee, mixte = _trois_epreuves(db_session)

    for filtres in [{}, {"club_only": True}]:
        page = participation_repository.events_page(db_session, **filtres)
        lignes = _lignes(page)

        assert lignes[seule.id] == (0, 0, 1), filtres
        assert lignes[mixte.id] == (1, 1, 1), filtres
        assert refusee.id not in lignes, filtres
        assert page["total_participations"] == 1, filtres
        assert page["total_events"] == 2, filtres


def test_events_page_par_nom_suit_les_lignes_en_attente(db_session):
    seule, _, mixte = _trois_epreuves(db_session)

    assert _lignes(participation_repository.events_page(db_session, name="seul")) == {seule.id: (0, 0, 1)}
    assert _lignes(participation_repository.events_page(db_session, name="mixtebis")) == {mixte.id: (0, 0, 1)}
    page = participation_repository.events_page(db_session, name="mixte")
    assert _lignes(page)[mixte.id] == (1, 1, 1)
    assert page["total_participations"] == 1


def test_events_with_counts_ne_liste_toujours_pas_l_epreuve_en_attente_seule(db_session):
    seule, _, mixte = _trois_epreuves(db_session)

    for filtres in [{}, {"club_only": True}]:
        ids = {r.course_id for r in participation_repository.events_with_counts(db_session, **filtres)}
        assert seule.id not in ids and mixte.id in ids, filtres
