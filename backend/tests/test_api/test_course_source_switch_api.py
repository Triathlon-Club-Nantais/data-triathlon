"""Bascule de la source active d'une épreuve — décision D2 de #275 (#285).

Le geste réécrit un classement entier : la source désignée devient l'active, les
participations de l'épreuve sont **supprimées**, et le nouveau chronométreur est
importé de zéro. Le remplacement est total et non un upsert par dossard : un
upsert laisserait survivre les lignes de l'ancienne source absentes de la
nouvelle, et le classement resterait le mélange que l'epic existe pour
supprimer.

**Le point le plus important du fichier est l'AC3.** L'ordre du service est ce
qui le rend vrai : on **scrape d'abord**, on valide, et on ne détruit qu'ensuite.
Rien de destructeur n'est écrit avant qu'on tienne des résultats utilisables,
donc un échec de scraping laisse l'épreuve exactement dans l'état d'avant le
clic — mêmes résultats, même source active. L'inverse (vider puis tenter de
remplir) serait une perte de données déclenchée par un clic d'administrateur, et
aucun rollback n'est aussi solide que le fait de n'avoir rien écrit.

**Pas de SSE ici, et c'est une décision.** #275 renvoie à #118 (re-scrape à la
demande depuis le back-office) et tranche : les deux gestes « doivent partager le
même mécanisme, pas en inventer deux ». Aucun des sept AC de #285 ne porte sur la
progression. Le geste est donc bloquant, et le mécanisme SSE d'administration
appartient à #118.
"""
from datetime import date

import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.exceptions import ScraperError
from app.core.permissions import P
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.scrapers.base import ScrapedResult
from app.services import import_service
from app.services.auth import session as session_service

#: Deux URLs de fournisseurs **réels** : `_validate_url` refuse une adresse
#: qu'aucun provider ne reconnaît, et un `.test` ferait échouer ces tests pour
#: une raison étrangère à ce qu'ils éprouvent.
#: Breizh Chrono est délibérément la source **entrante** : c'est un provider
#: mono-course, donc le chemin de scraping le plus court. Le fan-out a ses
#: propres tests, il n'a rien à établir sur la bascule.
KLIKEGO = "https://www.klikego.com/resultats/mesquer-2026/1706667557931-4"
BREIZH = "https://resultats.breizhchrono.com/resultats-courses/mesquer-2026-1732665322557-2"

NOM = "Triathlon de Mesquer"
JOUR = date(2026, 5, 16)
TYPE = "triathlon-s"


def _url(course_id: int, source_id: int) -> str:
    return f"/api/v1/admin/courses/{course_id}/sources/{source_id}"


def _result(bib: str, nom: str, *, event_name: str = NOM) -> ScrapedResult:
    """Un résultat du chronométreur entrant.

    `event_name` est un paramètre parce qu'un seul test s'en sert : celui de
    l'épreuve homonyme. Partout ailleurs l'identité est **la même** des deux
    côtés — c'est le cas mesuré, deux chronométreurs publiant la même épreuve
    champ pour champ.
    """
    return ScrapedResult(
        source_url=BREIZH,
        provider="breizhchrono",
        athlete_name=nom,
        athlete_firstname="Jean",
        bib_number=bib,
        event_name=event_name,
        event_date=JOUR,
        event_type=TYPE,
        total_time="01:59:00",
    )


@pytest.fixture
def scrape(monkeypatch):
    """Arme le chronométreur entrant, et **espionne** les URLs scrapées.

    L'espion n'est pas un ornement : deux AC ne se distinguent que par le fait
    qu'un scrape a eu lieu ou non — le no-op de l'AC4 (aucun) et le contournement
    du cache de l'AC7 (un, sur la nouvelle source).
    """
    appels: list[str] = []

    def armer(resultats_ou_exception):
        def _scrape(url, **kwargs):
            appels.append(url)
            if isinstance(resultats_ou_exception, Exception):
                raise resultats_ou_exception
            return resultats_ou_exception

        monkeypatch.setattr(import_service, "registry_scrape_event_all", _scrape)
        return appels

    return armer


