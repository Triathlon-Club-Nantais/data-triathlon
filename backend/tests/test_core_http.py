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


class _Dns:
    """Résolveur factice : une table de réponses **et** un journal d'appels.

    Les deux sont des attributs distincts, jamais deux clés d'un même dict : un
    host littéralement nommé `appels` aurait sinon résolu vers le journal.
    """

    def __init__(self) -> None:
        self.table: dict[str, list[str]] = {}
        self.appels: list[str] = []

    def resolve(self, host: str, port: int) -> list[str]:
        self.appels.append(host)
        return self.table.get(host, ["93.184.216.34"])


@pytest.fixture
def dns(monkeypatch):
    """Table de résolution factice. Tout host inconnu résout en adresse publique."""
    faux = _Dns()
    monkeypatch.setattr(http, "_resolve", faux.resolve)
    return faux


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

    assert dns.appels == []


def test_une_seule_adresse_interne_suffit_a_refuser(dns):
    """Un host hostile publie souvent une adresse publique *et* une interne."""
    dns.table["piege.example"] = ["93.184.216.34", "10.0.0.5"]

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
    """Une `gaierror` doit rester une panne réseau, pas une alerte de sécurité.

    Ce que ce test prouve : le garde **laisse passer** une résolution vide, donc
    aucun `BlockedTargetError` n'intercepte en amont et la requête atteint le
    transport. La `ConnectError` levée par le handler n'est qu'un échafaudage —
    c'est celle qu'httpx lèverait sur un vrai DNS mort ; l'assertion ne
    prouverait rien du comportement d'httpx, seulement de celui du mock.
    """
    monkeypatch.setattr(http, "_resolve", lambda host, port: [])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nom ou service inconnu")

    with _client(handler) as client:
        with pytest.raises(httpx.ConnectError):
            client.get("https://host-mort.example/x")


def test_une_resolution_impossible_ne_leve_pas_dexception_nue():
    """Un label de plus de 63 octets fait lever le codec `idna` de CPython.

    Sans rattrapage, cet `UnicodeEncodeError` nu remontait jusqu'au
    `except Exception` d'`import_service` et sortait en « Erreur lors de
    l'import », sans cause lisible. Ici : liste vide, donc `ConnectError`
    d'httpx en aval. Pas de fixture `dns` — c'est le vrai `_resolve` qu'on
    éprouve, sans réseau (rien ne part, l'encodage échoue avant).
    """
    assert http._resolve("a" * 64 + ".example", 80) == []


def test_url_sans_host_refusee(dns):
    """Cohérence avec `_is_internal` : ce qu'on n'a pas su lire, on le refuse."""
    with pytest.raises(BlockedTargetError):
        http._check_target(httpx.URL("http:///x"), {})

    assert dns.appels == []


def test_le_message_de_refus_ne_divulgue_pas_les_adresses_internes(dns, caplog):
    """Le host reste (bilans CLI) ; les adresses résolues vont au journal."""
    import logging

    dns.table["piege.example"] = ["10.0.0.5"]

    with caplog.at_level(logging.WARNING, logger="app.core.http"):
        with pytest.raises(BlockedTargetError) as excinfo:
            http._check_target(httpx.URL("https://piege.example/x"), {})

    assert "piege.example" in excinfo.value.message
    assert "10.0.0.5" not in excinfo.value.message
    assert "10.0.0.5" in caplog.text


def test_le_garde_resout_le_nom_du_fil_pas_sa_forme_unicode(dns):
    """Non-régression : contournement IDNA 2003 / IDNA 2008 (revue de #101).

    `url.host` est l'Unicode ; `socket.getaddrinfo` le ré-encode avec le codec
    `idna` de CPython, qui est IDNA **2003**. httpcore, lui, se connecte à
    `url.raw_host`, qu'httpx produit avec la bibliothèque idna **2008**. Mesuré
    ici : `faß.example` donne `fass.example` d'un côté, `xn--fa-hia.example` de
    l'autre — deux domaines enregistrables distincts. Vérifier le premier et
    joindre le second laissait le garde valider une adresse publique pendant que
    la connexion partait ailleurs.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    with _client(handler) as client:
        client.get("http://faß.example/x")

    assert dns.appels == ["xn--fa-hia.example"]


def test_memo_une_seule_resolution_par_host(dns):
    """`getaddrinfo` coûte 21-28 ms : T2Area fait ~26 requêtes vers le même host."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    with _client(handler) as client:
        client.get("https://timepulse.fr/a")
        client.get("https://timepulse.fr/b")

    assert dns.appels == ["timepulse.fr"]


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


def test_meta_aucun_httpx_nu_dans_app():
    """Aucune construction de client httpx hors de `app/core/http.py`.

    Pendant de `HostMatchedProvider` en #49 : il ne suffit pas de corriger les
    sites d'aujourd'hui, il faut que l'oubli du prochain fournisseur ajouté
    soit une erreur de test. La parenthèse évite de mordre sur les annotations
    de paramètre (`client: httpx.Client`), qui sont légitimes — ces fonctions
    reçoivent leur client, elles n'en construisent pas.
    """
    import re
    from pathlib import Path

    racine = Path(__file__).resolve().parent.parent / "app"
    motif = re.compile(
        r"\bhttpx\.(Client|AsyncClient|get|post|put|patch|delete|head|options|stream|request)\("
    )

    fautifs = [
        f"{chemin.relative_to(racine)}:{numero}"
        for chemin in sorted(racine.rglob("*.py"))
        if chemin != racine / "core" / "http.py"
        for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1)
        if motif.search(ligne)
    ]

    assert fautifs == [], (
        "Passer par `app.core.http.client()` — sans quoi la destination n'est "
        f"pas vérifiée (#101). Sites nus : {fautifs}"
    )
