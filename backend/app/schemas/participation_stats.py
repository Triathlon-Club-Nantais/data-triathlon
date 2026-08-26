"""Schémas Pydantic des statistiques détaillées d'une participation.

Tous ces objets sont des agrégats **calculés à la lecture** à partir du
classement complet de la course. Aucun n'est persisté : c'est ce qui garantit
qu'un rang affiché ici ne peut pas diverger de celui des autres écrans.
"""
from pydantic import BaseModel, Field


class RankingEvolutionStep(BaseModel):
    """Une étape du graphique d'évolution du classement."""

    segment: str
    scratch_position: int
    segment_position: int


class ComparisonRow(BaseModel):
    """Comparaison de l'athlète au coureur occupant une position de référence."""

    position_label: str
    rank: int
    #: Par clé de segment, plus « total » : temps de l'athlète en pourcentage de la référence.
    percentages: dict[str, float]
    #: Mêmes clés que `percentages` : temps bruts en secondes, déjà calculés
    #: avant réduction en pourcentage (US4, #466).
    mine_seconds: dict[str, int] = Field(default_factory=dict)
    theirs_seconds: dict[str, int] = Field(default_factory=dict)


class ImprovementRow(BaseModel):
    """Places scratch gagnées si un segment avait été amélioré d'un pourcentage donné."""

    segment: str
    gains: dict[str, int]


class ParticipationStatsOut(BaseModel):
    """Enveloppe des trois agrégats. `null` en sortie d'API quand la course n'est pas éligible."""

    #: Segments effectivement publiés par l'épreuve, dans l'ordre d'affichage.
    #: Porté par l'enveloppe plutôt que déduit des blocs : ceux-ci omettent les
    #: valeurs manquantes, et une colonne se déduirait alors de son absence.
    segments: list[str] = Field(default_factory=list)
    ranking_evolution: list[RankingEvolutionStep] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)
    improvement: list[ImprovementRow] = Field(default_factory=list)
