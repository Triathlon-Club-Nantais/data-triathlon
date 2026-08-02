"""
Sortie HTTP unique de l'application, avec garde de destination (SSRF, #101).

#49 a fermé le **routage** : une URL dont le host n'est servi par aucun provider
n'atteint aucun scraper. Restait la **redirection** — en `follow_redirects=True`,
httpx suit un `302 -> http://169.254.169.254/` sans revalider la cible.

Toute requête sortante de `app/` passe donc par `client()`, qui enveloppe le
transport d'un garde vérifiant **chaque** destination : la requête initiale
comme chaque saut. Le méta-test de `tests/test_core_http.py` refuse tout usage nu
d'`httpx` ailleurs dans `app/` — il n'y a plus de politique à écrire au prochain
fournisseur ajouté, comme `HostMatchedProvider` a supprimé le `matches` à écrire
en #49.

Design : `docs/superpowers/specs/2026-07-31-ssrf-redirection-design.md`.
"""
import ipaddress
import logging
import socket

import httpx

from app.core.exceptions import BlockedTargetError

logger = logging.getLogger(__name__)

#: Schémas autorisés. Le contrôle **porte** : mesuré, dès lors qu'un `transport=`
#: explicite est fourni, httpx n'écarte plus les autres schémas avant d'appeler
#: le transport — `ftp://` y arrive tel quel, et un `302 -> file:///etc/passwd`
#: y arrive réécrit en `file://<host>/etc/passwd`, jusqu'à `TooManyRedirects`.
_SCHEMES = ("http", "https")

_PORTS_PAR_DEFAUT = {"http": 80, "https": 443}


def _is_internal(addr: str) -> bool:
    """Vrai si `addr` n'est pas une adresse publique routable.

    `not is_global` plutôt qu'une disjonction
    `is_private or is_loopback or is_link_local or …` : un prédicat au lieu de
    six, et il ferme en plus la plage CGNAT (`100.64.0.0/10`, RFC 6598) et les
    plages de documentation, que la disjonction laissait passer. Mesuré sur les
    14 hosts fournisseurs réels : 24 adresses, aucune refusée.

    La forme IPv4 est employée quand l'adresse est IPv4-mapped
    (`::ffff:127.0.0.1`) : `is_global` la couvre déjà sur CPython 3.13, mais
    c'est une garantie du contrat, pas un détail de version.

    Une adresse illisible est traitée comme interne : refuser vaut mieux que
    laisser passer ce qu'on n'a pas su lire.
    """
    try:
        ip = ipaddress.ip_address(addr.split("%")[0])  # `%eth0` des adresses lien-local
    except ValueError:
        return True
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return not ip.is_global


