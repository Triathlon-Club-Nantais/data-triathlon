"""DTO des ressources d'administration (#115) — formes de `contracts/admin-api.md`."""
from datetime import date, datetime
from typing import ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_serializer,
    field_validator,
    model_validator,
)

from app.schemas.course import CourseSourceOut


class PermissionRead(BaseModel):
    """Un pouvoir de l'inventaire, prêt à cocher.

    `code` est un identifiant technique anglais et **stable** — il traverse la
    base ; `label` et `description` sont du français d'affichage.
    """

    code: str
    label: str
    description: str


class PermissionGroupRead(BaseModel):
    """Les pouvoirs d'une fonctionnalité. Composer un rôle en cochant dans une
    liste plate de codes techniques est le geste qu'on veut éviter."""

    feature: str
    permissions: list[PermissionRead]


class RoleBrief(BaseModel):
    """Un rôle tel qu'il se présente à son porteur — sans sa composition."""

    id: int
    slug: str
    name: str
    organisation_id: int | None


class RoleRead(BaseModel):
    """Un rôle, sa composition et son nombre de porteurs.

    `stale_permissions` liste les codes présents en base mais absents de
    l'inventaire — inertes, purgeables, jamais bloquants (FR-042). Les séparer
    de `permissions` est ce qui rend l'écran honnête : « ce rôle porte un code
    que l'application ne connaît plus » se lit, « ce rôle porte 4 pouvoirs dont
    un fantôme » ne se lit pas.
    """

    id: int
    organisation_id: int | None
    slug: str
    name: str
    description: str
    is_system: bool
    is_superuser: bool
    permissions: list[str]
    stale_permissions: list[str]
    holders: int


class RoleCreate(BaseModel):
    """Création d'un rôle. Le `slug` est fixé ici **une fois pour toutes**."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1)
    description: str = ""
    organisation_id: int | None = None
    permissions: list[str] = Field(default_factory=list)
    is_superuser: bool = False


class RoleUpdate(BaseModel):
    """Modification d'un rôle. Champs tous facultatifs, `permissions` **remplace**.

    `extra="forbid"` n'est pas de la rigueur gratuite : c'est ce qui fait qu'un
    `slug` soumis rend **422** au lieu d'être ignoré en silence. Le slug est le
    seul nom qui traverse une frontière (`grant-role --role`, le semis) ; le
    renommer casserait les deux sans bruit.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    permissions: list[str] | None = None
    is_superuser: bool | None = None


class RoleAssign(BaseModel):
    """Attribution d'un rôle. `organisation_id` vaut par défaut le seul club."""

    model_config = ConfigDict(extra="forbid")

    role_id: int
    organisation_id: int | None = None


class AdminUserRead(BaseModel):
    """Un utilisateur vu depuis l'administration.

    Sans pagination : le peuplement d'`users` est borné par la liste
    d'autorisation (`allowed_emails`, #170) — une personne y naît d'une
    connexion réussie **et autorisée**.
    """

    id: int
    email: str
    display_name: str
    is_active: bool
    roles: list[RoleBrief]
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        """Suffixe `Z`, comme `SessionUserRead` : les colonnes sont des datetimes
        **naïfs en UTC**, et un naïf sérialisé tel quel serait lu comme une heure
        locale par le client."""
        return f"{value.isoformat()}Z"


class GroupRead(BaseModel):
    """Un groupe tel qu'il apparaît dans la liste (#197).

    `member_count` évite un aller-retour par groupe pour afficher une liste ; il
    ne remplace pas le détail, qui seul nomme les membres.

    **Ni `is_superuser`, ni `is_system`, ni `permissions`** : un groupe n'accorde
    rien, et aucun n'est livré avec l'application. C'est ce qui le distingue d'un
    `RoleRead`, dont il partage par ailleurs la forme.
    """

    id: int
    organisation_id: int
    slug: str
    name: str
    description: str
    member_count: int
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return f"{value.isoformat()}Z"


