"""Le site public reste ouvert, et toute ressource d'administration est classée.

**Ce filet a changé de nature avec #115**, dans le même incrément que la première
route fermée — un filet rouge qu'on tolère est un filet mort. Il n'interdit plus
tout refus : il exige que **toute** ressource sous `/api/v1/admin/` soit soit
gardée, soit **déclarée publique nommément** ici, et que toute autre route
existante réponde sans session (FR-024, FR-025, SC-001, SC-002).

**Depuis #509, « ouvert » ne veut plus dire « atteignable par n'importe qui »**.
La garde transverse `require_site_access` ferme désormais l'essentiel de l'API
derrière le mot de passe partagé du site, y compris les routes que ce fichier
classe ici comme « publiques » : elles restent ouvertes **côté RBAC/SSO** — sans
session, sans pouvoir — mais un visiteur qui n'a jamais entré le mot de passe du
site ne les atteint plus du tout. Ce fichier ne le voit pas : `client`
(`tests/conftest.py`) neutralise `require_site_access` par défaut pour que ce
filet continue de n'éprouver que l'axe qu'il a toujours éprouvé (RBAC), et ses
assertions n'ont donc pas changé — la garde site, elle, est couverte séparément
par `test_site_access_gate.py`.

**Ce qu'il ne prouve plus.** Avec la politique en base, il établit qu'une
ressource exige *un* pouvoir — jamais *qui* le porte : la composition des rôles
est une donnée d'exploitation, modifiable à chaud, et aucun test ne peut en
répondre. C'est le prix assumé de l'édition sans redéploiement, et il est écrit
plutôt que découvert.

L'inventaire des routes est **dérivé de l'application**, jamais tenu à la main —
une liste manuelle vieillirait en silence, et c'est exactement la régression
qu'on veut interdire.
"""
import pytest

from app.main import app
from tests.test_auth.conftest import chemin_concret, toutes_les_routes

#: Le socle d'authentification est le seul préfixe exclu, et par **règle** (pas
#: par énumération) : `GET /auth/me` rend 401 par contrat, c'est sa raison d'être.

#: Le préfixe des ressources d'administration. Il ne **garde** rien — c'est
#: FR-018 : la protection se pose route par route. Il ne sert ici qu'à savoir
#: quelles routes doivent être classées.
PREFIXE_ADMIN = "/api/v1/admin/"

#: Les ressources d'administration **délibérément publiques**, nommées une par
#: une. Aujourd'hui une seule, et c'est un fait de terrain, pas une tolérance :
#: `TcnScrapeForm.tsx` l'appelle en `.catch(() => {})` quand un visiteur
#: **anonyme** colle une URL non supportée. C'est elle qui
#: interdit toute garde par préfixe (FR-022).
#:
#: Elle reste **seule** et c'est un choix : le signalement de #267 est tout
#: aussi public, mais il vit sous `/feedback` plutôt que d'agrandir cet
#: ensemble. Celui-ci n'a de raison d'être que pour une route déjà publiée
#: sous `/api/v1`, que le Principe IV interdit de déplacer.
ADMIN_PUBLIQUES = {
    ("POST", "/api/v1/admin/pending-providers"),
}

#: La ressource **hors `/admin/`** délibérément fermée par #115, et qui l'est
#: encore : destructive, elle était ouverte à Internet (FR-023). La nommer ici
#: est ce qui fait de sa fermeture une décision lue, et non un effet de bord.
#: `POST /api/v1/participations` l'a rejointe un temps (#115), puis en est
#: ressortie (#270) — la mise en quarantaine d'un résultat déclaré
#: (`is_pending_validation`) protège désormais l'intégrité des agrégats publics
#: à la place d'une session, ce qui permet de rouvrir la saisie manuelle à un
#: membre sans compte, l'usage que le formulaire vise.
#: Les ressources de la page bénévoles (#271, #437), fermées par un mot de
#: passe partagé (`require_benevole_access`) plutôt que par une session SSO —
#: mécanisme distinct, mais même exigence : anonyme n'obtient rien. `POST` et
#: `DELETE /benevoles/session` restent hors de cet ensemble : la première pose
#: la garde des autres, la seconde n'a aucun effet de bord sensible.
ROUTES_BENEVOLES_FERMEES = {
    ("GET", "/api/v1/benevoles/athletes"),
    ("GET", "/api/v1/benevoles/queue"),
    ("GET", "/api/v1/benevoles/queue/history"),
    ("GET", "/api/v1/benevoles/rejected"),
    ("PATCH", "/api/v1/benevoles/courses/{course_id}"),
    ("POST", "/api/v1/benevoles/participations/{participation_id}/reassign"),
    ("POST", "/api/v1/benevoles/participations/{participation_id}/validate"),
    ("POST", "/api/v1/benevoles/participations/{participation_id}/reject"),
    ("POST", "/api/v1/benevoles/participations/{participation_id}/unreject"),
    ("PATCH", "/api/v1/benevoles/participations/{participation_id}"),
}

