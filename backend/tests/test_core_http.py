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


def test_guarded_transport_garde_un_client_quon_ne_fabrique_pas(dns):
    """Voie légale des clients tiers héritant de `httpx.Client` (Authlib, #114).

    Le transport est ici passé à un `httpx.Client` nu — c'est exactement ce que
    fait `OAuth2Client`, dont les `**kwargs` descendent au constructeur httpx.
    """
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("la requête ne devait pas partir")

    transport = http.guarded_transport(httpx.MockTransport(handler))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(BlockedTargetError):
            client.get("http://169.254.169.254/latest/meta-data/")


#: Fonctions et classes d'`httpx` qui **ouvrent** une connexion. Une annotation
#: de paramètre (`client: httpx.Client`) n'en fait pas partie : ces fonctions
#: reçoivent leur client, elles n'en construisent pas — et l'AST les distingue
#: nativement, une annotation étant un `Attribute` et non un `Call`.
#:
#: Les transports en font partie depuis #114 : `httpx.HTTPTransport()` construit
#: la connexion que le garde doit envelopper, et un transport nu passé à un
#: client Authlib rendrait le garde inopérant sans qu'aucun `Client` n'apparaisse
#: dans le fichier.
_VERBES_HTTPX = frozenset({
    "Client", "AsyncClient",
    "HTTPTransport", "AsyncHTTPTransport",
    "get", "post", "put", "patch", "delete", "head", "options",
    "stream", "request",
})

#: Clients d'`authlib.integrations.httpx_client`. Ils **héritent de `httpx.Client`**
#: et ouvrent de vraies connexions, mais ne sont liés ni au module httpx ni à un
#: import venu de lui : sans cette seconde table, ils échappaient au détecteur
#: (mesuré au sondage du 2026-08-01, §7).
#: `AssertionClient` en fait partie : il est exporté par le même module et
#: hérite lui aussi de `httpx.Client`. Un méta-test compare cette table aux
#: exports **réels** du paquet, pour qu'une version d'Authlib qui en ajoute un
#: ne rouvre pas le trou en silence.
_VERBES_AUTHLIB = frozenset({
    "OAuth2Client", "AsyncOAuth2Client",
    "OAuth1Client", "AsyncOAuth1Client",
    "AssertionClient", "AsyncAssertionClient",
})

#: Module -> verbes qui y ouvrent une connexion.
_VERBES_PAR_MODULE = {
    "httpx": _VERBES_HTTPX,
    "authlib.integrations.httpx_client": _VERBES_AUTHLIB,
}


def _httpx_nu(source: str) -> list[int]:
    """Lignes de `source` qui ouvrent une connexion httpx sans passer par la fabrique.

    Analyse l'AST plutôt que le texte : un motif textuel est aveugle aux alias
    (`import httpx as h`, `from httpx import Client`), et il faut lui apprendre
    à ne pas mordre sur les annotations. L'AST résout les deux d'un coup — il
    sait à quel module un nom est lié, et un appel y est un nœud distinct d'une
    annotation.
    """
    import ast

    arbre = ast.parse(source)

    # Nom local -> verbes ouvrant une connexion (`httpx`, `h`, `httpx_client`, …).
    modules: dict[str, frozenset[str]] = {}
    directs: set[str] = set()   # noms liés à un verbe (`from httpx import Client`)
    def chemin_pointe(cible) -> str | None:
        """`a.b.c` pour un `Attribute` chaîné sur un `Name`, sinon `None`.

        `import authlib.integrations.httpx_client` (sans alias) lie le nom
        **complet** au site d'appel : la cible y est un `Attribute` imbriqué,
        pas un `Name`. Sans reconstruction, ni la liaison ni l'appel ne
        correspondaient — un fournisseur écrit sous cette forme aurait ouvert un
        client sur le transport httpx par défaut, sans qu'aucun test n'échoue.
        """
        morceaux: list[str] = []
        while isinstance(cible, ast.Attribute):
            morceaux.append(cible.attr)
            cible = cible.value
        if not isinstance(cible, ast.Name):
            return None
        morceaux.append(cible.id)
        return ".".join(reversed(morceaux))

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                verbes = _VERBES_PAR_MODULE.get(alias.name)
                if verbes:
                    # Sans alias, `import a.b.c` lie le chemin complet : c'est
                    # sous cette forme qu'il faudra le reconnaître à l'appel.
                    modules[alias.asname or alias.name] = verbes
        elif isinstance(noeud, ast.ImportFrom):
            verbes = _VERBES_PAR_MODULE.get(noeud.module or "")
            if verbes:
                directs |= {
                    alias.asname or alias.name
                    for alias in noeud.names
                    if alias.name in verbes
                }
                continue
            # `from authlib.integrations import httpx_client` : c'est le **module**
            # qui est lié, pas un verbe.
            for alias in noeud.names:
                complet = f"{noeud.module}.{alias.name}" if noeud.module else alias.name
                verbes_module = _VERBES_PAR_MODULE.get(complet)
                if verbes_module:
                    modules[alias.asname or alias.name] = verbes_module

    fautives: list[int] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        cible = noeud.func
        porteur = (
            chemin_pointe(cible.value) if isinstance(cible, ast.Attribute) else None
        )
        if (
            porteur is not None
            and isinstance(cible, ast.Attribute)
            and cible.attr in modules.get(porteur, frozenset())
        ) or (isinstance(cible, ast.Name) and cible.id in directs):
            fautives.append(noeud.lineno)
    return sorted(fautives)


