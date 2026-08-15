from datetime import date

from sqlalchemy import func, select, text

from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository


def test_get_or_create_dedups_on_identity(db_session):
    c1 = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider="klikego",
    )
    c2 = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider="klikego",
    )
    assert c1.id == c2.id


def test_different_event_type_is_distinct_course(db_session):
    c1 = course_repository.get_or_create(
        db_session, name="Tri X", event_date=date(2026, 5, 16), event_type="triathlon-s"
    )
    c2 = course_repository.get_or_create(
        db_session, name="Tri X", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    assert c1.id != c2.id


def test_is_relay_makes_distinct_course(db_session):
    solo = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=False,
    )
    relais = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=True,
    )
    assert solo.id != relais.id
    assert solo.is_relay is False
    assert relais.is_relay is True


def test_get_by_identity_discriminates_on_is_relay(db_session):
    course_repository.get_or_create(
        db_session,
        name="Tri Y",
        event_date=date(2026, 6, 1),
        event_type="triathlon-s",
        is_relay=True,
    )
    found_solo = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=False
    )
    found_relais = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=True
    )
    assert found_solo is None
    assert found_relais is not None
    assert found_relais.is_relay is True


def test_get_by_active_source_retrouve_lepreuve_malgre_un_event_type_different(db_session):
    """#294 — la lecture qui retrouve un heat reclassé, `event_type` hors du filtre.

    C'est le champ qui a changé de valeur entre deux scrapes (`classify` affiné) :
    le chercher à l'égalité est précisément ce qui faisait naître une seconde
    `Course` à côté de la première.
    """
    url = "https://www.wiclax.com/mesquer-2026/resultats"
    course = course_repository.get_or_create(
        db_session,
        name="Triathlon de Mesquer S",
        event_date=date(2026, 6, 14),
        event_type="swimrun-s",
        source_url=url,
        provider="wiclax",
    )

    trouvee = course_repository.get_by_active_source(
        db_session,
        source_url=url,
        name="Triathlon de Mesquer S",
        event_date=date(2026, 6, 14),
        is_relay=False,
    )

    assert trouvee is not None
    assert trouvee.id == course.id


def test_get_by_active_source_ne_voit_pas_les_sources_passives(db_session):
    """D2 — une passive n'alimente aucun affichage (#279), elle ne classe rien.

    Sans le filtre `is_active`, coller la seconde publication d'une épreuve
    reclasserait un classement venu d'un autre chronométreur.
    """
    from app.repositories import course_source_repository

    course = course_repository.get_or_create(
        db_session,
        name="Triathlon de Mesquer S",
        event_date=date(2026, 6, 14),
        event_type="swimrun-s",
        source_url="https://k/mesquer",
        provider="klikego",
    )
    passive = course_source_repository.attach(
        db_session, course=course, url="https://w/mesquer", provider="wiclax"
    )
    assert passive.is_active is False

    assert (
        course_repository.get_by_active_source(
            db_session,
            source_url="https://w/mesquer",
            name="Triathlon de Mesquer S",
            event_date=date(2026, 6, 14),
            is_relay=False,
        )
        is None
    )


def test_get_by_active_source_discrimine_sur_le_nom_la_date_et_le_relais(db_session):
    """Les trois champs d'identité restés dans le filtre séparent bien deux heats
    d'une même URL — c'est le solo qui répond au solo, jamais le relais."""
    url = "https://www.wiclax.com/carnac/resultats"
    solo = course_repository.get_or_create(
        db_session,
        name="Triathlon de Carnac",
        event_date=date(2026, 6, 14),
        event_type="triathlon-s",
        source_url=url,
        provider="wiclax",
    )
    course_repository.get_or_create(
        db_session,
        name="Triathlon de Carnac",
        event_date=date(2026, 6, 14),
        event_type="triathlon-s",
        is_relay=True,
        source_url=url,
        provider="wiclax",
    )

    trouvee = course_repository.get_by_active_source(
        db_session,
        source_url=url,
        name="Triathlon de Carnac",
        event_date=date(2026, 6, 14),
        is_relay=False,
    )

    assert trouvee.id == solo.id
    assert (
        course_repository.get_by_active_source(
            db_session,
            source_url=url,
            name="Un autre nom",
            event_date=date(2026, 6, 14),
            is_relay=False,
        )
        is None
    )


