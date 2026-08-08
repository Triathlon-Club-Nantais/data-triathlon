"""Inventaire des pouvoirs — la liste de référence de ce que l'application vérifie.

**Le pouvoir est ici ; le rôle et l'attribution sont en base.** C'est la décision
centrale du modèle (#115, `research.md` §D3), et elle se comprend de travers si
l'on confond deux choses :

- **Le code porté par un rôle est bien une donnée en base**, une chaîne dans une
  ligne de `role_permissions`, modifiable à chaud par `PATCH`.
- **Ce qui n'existe pas, c'est une table `permissions`** listant les codes
  possibles — un second inventaire doublant celui-ci. Le précédent explicite du
  dépôt est `Course.event_type`, chaîne en base et nomenclature en Python
  (`core/discipline.py`).

Ce que cette forme achète : **ajouter un pouvoir, c'est ajouter un membre à `P`**
— aucune migration (FR-014), aucun upsert au démarrage, et aucun sync capable
d'effacer des attributions en production parce qu'un module n'a pas été importé.

Aucune session, aucun état, aucune sortie : c'est ce qui autorise `core/`
(Principe II).
"""
from dataclasses import dataclass

#: Fonctionnalités, dans l'ordre d'affichage de `GET /admin/permissions`.
FEATURE_ROLES = "Rôles et accès"
#: Distincte de « Rôles et accès », et c'est ce qui rend l'écran de composition
#: lisible : mêler « attribuer les rôles » et « attribuer les groupes » dans le
#: même bloc est exactement le geste que ce regroupement existe pour éviter. Un
#: groupe dit à quoi on **appartient**, un rôle ce qu'on **peut faire** (#197).
FEATURE_GROUPS = "Groupes d'appartenance"
FEATURE_PENDING_PROVIDERS = "Chronométreurs signalés"
FEATURE_QUALITY = "Qualité des données"
FEATURE_COURSES = "Épreuves"
FEATURE_ATHLETES = "Coureurs"
FEATURE_PARTICIPATIONS = "Résultats"
FEATURE_BATCH = "Batches"


@dataclass(frozen=True, slots=True)
class Permission:
    """Un pouvoir : un code technique, et le français qui le présente.

    Gelée : un catalogue modifiable à l'exécution serait un état, et `core/`
    n'en porte pas. Le `code` est un identifiant anglais **stable** — il traverse
    la base, un renommage laisserait derrière lui des lignes inertes.
    """

    code: str
    label: str
    description: str
    feature: str

    def __str__(self) -> str:  # `require_permission(P.X)` journalise le code seul
        return self.code


class P:
    """Les pouvoirs, nommés — `require_permission(P.ROLES_READ)`.

    Passer par un membre plutôt que par une chaîne littérale n'est pas du confort :
    `require_permission("pending_providres")` refuserait tout le monde, en
    silence et sans qu'aucun test ne bouge. Un méta-test AST
    (`tests/test_permissions_catalogue.py`) tient les deux bouts.
    """

    ROLES_READ = Permission(
        "roles:read",
        "Consulter les rôles",
        "Voir la liste des rôles, leur composition et l'inventaire des pouvoirs.",
        FEATURE_ROLES,
    )
    ROLES_WRITE = Permission(
        "roles:write",
        "Composer les rôles",
        "Créer, renommer, recomposer et supprimer des rôles.",
        FEATURE_ROLES,
    )
    ROLES_ASSIGN = Permission(
        "roles:assign",
        "Attribuer les rôles",
        "Donner et retirer un rôle à un utilisateur.",
        FEATURE_ROLES,
    )
    USERS_READ = Permission(
        "users:read",
        "Consulter les utilisateurs",
        "Voir la liste des personnes connectées au moins une fois et leurs rôles.",
        FEATURE_ROLES,
    )
    ALLOWED_EMAILS_MANAGE = Permission(
        "allowed_emails:manage",
        "Gérer les accès",
        "Consulter, ajouter et retirer les adresses autorisées à ouvrir une session.",
        FEATURE_ROLES,
    )
    GROUPS_READ = Permission(
        "groups:read",
        "Consulter les groupes",
        "Voir la liste des groupes d'appartenance et la composition de chacun.",
        FEATURE_GROUPS,
    )
    GROUPS_WRITE = Permission(
        "groups:write",
        "Composer les groupes",
        "Créer, renommer et supprimer des groupes d'appartenance.",
        FEATURE_GROUPS,
    )
    GROUPS_ASSIGN = Permission(
        "groups:assign",
        "Gérer les membres",
        "Ajouter et retirer une personne d'un groupe d'appartenance.",
        FEATURE_GROUPS,
    )
    PENDING_PROVIDERS_READ = Permission(
        "pending_providers:read",
        "Consulter les signalements",
        "Voir la liste des chronométreurs non supportés signalés par les visiteurs.",
        FEATURE_PENDING_PROVIDERS,
    )
    PENDING_PROVIDERS_HANDLE = Permission(
        "pending_providers:handle",
        "Instruire les signalements",
        "Marquer un signalement comme traité et le retirer de la liste.",
        FEATURE_PENDING_PROVIDERS,
    )
    QUALITY_OVERRIDE = Permission(
        "quality:override",
        "Trancher la fiabilité",
        "Déclarer à la main qu'une épreuve est fiable ou douteuse, contre l'avis calculé.",
        FEATURE_QUALITY,
    )
    COURSES_DELETE = Permission(
        "courses:delete",
        "Supprimer une épreuve",
        "Retirer définitivement une épreuve, tous ses résultats, et les fiches "
        "coureur qui n'en auraient plus aucun.",
        FEATURE_COURSES,
    )
    COURSES_WRITE = Permission(
        "courses:write",
        "Corriger une épreuve",
        "Rectifier le nom, la date, le type ou le caractère relais d'une épreuve — "
        "les quatre champs qui la distinguent d'une autre.",
        FEATURE_COURSES,
    )
    ATHLETES_READ = Permission(
        "athletes:read",
        "Consulter les fiches coureur",
        "Rechercher un coureur et voir son identité complète, date de naissance "
        "comprise — la seule donnée personnelle que le site garde fermée.",
        FEATURE_ATHLETES,
    )
    ATHLETES_WRITE = Permission(
        "athletes:write",
        "Corriger un coureur",
        "Rectifier le nom, le prénom ou la date de naissance d'une fiche coureur.",
        FEATURE_ATHLETES,
    )
    PARTICIPATIONS_WRITE = Permission(
        "participations:write",
        "Créer un résultat",
        "Ajouter manuellement un résultat à une épreuve.",
        FEATURE_PARTICIPATIONS,
    )
    PARTICIPATIONS_DELETE = Permission(
        "participations:delete",
        "Supprimer un résultat",
        "Retirer définitivement un résultat d'une épreuve.",
        FEATURE_PARTICIPATIONS,
    )
    PARTICIPATIONS_REASSIGN = Permission(
        "participations:reassign",
        "Rattacher un résultat",
        "Associer un résultat au bon coureur, quand un scraper a créé un doublon "
        "d'identité.",
        FEATURE_PARTICIPATIONS,
    )
    # Deux pouvoirs et non un : lancer une reprise réécrit les résultats de
    # centaines d'épreuves, en relire le bilan ne touche à rien. Les confondre
    # obligerait à donner le premier pour obtenir le second.
    BATCH_RUN = Permission(
        "batch:run",
        "Lancer un batch",
        "Lancer une reprise de la base ou l'import d'un fichier de résultats.",
        FEATURE_BATCH,
    )
    BATCH_READ = Permission(
        "batch:read",
        "Consulter les batches",
        "Suivre les lancements en cours et relire leurs bilans.",
        FEATURE_BATCH,
    )


