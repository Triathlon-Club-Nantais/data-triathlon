"""DTO Pydantic pour le calendrier des entraînements jeunes (#868, epic #863)."""
from datetime import date as date_
from datetime import time as time_

from pydantic import BaseModel, ConfigDict

from app.schemas.ids import DbId
from app.schemas.utc_datetime import UtcDatetime


class ParticipantRead(BaseModel):
    """Un participant inscrit à un entraînement.

    `profile_id` seul, pas de nom : le profil du jeune référencé est porté par
    la sous-issue parallèle #867 (cf. `research.md` §Dépendance sur le profil
    jeune). Seul le contact d'urgence y est joint, pour l'appel (#1405).

    `present` (#869) est le statut de l'appel de **début** : `None` = pas
    encore pointé, `True`/`False` = le dernier statut enregistré.
    """

    profile_id: int
    present: bool | None = None
    #: Faux pour une inscription d'office par groupe (#1291).
    added_manually: bool
    #: Catégorie FFTri du profil, `None` sans date de naissance (#1291).
    category: str | None
    created_at: UtcDatetime
    #: Contact d'urgence du profil (#1405), `""` s'il est vide, `None` sans le pouvoir `jeunes:read`.
    emergency_contact: str | None = None


class TrainingSessionRead(BaseModel):
    """Un entraînement tel qu'il apparaît dans la liste du calendrier.

    `participant_count` évite un aller-retour par séance pour afficher la
    liste ; il ne remplace pas le détail, qui seul nomme les inscrits.
    """

    id: int
    date: date_
    start_time: time_ | None
    location: str | None
    session_type: str | None
    #: Note de séance en texte libre (#869) — rapport de l'encadrant.
    note: str
    participant_count: int
    #: Groupes visés, récurrence d'origine et séance modifiée seule (#1291).
    group_ids: list[int]
    recurrence_id: int | None
    detached: bool


class TrainingSessionDetailRead(TrainingSessionRead):
    """Un entraînement et sa liste de participants inscrits."""

    participants: list[ParticipantRead]


class TrainingSessionCreate(BaseModel):
    """Création d'un entraînement. Seule `date` est obligatoire (#868)."""

    model_config = ConfigDict(extra="forbid")

    date: date_
    start_time: time_ | None = None
    location: str | None = None
    session_type: str | None = None
    group_ids: list[DbId] = []


class TrainingSessionUpdate(BaseModel):
    """Modification d'un entraînement. Les cinq champs sont facultatifs et
    indépendants — seuls ceux fournis sont écrits (même patron que `GroupUpdate`).

    `note` (#869) n'est *pas* nullable côté modèle (`TrainingSession.note`,
    `NOT NULL`, défaut `""`) : un `PATCH` envoyant `null` n'a pas de sens
    (« pas de note » se dit `""`), traité côté route comme « champ absent ».
    """

    model_config = ConfigDict(extra="forbid")

    date: date_ | None = None
    start_time: time_ | None = None
    location: str | None = None
    session_type: str | None = None
    note: str | None = None
    #: Absent = groupes inchangés ; `[]` retire tous les groupes visés (#1291).
    group_ids: list[DbId] | None = None


class ParticipantAdd(BaseModel):
    """Inscription d'un jeune à un entraînement, par son identifiant seul.

    `present` (#869) pointe le jeune au même geste que son inscription —
    optionnel, défaut `None` (pas encore pointé), cf. `research.md` D4.
    """

    model_config = ConfigDict(extra="forbid")

    profile_id: DbId
    present: bool | None = None


class PresenceUpdate(BaseModel):
    """Corps de `PATCH .../participants/{profile_id}/presence` (#869).

    `present` est obligatoire, jamais `None` : cette route ne sert qu'à
    basculer entre présent et absent, jamais à revenir à « pas pointé »."""

    model_config = ConfigDict(extra="forbid")

    present: bool