class GroupMemberRead(BaseModel):
    """Un membre d'un groupe.

    `is_active` est rendu délibérément : un compte désactivé **reste membre** —
    rien de ce que porte un groupe ne dépend de son activité —, et un écran qui
    l'ignorerait afficherait un Codir faux.
    """

    user_id: int
    email: str
    display_name: str
    is_active: bool
    joined_at: datetime

    @field_serializer("joined_at")
    def _serialize_utc(self, value: datetime) -> str:
        return f"{value.isoformat()}Z"


class GroupDetailRead(GroupRead):
    """Un groupe et sa composition — la ressource qui justifie l'objet entier.

    « Liste-moi les membres du Codir » n'est rendu proprement par aucune
    agrégation de rôles : c'est la raison pour laquelle un groupe est un objet et
    non une convention de nommage.
    """

    members: list[GroupMemberRead]


class GroupCreate(BaseModel):
    """Création d'un groupe. Le `slug` est fixé ici **une fois pour toutes**.

    `organisation_id` vaut par défaut le seul club en base, comme pour
    l'attribution d'un rôle. La colonne, elle, est **non nulle** : un groupe
    global n'existe pas.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1)
    description: str = ""
    organisation_id: int | None = None


class GroupUpdate(BaseModel):
    """Modification d'un groupe. Les deux champs sont facultatifs et indépendants.

    `slug` et `organisation_id` sont **absents** : `extra="forbid"` en fait un
    422 plutôt qu'un silence. Renommer le slug d'un groupe serait un changement
    d'identité déguisé en modification de libellé.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class GroupMemberAdd(BaseModel):
    """Ajout d'un membre. Idempotent : réajouter est un succès."""

    model_config = ConfigDict(extra="forbid")

    user_id: int


