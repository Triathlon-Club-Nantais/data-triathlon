"""La portée des compteurs ne coûte aucune requête (#95, FR-006, SC-004).

Le registre est lu **en mémoire**. Un classement de 3 000 lignes ne doit donc
pas payer une requête de plus qu'avant la bascule en base.

La forme du test n'est pas un avant/après : celui-ci ne serait ni reproductible
ni rejouable en CI, et il ne dirait rien le jour où quelqu'un remettrait une
lecture par participation. On mesure la **propriété** elle-même — le nombre de
requêtes ne croît pas avec le nombre de participations —, sur le patron déjà
posé par `test_services/test_course_merge.py`. C'est la seule forme qui
distingue une lecture en mémoire d'une boucle.
"""
from datetime import date

from sqlalchemy import event

from app.core.club import tcn_clause
from app.core.discipline import federal_clause
from app.models.course import Course
from app.models.participation import Participation
from app.repositories import athlete_repository, course_repository, participation_repository


def _peupler(db_session, *, lignes: int, marqueur: str) -> None:
    """Une épreuve de `lignes` participations, moitié au club, moitié ailleurs."""
    course = course_repository.get_or_create(
        db_session,
        name=f"Tri {marqueur}",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
    )
    db_session.flush()
    for rang in range(lignes):
        athlete = athlete_repository.get_or_create(
            db_session, nom=f"COUREUR{marqueur}-{rang}", prenom="Test"
        )
        db_session.flush()
        participation_repository.create(
            db_session,
            athlete_id=athlete.id,
            course_id=course.id,
            bib_number=f"{marqueur}-{rang}",
            club="Triathlon Club Nantais" if rang % 2 else "RACING CLUB NANTAIS *",
        )
    db_session.commit()


def _requetes_pour(db_session, *, lignes: int, marqueur: str) -> list[str]:
    _peupler(db_session, lignes=lignes, marqueur=marqueur)
    requetes: list[str] = []

    def _noter(conn, cursor, statement, *reste):
        requetes.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _noter)
    try:
        # Les deux prédicats SQL sur la même requête, et la lecture des DTO qui
        # évalue `is_tcn` en Python ligne par ligne — c'est ce dernier qui
        # paierait une requête par participation s'il en payait une.
        lignes_lues = (
            db_session.query(Participation)
            .join(Course, Participation.course_id == Course.id)
            .filter(tcn_clause(Participation.club))
            .filter(federal_clause(Course.event_type))
            .all()
        )
        from app.core.club import is_tcn

        for participation in lignes_lues:
            is_tcn(participation.club)
    finally:
        event.remove(engine, "before_cursor_execute", _noter)
    return requetes


def test_le_nombre_de_requetes_ne_croit_pas_avec_les_participations(db_session):
    """Deux tailles, un seul compte : la configuration est lue en mémoire.

    Ce que ce test attrape, exactement : une lecture **par participation**,
    donc une régression de `is_tcn` ou `is_federal` — un chargement paresseux
    « au cas où » posé dans le prédicat Python. Il le ferait proportionnellement
    au volume, ce qu'un chronomètre ne sait pas montrer.

    Ce qu'il n'attrape pas, et il faut le savoir : une lecture **par requête**
    reste O(1), donc un cache relu une fois par requête HTTP le laisserait vert.
    Les deux miroirs SQL, appelés une fois par requête, sont dans ce cas.
    """
    petit = _requetes_pour(db_session, lignes=4, marqueur="petit")
    grand = _requetes_pour(db_session, lignes=40, marqueur="grand")

    assert len(petit) == len(grand), (
        f"{len(petit)} requêtes sur 4 participations, {len(grand)} sur 40 : "
        "la portée des compteurs se lit en base au lieu du registre.\n"
        + "\n".join(grand)
    )
