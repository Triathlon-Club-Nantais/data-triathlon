# Garde de destination HTTP contre le SSRF par redirection — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** faire passer **toute** sortie HTTP de `app/` par une fabrique unique qui
vérifie chaque destination — requête initiale et chaque saut de redirection — et
refuse celles qui ne sont pas des adresses publiques routables (issue #101).

**Architecture:** un module `app/core/http.py` expose `client(**kwargs)`, qui
construit un `httpx.Client` en enveloppant son transport dans un
`_GuardTransport`. Le garde s'exécute dans `handle_request`, donc sur une
`request.url` déjà résolue par httpx : il voit la requête initiale et chaque
saut, sans avoir à rejoindre un `Location` relatif. La politique est
`not ip.is_global`, évaluée sur toutes les adresses rendues par `getaddrinfo`.
Un méta-test interdit tout usage nu d'`httpx` ailleurs dans `app/`.

**Tech Stack:** Python 3.13, httpx 0.28.1, pytest, ruff, uv.

Spec : `docs/superpowers/specs/2026-07-31-ssrf-redirection-design.md` (canonique
— ne pas la réécrire). Issue : #101. Suite de #49 (`registry._host_match`).

## Global Constraints

- Toutes les commandes se lancent **depuis `backend/`**, via `uv run` (aucun venv à activer).
- **Aucun test unitaire ne touche le réseau.** Le réseau réel vit derrière le marker `integration`.
- Langue : **français** pour les docstrings de règle métier, les messages d'erreur
  visibles et les noms de tests ; **English** pour les identifiants de code.
  (Constitution v1.0.0, Principe I.)
- Commits en **Conventional Commits** (`feat:`, `fix:`, `test:`, `docs:`…).
- **Aucun test existant ne doit être modifié.** C'est le critère de non-régression
  du design : les 19 `monkeypatch` des tests patchent `httpx.Client` sur l'objet
  module, ils doivent continuer d'intercepter la fabrique.
- Prédicat de politique, verbatim : `not ip.is_global`, appliqué à
  `ip.ipv4_mapped or ip`.
- `BlockedTargetError` ne doit **jamais** dériver de `ValueError`.
- Dans `app/core/http.py`, `httpx.Client` se résout **par attribut sur le module**
  (`httpx.Client(...)`), jamais par `from httpx import Client`.

---

### Task 1 : le module de sortie HTTP et son garde

**Files:**
- Create: `backend/app/core/http.py`
- Modify: `backend/app/core/exceptions.py` (ajout de `BlockedTargetError` après `ScraperError`)
- Test: `backend/tests/test_core_http.py` (créé)

**Interfaces:**
- Consumes: `app.core.exceptions.DomainError` (existant).
- Produces:
  - `app.core.exceptions.BlockedTargetError(DomainError)` — `status_code = 422`.
  - `app.core.http.client(**kwargs) -> httpx.Client` — pose `follow_redirects=True`
    par défaut, accepte `transport=` (enveloppé), et tout kwarg d'`httpx.Client`.
  - `app.core.http._is_internal(addr: str) -> bool` — privé, testé directement.
  - `app.core.http._resolve(host: str, port: int) -> list[str]` — privé, point de
    monkeypatch des tests (renvoie `[]` sur `gaierror`).

- [ ] **Step 1 : écrire les tests qui échouent**

Créer `backend/tests/test_core_http.py` :

```python
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
```

- [ ] **Step 2 : lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_core_http.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.http'` (collecte impossible).

- [ ] **Step 3 : ajouter `BlockedTargetError`**

Dans `backend/app/core/exceptions.py`, juste après la classe `ScraperError` :

```python
class BlockedTargetError(DomainError):
    """Destination réseau refusée par le garde de `core/http` (SSRF, #101).

    Ne dérive **pas** de `ValueError` : `import_service._scrape_all` attrape
    `ValueError` pour dire « fournisseur non supporté », et une destination
    refusée s'y afficherait comme un problème de fournisseur. Elle tombe donc
    dans le `except Exception` qui suit, et ressort en `ScraperError` avec sa
    cause — visible dans le détail des épreuves en erreur des bilans CLI.
    """

    status_code = 422
    message = "Destination réseau refusée"
```

- [ ] **Step 4 : écrire `app/core/http.py`**

Créer `backend/app/core/http.py` :

```python
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
```

- [ ] **Step 5 : lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_core_http.py -v`
Expected: PASS — 25 tests (12 `INTERNES` + 2 `PUBLIQUES` + 11 tests nommés).

- [ ] **Step 6 : vérifier qu'aucun test existant n'a bougé**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS, sans avoir modifié un seul fichier de test existant. À ce stade
aucun site d'appel n'a migré, donc rien ne peut avoir régressé — c'est la
mesure de référence pour la tâche 2.

Run: `uv run ruff check .`
Expected: aucune erreur.

- [ ] **Step 7 : commit**

```bash
git add backend/app/core/http.py backend/app/core/exceptions.py backend/tests/test_core_http.py
git commit -m "feat(core): garde de destination sur le client HTTP partagé (#101)"
```

---

### Task 2 : faire passer les 18 sites par la fabrique

**Files:**
- Modify (scrapers, 16 sites) : `backend/app/scrapers/breizhchrono.py:217,384`,
  `sportinnovation.py:486,627`, `timepulse.py:78,92`, `klikego.py:313`,
  `wiclax.py:273`, `prolivesport.py:237`, `raceresult.py:1351`,
  `chronoplace.py:467`, `t2area.py:515`, `runnerbreizh.py:501`,
  `competitor.py:361`, `oktime.py:671`, `registry.py:139-144`
- Modify (services, 2 sites) : `backend/app/services/sheet_source.py:87`,
  `backend/app/services/geocode_service.py:47`
- Test: `backend/tests/test_core_http.py` (ajout du méta-test)

**Interfaces:**
- Consumes: `app.core.http.client(**kwargs)` de la tâche 1.
- Produces: aucune nouvelle interface. Invariant produit : plus aucun
  `httpx.Client(` / `httpx.get(` / `httpx.post(` / `httpx.stream(` /
  `httpx.request(` dans `app/` hors `app/core/http.py`.

- [ ] **Step 1 : écrire le méta-test qui échoue**

Ajouter à la fin de `backend/tests/test_core_http.py` :

```python
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
    motif = re.compile(r"\bhttpx\.(Client|AsyncClient|get|post|put|delete|head|stream|request)\(")

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
```

- [ ] **Step 2 : lancer le méta-test pour vérifier qu'il échoue**

Run: `uv run pytest tests/test_core_http.py::test_meta_aucun_httpx_nu_dans_app -v`
Expected: FAIL, avec **18 entrées** listées — 16 sous `scrapers/`, 2 sous `services/`.
Si le compte diffère de 18, ne pas corriger le test : relire la liste rendue,
un site a pu être ajouté depuis la rédaction du plan (c'est déjà arrivé entre
#49 et #101, de 13 à 18).

- [ ] **Step 3 : migrer les onze sites de forme identique**

Onze sites portent exactement la même ligne. Dans chacun de ces fichiers,
remplacer l'import et la ligne :

```python
# import — ajouter à côté des autres imports `app.`
from app.core import http

# ligne du site
with http.client(timeout=30, headers=HEADERS) as client:
```

Fichiers et lignes concernés (la ligne d'origine est, dans les onze cas,
`with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:`) :

| Fichier | Ligne |
| --- | --- |
| `app/scrapers/breizhchrono.py` | 217 |
| `app/scrapers/breizhchrono.py` | 384 |
| `app/scrapers/sportinnovation.py` | 627 |
| `app/scrapers/klikego.py` | 313 |
| `app/scrapers/prolivesport.py` | 237 |
| `app/scrapers/raceresult.py` | 1351 |
| `app/scrapers/chronoplace.py` | 467 |
| `app/scrapers/t2area.py` | 515 |
| `app/scrapers/runnerbreizh.py` | 501 |
| `app/scrapers/competitor.py` | 361 |
| `app/scrapers/oktime.py` | 671 |

**Ne pas retirer `import httpx`** de ces fichiers sauf `runnerbreizh.py` : les
dix autres s'en servent encore pour des annotations (`client: httpx.Client`) ou
pour `httpx.HTTPError`. `runnerbreizh.py` n'a que ce seul usage — y retirer
`import httpx` (ligne 26), sinon ruff lève `F401`.

- [ ] **Step 4 : migrer les trois sites de forme voisine**

`app/scrapers/sportinnovation.py:486` (timeout 15, variable `c`) :

```python
        with http.client(timeout=15, headers=HEADERS) as c:
```

`app/scrapers/wiclax.py:273` (sans `headers`) :

```python
    with http.client(timeout=30) as client:
```

`app/scrapers/registry.py:139-144` — l'import local d'`httpx` disparaît :

```python
        if not heat:
            # Auto-détection du heat via le helper klikego
            from app.core import http

            from app.scrapers.klikego import HEADERS as KL_HEADERS
            from app.scrapers.klikego import _detect_heat
            with http.client(timeout=20, headers=KL_HEADERS) as client:
                heat = _detect_heat(event_id, client)
```

- [ ] **Step 5 : migrer les deux `httpx.get` de `timepulse.py`**

`httpx.get` n'accepte ni `transport` ni `event_hooks` (signature vérifiée sur
httpx 0.28.1) : ces deux appels passent en `Client`. Remplacer les fonctions
`_fetch_xml` et `_fetch_event_page` (lignes 75-98) par :

```python
def _fetch_xml(id_event: str) -> str:
    with http.client(timeout=20, headers=_HEADERS) as client:
        for tpl in _DATA_API_URLS:
            try:
                r = client.get(tpl.format(id_event=id_event))
                if r.status_code == 200 and "<Epreuve" in r.text:
                    return r.text
            except httpx.HTTPError:
                continue
    return ""


def _fetch_event_page(id_event: str) -> str:
    """HTML de la page publique de l'épreuve (dernier recours pour la date)."""
    try:
        with http.client(timeout=20, headers=_HEADERS) as client:
            r = client.get(f"https://www.timepulse.fr/epreuves/resultats/{id_event}")
        return r.text if r.status_code == 200 else ""
    except httpx.HTTPError:
        return ""
```

Le `except httpx.HTTPError` est **conservé tel quel** et n'attrape pas
`BlockedTargetError` (une `DomainError`) : une destination refusée interrompt la
boucle des gabarits d'URL au lieu de la poursuivre en silence. C'est voulu — un
refus de destination est un fait à remonter, pas un gabarit qui ne marche pas.
Ajouter `from app.core import http` aux imports ; **garder** `import httpx`,
encore utilisé pour `httpx.HTTPError`.

- [ ] **Step 6 : migrer les deux sites de `services/`**

`app/services/sheet_source.py` — retirer `import httpx` (ligne 10), ajouter
`from app.core import http`, et remplacer `download_csv` :

```python
def download_csv(url: str) -> str:
    """Télécharge le CSV public du Sheet (sans auth).

    L'export d'un Google Sheet redirige vers `googleusercontent.com`, un autre
    domaine : c'est le cas qui a fait écarter l'allowlist de hosts par provider
    au profit de la politique par classe d'IP (#101).
    """
    with http.client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
```

`app/services/geocode_service.py` — retirer `import httpx` (ligne 11), ajouter
`from app.core import http`, et remplacer l'appel des lignes 47-51 :

```python
        with http.client(timeout=5) as client:
            r = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 5, "countrycodes": "fr"},
                headers={"User-Agent": settings.geocode_user_agent},
            )
```

Le `except Exception` de la ligne 62 avalerait une `BlockedTargetError` et le
géocodage rendrait `None` — acceptable : la cible est un host fixe de
configuration, et le géocodage est déjà au mieux-effort (il journalise en
`warning`).

- [ ] **Step 7 : lancer le méta-test et la suite complète**

Run: `uv run pytest tests/test_core_http.py -v`
Expected: PASS, méta-test compris (`fautifs == []`).

Run: `uv run pytest -m "not integration" -q`
Expected: PASS — **le même nombre de tests qu'à l'étape 6 de la tâche 1, sans
qu'un seul fichier de test existant ait été modifié**. C'est le critère de
non-régression du design. Si un test échoue, ne pas le modifier : la fabrique
diverge du comportement d'origine, c'est elle qu'il faut corriger.

Run: `uv run ruff check .`
Expected: aucune erreur — en particulier aucun `F401` sur `import httpx`.

- [ ] **Step 8 : commit**

```bash
git add backend/app backend/tests/test_core_http.py
git commit -m "fix(scrapers): passer les 18 sorties HTTP par le garde de destination (#101)"
```

---

### Task 3 : documenter la convention et vérifier en réseau réel

**Files:**
- Modify: `AGENTS.md` (section « Conventions scrapers »)
- Test: `backend/tests/test_integration_scrapers.py` (exécution seule, sans modification)

**Interfaces:**
- Consumes: l'invariant de la tâche 2.
- Produces: aucune interface de code.

- [ ] **Step 1 : documenter la convention dans `AGENTS.md`**

Dans la section « Conventions scrapers », ajouter après la puce « Détection par
host, jamais par sous-chaîne d'URL » :

```markdown
- **Toute sortie HTTP passe par `app/core/http.client()`**, jamais par
  `httpx.Client(...)` ni `httpx.get(...)` nus. La fabrique enveloppe le
  transport d'un garde qui refuse toute destination non publiquement routable
  (`not ip.is_global`), sur la requête initiale **et sur chaque saut de
  redirection** : #49 avait fermé le routage, un `302 → http://169.254.169.254/`
  restait ouvert (#101). Un méta-test refuse tout `httpx` nu dans `app/`. Deux
  conséquences à connaître : le refus lève `BlockedTargetError`, qui ne dérive
  pas de `ValueError` (sinon `import_service` la classerait en « fournisseur non
  supporté ») ; et une redirection vers un **autre domaine** reste autorisée —
  l'export CSV du Google Sheet en dépend. Design :
  `docs/superpowers/specs/2026-07-31-ssrf-redirection-design.md`.
```

- [ ] **Step 2 : vérifier en réseau réel**

Run: `uv run pytest -m integration -q`
Expected: PASS. C'est la **seule** vérification des redirections légitimes en
conditions réelles — le panel mock ne couvre que les cas construits.

Si une épreuve échoue en `BlockedTargetError`, ne pas désarmer le garde :
relever le host et ses adresses (`uv run python -c "import socket; print(socket.getaddrinfo('<host>', 443))"`),
puis reporter le cas ici — un fournisseur réel qui résoudrait vers une adresse
non globale serait un fait nouveau, absent du panel de 14 hosts / 24 adresses
mesuré au design.

Si des épreuves échouent pour une raison **étrangère** au garde (site en panne,
épreuve dépubliée), le noter dans le message de commit : les tests d'intégration
tapent des sites tiers et sont sujets à des échecs qui ne nous appartiennent pas.

- [ ] **Step 3 : vérification finale**

Run: `uv run pytest -m "not integration" -q && uv run ruff check .`
Expected: PASS, aucune erreur de lint.

- [ ] **Step 4 : commit**

```bash
git add AGENTS.md
git commit -m "docs: convention de sortie HTTP unique via le garde de destination (#101)"
```

---

## Ce que ce plan ne fait pas

- **L'épinglage de l'IP validée** (fermeture du rebinding DNS) — écarté au
  design : touche au SNI et à la vérification de certificat.
- **`playwright_fallback.py`**, code mort — ticket propre, déjà signalé par le
  design de #49.
- **`tests/test_integration_scrapers.py:336`**, qui construit son propre
  `httpx.Client` — c'est un test, pas du code de `app/` : le méta-test ne le
  regarde pas, et le faire passer par le garde masquerait ce qu'il mesure.
