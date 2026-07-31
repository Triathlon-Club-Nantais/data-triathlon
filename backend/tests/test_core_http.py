"""Garde de destination du client HTTP partagé (SSRF par redirection, #101).

Aucun réseau : `_resolve` est monkeypatché par la fixture `dns`, et le transport
interne est un `httpx.MockTransport`.
"""
import httpx
import pytest

from app.core import http
from app.core.exceptions import BlockedTargetError

# Panel mesuré au design (2026-07-31), tableau « disjonction vs is_global ».
INTERNES = [
    "169.254.169.254",   # métadonnées d'instance — l'exemple du ticket
    "127.0.0.1",
    "10.0.0.5",
    "192.168.1.1",
    "172.16.0.1",
    "0.0.0.0",
    "::1",
    "fe80::1",
    "fc00::1",
    "::ffff:127.0.0.1",  # IPv4-mapped
    "192.0.2.1",         # TEST-NET
    "100.64.0.1",        # CGNAT (RFC 6598) — que `is_private` seul laissait passer
]
PUBLIQUES = ["8.8.8.8", "2001:4860:4860::8888"]


@pytest.fixture
def dns(monkeypatch):
    """Table de résolution factice. Tout host inconnu résout en adresse publique."""
    table: dict[str, list[str]] = {}
    appels: list[str] = []

    def faux_resolve(host: str, port: int) -> list[str]:
        appels.append(host)
        return table.get(host, ["93.184.216.34"])

    monkeypatch.setattr(http, "_resolve", faux_resolve)
    table["appels"] = appels  # exposé aux tests qui comptent les résolutions
    return table


def _client(handler, **kwargs) -> httpx.Client:
    return http.client(transport=httpx.MockTransport(handler), **kwargs)


@pytest.mark.parametrize("addr", INTERNES)
def test_politique_refuse_les_adresses_internes(addr):
    assert http._is_internal(addr) is True


@pytest.mark.parametrize("addr", PUBLIQUES)
def test_politique_accepte_les_adresses_publiques(addr):
    assert http._is_internal(addr) is False


def test_la_redirection_vers_une_ip_interne_ne_part_pas(dns):
    """Le transport interne ne doit jamais voir la seconde URL.

    C'est ce qui prouve que la requête ne part pas — et non seulement qu'une
    exception sort. La cible étant un littéral d'IP, aucune résolution DNS
    n'entre en jeu — la fixture `dns` ne sert ici qu'à garantir l'absence de
    réseau.
    """
    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vues.append(str(request.url))
        if request.url.host == "timepulse.fr":
            return httpx.Response(
                302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
            )
        return httpx.Response(200, text="secret")

    with _client(handler) as client:
        with pytest.raises(BlockedTargetError):
            client.get("https://timepulse.fr/x")

    assert vues == ["https://timepulse.fr/x"]


def test_la_redirection_relative_vers_une_ip_interne_ne_part_pas(dns):
    """`Location: //169.254.169.254/meta` — httpx la résout, le garde la voit."""
    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vues.append(str(request.url))
        if request.url.host == "timepulse.fr":
            return httpx.Response(302, headers={"Location": "//169.254.169.254/meta"})
        return httpx.Response(200)

    with _client(handler) as client:
        with pytest.raises(BlockedTargetError):
            client.get("https://timepulse.fr/x")

    assert vues == ["https://timepulse.fr/x"]


def test_la_redirection_cross_host_legitime_passe(dns):
    """L'export CSV d'un Google Sheet redirige vers un autre domaine.

    Ce test interdit de resserrer plus tard vers une allowlist de hosts sans
    s'en apercevoir : `sheet_source` cesserait de fonctionner.
    """
    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vues.append(str(request.url))
        if request.url.host == "docs.google.com":
            return httpx.Response(
                302, headers={"Location": "https://doc-0.googleusercontent.com/export"}
            )
        return httpx.Response(200, text="a,b\n1,2\n")

    with _client(handler) as client:
        reponse = client.get("https://docs.google.com/spreadsheets/d/x/export")

    assert reponse.status_code == 200
    assert len(vues) == 2


def test_une_ip_interne_demandee_directement_est_refusee(dns):
    """Littéral d'IP : aucune résolution DNS n'est nécessaire."""
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("la requête ne devait pas partir")

    with _client(handler) as client:
        with pytest.raises(BlockedTargetError):
            client.get("http://169.254.169.254/latest/meta-data/")

    assert dns["appels"] == []


def test_une_seule_adresse_interne_suffit_a_refuser(dns):
    """Un host hostile publie souvent une adresse publique *et* une interne."""
    dns["piege.example"] = ["93.184.216.34", "10.0.0.5"]

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("la requête ne devait pas partir")

    with _client(handler) as client:
        with pytest.raises(BlockedTargetError):
            client.get("https://piege.example/x")


def test_schema_ftp_refuse(dns):
    """Mesuré : avec un `transport=` explicite, httpx laisse passer `ftp://`."""
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("la requête ne devait pas partir")

    with _client(handler) as client:
        with pytest.raises(BlockedTargetError):
            client.get("ftp://exemple.fr/x")


def test_redirection_vers_file_refusee(dns):
    """Sans le contrôle de schéma, httpx boucle 20 fois sur `file://<host>/…`."""
    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vues.append(str(request.url))
        return httpx.Response(302, headers={"Location": "file:///etc/passwd"})

    with _client(handler) as client:
        with pytest.raises(BlockedTargetError):
            client.get("https://timepulse.fr/x")

    assert vues == ["https://timepulse.fr/x"]


def test_dns_mort_nest_pas_un_refus(dns, monkeypatch):
    """Une `gaierror` doit rester une panne réseau, pas une alerte de sécurité."""
    monkeypatch.setattr(http, "_resolve", lambda host, port: [])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nom ou service inconnu")

    with _client(handler) as client:
        with pytest.raises(httpx.ConnectError):
            client.get("https://host-mort.example/x")


def test_memo_une_seule_resolution_par_host(dns):
    """`getaddrinfo` coûte 21-28 ms : T2Area fait ~26 requêtes vers le même host."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    with _client(handler) as client:
        client.get("https://timepulse.fr/a")
        client.get("https://timepulse.fr/b")

    assert dns["appels"] == ["timepulse.fr"]


def test_blocked_target_error_nest_pas_une_value_error():
    """`import_service._scrape_all` attrape `ValueError` pour « provider non
    supporté » : une destination refusée s'y afficherait comme un problème de
    fournisseur."""
    assert not issubclass(BlockedTargetError, ValueError)


def test_la_fabrique_pose_follow_redirects_par_defaut(monkeypatch):
    """Les 19 espions des tests existants assertent ce kwarg."""
    vus: dict = {}
    vrai_client = httpx.Client

    def espion(*args, **kwargs):
        vus.update(kwargs)
        return vrai_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", espion)
    with http.client(timeout=30):
        pass

    assert vus.get("follow_redirects") is True
    assert vus.get("timeout") == 30
