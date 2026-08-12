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
    athlete_repository,
    course_repository,
    participation_repository,
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
