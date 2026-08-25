"""Géocodage Nominatim (`app/services/geocode_service.py`).

Aucun réseau : la fabrique `http.client` est **enveloppée** — pas remplacée —
pour lui injecter un `httpx.MockTransport`, et `http._resolve` est monkeypatché
comme dans `test_core_http.py`.

Envelopper plutôt que remplacer n'est pas un détail : les kwargs du site
d'appel, dont `follow_redirects=False`, traversent alors la vraie fabrique. Un
faux client les aurait avalés, et le test le plus important de ce fichier — que
le géocodage ne suit pas les redirections — n'aurait mesuré que lui-même.
"""
import httpx
import pytest

from app.core import http
from app.services import geocode_service


@pytest.fixture(autouse=True)
def sans_reseau_ni_attente(monkeypatch):
    """Coupe la résolution DNS, l'attente de rate-limit et le cache mémoire."""
    monkeypatch.setattr(http, "_resolve", lambda host, port: ["93.184.216.34"])
    # `settings.geocode_min_interval_seconds` vaut 1,1 s : sans ça, chaque test
    # de ce fichier attendrait pour de vrai.
    monkeypatch.setattr(geocode_service.time, "sleep", lambda _: None)
    geocode_service._geo_cache.clear()
    yield
    geocode_service._geo_cache.clear()


def _bouchonne(monkeypatch, handler) -> list[httpx.Request]:
    """Injecte `handler` comme transport interne, et rend la liste des requêtes vues."""
    vues: list[httpx.Request] = []
    vraie_fabrique = http.client

    def fabrique(**kwargs):
        def espion(request: httpx.Request) -> httpx.Response:
            vues.append(request)
            return handler(request)

        return vraie_fabrique(transport=httpx.MockTransport(espion), **kwargs)

    monkeypatch.setattr(geocode_service.http, "client", fabrique)
    return vues


def _reponse(*lieux) -> httpx.Response:
    return httpx.Response(200, json=list(lieux))


def test_le_geocodage_ne_suit_pas_les_redirections(monkeypatch):
    """Le seul site du dépôt qui doit rester en `follow_redirects=False`.

    L'appel d'origine était un `httpx.get` nu — donc sans suivi de redirection.
    La fabrique pose `True` par défaut, et la migration vers le garde (#101) a
    failli changer ce comportement en silence. On mesure le fait, pas le kwarg :
    le transport ne doit voir **qu'une** requête.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "nominatim.openstreetmap.org":
            return httpx.Response(302, headers={"Location": "https://ailleurs.example/x"})
        return _reponse({"lat": "47.2", "lon": "-1.5", "class": "place"})

    vues = _bouchonne(monkeypatch, handler)

    assert geocode_service._nominatim_search("Nantes, France") is None
    assert [str(r.url.host) for r in vues] == ["nominatim.openstreetmap.org"]


def test_le_geocodage_rend_le_resultat_le_plus_pertinent(monkeypatch):
    """À classes égales, c'est `importance` qui départage."""
    _bouchonne(monkeypatch, lambda _: _reponse(
        {"lat": "1.0", "lon": "1.0", "class": "place", "importance": 0.3},
        {"lat": "47.2181", "lon": "-1.5528", "class": "place", "importance": 0.9},
    ))

    assert geocode_service._nominatim_search("Nantes, France") == (47.2181, -1.5528)


def test_les_lieux_priment_sur_les_autres_classes(monkeypatch):
    """Un `shop` mieux noté ne doit pas l'emporter sur une commune."""
    _bouchonne(monkeypatch, lambda _: _reponse(
        {"lat": "9.9", "lon": "9.9", "class": "shop", "importance": 0.99},
        {"lat": "47.2181", "lon": "-1.5528", "class": "boundary", "importance": 0.1},
    ))

    assert geocode_service._nominatim_search("Nantes, France") == (47.2181, -1.5528)


def test_sans_lieu_on_se_rabat_sur_les_autres_resultats(monkeypatch):
    """Aucune classe reconnue : mieux vaut le meilleur résultat brut que rien."""
    _bouchonne(monkeypatch, lambda _: _reponse(
        {"lat": "47.2181", "lon": "-1.5528", "class": "shop", "importance": 0.5},
    ))

    assert geocode_service._nominatim_search("Nantes, France") == (47.2181, -1.5528)


def test_une_reponse_vide_rend_none(monkeypatch):
    _bouchonne(monkeypatch, lambda _: _reponse())

    assert geocode_service._nominatim_search("Zzz, France") is None