def test_le_detecteur_voit_les_formes_alias():
    """Le détecteur suit les alias — c'est ce qu'un motif textuel ne savait pas faire."""
    assert _httpx_nu("import httpx\nhttpx.Client(timeout=1)\n") == [2]
    assert _httpx_nu("import httpx as h\nh.Client(timeout=1)\n") == [2]
    assert _httpx_nu("from httpx import Client\nClient(timeout=1)\n") == [2]
    assert _httpx_nu("from httpx import Client as C\nC(timeout=1)\n") == [2]
    assert _httpx_nu("import httpx as h\nh.get('http://x')\n") == [2]


def test_le_detecteur_voit_les_clients_authlib():
    """`OAuth2Client` hérite de `httpx.Client` et ouvre de vraies connexions (#114).

    Angle mort mesuré au sondage du 2026-08-01 : le détecteur ne flaguait qu'un
    nom lié **au module httpx**, or Authlib importe le sien depuis
    `authlib.integrations.httpx_client`. Il aurait donc laissé passer la
    **première** sortie HTTP invisible au filet de #101 — à l'endroit exact où
    circulent un `client_secret` et un code d'autorisation.
    """
    assert _httpx_nu(
        "from authlib.integrations.httpx_client import OAuth2Client\n"
        "OAuth2Client(client_id='x')\n"
    ) == [2]
    assert _httpx_nu(
        "from authlib.integrations.httpx_client import AsyncOAuth2Client\n"
        "AsyncOAuth2Client(client_id='x')\n"
    ) == [2]
    assert _httpx_nu(
        "from authlib.integrations import httpx_client\n"
        "httpx_client.OAuth2Client(client_id='x')\n"
    ) == [2]


def test_le_detecteur_voit_un_import_pointe_sans_alias():
    """`import authlib.integrations.httpx_client` puis appel sur le chemin pointé.

    Forme parfaitement légale que le détecteur laissait passer deux fois : la
    liaison était écartée (le nom contient des points) et la cible d'appel est
    un `Attribute` imbriqué, non un `Name`. Un second fournisseur écrit ainsi
    aurait ouvert un `OAuth2Client` sur le transport httpx par défaut — le
    `client_secret` de l'échange de jeton hors du contrôle de destination — sans
    qu'aucun test n'échoue.
    """
    assert _httpx_nu(
        "import authlib.integrations.httpx_client\n"
        "authlib.integrations.httpx_client.OAuth2Client(client_id='x')\n"
    ) == [2]
    assert _httpx_nu("import httpx\nhttpx.Client()\n") == [2]


def test_le_detecteur_voit_les_clients_assertion():
    """`AssertionClient` / `AsyncAssertionClient` sont exportés par le même module
    et héritent aussi de `httpx.Client` — vérifié dans le paquet installé."""
    assert _httpx_nu(
        "from authlib.integrations.httpx_client import AssertionClient\n"
        "AssertionClient(token_endpoint='x')\n"
    ) == [2]
    assert _httpx_nu(
        "from authlib.integrations.httpx_client import AsyncAssertionClient\n"
        "AsyncAssertionClient(token_endpoint='x')\n"
    ) == [2]


