# Correctif SSRF — détection de provider par host — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fermer le SSRF de `POST /api/v1/scrape/event` en routant les providers sur le **host** de l'URL et non sur une sous-chaîne de l'URL entière, et en validant le schéma d'entrée.

**Architecture:** Une fonction libre `_host_match(url, hosts)` dans `registry.py` porte l'unique définition de « host exact ou vrai sous-domaine » ; une classe de base `HostMatchedProvider` en fait le comportement par défaut de tout provider, de sorte qu'il n'y ait plus de `matches` à écrire — donc plus de `in url` à réintroduire. La validation d'entrée est posée à deux niveaux : `HttpUrl` sur `ScrapeRequest` (porte de l'API) et un `_validate_url` durci dans `import_service` (passage obligé de l'API, du SSE et des deux commandes CLI de batch).

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic v2, pytest, ruff.

**Spec :** `docs/superpowers/specs/2026-07-26-ssrf-detection-par-host-design.md`
**Issue :** [#49](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/49)

## Global Constraints

- Toutes les commandes se lancent **depuis `backend/`**, préfixées de `uv run` (aucun venv à activer).
- Tests unitaires **sans réseau** : `uv run pytest -m "not integration"`. Ne jamais lancer `-m integration` dans ce plan (URLs réelles, hors CI).
- Lint : `uv run ruff check .` doit passer. `line-length = 100`, règles `E, F, I, W, UP, B`.
- Langue : commentaires, docstrings et messages en **français avec accents**.
- Commits : Conventional Commits (`fix:`, `test:`, `docs:`…).
- **Ne pas** implémenter le point 3 de l'issue (whitelist explicite avant scrape) : écarté par le design, remplacé par le verrou de la Task 3.
- **Ne pas** toucher à `GET /scrape/detect` (aucune requête sortante) ni à `app/scrapers/playwright_fallback.py` (code mort, ticket de suivi séparé).
- **Ne pas** toucher aux `follow_redirects=True` des scrapers : résidu documenté, hors périmètre.

## Fichiers touchés

| Fichier | Responsabilité après le correctif |
| --- | --- |
| `app/scrapers/registry.py` | Ajoute `_host_match` + `HostMatchedProvider` ; les 8 providers passent à la détection par host. |
| `app/services/import_service.py` | `_validate_url` exige un schéma `http`/`https` **et** un host. |
| `app/schemas/scrape.py` | `ScrapeRequest.url` passe de `str` à `HttpUrl`. |
| `app/api/v1/scrape.py` | Les deux routers passent `str(body.url)` au service. |
| `tests/test_registry.py` | Tests du helper, de la classe de base, du routage et des contournements. |
| `tests/test_services/test_import_service.py` | Tests de `_validate_url`. |
| `tests/test_api/test_scrape_api.py` | Rejet 422 d'un schéma non-http à la porte de l'API. |
| `AGENTS.md` | La convention « détection par host » rejoint les conventions scrapers. |

---

### Task 1: Le helper `_host_match` et la classe de base `HostMatchedProvider`

Cette task ajoute la règle et son support **sans encore l'appliquer** aux providers : le comportement de l'application est inchangé à la fin. La Task 2 fait la bascule.

**Files:**
- Modify: `backend/app/scrapers/registry.py` (ajout après les imports, avant `class KlikegoProvider`)
- Test: `backend/tests/test_registry.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `_host_match(url: str, hosts: tuple[str, ...]) -> bool` — vrai si le host de `url` est exactement l'un de `hosts` ou un vrai sous-domaine de l'un d'eux.
  - `class HostMatchedProvider` avec l'attribut de classe `_HOSTS: tuple[str, ...] = ()` et la méthode `matches(self, url: str) -> bool`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_registry.py` :

```python
# ---------------------------------------------------------------------------
# Détection par host — la règle unique (issue #49)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://timepulse.fr/resultats/3090",                 # domaine exact
    "https://www.timepulse.fr/resultats/3090",             # sous-domaine
    "https://a.b.timepulse.fr/resultats/3090",             # sous-domaine profond
    "https://www.timepulse.fr:443/resultats/3090",         # port explicite
    "https://WWW.TIMEPULSE.FR/resultats/3090",             # casse
    "https://operateur@www.timepulse.fr/resultats/3090",   # credentials
])
def test_host_match_accepte_le_domaine_et_ses_sous_domaines(url):
    assert registry._host_match(url, ("timepulse.fr",)) is True


@pytest.mark.parametrize("url", [
    # Suffixe sans point : c'est tout l'intérêt du `.` dans la règle.
    "https://evil-timepulse.fr/resultats",
    # Le jeton est un sous-domaine d'un parent hostile.
    "https://timepulse.fr.attaquant.net/resultats",
    # Sous-chaîne en query — le vecteur exact de l'issue #49.
    "https://169.254.169.254/latest/meta-data/?x=timepulse.fr",
    # Sous-chaîne en path.
    "https://evil.example/timepulse.fr/resultats",
    # Sous-chaîne en fragment.
    "https://evil.example/resultats#timepulse.fr",
    # Confusion userinfo : le host réel est l'IP, pas le jeton avant le `@`.
    "https://timepulse.fr@169.254.169.254/latest/meta-data/",
    # Entrées dégradées : pas d'exception, pas de match.
    "pas-une-url",
    "",
])
def test_host_match_rejette_les_contournements(url):
    assert registry._host_match(url, ("timepulse.fr",)) is False


def test_host_match_accepte_plusieurs_hosts():
    hosts = ("raceresult.com", "chronoconsult.fr")
    assert registry._host_match("https://my3.raceresult.com/1/results", hosts) is True
    assert registry._host_match("https://www.chronoconsult.fr/result/x/", hosts) is True
    assert registry._host_match("https://exemple-inconnu.fr/x", hosts) is False


def test_host_matched_provider_derive_matches_de_ses_hosts():
    """Un provider qui hérite n'a pas de `matches` à écrire — donc pas de
    `in url` à réintroduire par mégarde (cf. #76)."""

    class _Faux(registry.HostMatchedProvider):
        name = "chronofictif"
        _HOSTS = ("exemple.fr", "exemple.com")

    provider = _Faux()

    assert provider.matches("https://www.exemple.fr/resultats") is True
    assert provider.matches("https://exemple.com/resultats") is True
    assert provider.matches("https://evil-exemple.fr/resultats") is False


def test_host_matched_provider_sans_hosts_ne_matche_rien():
    """Défaut sûr : un provider qui oublie `_HOSTS` ne capte rien, il ne capte pas tout."""

    class _Vide(registry.HostMatchedProvider):
        name = "vide"

    assert _Vide().matches("https://exemple.fr/resultats") is False
```

Le fichier n'importe aujourd'hui que `registry`. Ajouter `import pytest` **en tête**, avant l'import first-party (ordre isort : tiers, ligne vide, `app`) :

```python
import pytest

from app.scrapers import registry
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL — `AttributeError: module 'app.scrapers.registry' has no attribute '_host_match'` (et idem pour `HostMatchedProvider`).

- [ ] **Step 3: Écrire l'implémentation minimale**

Dans `backend/app/scrapers/registry.py`, insérer juste après `logger = logging.getLogger(__name__)` et avant `@runtime_checkable` :

```python
def _host_match(url: str, hosts: tuple[str, ...]) -> bool:
    """Vrai si le host de `url` est l'un de `hosts`, ou un vrai sous-domaine.

    `hostname` et non `netloc` : sans lui, un port explicite
    (`my.raceresult.com:443`) ou des credentials feraient rater le match — et
    `hostname` est déjà en minuscules, il isole aussi le host réel d'une URL
    du type `https://timepulse.fr@169.254.169.254/`.

    Le point compte : `endswith("timepulse.fr")` nu suivrait aussi
    `evil-timepulse.fr`. Ne **jamais** revenir à un test de sous-chaîne sur
    l'URL entière — c'était le SSRF de l'issue #49, le jeton suffisait en query.
    """
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith(f".{h}") for h in hosts)
```

Puis, juste après le bloc `class ScraperProtocol` (et avant `class KlikegoProvider`) :

```python
class HostMatchedProvider:
    """Détection par host, comportement par défaut de tout provider.

    Un provider n'a plus qu'à déclarer `_HOSTS` : il n'y a pas de `matches` à
    écrire, donc pas de `in url` à réintroduire au prochain fournisseur ajouté.
    Un provider dont la condition ne se réduit pas à une liste de hosts
    (cf. `WiclaxProvider`) surcharge `matches` et compose sur `_host_match` —
    jamais sur une copie de la règle.
    """

    #: Hosts servis par ce provider. Allowlist explicite : détecter le moteur
    #: par le contenu obligerait à télécharger la page de toute URL inconnue
    #: avant de savoir la traiter.
    _HOSTS: tuple[str, ...] = ()

    def matches(self, url: str) -> bool:
        return _host_match(url, self._HOSTS)
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (tous, y compris les 3 tests préexistants sur `provider_names`).

