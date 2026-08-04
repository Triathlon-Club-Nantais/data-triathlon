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
