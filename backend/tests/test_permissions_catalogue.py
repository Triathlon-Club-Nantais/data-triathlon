"""Le catalogue et les gardes ne divergent jamais (#115, FR-026, FR-031, SC-009).

Trois lectures d'**AST** des routers, sur le patron de `tests/test_core_http.py`.
L'AST plutôt qu'un motif textuel : il sait à quel objet un nom est lié, et un
appel y est un nœud distinct d'une annotation ou d'une chaîne de docstring.

C'est le **seul filet contre le couplage par chaîne** : `require_permission`
prend un code, et `require_permission("pending_providres")` refuserait tout le
monde, en silence, sans qu'aucun autre test ne bouge.

**Ce fichier ne peut pas être vert avant la dernière ressource de la feature** :
il exige que *chaque* pouvoir du catalogue garde quelque chose, et les gardes de
`roles:*`, `users:read` et `quality:override` naissent en US3 et US5. C'est le
seul filet du lot dans ce cas — celui de `test_public_routes_still_open.py`, lui,
change de nature dans le même incrément que la première route fermée.
"""
import ast
from pathlib import Path

import pytest

from app.core import permissions
from app.core.permissions import P

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "api"

#: Les tables que seule une ressource gardée a le droit d'écrire (FR-031).
TABLES_DE_POUVOIR = {"Role", "RolePermission", "UserRole"}

#: Les appels par lesquels une écriture passe. `db.delete` et `db.add` couvrent
#: l'ORM ; un `db.execute(insert(...))` échapperait — il n'en existe aucun, et
#: le jour où il en existera, c'est cette table qu'il faudra étendre.
ECRITURES = {"add", "add_all", "delete", "merge"}


def _sources() -> list[Path]:
    return sorted(ROUTERS.rglob("*.py"))


def _codes_cites(arbre: ast.AST) -> set[str]:
    """Les codes que les appels à `require_permission` de cet arbre nomment.

    Deux formes acceptées, et une seule recommandée : `P.QUALITY_OVERRIDE` (la
    façade, résolue ici en son code) et la chaîne littérale. La seconde n'est
    tolérée que parce que ce test la rattrape.
    """
    cites: set[str] = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        nom = cible.attr if isinstance(cible, ast.Attribute) else getattr(cible, "id", None)
        if nom != "require_permission" or not noeud.args:
            continue
        argument = noeud.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            cites.add(argument.value)
        elif isinstance(argument, ast.Attribute):
            # `P.QUALITY_OVERRIDE` → son code, résolu depuis le catalogue réel.
            pouvoir = getattr(P, argument.attr, None)
            cites.add(pouvoir.code if pouvoir is not None else f"<{argument.attr}>")
    return cites


def _tous_les_codes_cites() -> set[str]:
    return {
        code
        for chemin in _sources()
        for code in _codes_cites(ast.parse(chemin.read_text(encoding="utf-8")))
    }


def test_le_lecteur_voit_les_deux_formes_d_appel():
    """Garde du garde : un lecteur aveugle ferait passer les deux tests suivants."""
    arbre = ast.parse(
        "from app.api.deps import require_permission\n"
        "from app.core.permissions import P\n"
        "a = require_permission(P.QUALITY_OVERRIDE)\n"
        "b = require_permission('roles:read')\n"
    )

    assert _codes_cites(arbre) == {"quality:override", "roles:read"}


def test_le_lecteur_signale_un_membre_de_facade_inexistant():
    """`P.PENDING_PROVIDRES` n'existe pas : le lecteur ne doit pas l'ignorer."""
    arbre = ast.parse("x = require_permission(P.PENDING_PROVIDRES)\n")

    assert _codes_cites(arbre) == {"<PENDING_PROVIDRES>"}


@pytest.mark.parametrize("pouvoir", permissions.ALL, ids=lambda p: p.code)
def test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource(pouvoir):
    """FR-026, premier sens — un pouvoir que rien ne vérifie est un mensonge d'écran.

    Il apparaîtrait dans la liste de composition d'un rôle, se cocherait, et
    n'ouvrirait rien.
    """
    assert pouvoir.code in _tous_les_codes_cites(), (
        f"« {pouvoir.label} » ({pouvoir.code}) ne garde aucune ressource : "
        "posez-lui une garde, ou retirez-le du catalogue"
    )


def test_aucune_garde_ne_cite_un_code_absent_du_catalogue():
    """FR-026, second sens — la coquille qui refuse tout le monde en silence.

    `require_permission("pending_providres")` ne lève pas, ne journalise rien
    d'anormal, et rend 403 à tous, y compris au superutilisateur — non : lui
    passerait, ce qui rend le défaut encore plus discret.
    """
    inconnus = {
        code for code in _tous_les_codes_cites() if not permissions.is_known(code)
    }

    assert inconnus == set(), f"gardes citant un code hors catalogue : {sorted(inconnus)}"


def _ecrit_dans_une_table_de_pouvoir(arbre: ast.AST) -> set[str]:
    """Les tables de pouvoir que ce module écrit, par `db.add`/`db.delete`/…"""
    touchees: set[str] = set()
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call) or not isinstance(noeud.func, ast.Attribute):
            continue
        if noeud.func.attr not in ECRITURES:
            continue
        for argument in ast.walk(noeud):
            if isinstance(argument, ast.Call) and isinstance(argument.func, ast.Name):
                if argument.func.id in TABLES_DE_POUVOIR:
                    touchees.add(argument.func.id)
    return touchees


def test_aucun_router_n_ecrit_directement_dans_les_tables_de_pouvoir():
    """FR-031 — la propriété tient aujourd'hui par construction ; rien ne la retient.

    Les deux ressources qui distribuent des pouvoirs sont gardées,
    `GET /auth/me` ne fait que lire, `POST /admin/pending-providers` n'accorde
    rien. C'est vrai, et c'est **l'invariant qui se perd à la route suivante**,
    sans se rattraper après coup : une route qui écrirait un `UserRole` sans
    passer par le service contournerait du même geste la non-amplification et
    l'invariant du dernier administrateur.

    La règle est donc structurelle : les routers **délèguent**, ils n'écrivent
    pas ces trois tables.
    """
    fautifs = {
        chemin.name: tables
        for chemin in _sources()
        if (tables := _ecrit_dans_une_table_de_pouvoir(
            ast.parse(chemin.read_text(encoding="utf-8"))
        ))
    }

    assert fautifs == {}, (
        f"écriture directe d'une table de pouvoir depuis un router : {fautifs} — "
        "passez par services/auth/authorization.py"
    )


def test_le_lecteur_d_ecriture_voit_une_faute_reelle():
    """Garde du garde, encore : un lecteur aveugle rendrait le test précédent creux."""
    arbre = ast.parse(
        "db.add(UserRole(user_id=1, role_id=2, organisation_id=3))\n"
    )

    assert _ecrit_dans_une_table_de_pouvoir(arbre) == {"UserRole"}