def test_la_table_du_detecteur_couvre_tous_les_clients_exportes():
    """Garde du garde : la table est comparée aux exports **réels** du paquet.

    Sans elle, une version d'Authlib qui ajoute un client ouvrirait un trou que
    personne ne verrait — c'est exactement ce qui vient d'arriver avec
    `AssertionClient`.
    """
    import httpx as _httpx
    from authlib.integrations import httpx_client

    clients_reels = {
        nom
        for nom in httpx_client.__all__
        if isinstance(getattr(httpx_client, nom, None), type)
        and issubclass(
            getattr(httpx_client, nom), (_httpx.Client, _httpx.AsyncClient)
        )
    }

    assert clients_reels <= _VERBES_AUTHLIB, (
        f"clients Authlib absents de la table : {clients_reels - _VERBES_AUTHLIB}"
    )


def test_le_detecteur_voit_les_transports_nus():
    """`httpx.HTTPTransport()` construit la connexion que le garde doit envelopper.

    Un transport nu passé à un client Authlib rendrait le garde inopérant sans
    qu'aucun `httpx.Client` n'apparaisse dans le fichier.
    """
    assert _httpx_nu("import httpx\nhttpx.HTTPTransport()\n") == [2]
    assert _httpx_nu("from httpx import AsyncHTTPTransport\nAsyncHTTPTransport()\n") == [2]


def test_le_detecteur_ignore_ce_qui_nouvre_aucune_connexion():
    """Annotations, clients reçus en paramètre, et fabrique maison restent légitimes."""
    assert _httpx_nu("import httpx\ndef f(client: httpx.Client) -> None: ...\n") == []
    assert _httpx_nu("import httpx\ndef f(c): return c.get('http://x')\n") == []
    assert _httpx_nu("from app.core import http\nhttp.client(timeout=30)\n") == []
    # Un `Client` homonyme venu d'ailleurs n'est pas celui d'httpx.
    assert _httpx_nu("from ailleurs import Client\nClient()\n") == []
    # `httpx.HTTPError` n'ouvre rien : c'est une exception, pas un verbe.
    assert _httpx_nu("import httpx\ntry: ...\nexcept httpx.HTTPError: ...\n") == []


#: Les deux seuls fichiers qui construisent un client. `core/http.py` est la
#: fabrique elle-même ; `services/auth/idp/github.py` construit l'`OAuth2Client`
#: d'Authlib, à qui il passe `guarded_transport()` — le détecteur lit l'AST, il
#: ne peut pas juger *quel* transport est passé. Cette exemption est donc
#: doublée d'un test **positif** côté authentification
#: (`test_le_transport_par_defaut_est_le_transport_garde`), sans lequel elle
#: serait un trou : le fichier pourrait cesser de garder sans que rien n'échoue.
#: Nominative, jamais un motif de dossier — un second fichier ajouté dans `idp/`
#: doit repasser par la fabrique.
_FABRIQUES = ("core/http.py", "services/auth/idp/github.py")


def test_meta_aucun_httpx_nu_dans_app():
    """Aucune ouverture de connexion httpx hors des fabriques recensées.

    Pendant de `HostMatchedProvider` en #49 : il ne suffit pas de corriger les
    sites d'aujourd'hui, il faut que l'oubli du prochain fournisseur ajouté
    soit une erreur de test.
    """
    from pathlib import Path

    racine = Path(__file__).resolve().parent.parent / "app"

    fautifs = [
        f"{chemin.relative_to(racine)}:{ligne}"
        for chemin in sorted(racine.rglob("*.py"))
        if chemin.relative_to(racine).as_posix() not in _FABRIQUES
        for ligne in _httpx_nu(chemin.read_text(encoding="utf-8"))
    ]

    assert fautifs == [], (
        "Passer par `app.core.http.client()` — sans quoi la destination n'est "
        f"pas vérifiée (#101). Sites nus : {fautifs}"
    )
