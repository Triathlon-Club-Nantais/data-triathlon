"""DTO de la liste des doublons suspects (#288) et de leur mise à l'écart (#754)."""
from datetime import date, datetime

from pydantic import BaseModel, StrictInt


class DuplicateCourse(BaseModel):
    """Une épreuve d'une paire suspecte, avec de quoi trancher sur place.

    Les deux compteurs et non un : « le nombre d'athlètes est différent entre les
    2 imports » est l'observation qui a ouvert #261, et c'est **l'écart** entre
    les deux publications qui dit laquelle garder. Un second appel par épreuve
    pour l'obtenir mettrait cette information hors de portée de la liste.
    """

    id: int
    name: str
    event_date: date | None
    event_type: str
    is_relay: bool
    provider: str
    source_url: str
    total: int
    tcn_count: int


class DuplicateCandidate(BaseModel):
    """Une paire à arbitrer, et le motif qui l'a fait remonter.

    Deux champs pour un seul motif, et les deux servent : `reason` est le code
    stable sur lequel l'écran branche son traitement — #292 présente le cas
    « même URL » à part, parce qu'il se règle par une correction d'identité et
    non par un choix de chronométreur — et `reason_label` est la phrase affichée.

    Une paire, et non un cluster : les trois cas observés sont des paires, et un
    doublon triple se traiterait en deux passes, la liste se relisant après
    chaque arbitrage. Rendre des clusters obligerait l'écran à savoir fusionner
    N épreuves d'un coup pour un cas qui n'existe pas encore.
    """

    reason: str
    reason_label: str
    courses: list[DuplicateCourse]


class DuplicateCandidateCount(BaseModel):
    """Le nombre de paires suspectes — la pastille de la nav admin (#726)."""

    total: int


class DuplicateCandidateList(BaseModel):
    """Enveloppe, plutôt qu'une liste nue : la liste est la première d'une page
    d'administration qui accueillera des compteurs (#292), et un tableau JSON
    racine ne peut pas en recevoir sans casser le contrat."""

    candidates: list[DuplicateCandidate]


class DuplicateIgnoreCreate(BaseModel):
    """Corps de `POST /admin/courses/duplicates/ignore` (#754).

    `StrictInt`, patron de `CourseMergeRequest.absorbed_id` : en mode permissif,
    Pydantic coerce `true` en `1`, et une case à cocher mal sérialisée écarterait
    l'épreuve `1` d'une paire qu'elle ne visait pas.
    """

    course_id_a: StrictInt
    course_id_b: StrictInt


class DuplicateIgnoreOut(BaseModel):
    """Ce que l'écran reçoit après avoir écarté une paire (#754)."""

    course_id_a: int
    course_id_b: int
    ignored_at: datetime