- [ ] **Step 5: Lancer le lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add backend/app/scrapers/registry.py backend/tests/test_registry.py
git commit -m "feat(scrapers): règle unique de détection par host (#49)"
```

---

### Task 2: Basculer les 8 providers sur la détection par host

C'est la task qui ferme le SSRF. Elle porte aussi la mise à jour de la convention dans `AGENTS.md`, parce que c'est ici que la convention devient réelle.

**Files:**
- Modify: `backend/app/scrapers/registry.py:49-183` (les 8 classes de provider)
- Modify: `AGENTS.md` (section « Conventions scrapers »)
- Test: `backend/tests/test_registry.py`

**Interfaces:**
- Consumes: `_host_match(url, hosts)` et `HostMatchedProvider` (Task 1).
- Produces: `registry.detect_provider(url)` renvoie `"playwright"` pour toute URL dont le **host** n'est servi par aucun provider, quelle que soit la sous-chaîne présente ailleurs dans l'URL.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_registry.py` :

```python
# ---------------------------------------------------------------------------
# Routage : ce qui doit continuer à marcher, et ce qui ne doit plus passer
# ---------------------------------------------------------------------------

#: URLs légitimes, une ou plusieurs par façade réellement supportée.
_ROUTAGE_LEGITIME = [
    ("klikego", "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4"),
    ("klikego", "https://klikego.com/resultats/x/1674523163798-4"),
    ("breizhchrono",
     "https://resultats.breizhchrono.com/resultats-courses/triathlon-x-129540519-19/triathlon-m"),
    ("breizhchrono",
     "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488071608761-688"),
    ("wiclax", "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/"),
    ("wiclax", "https://www.chronosmetron.com/resultats/"),
    ("wiclax", "https://chronowest.fr/trail-des-2-ponts-2026/"),
    ("wiclax", "https://x.wiclax.com/G-Live/g-live.html?f=../E/e.clax"),
    ("timepulse", "https://www.timepulse.fr/epreuves/resultats/3232"),
    ("prolivesport", "https://www.prolivesport.fr/result/1082/6"),
    ("sportinnovation", "https://sportinnovation.fr/Evenements/Resultats/7031"),
    ("raceresult", "https://my3.raceresult.com/393893/results"),
    ("raceresult", "https://my.raceresult.com:443/399938/results"),
    ("raceresult", "https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/"),
    ("raceresult", "https://www.espace-competition.com/result/x/"),
    ("chronoplace", "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494"),
]


@pytest.mark.parametrize("provider, url", _ROUTAGE_LEGITIME)
def test_routage_des_urls_legitimes_inchange(provider, url):
    """Non-régression : le passage au host ne doit perdre aucune façade servie."""
    assert registry.detect_provider(url) == provider


#: Tous les jetons de host qu'un provider reconnaît, et le provider visé.
_JETONS_PROVIDERS = [
    "klikego.com",
    "breizhchrono.com",
    "timepulse.fr",
    "prolivesport.fr",
    "sportinnovation.fr",
    "raceresult.com",
    "espace-competition.com",
    "chronoconsult.fr",
    "chronoplace.fr",
    "wiclax.com",
    "wiclax-results.com",
    "chronosmetron.com",
    "chronowest.fr",
]

#: Les quatre familles de contournement de l'issue #49, plus la confusion userinfo.
_GABARITS_CONTOURNEMENT = [
    "https://169.254.169.254/latest/meta-data/?x={jeton}",   # sous-chaîne en query
    "https://evil.example/{jeton}/resultats",                # sous-chaîne en path
    "https://evil.example/resultats#{jeton}",                # sous-chaîne en fragment
    "https://evil-{jeton}/resultats",                        # host sosie, suffixe sans point
    "https://{jeton}.attaquant.net/resultats",               # jeton en sous-domaine hostile
    "https://{jeton}@169.254.169.254/latest/meta-data/",     # confusion userinfo
]


@pytest.mark.parametrize("jeton", _JETONS_PROVIDERS)
@pytest.mark.parametrize("gabarit", _GABARITS_CONTOURNEMENT)
def test_aucun_contournement_ne_route_vers_un_provider(gabarit, jeton):
    """SSRF #49 : une URL dont le host n'est pas servi tombe sur le fallback,
    qui lève avant toute requête réseau — quelle que soit la sous-chaîne."""
    url = gabarit.format(jeton=jeton)
    assert registry.detect_provider(url) == "playwright", url


def test_url_klikego_portant_un_jeton_timepulse_reste_klikego():
    """Hors sécurité : le point 1 fiabilise aussi la détection (note de l'issue #49).
    Aujourd'hui cette URL part chez TimePulse, qui n'en fera rien."""
    url = (
        "https://www.klikego.com/resultats/triathlon-x/1674523163798-4"
        "?retour=https%3A%2F%2Fwww.timepulse.fr%2Fresultats%2F1"
    )
    assert registry.detect_provider(url) == "klikego"


def test_wiclax_ne_capte_pas_le_site_vitrine_sans_chemin_g_live():
    """`wiclax.com` est le site de l'éditeur : seuls les chemins G-Live sont
    des pages de résultats. La condition de chemin doit survivre à la bascule."""
    assert registry.detect_provider("https://www.wiclax.com/tarifs") == "playwright"


@pytest.mark.parametrize("url", [
    "https://evil-wiclax.com/G-Live/g-live.html?f=../E/e.clax",
    "https://wiclax.com.attaquant.net/G-Live/g-live.html",
])
def test_wiclax_sosie_avec_chemin_g_live_non_capte(url):
    """Le seul contournement Wiclax réellement ouvert : `endswith("wiclax.com")`
    sans point suit `evil-wiclax.com`, et le chemin G-Live lève la seconde
    condition. Les gabarits génériques ne l'atteignent pas — leur path n'a pas
    de `G-Live` —, d'où ce cas dédié."""
    assert registry.detect_provider(url) == "playwright"
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_registry.py -v`
Expected: **32 échecs exactement**, tous attendus :

