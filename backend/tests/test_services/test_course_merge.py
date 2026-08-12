"""L'aperçu d'impact compte en SQL, jamais en Python (#286).

Un aperçu qui chargerait les deux classements pour les comparer en mémoire
tiendrait sur les épreuves de cette fixture et s'effondrerait sur les vraies :
l'épreuve la plus chargée de la base porte 1811 participations (#163). Le test
ci-dessous mesure le **nombre de requêtes**, pas le temps, et le compare entre
deux tailles de jeu — c'est la seule forme qui distingue un compte agrégé d'une
boucle.
"""
from datetime import date

from sqlalchemy import event

from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import course_merge


def _two_courses(db_session, *, results: int, marker: str):
    """Deux épreuves de `results` lignes chacune, aux dossards tous distincts.

    `marker` isole les deux jeux d'un même test : sans lui, la seconde paire
    retomberait sur les épreuves de la première (`uq_course_identity`) et
    l'insertion buterait sur `uq_participation_bib`.
    """
    target = course_repository.get_or_create(
        db_session, name=f"Cible {marker}", event_date=date(2026, 5, 16),
        event_type="triathlon-m", source_url=f"https://k/{marker}", provider="klikego",
    )
    absorbed = course_repository.get_or_create(
        db_session, name=f"Absorbée {marker}", event_date=date(2026, 5, 16),
        event_type="triathlon-s", source_url=f"https://b/{marker}", provider="breizhchrono",
    )
    db_session.flush()
    for rank in range(results):
        for course, offset in ((target, 0), (absorbed, 1000)):
            athlete = athlete_repository.get_or_create(
                db_session, nom=f"COUREUR{marker}-{rank + offset}", prenom="Test"
            )
            db_session.flush()
            participation_repository.create(
                db_session,
                athlete_id=athlete.id,
                course_id=course.id,
                bib_number=str(rank + offset),
                club="Triathlon Club Nantais",
            )
    db_session.commit()
    return target, absorbed


def _queries_for(db_session, *, results: int, marker: str) -> list[str]:
    target, absorbed = _two_courses(db_session, results=results, marker=marker)
    queries: list[str] = []

    def _record(conn, cursor, statement, *rest):
        queries.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _record)
    try:
        course_merge.merge_impact(db_session, course_id=target.id, absorbed_id=absorbed.id)
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return queries


def test_the_query_count_does_not_grow_with_the_number_of_results(db_session):
    """Le même nombre de requêtes sur 2 résultats et sur 40 : aucune boucle.

    Instrumenter le service entier, et non la seule requête d'agrégation : un
    lazy-load sur `course.sources` ou sur `participation.athlete` resterait
    invisible autrement, et c'est précisément la forme que prend le N+1 ici.
    """
    small = _queries_for(db_session, results=1, marker="small")
    large = _queries_for(db_session, results=20, marker="large")

    assert len(small) == len(large), (
        f"{len(small)} requêtes sur 2 résultats, {len(large)} sur 40 : "
        f"un compte s'est fait en Python\n" + "\n".join(large)
    )


def test_the_merge_flushes_but_never_commits(db_session):
    """Le service écrit sans clore : c'est la route qui `commit` (#287, FR-015).

    Sans cette propriété, le geste et sa trace cesseraient d'être indissociables —
    un `commit` dans le service rendrait irrécupérable une fusion dont
    l'enregistrement au journal échouerait ensuite, et le rollback ci-dessous ne
    ramènerait rien. Le test rejoue donc la transaction à l'envers : après
    `rollback`, l'épreuve absorbée doit être **exactement** là où elle était.
    """
    target, absorbed = _two_courses(db_session, results=2, marker="rollback")
    user = user_repository.create(db_session, email="fusion@exemple.fr")
    db_session.commit()

    course_merge.merge_courses(
        db_session, course_id=target.id, absorbed_id=absorbed.id, user_id=user.id
    )
    assert course_repository.get(db_session, absorbed.id) is None

    db_session.rollback()

    assert course_repository.get(db_session, absorbed.id) is not None
    assert participation_repository.count_for_course(db_session, absorbed.id) == 2
    assert (
        admin_action_log_repository.list_for_entity(
            db_session, entity_type="course", entity_id=target.id
        )
        == []
    )
