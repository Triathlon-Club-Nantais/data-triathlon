"""
Statistiques détaillées d'une participation : comparaison au classement complet
de sa course.

Les trois agrégats — évolution du rang par étape, comparaison à des positions
de référence, simulation de gains par amélioration — sont recalculés à chaque
lecture depuis le classement déjà en base. Rien n'est persisté : un rang
recalculé à la lecture ne peut pas diverger de celui qu'affichent les autres
écrans de l'application.
"""
from sqlalchemy.orm import Session

from app.core.splits_reliability import is_stats_eligible
from app.models.participation import Participation
from app.repositories import participation_repository
from app.schemas.participation_stats import (
    ComparisonRow,
    ImprovementRow,
    ParticipationStatsOut,
    RankingEvolutionStep,
)
from app.scrapers.utils import to_seconds

#: Positions du classement scratch auxquelles l'athlète se compare, et leur
#: libellé affiché. Une position que l'épreuve n'atteint pas est omise, jamais
#: rendue vide : une ligne vide se lit comme une performance, pas comme une
#: absence de coureur.
REFERENCE_POSITIONS: tuple[tuple[int, str], ...] = (
    (1, "1er"),
    (10, "10e"),
    (25, "25e"),
    (50, "50e"),
    (100, "100e"),
)

#: Clé du temps final dans les dictionnaires de pourcentages, à côté des segments.
TOTAL_KEY = "total"

#: Pourcentages d'amélioration simulés, en clés de sortie JSON.
IMPROVEMENT_PERCENTAGES: tuple[str, ...] = ("0.5", "1", "2", "5", "10", "25")


def build(db: Session, participation: Participation) -> ParticipationStatsOut | None:
    """Agrégats de cette participation, ou `None` si elle n'y a pas droit.

    Un relais est exclu : ses segments se répartissent entre plusieurs athlètes,
    une lecture individuelle y serait fausse plutôt qu'incomplète.
    """
    if participation.is_relay or not is_stats_eligible(participation.course):
        return None
    ranking = participation_repository.list_for_course(db, participation.course_id)
    return build_from_ranking(participation, ranking)


def published_segments(ranking: list[Participation]) -> list[str]:
    """Segments réellement publiés par l'épreuve, dans leur ordre de publication.

    Union ordonnée plutôt que liste figée `swim/t1/bike/t2/run` : les clés
    dépendent du sport (`course1`/`course2` en duathlon, étiquettes libres sur
    le chemin générique de `mapping.build_splits`), et une épreuve sans
    transition chronométrée ne doit pas ouvrir de colonne T1 vide.
    """
    segments: dict[str, None] = {}
    for row in ranking:
        for segment in row.splits or {}:
            segments.setdefault(segment, None)
    return list(segments)


def _segment_seconds(participation: Participation, segment: str) -> int | None:
    """Durée d'un segment, ou du temps final pour la clé `total`.

    `strict=True` : ici l'absence de durée doit rester absente. Le mode
    permissif la ramènerait à zéro, et un zéro se lit comme un temps parfait.
    """
    if segment == TOTAL_KEY:
        return to_seconds(participation.total_time, strict=True)
    return to_seconds((participation.splits or {}).get(segment), strict=True)


def _comparison(
    participation: Participation, ranking: list[Participation], segments: list[str]
) -> list[ComparisonRow]:
    """Temps de l'athlète en pourcentage de celui des positions de référence."""
    by_rank = {row.rank_overall: row for row in ranking if row.rank_overall is not None}
    keys = [*segments, TOTAL_KEY]
    rows = []

    for rank, label in REFERENCE_POSITIONS:
        reference = by_rank.get(rank)
        if reference is None:
            continue
        percentages = {}
        for key in keys:
            mine = _segment_seconds(participation, key)
            theirs = _segment_seconds(reference, key)
            # Un segment manquant d'un côté ou de l'autre n'a pas de rapport à
            # exprimer. Le rendre à 0 ou à 100 inventerait une comparaison.
            if mine is None or not theirs:
                continue
            percentages[key] = round(mine / theirs * 100, 1)
        rows.append(ComparisonRow(position_label=label, rank=rank, percentages=percentages))

    return rows


