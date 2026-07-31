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
import socket

import httpx

from app.core.exceptions import BlockedTargetError

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

    Point de monkeypatch des tests : c'est ici que le réseau s'arrête.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return [info[4][0] for info in infos]


def _check_target(url: httpx.URL, memo: dict[tuple[str, int], list[str]]) -> None:
    """Refuse `url` si son schéma ou sa destination n'est pas admissible."""
    if url.scheme not in _SCHEMES:
        raise BlockedTargetError(f"Schéma d'URL refusé : {url.scheme}")

    host = url.host
    port = url.port or _PORTS_PAR_DEFAUT[url.scheme]

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
        raise BlockedTargetError(
            f"Destination interne refusée : {host} → {', '.join(internes)}"
        )


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
    """
    kwargs.setdefault("follow_redirects", True)
    inner = kwargs.pop("transport", None) or httpx.HTTPTransport()
    return httpx.Client(transport=_GuardTransport(inner), **kwargs)