def test_un_echec_reseau_rend_none_et_journalise(monkeypatch, caplog):
    """Le géocodage est au mieux-effort : il dégrade, il ne fait pas échouer l'import."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nominatim injoignable")

    _bouchonne(monkeypatch, handler)

    with caplog.at_level("WARNING"):
        assert geocode_service._nominatim_search("Nantes, France") is None

    assert "Géocodage échoué" in caplog.text


def test_le_resultat_est_mis_en_cache(monkeypatch):
    """Deux géocodages du même nom d'épreuve : une seule requête."""
    vues = _bouchonne(monkeypatch, lambda _: _reponse(
        {"lat": "47.2181", "lon": "-1.5528", "class": "place", "importance": 0.9},
    ))

    assert geocode_service.geocode("Triathlon de Nantes") == (47.2181, -1.5528)
    assert geocode_service.geocode("Triathlon de Nantes") == (47.2181, -1.5528)
    assert len(vues) == 1


def test_un_echec_est_mis_en_cache_lui_aussi(monkeypatch):
    """Un nom qu'on ne sait pas géocoder ne doit pas être redemandé à chaque appel.

    `geocode` tente la ville puis, à défaut, le nom complet : deux requêtes au
    premier appel, aucune au second.
    """
    vues = _bouchonne(monkeypatch, lambda _: _reponse())

    assert geocode_service.geocode("Triathlon de Nulle Part") is None
    assert geocode_service.geocode("Triathlon de Nulle Part") is None
    assert len(vues) == 2


def test_un_nom_sans_ville_exploitable_ne_declenche_aucune_requete(monkeypatch):
    """Moins de trois caractères extraits : rien à demander à Nominatim.

    « Triathlon de X » se réduit à « X » — trop court pour valoir une requête.
    """
    vues = _bouchonne(monkeypatch, lambda _: _reponse())

    assert geocode_service.geocode("Triathlon de X") is None
    assert vues == []


@pytest.mark.parametrize(
    ("nom_epreuve", "attendu"),
    [
        ("Triathlon de Quiberon M", "Quiberon"),          # suffixe de format retiré
        ("Triathlon de Nantes 2025", "Nantes"),           # millésime retiré
        ("Duathlon du Val-André — 3e edition", "Val-André"),
        ("Triathlon de Saint-Brevin", "Brevin"),
        ("Triathlon d'Oléron", "Oléron"),                 # apostrophe droite
        ("Triathlon d’Oléron", "Oléron"),                 # apostrophe typographique
    ],
)
def test_extraction_de_la_ville(nom_epreuve, attendu):
    """La ville est déduite du nom d'épreuve, seul champ dont on dispose partout.

    Les deux graphies de l'apostrophe comptent autant l'une que l'autre : un nom
    saisi dans le Sheet y passe par l'autocorrection, qui produit U+2019, et
    plusieurs chronométreurs publient déjà cette forme.
    """
    assert geocode_service.extract_city(nom_epreuve) == attendu


@pytest.mark.parametrize(
    ("nom_epreuve", "rendu"),
    [
        ("Swimrun de l'Île-Tudy", "l'Île-Tudy"),  # l'article élidé n'est pas retiré
        ("Swimrun de l’Île-Tudy", "l’Île-Tudy"),  # … dans les deux graphies
        ("Trail des 3 Plages", "Trail des 3 Plages"),  # ne nomme aucune commune
        ("Bike and Run de Vertou", "Bike and Run de Vertou"),  # « and » ≠ « & »/« - »
    ],
)
def test_extraction_de_la_ville_limites_connues(nom_epreuve, rendu):
    """Trois cas que l'extraction ne sait pas réduire — mesurés, pas souhaités.

    Ils sont verrouillés ici pour que leur amélioration éventuelle soit un
    changement **visible** plutôt qu'un effet de bord. Aucun n'est dangereux :
    un libellé non réduit part tel quel à Nominatim, qui rend `None`, et le
    géocodage dégrade sans faire échouer l'import — c'est déjà le contrat de
    `_nominatim_search`. « Trail des 3 Plages » ne nomme d'ailleurs aucune
    commune : il n'y a rien à en extraire.
    """
    assert geocode_service.extract_city(nom_epreuve) == rendu


# --- Batch de géocodage persisté (#579) --------------------------------------


class _CourseFactice:
    """Objet minimal portant `.name`, `.latitude`/`.longitude`/`.geocoded_at` —
    évite d'ouvrir une vraie base pour tester la seule orchestration du batch.
    """

    def __init__(self, name: str) -> None:
        self.id = id(self)
        self.name = name
        self.latitude = None
        self.longitude = None
        self.geocoded_at = None


