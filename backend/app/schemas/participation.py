"""Schémas Pydantic pour Participation (sortie imbriquée et création manuelle)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.club import is_tcn as _is_tcn
from app.schemas.athlete import AthleteBrief
from app.schemas.course import CourseBrief
from app.schemas.participation_stats import ParticipationStatsOut


class ParticipationOut(BaseModel):
    """Résultat d'un athlète sur une course, athlète + course imbriqués."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete: AthleteBrief
    course: CourseBrief
    club: str | None = None
    category: str | None = None
    bib_number: str | None = None
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str | None = None
    status: str = "finisher"
    is_relay: bool = False
    team_name: str | None = None
    evidence_url: str | None = None
    # Résultat déclaré non encore vérifié par un bénévole (#270, #271).
    is_pending_validation: bool = False
    # Écarté par un bénévole comme non conforme (#437).
    is_rejected: bool = False
    splits: dict[str, str] | None = None
    created_at: datetime | None = None
    #: Statistiques détaillées, peuplées par la seule lecture d'**une** participation
    #: (`GET /participations/{id}`). Ailleurs — liste des finishers, fiche athlète —
    #: le champ existe mais reste `None` : aucun classement n'est parcouru pour lui.
    stats: ParticipationStatsOut | None = None

    @computed_field
    @property
    def is_tcn(self) -> bool:
        """Appartenance au club, tranchée par le backend.

        Exposée pour que le front n'ait pas à réimplémenter le prédicat : c'est
        cette duplication qui avait divergé et laissé passer les faux positifs
        de l'issue #76.
        """
        return _is_tcn(self.club)


class AthleteParticipationOut(ParticipationOut):
    """Participation vue depuis la fiche athlète : porte la taille du classement.

    `course_finishers` = nombre de finishers classés de la course, dans le même
    groupe solo/relais. `None` si le groupe n'a aucun classé. Champ réservé à la
    fiche athlète : le mettre sur `ParticipationOut` ferait payer l'agrégat aux
    routes de liste, qui n'en ont pas l'usage.
    """

    course_finishers: int | None = None


class CourseParticipationPage(BaseModel):
    """Réponse de `GET /courses/{id}` : l'épreuve et une tranche du classement.

    Le champ s'appelle `participations` et non `items` : c'est la clé que la
    route rend depuis toujours. La feature #163 change la **quantité** de lignes
    rendues par défaut, pas leur nom.

    `total` porte sur la sélection — recherche et portée club appliquées — et
    non sur l'épreuve : c'est lui qui donne le nombre de pages. Les décomptes
    d'épreuve entière vivent dans `CourseSummary`, et nulle part ailleurs.

    Réside ici plutôt que dans `schemas/course.py` pour ne pas créer de cycle
    d'import : ce module importe déjà `CourseBrief`.
    """

    course: CourseBrief
    participations: list[ParticipationOut]
    total: int
    page: int
    # `None` quand `page_size=all` a été demandé : il n'y a pas eu de découpage.
    page_size: int | None = None


class ParticipationCreate(BaseModel):
    """
    Création manuelle d'un résultat. Porte l'identité de l'athlète et de la course
    (forme plate) ; le service les normalise en Athlete + Course + Participation.
    """

    # Source / provider
    source_url: str = ""
    provider: str = "manuel"
    # Athlète
    athlete_name: str = ""
    athlete_firstname: str = ""
    gender: str = ""
    club: str = ""
    # Épreuve
    event_name: str = ""
    event_date: str | None = None
    event_type: str = ""
    is_relay: bool = False
    # Format libre quand l'épreuve n'entre dans aucune taille normalisée
    # (« Autre » du formulaire, #270). Propriété de l'épreuve.
    format_label: str = ""
    # Distance totale pour les disciplines sans format normalisé (#270).
    distance_km: float | None = None
    # Participation
    bib_number: str = ""
    category: str = ""
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str = ""
    status: str = ""
    # Nom de l'équipe si `is_relay` est vrai, lien vers les résultats publiés
    # comme pièce de vérification — jamais une source de scraping (#270).
    team_name: str = ""
    evidence_url: str = ""
    # Segments — commodité de saisie triathlon (mappés vers splits, ré-étiquetés
    # par sport). Pour les autres sports, préférer `segments` (chemin générique).
    swim_time: str = ""
    t1_time: str = ""
    bike_time: str = ""
    t2_time: str = ""
    run_time: str = ""
    # Chemin générique optionnel : liste ordonnée de (label, temps). Si renseigné,
    # prime sur les champs ci-dessus (déplafonné, étiquettes libres).
    segments: list[tuple[str, str]] | None = None
    raw_data: dict = {}
