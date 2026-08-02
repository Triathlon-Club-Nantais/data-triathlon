"""US2 — aucune ressource publique existante n'exige de session (FR-035, SC-001).

Ce fichier est un **filet**, pas une étape : il doit rester vert pendant tout le
reste de la livraison, et toute tâche ultérieure qui le casse est un défaut.

L'inventaire des routes est **dérivé de l'application**, jamais tenu à la main —
une liste manuelle vieillirait en silence, et c'est exactement la régression
qu'on veut interdire.
"""
import pytest

from app.main import app

#: Le socle d'authentification est le seul préfixe exclu, et par **règle** (pas
#: par énumération) : `GET /auth/me` rend 401 par contrat, c'est sa raison d'être.
PREFIXE_AUTH = "/api/v1/auth/"

#: Corps minimal des routes qui en exigent un. Un 422 de validation est une
#: réponse parfaitement acceptable ici : ce qu'on éprouve, c'est qu'aucune route
#: ne réclame de **session**, pas qu'elle accepte n'importe quoi.
CORPS_VIDE: dict = {}


def _routes_publiques() -> list[tuple[str, str]]:
    """Couples (méthode, chemin) de toutes les routes publiques de l'application.

    Lu dans le schéma OpenAPI et non dans `app.routes` : depuis FastAPI 0.139,
    `app.routes` n'est plus une liste plate d'`APIRoute` — un `include_router`
    y dépose un `_IncludedRouter` dont le dépliage passe par des internes
    privés. Le schéma est l'inventaire **public** de la même information.
    """
    return [
        (methode.upper(), chemin)
        for chemin, operations in app.openapi()["paths"].items()
        for methode in operations
        if not chemin.startswith(PREFIXE_AUTH)
    ]


def _chemin_concret(chemin: str) -> str:
    """Substitue `1` à chaque paramètre de chemin — un 404 vaut mieux qu'un 401."""
    morceaux = []
    for morceau in chemin.split("/"):
        morceaux.append("1" if morceau.startswith("{") and morceau.endswith("}") else morceau)
    return "/".join(morceaux)


def test_l_inventaire_des_routes_n_est_pas_vide():
    """Garde du garde : un inventaire vide ferait passer tous les tests ci-dessous."""
    assert len(_routes_publiques()) >= 17


@pytest.mark.parametrize(
    ("methode", "chemin"),
    _routes_publiques(),
    ids=lambda valeur: valeur.replace("/", "_") if isinstance(valeur, str) else valeur,
)
def test_une_route_publique_repond_sans_cookie(client, methode, chemin):
    """FR-035 : sans session, aucune route existante ne refuse l'accès.

    Seuls 401 et 403 sont proscrits. Un 404 (ressource absente de la base de
    test) ou un 422 (corps minimal) sont des réponses normales — elles prouvent
    que la requête a été **traitée**, ce qui est précisément le point.
    """
    reponse = client.request(methode, _chemin_concret(chemin), json=CORPS_VIDE)
    assert reponse.status_code not in (401, 403), (
        f"{methode} {chemin} exige une session — le site public doit rester ouvert (FR-035)"
    )


def test_aucune_dependance_globale_sur_l_application():
    """La protection de #115 se posera route par route, jamais globalement.

    Un `dependencies=` monté sur l'application fermerait le site public **d'un
    coup** et sans que rien ne le nomme : la régression serait invisible en
    développement et totale en production.
    """
    assert app.router.dependencies == []
    assert app.dependency_overrides.keys() <= set()  # aucune surcharge résiduelle


def test_aucune_dependance_globale_sur_les_routers_existants():
    """Même règle, un cran plus bas : les routers métier n'en portent aucune.

    Le router d'authentification, lui, en porte une — les en-têtes de cache
    (`Cache-Control: no-store`, `Vary: Cookie`) — et c'est sa seule raison
    d'être : elle n'accorde ni ne refuse rien.
    """
    from app.api.v1 import (
        admin,
        athletes,
        courses,
        health,
        participations,
        scrape,
        stats,
        version,
    )

    for module in (health, version, scrape, athletes, courses, participations, stats, admin):
        assert module.router.dependencies == [], (
            f"{module.__name__} porte une dépendance de router — "
            "la protection des ressources est hors périmètre de cette feature (FR-035)"
        )