- `test_aucun_contournement_ne_route_vers_un_provider` — **30 cas** : les 6 gabarits × les 5 jetons des providers détectés en sous-chaîne (`klikego.com`, `breizhchrono.com`, `timepulse.fr`, `prolivesport.fr`, `sportinnovation.fr`). Les 8 autres jetons passent déjà : leurs providers (raceresult, chronoplace, et les `_HOSTS` de wiclax) comparaient déjà sur le host.
- `test_url_klikego_portant_un_jeton_timepulse_reste_klikego` — **1 cas**, l'URL part chez TimePulse.
- `test_wiclax_sosie_avec_chemin_g_live_non_capte` — **1 cas** : `evil-wiclax.com` (le second, `wiclax.com.attaquant.net`, passe déjà — il ne suffixe pas `wiclax.com`).

`test_routage_des_urls_legitimes_inchange` et `test_wiclax_ne_capte_pas_le_site_vitrine_sans_chemin_g_live` passent dès le départ : ce sont des verrous de non-régression.

Un compte différent de 32 signale une erreur de recopie des tests — la vérifier avant d'implémenter.

- [ ] **Step 3: Écrire l'implémentation**

Dans `backend/app/scrapers/registry.py`, remplacer les 8 classes de provider. Chacune hérite désormais de `HostMatchedProvider` et déclare `_HOSTS` ; seules les méthodes `scrape_event_all` gardent leur corps actuel, **inchangé**.