def test_reclassify_updates_existing_course_instead_of_duplicating(db_session):
    """#294 — le geste lui-même : la ligne change de sport, elle ne se dédouble pas.

    Mesuré sur Mesquer 2026, 498 finishers rangés en `swimrun-s` alors que
    l'épreuve est un `triathlon-s`.
    """
    course = course_repository.get_or_create(
        db_session,
        name="Triathlon de Mesquer S",
        event_date=date(2026, 6, 14),
        event_type="swimrun-s",
        source_url="https://w/mesquer",
        provider="wiclax",
    )

    rendue = course_repository.reclassify(db_session, course, "triathlon-s")

    assert rendue.id == course.id
    assert course.event_type == "triathlon-s"
    assert db_session.query(Course).count() == 1


def test_reclassify_refuse_une_collision_didentite(db_session):
    """`uq_course_identity` d'abord : reclasser vers l'identité d'une épreuve déjà
    en base ferait tomber le flush sur la contrainte, en plein import. La ligne
    garde alors sa classification — c'est un doublon à fusionner (#287), pas une
    écriture à forcer."""
    occupante = course_repository.get_or_create(
        db_session,
        name="Triathlon de Mesquer S",
        event_date=date(2026, 6, 14),
        event_type="triathlon-s",
        source_url="https://autre/mesquer",
        provider="timepulse",
    )
    reclassee = course_repository.get_or_create(
        db_session,
        name="Triathlon de Mesquer S",
        event_date=date(2026, 6, 14),
        event_type="swimrun-s",
        source_url="https://w/mesquer",
        provider="wiclax",
    )

    rendue = course_repository.reclassify(db_session, reclassee, "triathlon-s")

    assert rendue.id == reclassee.id
    assert reclassee.event_type == "swimrun-s", "la contrainte prime sur le scrape"
    assert occupante.event_type == "triathlon-s"
    assert db_session.query(Course).count() == 2


def test_iter_all_filtre_par_provider_et_anciennete(db_session):
    from datetime import timedelta

    from app.core.time import utcnow

    # `source_url` en plus du provider, et ce n'est pas du décor depuis #279 : le
    # provider est porté par la **source**, dont l'URL est la raison d'être. Un
    # provider sans URL ne se range plus nulle part (cf.
    # `test_course_derived_source.test_a_provider_without_a_url_is_not_representable`).
    vieux = course_repository.get_or_create(
        db_session, name="Vieux", event_date=date(2025, 1, 1),
        event_type="triathlon-m", source_url="https://k/vieux", provider="klikego",
    )
    vieux.scraped_at = utcnow() - timedelta(days=40)
    frais = course_repository.get_or_create(
        db_session, name="Frais", event_date=date(2026, 1, 1),
        event_type="triathlon-m", source_url="https://t/frais", provider="timepulse",
    )
    frais.scraped_at = utcnow()
    db_session.flush()

    tous = course_repository.iter_all(db_session)
    assert {c.name for c in tous} == {"Vieux", "Frais"}

    klikego = course_repository.iter_all(db_session, provider="klikego")
    assert {c.name for c in klikego} == {"Vieux"}

    anciens = course_repository.iter_all(db_session, older_than_days=30)
    assert {c.name for c in anciens} == {"Vieux"}


def _epreuve_peuplee(db_session, nom, nb_participations):
    """Une épreuve et ses N résultats, chacun sur un athlète distinct."""
    from app.repositories import athlete_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 17),
        event_type="triathlon-m", source_url=f"https://k/{nom}", provider="klikego",
    )
    db_session.flush()
    for indice in range(nb_participations):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"{nom}-{indice}", prenom="Coureur"
        )
        db_session.flush()
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=course.id, bib_number=str(indice)
        )
    db_session.flush()
    return course


def test_delete_emporte_les_participations_de_l_epreuve(db_session):
    """AC1 — la cascade est portée par l'ORM (`delete-orphan`), pas par la DB."""
    from app.models.participation import Participation

    course = _epreuve_peuplee(db_session, "Supprimee", 3)
    course_id = course.id

    course_repository.delete(db_session, course)
    db_session.flush()

    assert course_repository.get(db_session, course_id) is None
    restantes = db_session.query(Participation).filter_by(course_id=course_id).count()
    assert restantes == 0


def test_delete_ne_touche_pas_les_epreuves_voisines(db_session):
    from app.models.participation import Participation

    cible = _epreuve_peuplee(db_session, "Cible", 2)
    voisine = _epreuve_peuplee(db_session, "Voisine", 2)
    voisine_id = voisine.id

    course_repository.delete(db_session, cible)
    db_session.flush()

    assert course_repository.get(db_session, voisine_id) is not None
    assert db_session.query(Participation).filter_by(course_id=voisine_id).count() == 2