class AdminAthleteRead(BaseModel):
    """Une fiche coureur **complète**, servie derrière `athletes:read` (#117).

    Diffère d'`AthleteBrief` par deux champs, et ce sont les deux qui comptent
    pour départager des homonymes : `birth_date` — le tiers de l'identité, et la
    seule donnée personnelle que le site garde fermée (FR-025) — et
    `participations`, le poids de la fiche.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str = ""
    birth_date: date | None = None
    gender: str = ""
    club: str | None = None
    participations: int = 0


class ParticipationReassign(BaseModel):
    """Le coureur vers qui déplacer un résultat."""

    athlete_id: int


class _PatchNonVide(BaseModel):
    """Socle des corrections partielles : un corps sans aucun champ est un 422.

    Sans ce contrôle, `PATCH {}` répondrait 200 sans rien faire — une réussite
    qui n'a rien réussi. Le **champ présent** est ce qui compte, pas sa valeur :
    `event_date: null` est une mise à `NULL` légitime, et `model_fields_set` est
    la seule chose qui la distingue d'une absence.

    `str_strip_whitespace` n'est pas du confort : `min_length=1` compte les
    **caractères**, pas les non-blancs, et laissait donc passer `"   "` jusqu'à
    la base — un nom d'affichage vide, que la spec proscrit nommément.

    **Le `None` de ces champs veut dire « absent », pas « NULL ».** Les colonnes
    visées sont `NOT NULL` : sans le garde ci-dessous, un `{"nom": null}` était
    accepté par le schéma, transmis au service, et ressortait en **500**
    (`IntegrityError`) au lieu du 422 annoncé par le contrat. Chaque modèle
    déclare donc les champs où `null` est réellement une valeur.
    """

    #: Les champs dont `null` est une valeur légitime, et non une absence.
    _NULLABLES: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _au_moins_un_champ(self):
        if not self.model_fields_set:
            raise ValueError("Aucune modification demandée.")
        return self

    @model_validator(mode="after")
    def _pas_de_null_sur_un_champ_obligatoire(self):
        for champ in self.model_fields_set:
            if champ not in self._NULLABLES and getattr(self, champ) is None:
                raise ValueError(f"« {champ} » ne peut pas être vidé.")
        return self


class AdminAthleteUpdate(_PatchNonVide):
    """Correction d'identité d'un coureur (#117, FR-004).

    `nom` et `prenom` restent en français : gelés par un contrat public
    (Principe I) — ils traversent la base, l'API et `frontend/lib/types.ts`.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    _NULLABLES: ClassVar[frozenset[str]] = frozenset({"birth_date"})

    nom: str | None = Field(default=None, min_length=1)
    prenom: str | None = Field(default=None, min_length=1)
    birth_date: date | None = None


class AdminCourseUpdate(_PatchNonVide):
    """Correction du libellé d'une épreuve (#117, FR-020).

    Exactement les quatre colonnes de `uq_course_identity` — les toucher, c'est
    toucher ce qui distingue deux épreuves l'une de l'autre.

    **`event_type` est validé contre la nomenclature**, pas seulement contre le
    vide : ce slug pilote le partage fédéral/non-fédéral (`core/discipline.py`),
    les statistiques et le gabarit de splits. Un `triathlon_m` au lieu de
    `triathlon-m` retirerait l'épreuve des filtres et des agrégats **en
    silence** — le classifieur d'import, lui, ne produit que des slugs canoniques.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    _NULLABLES: ClassVar[frozenset[str]] = frozenset({"event_date"})

    name: str | None = Field(default=None, min_length=1)
    event_date: date | None = None
    event_type: str | None = Field(default=None, min_length=1)
    is_relay: bool | None = None

    @field_validator("event_type")
    @classmethod
    def _slug_connu(cls, valeur: str | None) -> str | None:
        from app.scrapers.classify import CANONICAL_TYPES

        if valeur is not None and valeur not in CANONICAL_TYPES:
            raise ValueError(
                f"Type d'épreuve inconnu. Valeurs acceptées : "
                f"{', '.join(sorted(CANONICAL_TYPES))}."
            )
        return valeur


class CourseDeletionImpact(BaseModel):
    """Ce qu'une suppression d'épreuve détruirait, chiffré avant le geste (#117).

    `athletes` n'est pas le nombre d'inscrits : c'est celui des coureurs dont
    **toutes** les participations sont sur cette épreuve, donc ceux qui
    disparaîtront par ricochet (FR-022). C'est ce nombre que la confirmation
    annonce, et il vient de la même fonction que celle qui purge (SC-007).
    """

    course_id: int
    name: str
    participations: int
    athletes: int


class ParticipationsWipeImpact(BaseModel):
    """Ce qu'une purge totale des résultats détruirait, chiffré avant le geste (#384).

    `athletes` est le compte total de fiches coureur : vider `participations`
    entièrement laisse *toute* fiche orpheline (`Participation.athlete_id` en
    est la seule FK jamais peuplée), donc c'est le compte de la table entière,
    pas seulement des coureurs inscrits quelque part.
    """

    participations: int
    athletes: int


class CoursesWipeImpact(BaseModel):
    """Ce qu'une purge totale des épreuves détruirait, chiffré avant le geste (#384).

    Contrairement à `ParticipationsWipeImpact`, ce geste emporte aussi les
    épreuves elles-mêmes et leurs sources — `courses` s'ajoute donc aux deux
    compteurs déjà connus.
    """

    courses: int
    participations: int
    athletes: int


class MergeImpactCourse(BaseModel):
    """Un des deux côtés d'une fusion, tel qu'il se présente à l'arbitrage (#286).

    Les six premiers champs sont ceux par lesquels un exploitant **reconnaît**
    l'épreuve qu'il désigne, et les trois qui divergent le plus souvent — `name`,
    `event_date`, `event_type` — sont rendus tels quels : deux libellés
    différents sont le cas nominal d'une épreuve publiée deux fois.

    Ni `source_url`, ni les sources : elles ont leur propre ressource
    (`GET /courses/{id}/sources`, #284), et les redire ici en ferait deux
    inventaires à tenir d'accord.
    """

    id: int
    name: str
    event_date: date | None = None
    event_type: str = ""
    is_relay: bool = False
    provider: str = ""
    participations: int


class CourseMergeImpact(BaseModel):
    """Ce qu'une fusion d'épreuves coûterait, chiffré **avant** le geste (#286).

    `participations_without_match` compte les résultats de l'absorbée sans
    jumeau de dossard dans la cible : ceux que la fusion perd jusqu'au prochain
    re-scrape. `tcn_participations_without_match` en est le sous-ensemble qui
    décide en pratique — perdre le résultat d'un membre du club n'a pas le même
    poids que perdre celui d'un inconnu.

    `athletes_orphaned` n'est pas le nombre de partants de l'absorbée : ce sont
    les coureurs dont **toutes** les participations y sont, donc les fiches que
    la fusion viderait, comptées par la même fonction que celle qui purge.

    `same_source_url` dit que l'URL de l'absorbée est déjà une source de la
    cible : la fusion n'ajoute alors aucune source, elle supprime un doublon.
    """

    target: MergeImpactCourse
    absorbed: MergeImpactCourse
    participations_without_match: int
    tcn_participations_without_match: int
    athletes_orphaned: int
    same_source_url: bool


class CourseMergeRequest(BaseModel):
    """Le corps de la fusion (#287) : l'épreuve qui **disparaît**, et rien d'autre.

    L'absorbée est nommée dans le corps et la cible dans le chemin, parce que la
    ressource s'écrit du point de vue de ce qui **survit** : `POST
    /admin/courses/{id}/merge` agit sur l'épreuve `{id}`, qui garde son identité,
    ses résultats et sa source active.

    `StrictInt` et non `int` : en mode permissif, Pydantic coerce `true` en `1`, et
    l'épreuve `1` serait **supprimée** avec ses résultats. Même parti pris que
    `AllowedEmailCreate.role_id`, pour un geste plus destructeur encore.

    Aucune contrainte ne dit ici qu'une épreuve ne se fusionne pas avec elle-même :
    ce refus est métier, il vit dans le service et sort en 400 avec un message
    français. Un `model_validator` rendrait un 422 dont le `detail` est une liste
    d'objets, en anglais — illisible à l'écran (même raison que `CourseSourceSwitch`).
    """

    model_config = ConfigDict(extra="forbid")

    absorbed_id: StrictInt


class CourseMergeResult(BaseModel):
    """Ce que la fusion a fait, une fois faite (#287).

    Les trois chiffres sont l'**ampleur réelle** du geste, à comparer à celle que
    l'aperçu annonçait : `participations_deleted` et `athletes_purged` sont les
    destructions, `source_added` dit si la cible a gagné une source ou si l'URL
    de l'absorbée y était déjà connue (`same_source_url` de l'aperçu).

    `sources` est la liste de la cible dans la forme et l'ordre de
    `GET /courses/{id}/sources` (#284), comme la bascule (#285) : l'écran
    d'arbitrage se réaffiche sans second appel, et le front n'a qu'une forme à
    connaître pour cette donnée.
    """

    target_id: int
    absorbed_id: int
    participations_deleted: int
    athletes_purged: int
    source_added: bool
    sources: list[CourseSourceOut]


class CourseReliabilityUpdate(BaseModel):
    """L'avis humain sur la fiabilité d'une épreuve. `null` **lève** l'avis."""

    model_config = ConfigDict(extra="forbid")

    #: Pas de défaut : `null` **lève** l'avis humain, un `PATCH` qui n'envoie que
    #: `notes` ne doit pas produire la même écriture sous silence. L'unique
    #: appelant (`ReliabilityVerdictDialog`) l'envoie toujours.
    reliability_override: bool | None
    #: Le motif de la décision, consigné au journal (#119, AC3). Facultatif —
    #: un verdict sans commentaire reste un verdict — mais borné : un champ
    #: texte libre écrit en base se borne, même derrière une session.
    notes: str | None = Field(default=None, max_length=500)


class CourseReliabilityRead(BaseModel):
    """Les **trois** valeurs, rendues délibérément.

    « La machine a relevé trois trous de classement et doute ; un humain a
    tranché que l'épreuve est fiable » : c'est ce qu'une interface de revue doit
    montrer, et ce qu'une valeur unique rendrait indicible. Ces deux champs
    supplémentaires n'apparaissent **que** sur cette route (FR-038).
    """

    id: int
    is_reliable: bool | None
    is_reliable_computed: bool | None
    reliability_override: bool | None
    quality_issues: dict | None


class AllowedEmailRead(BaseModel):
    """Une adresse autorisée à ouvrir une session (#170).

    `created_by_name` — et non `created_by` : la colonne s'appelle
    `created_by_user_id`, un champ nu se lirait comme l'identifiant qu'il n'est
    pas. C'est un nom d'affichage, que l'écran rend et que rien ne suit ; il est
    `null` quand l'inscription vient de la CLI ou de la reprise de production.
    """

    id: int
    email: str
    created_at: datetime
    created_by_name: str | None = None
    #: Le rôle que portera le compte **à sa création** (#239). `null` = aucun,
    #: qui reste le cas ordinaire. Objet et non identifiant : l'écran affiche un
    #: nom, et un `role_id` nu l'obligerait à recouper une seconde liste.
    role: RoleBrief | None = None
    #: Cette adresse porte-t-elle au moins un compte ? `False` = autorisée, jamais
    #: venue. C'est le seul retour que l'écran ait sur le rôle à l'inscription :
    #: sans lui, « déjà appliqué » et « attend toujours » se ressemblent.
    #:
    #: **Un booléen, et non le compte lui-même** : `users.email` n'est pas unique
    #: (FR-003), une adresse peut en porter plusieurs, et l'entrée ne désigne
    #: aucun titulaire — elle autorise, elle n'identifie pas.
    has_account: bool = False

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return f"{value.isoformat()}Z"


class AllowedEmailCreate(BaseModel):
    """Inscription d'une adresse.

    **`str` et non `EmailStr`, délibérément.** Une contrainte Pydantic sur le DTO
    fait rendre par FastAPI son 422 par défaut : `detail` y est une **liste**
    d'objets et le message vient d'`email-validator`, donc en **anglais**. Deux
    contrats y passaient à la trappe — FR-010 (« message en français ») et la
    forme `{"detail": "<chaîne>"}` que le front réaffiche verbatim.

    La validation vit donc dans `services/auth/allowed_emails`, où elle lève un
    `DomainError` français. Les deux appelants — la ressource HTTP et la CLI
    d'amorçage — en héritent, au lieu de valider chacun à sa façon.
    """

    model_config = ConfigDict(extra="forbid")

    email: str
    #: Rôle donné au compte à sa **création** (#239). Facultatif : autoriser sans
    #: rien donner reste le cas ordinaire. **`null` lève le rôle posé, le champ
    #: absent n'y touche pas** — le service distingue les deux.
    #:
    #: `StrictInt` : en mode permissif, Pydantic coerce `true` en `1`, et le rôle
    #: `1` est celui que le semis pose — l'administrateur. Une case à cocher mal
    #: sérialisée garerait l'administration sur une adresse.
    role_id: StrictInt | None = None


class SessionRevocation(BaseModel):
    """Bilan d'une révocation d'urgence (#169).

    **Deux unités, et chaque nom le dit** — même règle que les bilans de la CLI :
    `sessions` compte des jetons coupés, `accounts` les comptes qui en portaient
    au moins un. Un seul des deux chiffres ne dirait rien à l'exploitant, qui
    veut savoir *combien de monde* il vient de déconnecter, pas seulement
    combien d'appareils.

    Les deux chiffres ne comptent que le **vivant** — session non expirée, compte
    actif, soit le filtre exact de `session.resolve` —, alors que la suppression
    emporte aussi les lignes mortes. Dire « 12 comptes » quand onze dormaient
    donnerait à un geste dans le vide l'air d'un geste utile ; annoncer des
    sessions expirées comme « fermées » ferait le même effet, en pire, puisque
    faute d'ordonnanceur une base réelle en est pleine.
    """

    sessions: int
    accounts: int


class SessionRevocationRequest(BaseModel):
    """Portée d'une révocation (#169). Corps **facultatif**.

    Absent ou `email: null` → toutes les sessions. Une adresse → les comptes qui
    la portent, **tous** : `users.email` n'est pas unique (FR-003), et l'écran
    qui appelle cette route liste des *adresses*, pas des comptes. En épargner un
    sous incident serait l'erreur coûteuse.
    """

    model_config = ConfigDict(extra="forbid")

    email: str | None = None