`KlikegoProvider` — supprimer `matches`, ajouter `_HOSTS`, garder `scrape_event_all` tel quel :

```python
class KlikegoProvider(HostMatchedProvider):
    name = "klikego"
    _HOSTS = ("klikego.com",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        # … corps actuel inchangé (lignes 55-71) …
```

`BreizhChronoProvider` — idem, `matches` supprimé :

```python
class BreizhChronoProvider(HostMatchedProvider):
    name = "breizhchrono"
    _HOSTS = ("breizhchrono.com",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        # … corps actuel inchangé (lignes 80-99) …
```

`WiclaxProvider` — seul provider à surcharger `matches`, parce que `wiclax.com` demande une condition de chemin et ne peut donc pas entrer dans `_HOSTS` :

```python
class WiclaxProvider(HostMatchedProvider):
    name = "wiclax"

    # Hosts servant un moteur G-Live. `chronowest.fr` : WordPress + iframe
    # G-Live (issue #35).
    _HOSTS = ("wiclax-results.com", "chronosmetron.com", "chronowest.fr")

    def matches(self, url: str) -> bool:
        # `wiclax.com` est le site vitrine de l'éditeur : il n'est pas dans
        # `_HOSTS`, seuls ses chemins G-Live sont des pages de résultats. D'où
        # la composition sur `_host_match` — surtout pas une copie de la règle.
        parsed = urlparse(url)
        return super().matches(url) or (
            _host_match(url, ("wiclax.com",)) and "G-Live" in (parsed.path or "")
        )

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return wiclax.scrape_event_all(url)
```