def test_le_filtre_scope_club_utilise_l_index_fonctionnel(db_session):
    """Non-régression #351 : `_filtered(club_only=True)` ne balaie plus `participations`.

    Sans index fonctionnel, `tcn_clause(Participation.club)` (huit fonctions SQL
    imbriquées) ne peut être servi que ligne à ligne — mesuré 15-20x plus lent en
    production sur ce chemin (876-1906 ms contre 92-109 ms, sondage #328). Ce test
    verrouille le **plan de requête**, pas un temps d'exécution : à cette échelle,
    SQLite en mémoire reste rapide même sans index (~13 ms mesurés sur la base de
    dev, 20 300 lignes, cf. le commit) — un test chronométré ne détecterait donc
    pas la régression qu'un retrait de l'index représenterait.

    Volume comparable à l'ordre de grandeur du sondage (des milliers de lignes,
    pas une poignée) : bulk-insert via le Core plutôt que le repository ligne à
    ligne, dont chaque `flush()` serait un aller-retour à cette échelle.
    """
    course = course_repository.get_or_create(
        db_session, name="Volume club", event_date=date(2026, 5, 18),
        event_type="triathlon-m",
    )
    db_session.flush()

    nb_participations = 3000
    db_session.execute(
        Athlete.__table__.insert(),
        [
            {"nom": f"Bulk{i}", "prenom": "Test", "gender": "", "birth_date": None,
             "club": None, "created_at": utcnow()}
            for i in range(nb_participations)
        ],
    )
    db_session.flush()
    athlete_ids = [
        row[0]
        for row in db_session.execute(
            select(Athlete.id).where(Athlete.nom.like("Bulk%")).order_by(Athlete.id)
        ).all()
    ]
    db_session.execute(
        Participation.__table__.insert(),
        [
            {
                "athlete_id": athlete_id,
                "course_id": course.id,
                "club": "Triathlon Club Nantais" if i % 50 == 0 else f"Autre Club {i}",
                "bib_number": str(i),
                "status": "finisher",
                "created_at": utcnow(),
            }
            for i, athlete_id in enumerate(athlete_ids)
        ],
    )
    db_session.flush()

    qobj = course_repository._filtered(
        db_session, name=None, event_type=None, club_only=True,
        date_from=None, date_to=None,
    )
    # Même forme que la requête réellement journalisée « lente » dans le sondage :
    # un `count(*)` enveloppant la sous-requête distincte, pas la liste paginée.
    count_stmt = select(func.count()).select_from(qobj.statement.subquery())
    compiled = count_stmt.compile(db_session.bind, compile_kwargs={"literal_binds": True})

    with db_session.bind.connect() as conn:
        plan = [tuple(row) for row in conn.execute(text(f"EXPLAIN QUERY PLAN {compiled}"))]

    plan_text = " | ".join(str(row) for row in plan)
    assert "ix_participations_club_normalized" in plan_text, plan_text


def test_reset_scraped_at_all_remet_toutes_les_epreuves_a_null(db_session):
    a = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 1), event_type="triathlon-m"
    )
    b = course_repository.get_or_create(
        db_session, name="Tri B", event_date=date(2026, 5, 2), event_type="triathlon-m"
    )
    course_repository.touch_scraped_at(db_session, a)
    course_repository.touch_scraped_at(db_session, b)
    db_session.flush()

    touchees = course_repository.reset_scraped_at_all(db_session)

    assert touchees == 2
    db_session.expire(a)
    db_session.expire(b)
    assert course_repository.get(db_session, a.id).scraped_at is None
    assert course_repository.get(db_session, b.id).scraped_at is None


def test_delete_all_supprime_toutes_les_epreuves_sources_et_resultats(db_session):
    a = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 1), event_type="triathlon-m",
        source_url="https://k/a", provider="klikego",
    )
    b = course_repository.get_or_create(
        db_session, name="Tri B", event_date=date(2026, 5, 2), event_type="triathlon-m",
        source_url="https://k/b", provider="klikego",
    )
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.flush()
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=a.id, bib_number="1"
    )
    db_session.flush()

    efface = course_repository.delete_all(db_session)

    assert efface == 2
    assert course_repository.get(db_session, a.id) is None
    assert course_repository.get(db_session, b.id) is None
    assert db_session.query(CourseSource).count() == 0
    assert db_session.query(Participation).count() == 0