def _cumulative_seconds(participation: Participation, segments: list[str]) -> int | None:
    """Temps cumulé jusqu'à la sortie d'une étape, ou `None` si un segment manque.

    Un cumul partiel placerait le coureur en tête : mieux vaut ne pas le classer
    sur cette étape que de lui inventer une avance.
    """
    total = 0
    for segment in segments:
        seconds = _segment_seconds(participation, segment)
        if seconds is None:
            return None
        total += seconds
    return total


def _rank_among(values: dict[int, int], participation_id: int) -> int | None:
    """Rang d'une participation sur une valeur, le plus petit temps en tête."""
    mine = values.get(participation_id)
    if mine is None:
        return None
    return 1 + sum(1 for value in values.values() if value < mine)


def _ranking_evolution(
    participation: Participation, ranking: list[Participation], segments: list[str]
) -> list[RankingEvolutionStep]:
    """Position cumulée et position sur le segment isolé, étape par étape."""
    steps = []

    for index, segment in enumerate(segments):
        traversed = segments[: index + 1]
        cumulative = {}
        isolated = {}
        for row in ranking:
            total = _cumulative_seconds(row, traversed)
            if total is not None:
                cumulative[row.id] = total
            seconds = _segment_seconds(row, segment)
            if seconds is not None:
                isolated[row.id] = seconds

        scratch = _rank_among(cumulative, participation.id)
        isolated_position = _rank_among(isolated, participation.id)
        if scratch is None or isolated_position is None:
            continue
        steps.append(
            RankingEvolutionStep(
                segment=segment,
                scratch_position=scratch,
                segment_position=isolated_position,
            )
        )

    # À l'arrivée, la position scratch **est** le classement de l'épreuve. La
    # recalculer par somme de splits la ferait diverger du rang affiché partout
    # ailleurs dès que les splits publiés ne totalisent pas le temps final.
    if steps and steps[-1].segment == segments[-1] and participation.rank_overall is not None:
        steps[-1].scratch_position = participation.rank_overall

    return steps


def _improvement(
    participation: Participation, ranking: list[Participation], segments: list[str]
) -> list[ImprovementRow]:
    """Places scratch gagnées si un segment avait été couru plus vite.

    Le rang courant est recalculé sur les temps finaux du classement plutôt que
    lu dans `rank_overall` : le gain est une **différence** entre deux rangs, et
    la mesurer entre deux bases distinctes la fausserait.
    """
    mine = _segment_seconds(participation, TOTAL_KEY)
    if mine is None:
        return []

    others = []
    for row in ranking:
        if row.id == participation.id:
            continue
        seconds = _segment_seconds(row, TOTAL_KEY)
        if seconds is not None:
            others.append(seconds)

    current_rank = 1 + sum(1 for total in others if total < mine)
    rows = []

    for segment in segments:
        seconds = _segment_seconds(participation, segment)
        if seconds is None:
            continue
        gains = {}
        for percentage in IMPROVEMENT_PERCENTAGES:
            improved = mine - seconds * float(percentage) / 100
            rank = 1 + sum(1 for total in others if total < improved)
            gains[percentage] = max(0, current_rank - rank)
        rows.append(ImprovementRow(segment=segment, gains=gains))

    return rows


def build_from_ranking(
    participation: Participation, ranking: list[Participation]
) -> ParticipationStatsOut:
    """Assemble les trois blocs à partir du classement complet, sans toucher la base."""
    segments = published_segments(ranking)
    return ParticipationStatsOut(
        segments=segments,
        ranking_evolution=_ranking_evolution(participation, ranking, segments),
        comparison=_comparison(participation, ranking, segments),
        improvement=_improvement(participation, ranking, segments),
    )
