"""**Un groupe n'accorde rien** — la borne de la v1 de #197 (AC6).

C'est ce qui rendait le retard de cette feature gratuit : tant qu'un groupe ne
porte aucun droit, la table n'intersecte aucune décision d'accès, donc aucun test
de garde n'est à défaire. Ce fichier transforme cette phrase en propriété
vérifiée.

**Deux tests, deux natures, et l'un ne remplace pas l'autre.**

Le comportemental protège le produit, mais ne couvre que ce qu'il échantillonne :
il resterait vert si la garde lisait les groupes pour n'en rien conclure —
c'est-à-dire au moment précis où la borne commence à céder.

Le structurel, lui, tient la frontière : le module qui décide ne nomme jamais
les modèles de groupe. **Il doit rougir le jour de la v2**, quand les rôles
portés par un groupe entreront dans la décision d'accès. On le supprimera alors
sciemment, et sa mort sera le signal que #197 a rempli son office.
"""
import ast
from pathlib import Path

from app.core.permissions import P
from app.repositories import group_repository
from app.services.auth import authorization

BACKEND = Path(__file__).resolve().parents[2]

#: **Tout** le chemin de décision, pas seulement son sommet.
#:
#: Se limiter à `deps.py` et `authorization.py` laisserait passer une v2 écrite
#: un cran plus bas — un `list_for_user_including_groups()` dans le repository
#: des attributions, ou une jointure dans la résolution de session — qui
#: franchirait la borne sans faire rougir quoi que ce soit, en gardant le sommet
#: cosmétiquement propre. Les six fichiers ci-dessous sont l'ensemble de ce qui
#: est consulté entre le cookie et le verdict :
DECISION_MODULES = (
    # la garde d'une route, et l'ordre 401-avant-403
    BACKEND / "app" / "api" / "deps.py",
    # qui porte quoi, et l'invariant du dernier administrateur
    BACKEND / "app" / "services" / "auth" / "authorization.py",
    # l'invariant à trois conditions qui valide une session
    BACKEND / "app" / "services" / "auth" / "session.py",
    # les deux seules sources de `effective_permissions`
    BACKEND / "app" / "repositories" / "user_role_repository.py",
    BACKEND / "app" / "repositories" / "role_repository.py",
    # l'inventaire des pouvoirs
    BACKEND / "app" / "core" / "permissions.py",
)

#: Les noms qu'aucun de ces modules ne doit prononcer.
GROUP_NAMES = {"Group", "UserGroup", "group_repository", "groups"}


def _names_used(tree: ast.AST) -> set[str]:
    """Tous les identifiants que cet arbre nomme — liaisons, attributs, imports.

    On regarde les **noms**, pas les chaînes : un code de pouvoir
    `"groups:read"` cité dans une docstring ne doit pas déclencher le test, mais
    `from app.repositories import group_repository` doit le faire.
    """
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            named.add(node.id)
        elif isinstance(node, ast.Attribute):
            named.add(node.attr)
        elif isinstance(node, ast.alias):
            # **Les deux noms**, pas seulement celui qui reste lié : un
            # `import app.services.auth.groups as raccourci` ne prononcerait
            # sinon que « raccourci », et le renommage suffirait à passer.
            named.add(node.name.split(".")[-1])
            if node.asname:
                named.add(node.asname)
        elif isinstance(node, ast.ImportFrom) and node.module:
            named.update(node.module.split("."))
    return named


def test_no_access_decision_names_the_groups():
    """AC6, volet structurel — l'énoncé rendu mécanique.

    C'est pour ce test que `services/auth/groups.py` est un module **séparé**
    d'`authorization.py`. Fondues dans le même fichier, les deux responsabilités
    ne seraient plus séparables par aucun outil, et la borne retomberait sur la
    vigilance du relecteur — précisément ce que #115 a refusé pour la
    non-amplification.
    """
    offenders = {}
    for path in DECISION_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if found := _names_used(tree) & GROUP_NAMES:
            offenders[path.name] = sorted(found)

    assert offenders == {}, (
        f"un module de décision nomme les groupes : {offenders} — "
        "un groupe n'accorde rien (AC6). Si c'est la v2 qui arrive, "
        "supprimez ce test sciemment plutôt que de le contourner"
    )


def test_the_reader_sees_access_through_the_repository():
    """Garde du garde : un lecteur aveugle rendrait le test précédent creux."""
    tree = ast.parse(
        "from app.repositories import group_repository\n"
        "def has_permission(db, user):\n"
        "    return bool(group_repository.list_all(db))\n"
    )

    assert _names_used(tree) & GROUP_NAMES == {"group_repository"}


def test_the_reader_sees_access_through_the_service():
    """L'autre porte d'entrée, et elle ne se nomme pas comme la première."""
    tree = ast.parse("from app.services.auth import groups\n")

    assert _names_used(tree) & GROUP_NAMES == {"groups"}


def test_the_reader_sees_a_renamed_import():
    """La faille que le renommage ouvrirait : le nom d'origine compte aussi."""
    tree = ast.parse("import app.services.auth.groups as raccourci\n")

    assert _names_used(tree) & GROUP_NAMES == {"groups"}


def test_the_reader_sees_access_through_the_model():
    tree = ast.parse("from app.models.user_group import UserGroup\n")

    assert _names_used(tree) & GROUP_NAMES == {"UserGroup"}


def test_the_reader_does_not_fire_on_a_string():
    """…et pas trop sensible non plus : un code de pouvoir cité reste une chaîne."""
    tree = ast.parse('code = "groups:read"\n')

    assert _names_used(tree) & GROUP_NAMES == set()


def test_belonging_to_every_group_grants_no_privilege(
    client, db_session, ouvrir_session
):
    """AC6, volet comportemental — la propriété qui intéresse le produit."""
    member = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    for slug in ("codir", "arbitres", "benevolat"):
        group = client.post(
            "/api/v1/admin/groups", json={"slug": slug, "name": slug.title()}
        ).json()
        client.post(
            f"/api/v1/admin/groups/{group['id']}/members", json={"user_id": member.id}
        )

    assert authorization.effective_permissions(db_session, member) == frozenset()
    assert not authorization.has_permission(db_session, member, P.PENDING_PROVIDERS_READ)


def test_a_member_of_every_group_is_still_refused_on_a_guarded_resource(
    client, db_session, ouvrir_session, organisation
):
    """La même chose, vue de l'extérieur : rien ne change pour lui.

    Les appartenances sont posées par le repository et non par l'API : ce qu'on
    éprouve ici est la **décision d'accès**, et la faire dépendre d'une session
    d'exploitant y mêlerait un second sujet.
    """
    member = ouvrir_session(email="membre@exemple.fr")
    for slug in ("codir", "arbitres", "benevolat"):
        group = group_repository.create(
            db_session,
            organisation_id=organisation.id,
            slug=slug,
            name=slug.title(),
        )
        group_repository.add_member(db_session, group_id=group.id, user_id=member.id)
    db_session.commit()

    assert client.get("/api/v1/admin/pending-providers").status_code == 403