@pytest.fixture
def organisation(db_session) -> Organisation:
    """Le club, créé par le conftest du dossier — les sessions à pouvoirs mesurés
    de `connecte` s'y rattachent."""
    return db_session.query(Organisation).filter_by(slug="tcn").one()


def connecte(client, db_session, organisation, *codes, email="arbitre@exemple.fr"):
    """Ouvre une session portant **exactement** ces pouvoirs.

    Patron de `tests/test_auth/test_admin_guards.py`, et la seule façon
    d'éprouver qu'un pouvoir voisin ne suffit pas : la session du conftest de ce
    dossier est superutilisateur, elle ne peut rien établir sur la garde.
    """
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    role = role_repository.create(db_session, slug="arbitre", name="Arbitre de test")
    for code in codes:
        role.permissions.append(RolePermission(permission_code=code))
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


@pytest.fixture
def epreuve(db_session):
    """L'épreuve, son active Klikego à deux dossards, sa passive Breizh Chrono.

    Peuplée à la main plutôt que par un import : ce fichier éprouve la bascule,
    pas le chemin d'import, et un peuplement explicite dit noir sur blanc ce que
    la bascule doit détruire.
    """
    course = course_repository.get_or_create(
        db_session, name=NOM, event_date=JOUR, event_type=TYPE,
        source_url=KLIKEGO, provider="klikego",
    )
    passive = course_source_repository.add(
        db_session, course=course, url=BREIZH, provider="breizhchrono"
    )
    for bib, nom in (("1", "DUPONT"), ("2", "MARTIN")):
        athlete, _ = athlete_repository.resolve(db_session, nom=nom, prenom="Jean")
        db_session.flush()
        participation_repository.create(
            db_session, course_id=course.id, athlete_id=athlete.id,
            bib_number=bib, status="finisher", total_time="01:59:00",
        )
    db_session.commit()
    return course, passive


def _dossards(db_session, course_id: int) -> list[str]:
    return sorted(
        ligne.bib_number
        for ligne in participation_repository.list_for_course(db_session, course_id)
    )


def _sources(db_session, course_id: int) -> list[tuple[str, bool]]:
    return [
        (source.url, source.is_active)
        for source in course_source_repository.list_for_course(db_session, course_id)
    ]


def _bascules(db_session, course_id: int) -> list:
    return [
        entree
        for entree in admin_action_log_repository.list_for_entity(
            db_session, entity_type="course", entity_id=course_id
        )
        if entree.action == "course.source.switch"
    ]


# --------------------------------------------------------------------- AC1


def test_a_holder_of_courses_write_alone_is_refused(client, db_session, organisation, epreuve):
    """AC1 — `courses:write` ne donne pas le droit de basculer une source.

    Le pouvoir voisin est borné aux quatre champs d'identité : corriger un
    libellé ne détruit rien, basculer une source réécrit un classement entier.
    Le réutiliser aurait élargi un pouvoir déjà distribué, sans que personne ne
    l'ait décidé.
    """
    course, passive = epreuve
    connecte(client, db_session, organisation, P.COURSES_WRITE.code)

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 403
    assert _dossards(db_session, course.id) == ["1", "2"]


def test_a_holder_of_courses_sources_passes(client, db_session, organisation, epreuve, scrape):
    """AC1, seconde moitié — le pouvoir dédié suffit, seul."""
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU")])
    connecte(client, db_session, organisation, P.COURSES_SOURCES.code)

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 200, reponse.text


def test_the_switch_is_closed_to_anonymous_visitors(client, epreuve):
    """La troisième issue de toute ressource fermée : 401 sans session."""
    course, passive = epreuve
    client.cookies.clear()

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 401


# --------------------------------------------------------------------- AC2