def test_run_geocode_courses_persiste_les_succes_et_les_echecs(monkeypatch, db_session):
    from app.repositories import course_repository as cr

    succes = _CourseFactice("Triathlon de Nantes")
    echec = _CourseFactice("Triathlon Introuvable")
    monkeypatch.setattr(cr, "list_missing_geocode", lambda db, **kw: [succes, echec])
    monkeypatch.setattr(
        geocode_service, "geocode",
        lambda nom: (47.2181, -1.5528) if "Nantes" in nom else None,
    )

    outcome = geocode_service.run_geocode_courses(db_session)

    assert outcome.total == 2
    assert outcome.geocoded == 1
    assert outcome.errors == 1
    assert outcome.processed == 2
    assert not outcome.interrupted
    assert (succes.latitude, succes.longitude) == (47.2181, -1.5528)
    assert succes.geocoded_at is not None
    assert echec.latitude is None
    assert echec.geocoded_at is not None
    assert [f.url for f in outcome.failures] == ["Triathlon Introuvable"]


def test_run_geocode_courses_echec_total_si_rien_n_a_abouti(monkeypatch, db_session):
    from app.repositories import course_repository as cr

    monkeypatch.setattr(
        cr, "list_missing_geocode", lambda db, **kw: [_CourseFactice("Introuvable")]
    )
    monkeypatch.setattr(geocode_service, "geocode", lambda nom: None)

    outcome = geocode_service.run_geocode_courses(db_session)

    assert outcome.echec_total is True


def test_run_geocode_courses_zero_cible_n_est_pas_un_echec(monkeypatch, db_session):
    from app.repositories import course_repository as cr

    monkeypatch.setattr(cr, "list_missing_geocode", lambda db, **kw: [])

    outcome = geocode_service.run_geocode_courses(db_session)

    assert outcome.total == 0
    assert outcome.echec_total is False


def test_run_geocode_courses_respecte_le_cooldown_par_la_requete(monkeypatch, db_session):
    """Le filtre de cooldown est délégué à `list_missing_geocode` : on vérifie
    que `run_geocode_courses` lui transmet bien `retry_after`."""
    from datetime import timedelta

    from app.repositories import course_repository as cr

    captes = {}

    def _capture(db, *, retry_after, limit=None):
        captes["retry_after"] = retry_after
        return []

    monkeypatch.setattr(cr, "list_missing_geocode", _capture)

    delai = timedelta(days=3)
    geocode_service.run_geocode_courses(db_session, retry_after=delai)

    assert "retry_after" in captes


def test_run_geocode_courses_dry_run_ne_touche_pas_nominatim(monkeypatch, db_session):
    from app.repositories import course_repository as cr

    def _echoue(nom):
        raise AssertionError("dry-run ne doit appeler ni geocode ni save_geocode_attempt")

    monkeypatch.setattr(
        cr, "list_missing_geocode", lambda db, **kw: [_CourseFactice("Tri Cible")]
    )
    monkeypatch.setattr(geocode_service, "geocode", _echoue)
    monkeypatch.setattr(cr, "save_geocode_attempt", _echoue)

    outcome = geocode_service.run_geocode_courses(db_session, dry_run=True)

    assert outcome.total == 1
    assert outcome.dry_run_names == ["Tri Cible"]
    assert outcome.geocoded == 0
    assert outcome.echec_total is False


def test_run_geocode_courses_notifie_on_item_apres_chaque_tentative(monkeypatch, db_session):
    from app.repositories import course_repository as cr

    monkeypatch.setattr(
        cr, "list_missing_geocode", lambda db, **kw: [_CourseFactice("Tri Nantes")]
    )
    monkeypatch.setattr(geocode_service, "geocode", lambda nom: (47.2, -1.5))

    vues = []
    geocode_service.run_geocode_courses(
        db_session, on_item=lambda index, total, nom, coord: vues.append((index, total, nom, coord))
    )

    assert vues == [(0, 1, "Tri Nantes", (47.2, -1.5))]


def test_run_geocode_courses_interrompu_garde_le_bilan_partiel(monkeypatch, db_session):
    """Ctrl-C au milieu du lot : les tentatives déjà faites restent dans le bilan."""
    from app.repositories import course_repository as cr

    premiere = _CourseFactice("Tri Un")
    seconde = _CourseFactice("Tri Deux")
    monkeypatch.setattr(cr, "list_missing_geocode", lambda db, **kw: [premiere, seconde])

    appels = []

    def _geocode(nom):
        appels.append(nom)
        if len(appels) == 2:
            raise KeyboardInterrupt
        return (47.2, -1.5)

    monkeypatch.setattr(geocode_service, "geocode", _geocode)

    outcome = geocode_service.run_geocode_courses(db_session)

    assert outcome.interrupted is True
    assert outcome.processed == 1
    assert outcome.geocoded == 1
    assert premiere.latitude == 47.2