def _resolve(host: str, port: int) -> list[str]:
    """Adresses de `host`, liste vide si la résolution échoue.

    Une `gaierror` n'est **pas** un refus : on rend une liste vide, le garde
    laisse passer, et httpx lève sa `ConnectError` habituelle. Un DNS mort est
    une panne, pas une attaque ; le déguiser en refus de destination enverrait
    l'opérateur chercher au mauvais endroit.

    On rattrape large — `OSError` (dont dérivent `gaierror` et `herror`) et
    `UnicodeError` : `getaddrinfo` ré-encode toute chaîne avec le codec `idna`,
    qui lève un `UnicodeEncodeError` nu sur un label de plus de 63 octets. Fail
    **closed** dans les deux cas — aucune requête ne part —, mais l'appelant
    doit recevoir la `ConnectError` d'httpx, pas une exception opaque qui
    ressortirait en « Erreur lors de l'import » sans cause lisible.

    Point de monkeypatch des tests : c'est ici que le réseau s'arrête.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return []
    # `str()` : le stub typeshed type `info[4][0]` en `str | int` à cause d'une
    # variante AF_PACKET inatteignable ici (SOCK_STREAM, AF_INET/AF_INET6).
    return [str(info[4][0]) for info in infos]


def _check_target(url: httpx.URL, memo: dict[tuple[str, int], list[str]]) -> None:
    """Refuse `url` si son schéma ou sa destination n'est pas admissible.

    Le nom vérifié est `url.raw_host` — le nom **du fil**, celui qu'httpcore
    joindra — et jamais `url.host`, sa forme Unicode. Ne pas « simplifier » vers
    `url.host` : `socket.getaddrinfo` ré-encoderait cet Unicode avec le codec
    `idna` de CPython, qui est IDNA **2003**, alors qu'httpx a produit
    `raw_host` avec la bibliothèque idna **2008**. Sur ß, sigma final ou
    ZWJ/ZWNJ les deux normes divergent (`faß.example` → `fass.example` contre
    `xn--fa-hia.example`) : ce sont deux domaines enregistrables distincts, donc
    le garde validerait l'un pendant que la connexion partirait vers l'autre.
    Pour un littéral d'IP ou un nom ASCII, `raw_host` et `host` coïncident —
    mesuré, rien d'autre ne change, mémo compris.
    """
    if url.scheme not in _SCHEMES:
        raise BlockedTargetError(f"Schéma d'URL refusé : {url.scheme}")

    host = url.raw_host.decode("ascii")
    port = url.port or _PORTS_PAR_DEFAUT[url.scheme]

    if not host:
        # Même politique que `_is_internal` : ce qu'on n'a pas su lire, on le
        # refuse. Un host vide n'est joignable par personne, mais le garde doit
        # rester cohérent avec lui-même.
        raise BlockedTargetError("Destination refusée : URL sans host")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        cle = (host, port)
        if cle not in memo:
            memo[cle] = _resolve(host, port)
        adresses = memo[cle]
    else:
        adresses = [host]  # littéral d'IP : aucune résolution nécessaire

    internes = [a for a in adresses if _is_internal(a)]
    if internes:
        # Le détail (les adresses résolues) est journalisé ; le message rendu à
        # l'appelant garde le host — l'opérateur en a besoin dans les bilans
        # CLI — mais pas les adresses, qui décriraient le réseau interne.
        logger.warning(
            "Destination interne refusée (#101) : %s:%s → %s", host, port, ", ".join(internes)
        )
        raise BlockedTargetError(f"Destination interne refusée : {host}")


class _GuardTransport(httpx.BaseTransport):
    """Refuse toute destination qui n'est pas une adresse publique routable.

    **Enveloppe** un transport plutôt que d'hériter de `httpx.HTTPTransport` :
    le garde se teste alors hors réseau, en lui passant un `MockTransport`
    interne.

    Le contrôle vit dans `handle_request`, et non dans un `event_hook` sur
    `response` : le hook ne voit pas la requête initiale, et ne reçoit que le
    `Location` **brut**, qu'il faudrait rejoindre soi-même quand il est relatif
    (`//169.254.169.254/meta`). Ici, `request.url` est déjà résolue par httpx.
    """

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self._inner = inner
        # Mémo host:port -> adresses. `getaddrinfo` coûte 21 à 28 ms sans cache
        # OS observable, et T2Area fait ~26 requêtes vers le même host par
        # épreuve. Sans TTL : la durée de vie est celle du client, un scrape.
        self._resolved: dict[tuple[str, int], list[str]] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        _check_target(request.url, self._resolved)
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def guarded_transport(inner: httpx.BaseTransport | None = None) -> httpx.BaseTransport:
    """Transport gardé, à passer à un client que la fabrique ne construit pas.

    `client()` rend un `httpx.Client` **déjà construit** : inutilisable pour un
    client tiers qui hérite de `httpx.Client` sans être fabriqué ici — c'est le
    cas d'`authlib.integrations.httpx_client.OAuth2Client` (#114), dont les
    `**kwargs` descendent au constructeur httpx, `transport=` compris.

    Sans cette fabrique il n'existerait **aucune voie légale** pour un tel
    client, et la docstring de `client()` (« **Seule** voie de sortie ») serait
    fausse. Il n'y a donc qu'une seule construction du garde, ici — pas de
    second garde parallèle (règle « une seule définition », #33, #76).
    """
    return _GuardTransport(inner or httpx.HTTPTransport())


def client(**kwargs) -> httpx.Client:
    """Client HTTP de l'application. **Seule** voie de sortie de `app/`.

    `follow_redirects=True` par défaut (le comportement des 17 sites d'origine),
    surchargeable. Un `transport=` passé est enveloppé, pas remplacé.

    `httpx.Client` est résolu **par attribut sur le module**, jamais importé
    (`from httpx import Client`) : les tests remplacent `httpx.Client` sur
    l'objet module (`oktime.httpx` *est* `httpx`), donc ils continuent
    d'intercepter la fabrique. Un import direct du symbole les rendrait tous
    muets **sans qu'aucun n'échoue** — ils taperaient le réseau en silence.

    Le transport étant fourni, les kwargs `verify` / `proxy` / `trust_env`
    d'`httpx.Client` cessent de s'appliquer : aucun site d'appel n'en use, mais
    un futur besoin se règle en configurant le transport interne, pas ici.

    Cela vaut aussi, et surtout, pour l'**environnement** : mesuré sur httpx
    0.28.1, `allow_env_proxies = trust_env and transport is None`. La fabrique
    passant toujours un transport, `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` ne
    sont plus honorés — un proxy posé dans l'environnement de déploiement serait
    ignoré **en silence**. Inerte aujourd'hui (ni `render.yaml`, ni le
    Dockerfile, ni `.env.example` n'en définissent) ; le jour où il en faut un,
    il se configure sur le `httpx.HTTPTransport()` interne.
    """
    kwargs.setdefault("follow_redirects", True)
    return httpx.Client(transport=guarded_transport(kwargs.pop("transport", None)), **kwargs)