def test_the_switch_replaces_the_ranking_instead_of_merging_it(
    client, db_session, epreuve, scrape
):
    """AC2 — plus une seule participation de l'ancienne source, une seule active.

    Le chronométreur entrant ne publie **qu'un** dossard là où le sortant en avait
    deux, et c'est ce déséquilibre qui donne son sens au test : avec deux dossards
    identiques, un upsert et un remplacement total rendraient le même état final.
    """
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU")])

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 200, reponse.text
    assert _dossards(db_session, course.id) == ["7"]
    assert _sources(db_session, course.id) == [(BREIZH, True), (KLIKEGO, False)]


def test_the_derived_fields_follow_the_new_active_source(client, db_session, epreuve, scrape):
    """`Course.source_url` et `provider` suivent, puisqu'ils lisent l'active (#279).

    Ce n'est pas une redite de l'AC2 : ces deux propriétés sont ce que le front
    affiche et ce que le cache TTL indexe. Une bascule qui les laisserait sur
    l'ancien chronométreur ferait afficher Klikego au-dessus d'un classement
    Breizh Chrono.
    """
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU")])

    client.patch(_url(course.id, passive.id), json={"is_active": True})

    db_session.expire_all()
    course = course_repository.get(db_session, course.id)
    assert (course.source_url, course.provider) == (BREIZH, "breizhchrono")


def test_the_athletes_left_without_any_result_are_purged(client, db_session, epreuve, scrape):
    """Le remplacement total laisse des fiches vides — même dette qu'une suppression.

    DUPONT et MARTIN ne couraient que cette épreuve : après la bascule, leurs
    fiches n'ont plus aucun résultat. Les laisser ferait de chaque bascule un
    ajout d'orphelins, que seul un `rescrape-db` finirait par balayer ;
    `delete_course` purge déjà au même endroit, avec la même primitive.
    """
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU")])

    client.patch(_url(course.id, passive.id), json={"is_active": True})

    restants = {athlete.nom for athlete in db_session.query(Athlete).all()}
    assert "NOUVEAU" in restants
    assert not restants & {"DUPONT", "MARTIN"}


# --------------------------------------------------------------------- AC3


def test_a_failing_scrape_leaves_the_course_untouched(client, db_session, epreuve, scrape):
    """AC3 — jamais d'épreuve vidée puis abandonnée.

    Le scrape précède toute écriture destructrice : quand il lève, il n'y a rien
    à défaire. L'épreuve garde ses deux dossards **et** son active — l'exploitant
    peut réessayer ou renoncer sur un état identique à celui d'avant son clic.
    """
    course, passive = epreuve
    scrape(ScraperError("Le site du chronométreur est injoignable."))

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 422
    db_session.expire_all()
    assert _dossards(db_session, course.id) == ["1", "2"]
    assert _sources(db_session, course.id) == [(KLIKEGO, True), (BREIZH, False)]


def test_a_scrape_that_returns_nothing_is_a_refusal_not_an_emptying(
    client, db_session, epreuve, scrape
):
    """Zéro résultat est un refus : l'accepter viderait l'épreuve en silence.

    Le cas est réel — une page de classement retirée, une URL qui répond encore
    mais ne publie plus rien. Sur le chemin d'import ordinaire, zéro résultat est
    un succès à zéro compteur ; ici ce serait un classement effacé, donc c'est un
    refus, avec un message qui dit que rien n'a été touché.
    """
    course, passive = epreuve
    scrape([])

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 422
    assert "aucun résultat" in reponse.json()["detail"].lower()
    db_session.expire_all()
    assert _dossards(db_session, course.id) == ["1", "2"]
    assert _sources(db_session, course.id) == [(KLIKEGO, True), (BREIZH, False)]


