"""Ce qui compte pour le club : la règle, et son seul point d'écriture (#1206).

`Participation.counts_for_tcn` porte le verdict de chaque résultat, et
`Course.tcn_count` en est le compte dénormalisé (#623). Les deux se calculent
ici, en SQL, portable SQLite (dev, tests) et PostgreSQL (prod). Seules autres
écritures : la valeur provisoire de l'écouteur d'insertion de `Participation`
(la condition 1 seule, recalculée ensuite) et la remise à zéro de
`course_repository.zero_counts_all` quand toutes les participations sont effacées.

Un résultat compte pour le club si :

1. son libellé est dans la portée et n'est pas ambigu ;
2. son athlète, ou un équipier du relais, est un licencié rattaché pour la
   saison de l'épreuve (#1202) ;
3. son libellé est ambigu (« TCN », aussi le Triathlon Club Narbonne) et son
   athlète est rattaché au club par ailleurs : un autre résultat **validé**
   sous un libellé non ambigu, ou une licence rattachée de n'importe quelle
   saison.

Nulle part ailleurs la règle ne s'écrit.
"""
from collections.abc import Iterable

from sqlalchemy import and_, case, false, func, literal, or_, select, update
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from app.core.club import ClubLabels, _normalise_sql
from app.core.season import season_of_sql
from app.core.validation import validated_clause
from app.models.club_member import LINKED, ClubMember
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate


def _clear_label(club, labels: ClubLabels) -> ColumnElement[bool]:
    return _normalise_sql(club).in_(sorted(labels.clear))


def _ambiguous_label(club, labels: ClubLabels) -> ColumnElement[bool]:
    return _normalise_sql(club).in_(sorted(labels.ambiguous))


def linked_member(athlete_id, season=None) -> ColumnElement[bool]:
    """Un licencié rattaché à cette fiche, pour `season` ou n'importe quelle saison."""
    clauses = [ClubMember.athlete_id == athlete_id, ClubMember.link_status.in_(LINKED)]
    if season is not None:
        clauses.append(ClubMember.season == season)
    # `correlate_except` : l'équipier de la condition 2 vient de la requête englobante.
    return select(literal(1)).where(*clauses).correlate_except(ClubMember).exists()


def _member_of_course_season() -> ColumnElement[bool]:
    """Condition 2 : l'athlète, ou un équipier du relais, licencié la saison de l'épreuve.

    Sans date d'épreuve, la saison est NULL : aucune licence ne la couvre.
    """
    season = (
        select(season_of_sql(Course.event_date))
        .where(Course.id == Participation.course_id)
        .correlate(Participation)
        .scalar_subquery()
    )
    teammate_licensed = (
        select(literal(1))
        .where(
            ParticipationTeammate.participation_id == Participation.id,
            linked_member(ParticipationTeammate.athlete_id, season),
        )
        .correlate(Participation)
        .exists()
    )
    return or_(linked_member(Participation.athlete_id, season), teammate_licensed)


def _attached_to_club(labels: ClubLabels) -> ColumnElement[bool]:
    """Condition 3 : l'athlète de la ligne est rattaché au club par ailleurs."""
    other = aliased(Participation)
    clear_result = (
        select(literal(1))
        .where(
            other.athlete_id == Participation.athlete_id,
            other.id != Participation.id,
            validated_clause(other.is_pending_validation),
            _clear_label(other.club, labels),
        )
        .correlate(Participation)
        .exists()
    )
    return or_(clear_result, linked_member(Participation.athlete_id))


def _rule(labels: ClubLabels) -> ColumnElement[bool]:
    return or_(
        _clear_label(Participation.club, labels),
        _member_of_course_season(),
        and_(_ambiguous_label(Participation.club, labels), _attached_to_club(labels)),
    )


def _scope(course_ids: list[int] | None, athlete_ids: list[int] | None) -> ColumnElement[bool] | None:
    """`None` : toutes les lignes. Sinon l'union décrite par `recompute_counts_for_tcn`."""
    if course_ids is None and athlete_ids is None:
        return None
    conditions = []
    if course_ids:
        on_courses = aliased(Participation)
        conditions += [
            Participation.course_id.in_(course_ids),
            Participation.athlete_id.in_(
                select(on_courses.athlete_id).where(on_courses.course_id.in_(course_ids))
            ),
        ]
    if athlete_ids:
        conditions += [
            Participation.athlete_id.in_(athlete_ids),
            # Condition 2 : la licence d'un équipier fait compter le relais.
            Participation.id.in_(
                select(ParticipationTeammate.participation_id).where(
                    ParticipationTeammate.athlete_id.in_(athlete_ids)
                )
            ),
        ]
    return or_(*conditions) if conditions else false()


def recompute_counts_for_tcn(
    db: Session,
    *,
    course_ids: Iterable[int] | None = None,
    athlete_ids: Iterable[int] | None = None,
    labels: ClubLabels | None = None,
) -> None:
    """Réécrit `counts_for_tcn` sur la portée, puis `tcn_count` des épreuves touchées.

    Sans identifiant : tout. La portée d'une épreuve s'étend à tous les résultats
    de ses athlètes, la condition 3 traversant les épreuves. `course_ids` sert
    aussi à recompter une épreuve dont des lignes viennent d'être supprimées.
    `labels` : ceux d'une transaction pas encore rechargée dans le registre
    (écriture de la portée, #939) ; sinon le registre.
    """
    if labels is None:
        labels = ClubLabels.from_registry()
    courses = sorted(set(course_ids)) if course_ids is not None else None
    athletes = sorted(set(athlete_ids)) if athlete_ids is not None else None
    if (courses is not None or athletes is not None) and not courses and not athletes:
        return
    db.flush()

    scope = _scope(courses, athletes)
    statement = update(Participation).values(
        counts_for_tcn=case((_rule(labels), True), else_=False)
    )
    if scope is not None:
        touched = set(db.scalars(select(Participation.course_id).where(scope).distinct()))
        touched.update(courses or ())
        statement = statement.where(scope)
    db.execute(statement.execution_options(synchronize_session=False))

    counted = (
        select(func.count(Participation.id))
        .where(
            Participation.course_id == Course.id,
            validated_clause(Participation.is_pending_validation),
            Participation.counts_for_tcn.is_(True),
        )
        .correlate(Course)
        .scalar_subquery()
    )
    recount = update(Course).values(tcn_count=counted)
    if scope is not None:
        recount = recount.where(Course.id.in_(sorted(touched)))
    db.execute(recount.execution_options(synchronize_session=False))
    _expire_verdicts(db)


def _expire_verdicts(db: Session) -> None:
    """Les instances déjà chargées relisent le verdict : une route qui sérialise
    une ligne qu'elle tient ne doit pas servir l'ancien."""
    for instance in list(db.identity_map.values()):
        if isinstance(instance, Participation):
            db.expire(instance, ["counts_for_tcn"])
        elif isinstance(instance, Course):
            db.expire(instance, ["tcn_count"])