#: Les déclarations de bénévolat (#751) — self-service, hors `/admin/`, mais
#: fermées par `current_user` (session SSO, pas de pouvoir RBAC) : une
#: déclaration porte toujours l'identité de son auteur, un anonyme n'en a pas.
ROUTES_VOLUNTEER_DECLARATIONS_FERMEES = {
    ("POST", "/api/v1/volunteer-declarations"),
    ("GET", "/api/v1/volunteer-declarations"),
    ("DELETE", "/api/v1/volunteer-declarations/{declaration_id}"),
}

#: Le formulaire public de déclaration de bénévolat pour un athlète (#778) —
#: self-service, hors `/admin/`, fermé par `current_user` (session SSO, pas de
#: pouvoir RBAC) : une déclaration porte toujours l'identité de son auteur, un
#: anonyme n'en a pas.
ROUTES_VOLUNTEER_ACTIONS_FERMEES = {
    ("POST", "/api/v1/volunteer-actions"),
}

ROUTES_FERMEES = {
    ("DELETE", "/api/v1/participations/{participation_id}"),
    *ROUTES_BENEVOLES_FERMEES,
    *ROUTES_VOLUNTEER_DECLARATIONS_FERMEES,
    *ROUTES_VOLUNTEER_ACTIONS_FERMEES,
}

#: Corps minimal des routes qui en exigent un. Un 422 de validation est une
#: réponse parfaitement acceptable ici : ce qu'on éprouve, c'est qu'aucune route
#: ne réclame de **session**, pas qu'elle accepte n'importe quoi.
CORPS_VIDE: dict = {}


def _routes_publiques() -> list[tuple[str, str]]:
    """Les routes qui doivent répondre sans session.

    Tout hors `/admin/` et hors des fermetures nommées, plus les ressources
    d'administration explicitement déclarées publiques.
    """
    return [
        (methode, chemin)
        for methode, chemin in toutes_les_routes()
        if (methode, chemin) in ADMIN_PUBLIQUES
        or (
            not chemin.startswith(PREFIXE_ADMIN)
            and (methode, chemin) not in ROUTES_FERMEES
        )
    ]


def _routes_gardees() -> list[tuple[str, str]]:
    """Les ressources qui doivent exiger un pouvoir : `/admin/` moins les
    publiques nommées, plus les fermetures nommées hors préfixe."""
    return [
        (methode, chemin)
        for methode, chemin in toutes_les_routes()
        if (
            chemin.startswith(PREFIXE_ADMIN) and (methode, chemin) not in ADMIN_PUBLIQUES
        )
        or (methode, chemin) in ROUTES_FERMEES
    ]


def test_l_inventaire_des_routes_n_est_pas_vide():
    """Garde du garde : un inventaire vide ferait passer tous les tests ci-dessous."""
    assert len(toutes_les_routes()) >= 17
    assert len(_routes_publiques()) >= 15
    assert len(_routes_gardees()) >= 4
    # Aucune route ne doit tomber dans les deux, ni dans aucun des deux.
    assert set(_routes_publiques()) | set(_routes_gardees()) == set(toutes_les_routes())
    assert not set(_routes_publiques()) & set(_routes_gardees())