def test_a_source_publishing_another_event_is_refused(client, db_session, epreuve, scrape):
    """La source entrante doit alimenter **cette** épreuve, pas en créer une autre.

    `get_or_create_course` apparie sur `(nom, date, type, relais)`, à l'égalité
    stricte. Si l'autre chronométreur publie un libellé différent, l'import crée
    une **nouvelle** épreuve et laisse celle qu'on vient de vider à zéro
    résultat : une perte de données qu'aucune exception ne signale, puisque du
    point de vue de l'import tout s'est bien passé.

    Faire converger deux identités est le travail de #289, les rapprocher celui
    de #287. Ici on refuse, et le message nomme ce qui a été publié.
    """
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU", event_name="Triathlon de Mesquer - format XS")])

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 422
    assert "XS" in reponse.json()["detail"]
    db_session.expire_all()
    assert _dossards(db_session, course.id) == ["1", "2"]
    assert _sources(db_session, course.id) == [(KLIKEGO, True), (BREIZH, False)]
    assert course_repository.get_by_identity(
        db_session, "Triathlon de Mesquer - format XS", JOUR, TYPE, False
    ) is None, "le refus précède l'écriture : aucune épreuve homonyme n'a été créée"


def test_nothing_is_journalled_when_the_switch_is_refused(client, db_session, epreuve, scrape):
    """FR-015 — le geste et sa trace sont indissociables, dans les deux sens."""
    course, passive = epreuve
    scrape(ScraperError("injoignable"))

    client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert _bascules(db_session, course.id) == []


# --------------------------------------------------------------------- AC4


def test_switching_to_the_already_active_source_changes_nothing(
    client, db_session, epreuve, scrape
):
    """AC4 — ni suppression ni scrape : la demande est sans effet, pas une erreur.

    Un double-clic, un rechargement de l'écran d'arbitrage : le geste doit être
    idempotent. Re-scraper « par acquit de conscience » détruirait un classement
    pour rien, et le journal se remplirait de non-événements (FR-012).
    """
    course, _ = epreuve
    active = course_source_repository.get_active(db_session, course.id)
    appels = scrape([_result("7", "NOUVEAU")])

    reponse = client.patch(_url(course.id, active.id), json={"is_active": True})

    assert reponse.status_code == 200, reponse.text
    assert appels == [], "aucun scrape ne doit avoir lieu"
    assert _dossards(db_session, course.id) == ["1", "2"]
    assert _bascules(db_session, course.id) == []


# --------------------------------------------------------------------- AC5


def test_a_source_of_another_course_is_a_not_found(client, db_session, epreuve):
    """AC5 — 404, ni 403 ni 500 : l'adresse ne désigne rien, elle n'est pas interdite.

    `UNIQUE(course_id, url)` autorise la même URL sur N épreuves, donc « la
    source 12 » n'a de sens que rapportée à une épreuve. Chercher la source par
    son seul identifiant rendrait ici un 200 qui basculerait la source d'une
    **autre** épreuve.
    """
    course, _ = epreuve
    autre = course_repository.get_or_create(
        db_session, name="Duathlon Nozéen", event_date=date(2026, 3, 1),
        event_type="duathlon-s", source_url="https://www.klikego.com/resultats/nozeen",
        provider="klikego",
    )
    etrangere = course_source_repository.get_active(db_session, autre.id)
    db_session.commit()

    reponse = client.patch(_url(course.id, etrangere.id), json={"is_active": True})

    assert reponse.status_code == 404
    assert _sources(db_session, autre.id) == [
        ("https://www.klikego.com/resultats/nozeen", True)
    ]


def test_an_unknown_course_is_a_not_found(client, epreuve):
    """Même patron que les deux routes voisines d'`admin_data`."""
    assert client.patch(_url(999999, 1), json={"is_active": True}).status_code == 404


def test_deactivating_a_source_is_refused(client, db_session, epreuve):
    """`{"is_active": false}` n'est pas un geste : une épreuve garde son active.

    L'index partiel `UNIQUE(course_id) WHERE is_active` autorise **zéro** active,
    et une épreuve sans active n'est plus scrapée (#282) ni affichée avec sa
    source (#279). Le seul moyen de changer d'active est d'en désigner une autre
    — accepter `false` en silence donnerait à l'exploitant un moyen d'éteindre
    une épreuve sans savoir qu'il le fait.
    """
    course, passive = epreuve

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": False})

    assert reponse.status_code == 400
    assert _sources(db_session, course.id) == [(KLIKEGO, True), (BREIZH, False)]