`TimePulseProvider`, `ProLiveSportProvider`, `SportInnovationProvider` :

```python
class TimePulseProvider(HostMatchedProvider):
    name = "timepulse"
    _HOSTS = ("timepulse.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return timepulse.scrape_event_all(url)


class ProLiveSportProvider(HostMatchedProvider):
    name = "prolivesport"
    _HOSTS = ("prolivesport.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return prolivesport.scrape_event_all(url)


class SportInnovationProvider(HostMatchedProvider):
    name = "sportinnovation"
    _HOSTS = ("sportinnovation.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return sportinnovation.scrape_event_all(url)
```

`RaceResultProvider` et `ChronoplaceProvider` — ils portaient chacun leur copie correcte de la règle ; elles disparaissent au profit de la définition commune :

```python
class RaceResultProvider(HostMatchedProvider):
    name = "raceresult"

    # Trois façades d'un même produit RaceResult (issue #50), toutes servies
    # par la même API JSON publique.
    _HOSTS = ("raceresult.com", "espace-competition.com", "chronoconsult.fr")

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return raceresult.scrape_event_all(url)


class ChronoplaceProvider(HostMatchedProvider):
    name = "chronoplace"
    _HOSTS = ("chronoplace.fr",)

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return chronoplace.scrape_event_all(url)
```

`PlaywrightProvider` est **inchangé** : il n'hérite pas (son `matches` renvoie `True` par construction, c'est le fallback).

Enfin, mettre à jour la docstring du module (`registry.py:1-14`) en ajoutant après la ligne « Provider inconnu → fallback Playwright. » :

```
La détection se fait sur le **host** de l'URL, jamais sur une sous-chaîne de
l'URL entière : un jeton en query suffisait à router n'importe quelle URL vers
un scraper, qui la requêtait telle quelle (SSRF, issue #49). La règle est dans
`_host_match`, appliquée par défaut via `HostMatchedProvider`.
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Lancer toute la suite unitaire (non-régression du routage)**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS — en particulier `tests/test_wiclax.py`, `tests/test_raceresult.py`, `tests/test_chronoplace.py` et `tests/test_breizhchrono.py`, qui portent déjà des tests de détection sur des hosts réels.

- [ ] **Step 6: Documenter la convention dans `AGENTS.md`**

Dans la section « Conventions scrapers », après la puce « Tout nouveau fournisseur : … », insérer :

```markdown
- **Détection par host, jamais par sous-chaîne d'URL.** Un provider déclare ses
  `_HOSTS` et hérite de `HostMatchedProvider` : il n'a pas de `matches` à
  écrire. La règle « host exact ou vrai sous-domaine » a une seule définition,
  `registry._host_match`. Un `"exemple.fr" in url` route n'importe quelle URL
  portant le jeton en query vers le scraper, qui la requête telle quelle —
  c'était le SSRF de #49. Un provider dont la condition ne se réduit pas à une
  liste de hosts (Wiclax : `wiclax.com` n'est une page de résultats que sur un
  chemin G-Live) surcharge `matches` et **compose** sur `_host_match`.