@pytest.mark.parametrize(
    ("methode", "chemin"),
    _routes_publiques(),
    ids=lambda valeur: valeur.replace("/", "_") if isinstance(valeur, str) else valeur,
)
def test_une_route_publique_repond_sans_cookie(client, methode, chemin):
    """FR-024 : sans session, le site public répond.

    Seuls 401 et 403 sont proscrits. Un 404 (ressource absente de la base de
    test) ou un 422 (corps minimal) sont des réponses normales — elles prouvent
    que la requête a été **traitée**, ce qui est précisément le point.
    """
    reponse = client.request(methode, chemin_concret(chemin), json=CORPS_VIDE)
    assert reponse.status_code not in (401, 403), (
        f"{methode} {chemin} exige une session — le site public doit rester ouvert (FR-024)"
    )


@pytest.mark.parametrize(
    ("methode", "chemin"),
    _routes_gardees(),
    ids=lambda valeur: valeur.replace("/", "_") if isinstance(valeur, str) else valeur,
)
def test_une_ressource_protegee_refuse_l_anonyme(client, methode, chemin):
    """FR-021 — et une ressource ajoutée sans classement fait rougir la suite **en la nommant**.

    C'est le sens du renversement : avant #115, ce fichier interdisait tout
    refus ; il exige désormais une décision explicite pour chaque ressource
    d'administration et pour chaque fermeture hors préfixe. L'oubli n'est plus
    silencieux.
    """
    reponse = client.request(methode, chemin_concret(chemin), json=CORPS_VIDE)

    assert reponse.status_code == 401, (
        f"{methode} {chemin} répond {reponse.status_code} sans session : "
        "posez-lui une garde de pouvoir, ou déclarez-la dans ADMIN_PUBLIQUES"
    )


def test_le_signalement_anonyme_reste_ouvert(client):
    """FR-022 — le fait de terrain qui interdit toute garde par préfixe.

    Un visiteur **anonyme au sens RBAC** — sans session, sans pouvoir — colle
    une URL non supportée ; le formulaire la signale en `.catch(() => {})`.
    Depuis #509, il doit en plus avoir déjà entré le mot de passe du site, une
    garde que `client` neutralise ici par défaut (cf. docstring de module) :
    ce test continue de n'éprouver que l'absence de RBAC. Une garde de préfixe
    RBAC supprimerait la fonctionnalité sans que rien ne la nomme, et sans que
    personne ne le voie en développement.
    """
    reponse = client.post(
        "/api/v1/admin/pending-providers", json={"url": "https://inconnu.example/x"}
    )

    assert reponse.status_code == 201
    assert not client.cookies, "le test doit passer sans le moindre cookie"


def test_aucune_dependance_globale_sur_l_application():
    """La protection de #115 se pose route par route, jamais globalement.

    Un `dependencies=` monté sur l'application fermerait le site public **d'un
    coup** et sans que rien ne le nomme : la régression serait invisible en
    développement et totale en production. Ces deux lignes viennent de #114 et
    n'ont pas bougé.
    """
    assert app.router.dependencies == []
    assert app.dependency_overrides.keys() <= set()  # aucune surcharge résiduelle


def test_aucune_dependance_globale_sur_les_routers_existants():
    """Même règle, un cran plus bas : les routers métier n'en portent aucune.

    Le router d'authentification, lui, en porte une — les en-têtes de cache
    (`Cache-Control: no-store`, `Vary: Cookie`) — et c'est sa seule raison
    d'être : elle n'accorde ni ne refuse rien.

    `admin` est dans cette liste **et le reste** : c'est là que
    `POST /admin/pending-providers` se joue (FR-018).
    """
    from app.api.v1 import (
        admin,
        admin_data,
        admin_roles,
        athletes,
        benevoles,
        courses,
        health,
        participations,
        scrape,
        stats,
    )

    for module in (
        health,
        scrape,
        athletes,
        courses,
        participations,
        stats,
        admin,
        admin_data,
        admin_roles,
        benevoles,
    ):
        assert module.router.dependencies == [], (
            f"{module.__name__} porte une dépendance de router — "
            "la protection se pose route par route (FR-018)"
        )