# --------------------------------------------------------------------- AC6


def test_the_switch_is_journalled_with_both_sources(client, db_session, epreuve, scrape):
    """AC6 — le journal nomme l'épreuve, la source sortante et l'entrante.

    Sans les deux URLs, l'entrée dirait « la source a changé » sans dire depuis
    quoi, et ne permettrait pas de défaire le geste de tête. Le nombre de
    participations remplacées est ce qui en donne l'ampleur — c'est le seul
    chiffre qui distingue une correction anodine d'un classement de 1811 lignes
    réécrit.
    """
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU")])

    client.patch(_url(course.id, passive.id), json={"is_active": True})

    entrees = _bascules(db_session, course.id)
    assert len(entrees) == 1
    charge = entrees[0].payload
    assert charge["name"] == NOM
    assert charge["previous_url"] == KLIKEGO
    assert charge["new_url"] == BREIZH
    assert charge["participations_deleted"] == 2
    assert charge["participations_imported"] == 1
    assert charge["athletes_purged"] == 2


# --------------------------------------------------------------------- AC7


def test_a_fresh_course_is_scraped_anyway(client, db_session, epreuve, scrape):
    """AC7 — le cache TTL ne s'applique pas à une bascule.

    Une épreuve qu'on vient de scraper est **fraîche**, et c'est le cas nominal :
    on ne bascule que sur une épreuve déjà importée. Si la bascule passait par le
    chemin d'import ordinaire, le court-circuit de fraîcheur rendrait « 0 importé,
    N déjà en base » sans un seul résultat changé — la bascule serait un simple
    renommage de source. C'est l'échec le plus silencieux que cette issue puisse
    produire, d'où un test qui vérifie qu'un scrape a bien eu lieu.
    """
    course, passive = epreuve
    course.scraped_at = utcnow()
    db_session.commit()
    appels = scrape([_result("7", "NOUVEAU")])

    reponse = client.patch(_url(course.id, passive.id), json={"is_active": True})

    assert reponse.status_code == 200, reponse.text
    assert appels == [BREIZH]
    assert _dossards(db_session, course.id) == ["7"]


# ------------------------------------------------- ce que la route rend à l'écran


def test_the_response_is_the_updated_source_list(client, epreuve, scrape):
    """L'écran d'arbitrage (#291) se réaffiche sans second appel.

    Même forme que `GET /courses/{id}/sources` (#284) : le front consomme déjà ce
    schéma, en rendre un autre l'obligerait à tenir deux formes pour une même
    donnée. Et le sixième champ reste absent — qui a soumis une URL ne sort pas
    plus d'ici que de la liste publique.
    """
    course, passive = epreuve
    scrape([_result("7", "NOUVEAU")])

    corps = client.patch(_url(course.id, passive.id), json={"is_active": True}).json()

    assert [(source["url"], source["is_active"]) for source in corps] == [
        (BREIZH, True),
        (KLIKEGO, False),
    ]
    assert set(corps[0]) == {"id", "url", "provider", "is_active", "last_scraped_at"}


# --------------------------------------------------- l'inventaire des pouvoirs


def test_the_new_power_is_its_own_entry_in_the_catalogue():
    """Un membre de plus dans `P`, pas un élargissement de `courses:write`.

    Ni migration ni upsert (FR-014) : le pouvoir vit en Python, l'attribution en
    base. Le test fige le code, la fonctionnalité de regroupement, et le fait que
    la description **dise ce que le geste détruit** — c'est elle que lit
    l'exploitant qui compose un rôle.
    """
    from app.core import permissions

    assert P.COURSES_SOURCES.code == "courses:sources"
    assert P.COURSES_SOURCES in permissions.ALL
    assert P.COURSES_SOURCES.feature == permissions.FEATURE_COURSES
    assert "réécrit" in P.COURSES_SOURCES.description