```

- [ ] **Step 7: Lancer le lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add backend/app/scrapers/registry.py backend/tests/test_registry.py AGENTS.md
git commit -m "fix(security): route les providers sur le host, plus sur une sous-chaîne d'URL (#49)"
```

---

### Task 3: Verrou — un host non reconnu ne déclenche aucune requête

Ce test tient lieu du point 3 de l'issue (« whitelist explicite comme filet »), écarté par le design : le refus existe déjà via `PlaywrightProvider`, on le **verrouille** plutôt que de le dupliquer.

**Files:**
- Test: `backend/tests/test_registry.py`

**Interfaces:**
- Consumes: `registry.scrape_event_all(url)` (comportement de la Task 2).
- Produces: rien (task de test pur).

- [ ] **Step 1: Écrire le test**

Ajouter à la fin de `backend/tests/test_registry.py` :

```python
# ---------------------------------------------------------------------------
# Verrou : le fallback refuse AVANT le réseau (tient lieu du point 3 de #49)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://169.254.169.254/latest/meta-data/?x=timepulse.fr",
    "https://127.0.0.1:8001/api/v1/admin?x=prolivesport.fr",
    "https://evil.example/breizhchrono.com/resultats",
])
def test_host_non_reconnu_ne_declenche_aucune_requete(monkeypatch, url):
    """Le fallback Playwright lève avant tout réseau : c'est ce qui rend une
    whitelist explicite superflue. Si quelqu'un rebranche un scraper générique
    sur le fallback, ce test tombe."""
    import httpx

    def _interdit(*args, **kwargs):
        raise AssertionError(f"requête réseau émise pour un host non reconnu : {url}")

    monkeypatch.setattr(httpx.Client, "request", _interdit)
    monkeypatch.setattr(httpx.Client, "send", _interdit)

    with pytest.raises(ValueError, match="playwright"):
        registry.scrape_event_all(url)
```

- [ ] **Step 2: Lancer le test**

Run: `uv run pytest tests/test_registry.py::test_host_non_reconnu_ne_declenche_aucune_requete -v`
Expected: PASS immédiatement — la Task 2 a déjà produit ce comportement. Ce test **verrouille** un acquis, il ne pilote pas de code neuf ; c'est le seul de ce plan dans ce cas, et c'est délibéré.

Si le test échoue avec `AssertionError: requête réseau émise…`, c'est que la Task 2 est incomplète : un provider capte encore l'une de ces URLs. Reprendre la Task 2 avant de continuer.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_registry.py
git commit -m "test(scrapers): verrouille l'absence de requête sur un host non reconnu (#49)"
```

---

### Task 4: Durcir `_validate_url` (le passage obligé de tous les imports)

`ScrapeRequest` ne couvre que deux des chemins d'import. `_validate_url` est traversé par l'API, le SSE et les deux commandes CLI de batch — c'est la seule garde du batch, qui n'a aucun schéma Pydantic.

**Files:**
- Modify: `backend/app/services/import_service.py:45-49`
- Test: `backend/tests/test_services/test_import_service.py`

**Interfaces:**
- Consumes: `InvalidUrlError` (déjà importé, `import_service.py:16`).
- Produces: `_validate_url(url: str) -> str` lève `InvalidUrlError` si le schéma n'est pas `http`/`https` ou si le host est vide ; renvoie l'URL *strippée*, sans autre réécriture.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_services/test_import_service.py` :