#: L'inventaire, dans l'ordre d'affichage. `P` en est la façade d'appel ; un
#: méta-test vérifie que les deux ne divergent jamais.
ALL: tuple[Permission, ...] = (
    P.ROLES_READ,
    P.ROLES_WRITE,
    P.ROLES_ASSIGN,
    P.USERS_READ,
    P.ALLOWED_EMAILS_MANAGE,
    P.GROUPS_READ,
    P.GROUPS_WRITE,
    P.GROUPS_ASSIGN,
    P.PENDING_PROVIDERS_READ,
    P.PENDING_PROVIDERS_HANDLE,
    P.QUALITY_OVERRIDE,
    P.COURSES_WRITE,
    P.COURSES_DELETE,
    P.ATHLETES_READ,
    P.ATHLETES_WRITE,
    P.PARTICIPATIONS_WRITE,
    P.PARTICIPATIONS_DELETE,
    P.PARTICIPATIONS_REASSIGN,
    P.BATCH_RUN,
    P.BATCH_READ,
)

_BY_CODE: dict[str, Permission] = {pouvoir.code: pouvoir for pouvoir in ALL}

#: Les codes seuls — c'est cet ensemble que la non-amplification intersecte
#: (FR-011), et c'est ce qui rend un code périmé retirable par tout le monde.
CODES: frozenset[str] = frozenset(_BY_CODE)


def get(code: str) -> Permission | None:
    """Le pouvoir portant ce code, ou `None` s'il est absent de l'inventaire."""
    return _BY_CODE.get(code)


def is_known(code: str) -> bool:
    """Ce code est-il de l'inventaire ? Un code inconnu n'accorde rien (FR-042)."""
    return code in _BY_CODE


@dataclass(frozen=True, slots=True)
class FeatureGroup:
    """Une fonctionnalité et les pouvoirs qu'elle offre, prêts à l'affichage."""

    feature: str
    permissions: tuple[Permission, ...]


def grouped_by_feature() -> list[FeatureGroup]:
    """L'inventaire rangé par fonctionnalité, dans l'ordre de déclaration.

    Composer un rôle en cochant dans une liste plate de treize codes techniques
    est le geste qu'on veut éviter — c'est ce regroupement qui rend l'écran
    lisible, et il n'a pas d'autre lecteur.
    """
    ordre: list[str] = []
    par_feature: dict[str, list[Permission]] = {}
    for pouvoir in ALL:
        if pouvoir.feature not in par_feature:
            ordre.append(pouvoir.feature)
            par_feature[pouvoir.feature] = []
        par_feature[pouvoir.feature].append(pouvoir)
    return [FeatureGroup(feature, tuple(par_feature[feature])) for feature in ordre]
