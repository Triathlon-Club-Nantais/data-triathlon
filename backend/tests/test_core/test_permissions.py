"""L'inventaire des pouvoirs (#115, FR-001, FR-002, FR-040).

Ce module est le seul endroit du dépôt où la **liste de référence** des pouvoirs
existe. La base, elle, stocke les codes *portés par un rôle* — deux choses
distinctes, et les confondre a coûté une clarification (2026-08-05).

Aucun accès base, aucun réseau : c'est ce qui autorise `core/` (Principe II).
"""
import dataclasses

import pytest

from app.core import permissions
from app.core.permissions import P, Permission

#: Les vingt-et-un codes des contrats : les neuf de `contracts/admin-api.md`
#: (#115), les trois de `contracts/admin-groups-api.md` (#197), celui de la
#: liste d'autorisation (#170), les cinq des gestes correctifs (#117), les deux
#: du lancement de batches (#47) et celui de la révocation d'urgence des
#: sessions (#169). Écrits **à la main** ici, et c'est délibéré : un test qui
#: dériverait la liste du catalogue ne prouverait rien. C'est ce qui fait
#: qu'ajouter un pouvoir est un geste conscient — cette liste est le seul
#: endroit du dépôt qui s'y oppose.
CODES_ATTENDUS = {
    "roles:read",
    "roles:write",
    "roles:assign",
    "users:read",
    "allowed_emails:manage",
    "sessions:revoke",
    "groups:read",
    "groups:write",
    "groups:assign",
    "pending_providers:read",
    "pending_providers:handle",
    "quality:override",
    "courses:write",
    "courses:delete",
    "athletes:read",
    "athletes:write",
    "participations:write",
    "participations:delete",
    "participations:reassign",
    "batch:run",
    "batch:read",
}


def test_le_catalogue_expose_exactement_les_codes_du_contrat():
    assert {pouvoir.code for pouvoir in permissions.ALL} == CODES_ATTENDUS


def test_aucun_code_n_est_en_double():
    codes = [pouvoir.code for pouvoir in permissions.ALL]
    assert len(codes) == len(set(codes))


@pytest.mark.parametrize("pouvoir", permissions.ALL, ids=lambda p: p.code)
def test_un_pouvoir_porte_son_francais_d_affichage(pouvoir: Permission):
    """Le `code` est un identifiant technique anglais ; le reste est affiché.

    Principe I : ce qui est visible d'un utilisateur est en français. Ces trois
    chaînes composent l'écran de composition d'un rôle.
    """
    assert pouvoir.label, f"{pouvoir.code} n'a pas de libellé"
    assert pouvoir.description, f"{pouvoir.code} n'a pas de description"
    assert pouvoir.feature, f"{pouvoir.code} n'est rattaché à aucune fonctionnalité"


@pytest.mark.parametrize("pouvoir", permissions.ALL, ids=lambda p: p.code)
def test_un_code_suit_la_forme_domaine_deux_points_geste(pouvoir: Permission):
    """FR-040 — `<domaine>:<geste>`, en minuscules, sans espace.

    La forme CRUD n'est pas la norme : le geste nomme l'acte métier quand il en
    a un (`quality:override`), et retombe sur `read`/`write` sinon.
    """
    domaine, separateur, geste = pouvoir.code.partition(":")
    assert separateur == ":", f"{pouvoir.code} ne porte pas de « : »"
    assert domaine and geste
    assert pouvoir.code == pouvoir.code.lower()
    assert " " not in pouvoir.code


@pytest.mark.parametrize("pouvoir", permissions.ALL, ids=lambda p: p.code)
def test_un_pouvoir_est_immuable(pouvoir: Permission):
    """Dataclass **gelée** : un catalogue modifiable à chaud serait un état."""
    assert dataclasses.is_dataclass(pouvoir)
    with pytest.raises(dataclasses.FrozenInstanceError):
        pouvoir.code = "autre:chose"


def test_chaque_membre_nomme_de_la_facade_est_dans_le_catalogue():
    """`P` est la façade d'appel (`require_permission(P.ROLES_READ)`).

    Un membre qui n'y figurerait pas serait un pouvoir que le code sait citer et
    que l'inventaire ignore — exactement le couplage par chaîne qu'on ferme.
    """
    membres = {
        valeur
        for nom, valeur in vars(P).items()
        if not nom.startswith("_") and isinstance(valeur, Permission)
    }
    assert membres == set(permissions.ALL)


def test_l_acces_par_code_rend_le_pouvoir_ou_rien():
    assert permissions.get("quality:override") is P.QUALITY_OVERRIDE
    assert permissions.get("pending_providres") is None  # la coquille du contrat
    assert permissions.is_known("quality:override") is True
    # Un code plausible mais absent du catalogue. Ce n'était pas `courses:delete`
    # par hasard : #117 l'a rendu réel, et l'exemple a dû changer de code.
    assert permissions.is_known("courses:archive") is False


def test_le_catalogue_est_groupe_par_fonctionnalite_pour_l_affichage():
    """`GET /admin/permissions` sert cette forme telle quelle."""
    groupes = permissions.grouped_by_feature()

    assert groupes, "aucun groupe"
    assert [pouvoir for groupe in groupes for pouvoir in groupe.permissions] == list(
        permissions.ALL
    )
    intitules = [groupe.feature for groupe in groupes]
    assert len(intitules) == len(set(intitules)), "une fonctionnalité apparaît deux fois"


def test_le_module_ne_touche_ni_la_base_ni_le_reseau():
    """Vérifié sur la **source**, pas sur un appel : c'est une propriété du module.

    `core/` ne connaît ni `Session` ni repository (Principe II) ; un catalogue
    qui lirait la base rouvrirait la question tranchée par `research.md` §D3.
    """
    from pathlib import Path

    source = Path(permissions.__file__).read_text(encoding="utf-8")
    for interdit in ("sqlalchemy", "app.repositories", "app.models", "httpx", "Session"):
        assert interdit not in source, f"`{interdit}` apparaît dans core/permissions.py"