```python
# ---------------------------------------------------------------------------
# Validation d'URL — seule garde du batch CLI, qui n'a pas de schéma Pydantic (#49)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://www.klikego.com/resultats/x/1",
    "http://www.timepulse.fr/resultats/3090",
    "  https://www.klikego.com/resultats/x/1  ",   # espaces tolérés
])
def test_validate_url_accepte_http_et_https(url):
    from app.services.import_service import _validate_url

    assert _validate_url(url) == url.strip()


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://169.254.169.254/",
    "ftp://interne.local/",
    "javascript:alert(1)",
    "httpfoo://exemple.fr/",   # `startswith('http')` laissait passer ceci
    "https:///resultats",      # schéma correct, host vide
    "/resultats/x/1",          # relatif : aucun host
    "pas-une-url",
    "",
    None,
])
def test_validate_url_refuse_tout_le_reste(url):
    from app.core.exceptions import InvalidUrlError
    from app.services.import_service import _validate_url

    with pytest.raises(InvalidUrlError):
        _validate_url(url)


def test_validate_url_ne_reecrit_pas_l_url():
    """`source_url` est la clé du cache TTL : une réécriture ici la ferait dériver."""
    from app.services.import_service import _validate_url

    url = "https://www.prolivesport.fr/index.php?chap=event&race=Triathlon%20M"
    assert _validate_url(url) == url
```

`import pytest` est déjà présent en tête de ce fichier (ligne 4) — rien à ajouter.

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_services/test_import_service.py -v -k validate_url`
Expected: FAIL sur `httpfoo://exemple.fr/`, `https:///resultats` et `/resultats/x/1` — `startswith("http")` les accepte aujourd'hui. Les autres cas passent déjà.

- [ ] **Step 3: Écrire l'implémentation**

Dans `backend/app/services/import_service.py`, ajouter l'import en tête (après `from dataclasses import dataclass`) :

```python
from urllib.parse import urlparse
```

Puis remplacer `_validate_url` (lignes 45-49) par :

```python
def _validate_url(url: str) -> str:
    """Refuse tout ce qui n'est pas une URL http(s) nommant un host.

    Passage obligé de **tous** les chemins d'import — API, SSE, CLI
    `import-sheet` et `rescrape-db` — et donc la seule garde du batch, qui n'a
    aucun schéma Pydantic devant lui. L'ancien `startswith("http")` laissait
    passer `httpfoo://` comme une URL sans host (#49).

    Ne réécrit rien au-delà du strip : `source_url` est la clé du cache TTL.
    """
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise InvalidUrlError()
    return url
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_services/test_import_service.py -v`
Expected: PASS (les nouveaux et tous les préexistants).

- [ ] **Step 5: Lancer toute la suite unitaire**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS — surveiller `tests/test_cli/` et `tests/test_services/test_batch*.py`, qui traversent `iter_import_event`.

- [ ] **Step 6: Lancer le lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/import_service.py backend/tests/test_services/test_import_service.py
git commit -m "fix(security): exige un schéma http(s) et un host dans _validate_url (#49)"
```

---

### Task 5: `ScrapeRequest.url` en `HttpUrl` (rejet à la porte de l'API)

**Files:**
- Modify: `backend/app/schemas/scrape.py:1-6`
- Modify: `backend/app/api/v1/scrape.py:40` et `:51`
- Test: `backend/tests/test_api/test_scrape_api.py`

**Interfaces:**
- Consumes: `_validate_url` durci (Task 4) — le second niveau reste en place, il couvre la CLI.
- Produces: `ScrapeRequest.url: HttpUrl`. Les appelants du schéma doivent passer `str(body.url)` aux services, qui attendent un `str`.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter `import pytest` **en tête** de `backend/tests/test_api/test_scrape_api.py`, avec les imports existants (`import json`, `from datetime import date`) — pas en fin de fichier, ruff a `E402` actif :

```python
import json
from datetime import date

import pytest

from app.scrapers.base import ScrapedResult
```

Puis ajouter les tests à la fin du fichier :

```python
@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://169.254.169.254/",
    "javascript:alert(1)",
    "pas-une-url",
    "",
])
@pytest.mark.parametrize("route", ["/api/v1/scrape/event", "/api/v1/scrape/event/stream"])
def test_schema_non_http_rejete_a_la_porte(client, route, url):
    """422 de Pydantic, avant d'atteindre le service : le schéma d'entrée est
    la première garde des deux endpoints d'import (#49)."""
    resp = client.post(route, json={"url": url})
    assert resp.status_code == 422


