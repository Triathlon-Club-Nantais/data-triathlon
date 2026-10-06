"""Schémas Pydantic pour Participation (sortie imbriquée et création manuelle)."""
import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from app.schemas.athlete import AthleteBrief
from app.schemas.challenge import AthleteChallengeOut
from app.schemas.course import CourseBrief
from app.schemas.participation_stats import ParticipationStatsOut
from app.scrapers.base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER
from app.scrapers.classify import CANONICAL_TYPES
from app.services import split_gap

_DUREE = r"^(\d{1,3}:[0-5]\d:[0-5]\d)?$"

#: Une durée `H:MM:SS`, ou vide (#1019).
Duree = Annotated[str, Field(pattern=_DUREE)]


def _segment_duree(segment: tuple[str, str]) -> tuple[str, str]:
    if not re.fullmatch(_DUREE, segment[1]):
        raise ValueError("Temps attendu au format H:MM:SS.")
    return segment


class ParticipationOut(BaseModel):
    """Résultat d'un athlète sur une course, athlète + course imbriqués."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete: AthleteBrief
    # Équipiers d'un relais attribué (#894), porteur compris ; vide sinon.
    teammates: list[AthleteBrief] = []
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
    #: Ce résultat compte-t-il pour le club ? Verdict stocké (#1206), lu sur
    #: `Participation.counts_for_tcn` : le front n'a pas à réimplémenter la règle,
    #: c'est cette duplication qui avait laissé passer les faux positifs de #76.
    is_tcn: bool = Field(default=False, validation_alias=AliasChoices("counts_for_tcn", "is_tcn"))
    splits: dict[str, str] | None = None
    created_at: datetime | None = None
    #: Statistiques détaillées, peuplées par la seule lecture d'**une** participation
    #: (`GET /participations/{id}`). Ailleurs — liste des finishers, fiche athlète —
    #: le champ existe mais reste `None` : aucun classement n'est parcouru pour lui.
    stats: ParticipationStatsOut | None = None

    @computed_field
    @property
    def split_gap_ratio(self) -> float | None:
        """Écart relatif **signé** entre le temps total et la somme des inters (#486).

        Exposé pour la même raison que `is_tcn`, et c'est le même
        précédent qui l'impose : le front en a besoin par ligne, le serveur en a besoin
        pour la médiane d'épreuve, et deux implémentations de la même règle divergent
        (#76). Le serveur mesure, l'écran applique ses seuils d'affichage.

        `None` dès qu'une des cinq conditions d'évaluabilité manque : relais, splits
        absents, schéma de segments incomplet, temps total ou inter illisible.
        """
        return split_gap.gap(
            self.total_time,
            self.splits,
            event_type=self.course.event_type,
            is_relay=self.course.is_relay,
        )


class AthleteParticipationOut(ParticipationOut):
    """Participation vue depuis la fiche athlète : porte la taille du classement.

    `course_finishers` = nombre de finishers classés de la course, dans le même
    groupe solo/relais. `None` si le groupe n'a aucun classé. Champ réservé à la
    fiche athlète : le mettre sur `ParticipationOut` ferait payer l'agrégat aux
    routes de liste, qui n'en ont pas l'usage.
    """

    course_finishers: int | None = None


class AthleteDetail(BaseModel):
    """`GET /athletes/{id}` : la fiche et ses participations (#1055)."""

    athlete: AthleteBrief
    participations: list[AthleteParticipationOut]
    #: Classements Challenge (#1008) : la carrière entière, `seasons` et
    #: `federal_only` ne s'y appliquent pas.
    challenges: list[AthleteChallengeOut] = []


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

    **Contrat resserré par #1019** (changement explicite, Principe IV) : la route
    est ouverte sans session, et une valeur hors nomenclature (type, statut,
    date illisible) retirait le résultat des filtres et des saisons **en
    silence**, sans correction possible depuis la page bénévole. Mêmes règles
    qu'`AdminCourseUpdate` et `AdminAthleteUpdate` sur les mêmes colonnes. Un
    champ inconnu reste ignoré : c'est ainsi que `raw_data`, que le formulaire
    n'envoie pas et dont la taille n'était pas bornée, n'est plus lu.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # Ignoré par la route, jamais lu (#565) : accepté pour ne pas casser un
    # appelant `/api/v1` existant (Principe IV), mais `provider="manuel"` et
    # l'absence de source active sont forcés côté serveur, voir
    # `api/v1/participations._to_scraped` et `backend/app/api/AGENTS.md`.
    source_url: str = ""
    # Athlète
    athlete_name: str = Field(min_length=1, max_length=200)
    athlete_firstname: str = ""
    gender: str = ""
    club: str = ""
    # Épreuve
    event_name: str = Field(min_length=1, max_length=300)
    event_date: date | None = None
    event_type: str
    is_relay: bool = False
    # Format libre quand l'épreuve n'entre dans aucune taille normalisée
    # (« Autre » du formulaire, #270). Propriété de l'épreuve.
    format_label: str = ""
    # Distance totale pour les disciplines sans format normalisé (#270).
    distance_km: float | None = None
    # Participation
    bib_number: str = ""
    category: str = ""
    rank_overall: int | None = Field(default=None, ge=1)
    rank_category: int | None = Field(default=None, ge=1)
    rank_gender: int | None = Field(default=None, ge=1)
    total_time: Duree = ""
    status: Literal["", STATUS_FINISHER, STATUS_DNF, STATUS_DNS, STATUS_DSQ] = ""
    # Nom de l'équipe si `is_relay` est vrai, lien vers les résultats publiés
    # comme pièce de vérification — jamais une source de scraping (#270).
    team_name: str = ""
    evidence_url: str = ""
    # Segments — commodité de saisie triathlon (mappés vers splits, ré-étiquetés
    # par sport). Pour les autres sports, préférer `segments` (chemin générique).
    swim_time: Duree = ""
    t1_time: Duree = ""
    bike_time: Duree = ""
    t2_time: Duree = ""
    run_time: Duree = ""
    # Chemin générique optionnel : liste ordonnée de (label, temps). Si renseigné,
    # prime sur les champs ci-dessus (déplafonné, étiquettes libres).
    segments: list[Annotated[tuple[str, str], AfterValidator(_segment_duree)]] | None = None

    @field_validator("event_type")
    @classmethod
    def _slug_connu(cls, valeur: str) -> str:
        if valeur not in CANONICAL_TYPES:
            raise ValueError(
                f"Type d'épreuve inconnu. Valeurs acceptées : "
                f"{', '.join(sorted(CANONICAL_TYPES))}."
            )
        return valeur