def test_url_http_valide_toujours_acceptee(client, monkeypatch):
    """Non-régression : `HttpUrl` ne doit refuser aucune URL de chronométrage réelle."""
    from app.services import import_service

    vues: list[str] = []

    def fake_scrape(url):
        vues.append(url)
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)

    url = "https://www.prolivesport.fr/index.php?chap=event&eventId=979&race=Triathlon%20M"
    resp = client.post("/api/v1/scrape/event", json={"url": url})

    assert resp.status_code == 200
    # Le service reçoit bien une `str`, pas un objet `HttpUrl`, et l'URL n'a pas
    # été réécrite : `source_url` est la clé du cache TTL.
    assert vues == [url]
    assert isinstance(vues[0], str)
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `uv run pytest tests/test_api/test_scrape_api.py -v`
Expected: FAIL — `test_schema_non_http_rejete_a_la_porte` renvoie 400 (via `InvalidUrlError`) ou 200 au lieu de 422, et `test_url_http_valide_toujours_acceptee` échoue sur `isinstance(vues[0], str)` seulement après le Step 3 s'il est mal fait.

- [ ] **Step 3: Écrire l'implémentation**

`backend/app/schemas/scrape.py` :

```python
"""Schémas Pydantic pour le scraping (requête d'import + résultat)."""
from pydantic import BaseModel, HttpUrl


class ScrapeRequest(BaseModel):
    #: `HttpUrl` et non `str` : rejette `file://`, `gopher://`, `javascript:` et
    #: les URLs sans host dès la porte de l'API, en 422 (#49). Mesuré sur nos
    #: URLs de chronométrage : il ne réécrit que le host en minuscules et
    #: n'ajoute un `/` final qu'à un domaine nu — aucune n'est dans ce cas, la
    #: clé de cache `source_url` ne dérive pas.
    #: Il ne dispense pas de `import_service._validate_url`, qui couvre la CLI.
    url: HttpUrl


class ImportResult(BaseModel):
    imported: int
    updated: int = 0
    skipped: int
    cached: bool = False
```

`backend/app/api/v1/scrape.py` — deux appels à ajuster, les services attendent une `str` :

Ligne 40 :
```python
    return import_service.import_event(db, str(body.url), settings)
```

Ligne 51 :
```python
            for event in import_service.iter_import_event(db, str(body.url), settings):
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `uv run pytest tests/test_api/test_scrape_api.py -v`
Expected: PASS (les nouveaux et les 4 préexistants).

- [ ] **Step 5: Lancer toute la suite unitaire**

Run: `uv run pytest -m "not integration" -q`
Expected: PASS.

- [ ] **Step 6: Lancer le lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/scrape.py backend/app/api/v1/scrape.py backend/tests/test_api/test_scrape_api.py
git commit -m "fix(security): valide ScrapeRequest.url en HttpUrl (#49)"
```

---

## Vérification finale

- [ ] `uv run pytest -m "not integration" -q` — toute la suite verte (≈745 tests préexistants + ~143 nouveaux cas, paramétrage déplié : 17 en Task 1, 98 en Task 2, 3 en Task 3, 14 en Task 4, 11 en Task 5).
- [ ] `uv run ruff check .` — `All checks passed!`
- [ ] Relire `git log --oneline main..` — 5 commits, un par task.
- [ ] Vérifier à la main que le vecteur de l'issue est fermé :

```bash
uv run python -c "
from app.scrapers import registry
u = 'https://169.254.169.254/latest/meta-data/?x=timepulse.fr'
print(registry.detect_provider(u))   # attendu : playwright
"
```

## Suites à ouvrir après la PR

Deux tickets, documentés en fin de spec, volontairement hors de ce plan :

1. **SSRF par redirection** — les 8 scrapers, `sheet_source` et l'auto-détection de heat de `registry.py` sont en `follow_redirects=True` (13 sites d'appel sur 10 modules). Un host provider qui répondrait `302 → http://169.254.169.254/` ferait toujours partir la requête.
2. **`app/scrapers/playwright_fallback.py`, code mort** — aucun import dans `app/` ni `tests/`. C'est le seul module capable de naviguer vers une URL arbitraire.
