# Support `chronowest.fr` (Wiclax / G-Live) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconnaître `chronowest.fr` comme déploiement Wiclax/G-Live et généraliser la chaîne de résolution « page → iframe G-Live → `.clax` » pour qu'elle soit indépendante de l'hébergeur.

**Architecture:** Le parseur `.clax` n'est **pas** touché — il parse déjà ChronoWest de bout en bout (vérifié : 415 participants sur le Trail des 2 Ponts, 162 sur le RED OUF Swimrun). Tout le travail est dans la **résolution d'URL** de `wiclax.py` : on extrait la chaîne de résolution en helpers **purs** (`html + url → url`), testables sans réseau, et on remplace les regex HTML par BeautifulSoup. Le registre gagne un host.

**Tech Stack:** Python 3.11+, httpx, BeautifulSoup (`lxml`), pytest, ruff.

**Spec :** `docs/superpowers/specs/2026-07-12-chronowest-wiclax-design.md`
**Issue :** [#35](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/35)

## Global Constraints

- Toutes les commandes s'exécutent depuis `backend/`, venv activé (`backend/.venv`).
- Tests unitaires **sans réseau**. Le réseau réel vit derrière le marker `integration` (`pytest.ini`).
- Commentaires, docstrings et messages d'erreur en **français** (avec accents).
- Commits en Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).
- `ruff check .` doit passer à chaque commit.
- BeautifulSoup s'utilise avec le parseur `"lxml"` — c'est l'idiome établi (`klikego.py`, `breizhchrono.py`, `sportinnovation.py`).
- **Non-régression absolue sur ChronoSmetron** : `chronosmetron.wiclax-results.com` est en production. Aucun changement de nom de course, de type d'épreuve ou de dossard n'est acceptable pour ce provider.

## File Structure

| Fichier | Responsabilité |
|---|---|
| `app/scrapers/registry.py` | **Modifier** — `WiclaxProvider.matches()` : ajouter l'host `chronowest.fr`. |
| `app/scrapers/wiclax.py` | **Modifier** — helpers purs de résolution d'URL (`_find_glive_url`, `_find_wiclax_link`, `_clax_url`), `_resolve_to_wiclax_url` récursif avec garde, `_fetch_clax` sans `/G-Live/` en dur, `_parse_competitor` (event_type depuis le nom qualifié). |
| `tests/fixtures/chronowest_shell_locorrida.html` | **Créer** — coquille WordPress réelle, `src` d'iframe contenant une **apostrophe** (`LOC'orrida 2026.clax`). Fixture de non-régression du bug de troncature. |
| `tests/fixtures/chronowest_event_page.html` | **Créer** — page épreuve WordPress réduite : pas d'iframe, un lien vers `/resultats/<slug>/`. |
| `tests/fixtures/wiclax_directory_chronosmetron.html` | **Créer** — page annuaire ChronoSmetron : iframe en chemin **racine-absolu**. |
| `tests/fixtures/chronowest_red_ouf_reduit.clax` | **Créer** — `.clax` ChronoWest réduit (`<Engages>` / `<Resultats>` / `<Equipes>`). |
| `tests/test_wiclax.py` | **Modifier** — tests des helpers purs, de la résolution récursive, du parsing sur fixture réelle. |
| `tests/test_integration_scrapers.py` | **Modifier** — entrée ChronoWest (réseau réel). |
| `AGENTS.md` | **Modifier** — liste des fournisseurs supportés. |

---

### Task 1 : Reconnaître l'host `chronowest.fr`

Sans ça, l'URL tombe sur le fallback `playwright`, qui refuse l'import d'épreuve. C'est la seule raison pour laquelle ChronoWest ne marche pas aujourd'hui.

**Files:**
- Modify: `backend/app/scrapers/registry.py:91-105` (`WiclaxProvider`)
- Test: `backend/tests/test_wiclax.py`

**Interfaces:**
- Consumes: rien.
- Produces: `registry.detect_provider(url) -> str` renvoie `"wiclax"` pour un host `chronowest.fr`.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à la fin de `backend/tests/test_wiclax.py` (et ajouter `from app.scrapers import registry` aux imports en tête de fichier) :

```python
# ---------------------------------------------------------------------------
# Détection de provider (registre)
# ---------------------------------------------------------------------------


def test_registry_detecte_chronowest():
    """chronowest.fr est un déploiement Wiclax/G-Live, pas un moteur inconnu."""
    assert registry.detect_provider(
        "https://chronowest.fr/resultats/trail-des-2-ponts-2026/"
    ) == "wiclax"
    assert registry.detect_provider("https://chronowest.fr/trail-des-2-ponts-2026/") == "wiclax"


def test_registry_hosts_wiclax_existants_inchanges():
    """Non-régression : les hosts déjà supportés restent routés vers wiclax."""
    for url in (
        "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
        "https://www.chronosmetron.com/resultats/",
        "https://x.wiclax.com/G-Live/g-live.html?f=../E/e.clax",
    ):
        assert registry.detect_provider(url) == "wiclax", url


def test_registry_host_inconnu_reste_playwright():
    """L'allowlist reste explicite : pas de sniffing de contenu."""
    assert registry.detect_provider("https://exemple-inconnu.fr/resultats/") == "playwright"
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
pytest tests/test_wiclax.py -k registry -v
```

Attendu : `test_registry_detecte_chronowest` **FAIL** avec `AssertionError: assert 'playwright' == 'wiclax'`. Les deux autres passent déjà.

- [ ] **Step 3: Ajouter l'host**

Dans `backend/app/scrapers/registry.py`, remplacer la méthode `matches` de `WiclaxProvider` :

```python
class WiclaxProvider:
    name = "wiclax"

    # Hosts servant un moteur G-Live. Allowlist **explicite** : détecter du G-Live
    # par le contenu obligerait à télécharger la page de toute URL inconnue avant
    # de savoir la traiter. Un nouveau déploiement tiers = une ligne ici.
    # `chronowest.fr` : WordPress + iframe G-Live (issue #35).
    _HOSTS = ("wiclax-results.com", "chronosmetron.com", "chronowest.fr")

    def matches(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""
        return (
            any(host == h or host.endswith(f".{h}") for h in self._HOSTS)
            or (host.endswith("wiclax.com") and "G-Live" in path)
        )
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_wiclax.py -k registry -v && ruff check .
```

Attendu : 3 PASS, ruff sans erreur.

- [ ] **Step 5: Commit**

```bash
git add app/scrapers/registry.py tests/test_wiclax.py
git commit -m "feat(scrapers): reconnaître chronowest.fr comme déploiement Wiclax"
```

---

### Task 2 : Extraire l'iframe G-Live avec un parseur HTML (bug de l'apostrophe)

La regex actuelle (`wiclax.py:172`) capture le `src` avec la classe `[^"\']*`, qui **s'arrête à la première apostrophe**. Le fichier `LOC'orrida 2026.clax` est tronqué à `LOC` → `404`. Le bug frappe aussi les hosts déjà supportés. On remplace regex par BeautifulSoup et on unifie les deux sauts de résolution (annuaire ChronoSmetron, page épreuve WordPress) en une seule récursion gardée.

**Files:**
- Modify: `backend/app/scrapers/wiclax.py:10-22` (imports), `:149-179` (`_resolve_to_wiclax_url`)
- Create: `backend/tests/fixtures/chronowest_shell_locorrida.html`
- Create: `backend/tests/fixtures/chronowest_event_page.html`
- Create: `backend/tests/fixtures/wiclax_directory_chronosmetron.html`
- Test: `backend/tests/test_wiclax.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `_find_glive_url(html: str, page_url: str) -> str | None` — URL absolue du `g-live.html` référencé par une `<iframe>`, `None` si absente.
  - `_find_wiclax_link(html: str, page_url: str) -> str | None` — lien sortant vers une page de résultats Wiclax (host `wiclax-results.com`) ou vers la coquille `/resultats/<slug>/` du même host, `None` si absent.
  - `_resolve_to_wiclax_url(url: str, client: httpx.Client, _hops: int = 0) -> str` — signature élargie (`_hops`), lève `ValueError` au-delà de `_MAX_RESOLVE_HOPS`.

- [ ] **Step 1: Créer les trois fixtures HTML**

`backend/tests/fixtures/chronowest_shell_locorrida.html` — coquille réelle (le `src` contient une apostrophe, c'est tout l'intérêt) :

```html
<!DOCTYPE html>
<html lang="">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LOC'orrida - 2026</title>
</head>
<body>
    <iframe id="FGL" style="position:absolute; top:0; left:0; bottom:0; right:0; border:0; width:100%; height:100%"
        src="https://chronowest.fr/wp-content/glive/g-live.html?f=/wp-content/glive-results/locorrida-2026/LOC'orrida%202026.clax&t=0203054427&wp=1"></iframe>
</body>
</html>
```

`backend/tests/fixtures/chronowest_event_page.html` — page épreuve WordPress réduite. Pas d'iframe ; le lien de nav `/resultats-des-courses-et-classement/` ne doit **pas** être confondu avec la coquille `/resultats/<slug>/` :

```html
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Trail des 2 ponts 2026</title></head>
<body>
  <nav>
    <a href="https://chronowest.fr/">Accueil</a>
    <a href="https://chronowest.fr/resultats-des-courses-et-classement/">Résultats des courses</a>
  </nav>
  <main>
    <h1>Trail des 2 ponts 2026</h1>
    <a href="https://chronowest.fr/resultats/trail-des-2-ponts-2026/">Voir les résultats</a>
  </main>
</body>
</html>
```

`backend/tests/fixtures/wiclax_directory_chronosmetron.html` — annuaire ChronoSmetron : iframe en chemin **racine-absolu**, `f=` relatif (`../`) :

```html
<html><body>
 <iframe src="/G-Live/g-live.html?f=../Triathlon de la Roche 2026/Triathlon de la Roche.clax&t=1782107927"
    style="position:fixed; top:0; left:0; width:100%; height:100%; border:none"
    bubble="1">
 </iframe>
</body></html>
```

- [ ] **Step 2: Écrire les tests qui échouent**

Dans `backend/tests/test_wiclax.py`, ajouter `from pathlib import Path` aux imports, la constante `FIXTURES` sous les imports, et ces tests :

```python
FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Résolution d'URL : page → iframe G-Live
# ---------------------------------------------------------------------------


def test_find_glive_url_apostrophe_non_tronquee():
    """Bug #35 : la regex `[^"\\']*` coupait le src à l'apostrophe de LOC'orrida."""
    src = _find_glive_url(
        _fixture("chronowest_shell_locorrida.html"),
        "https://chronowest.fr/resultats/locorrida-2026/",
    )
    assert src == (
        "https://chronowest.fr/wp-content/glive/g-live.html"
        "?f=/wp-content/glive-results/locorrida-2026/LOC'orrida%202026.clax"
        "&t=0203054427&wp=1"
    )


def test_find_glive_url_src_racine_absolu():
    """ChronoSmetron : src racine-absolu → résolu contre l'host de la page."""
    src = _find_glive_url(
        _fixture("wiclax_directory_chronosmetron.html"),
        "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    )
    assert src.startswith("https://chronosmetron.wiclax-results.com/G-Live/g-live.html?f=")


def test_find_glive_url_absente():
    """Une page sans iframe G-Live renvoie None (et non une exception)."""
    assert _find_glive_url(_fixture("chronowest_event_page.html"), "https://chronowest.fr/x/") is None


# ---------------------------------------------------------------------------
# Résolution d'URL : page épreuve → coquille de résultats
# ---------------------------------------------------------------------------


def test_find_wiclax_link_page_wordpress():
    """La page épreuve WordPress pointe vers la coquille /resultats/<slug>/.

    Le lien de nav /resultats-des-courses-et-classement/ ne doit pas matcher.
    """
    lien = _find_wiclax_link(
        _fixture("chronowest_event_page.html"),
        "https://chronowest.fr/trail-des-2-ponts-2026/",
    )
    assert lien == "https://chronowest.fr/resultats/trail-des-2-ponts-2026/"


def test_find_wiclax_link_absent():
    """Une coquille à iframe n'a pas de lien sortant Wiclax → None."""
    assert _find_wiclax_link(
        _fixture("chronowest_shell_locorrida.html"),
        "https://chronowest.fr/resultats/locorrida-2026/",
    ) is None


class _FakeClient:
    """Client httpx factice : sert des fixtures depuis une table url → html."""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.appels: list[str] = []

    def get(self, url: str, headers=None):  # noqa: ARG002 — signature httpx
        self.appels.append(url)
        if url not in self.pages:
            raise AssertionError(f"URL non prévue par le test : {url}")
        return httpx.Response(200, text=self.pages[url], request=httpx.Request("GET", url))


def test_resolve_saute_de_la_page_epreuve_a_la_coquille():
    """Page épreuve WP (sans iframe) → lien /resultats/ → iframe G-Live."""
    client = _FakeClient({
        "https://chronowest.fr/trail-des-2-ponts-2026/": _fixture("chronowest_event_page.html"),
        "https://chronowest.fr/resultats/trail-des-2-ponts-2026/": _fixture(
            "chronowest_shell_locorrida.html"
        ),
    })
    url = _resolve_to_wiclax_url("https://chronowest.fr/trail-des-2-ponts-2026/", client)
    assert url.startswith("https://chronowest.fr/wp-content/glive/g-live.html?f=")
    assert len(client.appels) == 2


def test_resolve_boucle_infinie_gardee():
    """Une page qui se pointe elle-même s'arrête sur ValueError, pas sur RecursionError."""
    piege = (
        '<html><body><a href="https://chronowest.fr/resultats/boucle/">ici</a></body></html>'
    )
    client = _FakeClient({"https://chronowest.fr/resultats/boucle/": piege})
    with pytest.raises(ValueError, match="G-Live"):
        _resolve_to_wiclax_url("https://chronowest.fr/resultats/boucle/", client)


def test_resolve_sans_iframe_ni_lien_leve_valueerror():
    client = _FakeClient({"https://chronowest.fr/vide/": "<html><body>rien</body></html>"})
    with pytest.raises(ValueError, match="G-Live"):
        _resolve_to_wiclax_url("https://chronowest.fr/vide/", client)
```

Compléter les imports en tête de `tests/test_wiclax.py` :

```python
import httpx
import pytest

from app.scrapers.wiclax import (
    _find_glive_url,
    _find_wiclax_link,
    _resolve_to_wiclax_url,
)
```

- [ ] **Step 3: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_wiclax.py -k "find_glive or find_wiclax or resolve" -v
```

Attendu : **collection error** — `ImportError: cannot import name '_find_glive_url' from 'app.scrapers.wiclax'`.

- [ ] **Step 4: Implémenter les helpers**

Dans `backend/app/scrapers/wiclax.py`, ajouter l'import BeautifulSoup en tête (après `import httpx`) :

```python
from bs4 import BeautifulSoup
```

Puis **remplacer intégralement** la fonction `_resolve_to_wiclax_url` (lignes 149-179) par :

```python
# Sauts max dans la chaîne « page épreuve → coquille → iframe G-Live ».
# Garde anti-boucle : une page qui se pointe elle-même s'arrête sur ValueError.
_MAX_RESOLVE_HOPS = 3


def _find_glive_url(html: str, page_url: str) -> str | None:
    """URL absolue du moteur G-Live référencé par une <iframe> de la page.

    BeautifulSoup et non une regex : le `src` contient des apostrophes dès que le
    nom d'épreuve en a une (« LOC'orrida 2026.clax »), ce qui tronquait la capture
    d'une classe `[^"']*` et produisait un 404 (issue #35). Le parseur décode aussi
    les entités HTML. Le `src` est résolu contre l'URL de la page : correct pour un
    src absolu (ChronoWest) comme racine-relatif (ChronoSmetron).
    """
    soup = BeautifulSoup(html, "lxml")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or ""
        if "g-live.html" in src.lower():
            return urljoin(page_url, src)
    return None


def _find_wiclax_link(html: str, page_url: str) -> str | None:
    """Lien sortant menant à une page de résultats Wiclax, ou None.

    Deux formes, unifiées ici :
      - un lien vers `*.wiclax-results.com` (page événement ChronoSmetron) ;
      - un lien vers la coquille `/resultats/<slug>/` du même host (page épreuve
        WordPress d'un déploiement type ChronoWest). Le lien de nav
        `/resultats-des-courses-et-classement/` ne matche pas : on exige le
        segment `resultats` exact suivi d'un unique slug.
    """
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(page_url).netloc.lower()
    for a in soup.find_all("a", href=True):
        cible = urljoin(page_url, a["href"])
        parsed = urlparse(cible)
        if parsed.netloc.lower().endswith("wiclax-results.com"):
            # Les espaces du nom d'épreuve vivent tels quels dans le href.
            chemin = quote(parsed.path, safe="/%+").rstrip("/") + "/"
            return parsed._replace(path=chemin).geturl()
        if parsed.netloc.lower() == host and re.fullmatch(
            r"/resultats/[^/]+/?", parsed.path
        ):
            return cible
    return None


def _resolve_to_wiclax_url(url: str, client: httpx.Client, _hops: int = 0) -> str:
    """Remonte de n'importe quelle page Wiclax jusqu'à l'URL du `g-live.html`.

    Chaîne : page épreuve WordPress → coquille `/resultats/<slug>/` → iframe
    G-Live. Une page portant directement l'iframe court-circuite les sauts.
    """
    if _hops >= _MAX_RESOLVE_HOPS:
        raise ValueError(
            f"Trop de sauts en cherchant le moteur G-Live depuis : {url}"
        )

    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()

    glive_url = _find_glive_url(resp.text, url)
    if glive_url:
        return glive_url

    lien = _find_wiclax_link(resp.text, url)
    if lien:
        return _resolve_to_wiclax_url(lien, client, _hops + 1)

    raise ValueError(f"Impossible de trouver le lien G-Live dans la page Wiclax : {url}")
```

Ajouter `quote` à l'import `urllib.parse` en tête de fichier (l'import local `from urllib.parse import quote` de l'ancienne fonction disparaît avec elle) :

```python
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse, urlunparse
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_wiclax.py -v && ruff check .
```

Attendu : tous PASS (les tests existants inclus — le parseur `.clax` n'a pas bougé), ruff sans erreur.

- [ ] **Step 6: Commit**

```bash
git add app/scrapers/wiclax.py tests/test_wiclax.py tests/fixtures/chronowest_shell_locorrida.html tests/fixtures/chronowest_event_page.html tests/fixtures/wiclax_directory_chronosmetron.html
git commit -m "fix(scrapers): extraire l'iframe G-Live via BeautifulSoup (src tronqué à l'apostrophe)"
```

---

### Task 3 : Résoudre le `.clax` relativement au `g-live.html`

`_fetch_clax` résout le paramètre `f=` contre un `/G-Live/` **codé en dur**. Ça ne marche chez ChronoWest (moteur sous `/wp-content/glive/`) que par accident : son `f=` est racine-absolu et écrase la base dans `urljoin`. Le premier déploiement WordPress avec un `f=` relatif (`../`) casserait.

**Files:**
- Modify: `backend/app/scrapers/wiclax.py:182-225` (`_fetch_clax`)
- Test: `backend/tests/test_wiclax.py`

**Interfaces:**
- Consumes: `_resolve_to_wiclax_url` (Task 2).
- Produces: `_clax_url(glive_url: str) -> str` — URL absolue du `.clax` depuis une URL de `g-live.html` portant un `f=`. Lève `ValueError` si `f=` est absent.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `backend/tests/test_wiclax.py` :

```python
# ---------------------------------------------------------------------------
# Résolution d'URL : g-live.html?f=… → .clax
# ---------------------------------------------------------------------------


def test_clax_url_chronosmetron_f_relatif():
    """Moteur sous /G-Live/, f= relatif (../) → remonte d'un cran."""
    assert _clax_url(
        "https://chronosmetron.wiclax-results.com/G-Live/g-live.html"
        "?f=../Triathlon%20de%20la%20Roche%202026/Triathlon%20de%20la%20Roche.clax"
    ) == (
        "https://chronosmetron.wiclax-results.com/"
        "Triathlon de la Roche 2026/Triathlon de la Roche.clax"
    )


def test_clax_url_chronowest_f_racine_absolu():
    """Moteur sous /wp-content/glive/, f= racine-absolu → écrase le chemin."""
    assert _clax_url(
        "https://chronowest.fr/wp-content/glive/g-live.html"
        "?f=/wp-content/glive-results/locorrida-2026/LOC'orrida%202026.clax"
        "&t=0203054427&wp=1"
    ) == "https://chronowest.fr/wp-content/glive-results/locorrida-2026/LOC'orrida 2026.clax"


def test_clax_url_sans_f_leve_valueerror():
    with pytest.raises(ValueError, match="f="):
        _clax_url("https://chronowest.fr/wp-content/glive/g-live.html")
```

Ajouter `_clax_url` à l'import depuis `app.scrapers.wiclax`.

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
pytest tests/test_wiclax.py -k clax_url -v
```

Attendu : `ImportError: cannot import name '_clax_url' from 'app.scrapers.wiclax'`.

- [ ] **Step 3: Implémenter**

Dans `backend/app/scrapers/wiclax.py`, ajouter le helper juste avant `_fetch_clax` :

```python
def _clax_url(glive_url: str) -> str:
    """URL absolue du `.clax` depuis une URL de moteur `g-live.html?f=…`.

    Le `f=` est résolu contre l'URL réelle du `g-live.html` — et non contre un
    `/G-Live/` codé en dur. Ça couvre les deux familles connues : moteur sous
    `/G-Live/` avec un `f=` relatif (ChronoSmetron), et moteur sous
    `/wp-content/glive/` avec un `f=` racine-absolu (ChronoWest).
    """
    f_param = parse_qs(urlparse(glive_url).query).get("f", [""])[0]
    if not f_param:
        raise ValueError(f"Paramètre f= absent de l'URL G-Live : {glive_url}")
    return urljoin(glive_url, f_param)
```

Puis remplacer le début de `_fetch_clax` — l'ancien bloc :

```python
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        # Resolve chronosmetron.com or directory URLs to G-Live URL if needed
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if not params.get("f") or "chronosmetron.com" in url and "wiclax-results.com" not in url:
            url = _resolve_to_wiclax_url(url, client)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

        f_param = params.get("f", [""])[0]
        base = f"{parsed.scheme}://{parsed.netloc}"
        glive_dir = "/G-Live/"
        clax_url = urljoin(base + glive_dir, f_param)

        resp = client.get(clax_url, headers=HEADERS)
```

devient :

```python
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        # Toute URL qui ne porte pas déjà le `f=` du moteur (page épreuve, coquille
        # WordPress, annuaire ChronoSmetron) est remontée jusqu'au `g-live.html`.
        if not parse_qs(urlparse(url).query).get("f"):
            url = _resolve_to_wiclax_url(url, client)

        clax_url = _clax_url(url)
        f_param = parse_qs(urlparse(url).query).get("f", [""])[0]

        resp = client.get(clax_url, headers=HEADERS)
```

`f_param` reste utilisé plus bas dans la fonction pour le repli du nom d'épreuve
(`unquote(f_param).split("/")[-1].replace(".clax", "")`) — ne pas le supprimer.

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_wiclax.py -v && ruff check .
```

Attendu : tous PASS, ruff sans erreur.

- [ ] **Step 5: Commit**

```bash
git add app/scrapers/wiclax.py tests/test_wiclax.py
git commit -m "fix(scrapers): résoudre le .clax relativement au g-live.html (fin du /G-Live/ en dur)"
```

---

### Task 4 : `event_type` depuis le nom qualifié, pas depuis le parcours seul

**Découvert pendant la planification, hors spec initiale.** `_parse_competitor` écrase l'`event_type` par `classify_event_type(p)` où `p` est le parcours. Or le classifieur **retombe sur `triathlon`** quand il ne reconnaît rien (`classify.py`, étape 4). Chez ChronoWest, les parcours du RED OUF **Swimrun** s'appellent `« S Duo »`, `« M Solo »`, `« L Duo »` → classés `triathlon-s`, `triathlon-m`, `triathlon-l`. Sans ce correctif, **un swimrun serait importé en triathlon**.

Correctif : classer le **nom qualifié** (`« RED OUF Swimrun 2026 - S Duo »`) au lieu du parcours nu. Le sport vient du nom d'épreuve, la taille du parcours.

Vérifié sur les données réelles :

| Épreuve | Parcours | Actuel | Après |
|---|---|---|---|
| RED OUF Swimrun 2026 | `S Duo` / `M Solo` / `L Duo` | `triathlon-s/m/l` ❌ | `swimrun-s/m/l` ✅ |
| Trail des 2 ponts 2026 | `… Solo` / `… Trio` | `trail` | `trail` (inchangé) |
| Triathlon de la Roche | `Relais S/M/L`, `6-9 Ans` | `triathlon-s/m/l`, `triathlon` | **strictement inchangé** |

**Files:**
- Modify: `backend/app/scrapers/wiclax.py:55-75` (`_parse_competitor`)
- Modify: `docs/superpowers/specs/2026-07-12-chronowest-wiclax-design.md`
- Test: `backend/tests/test_wiclax.py`

**Interfaces:**
- Consumes: `_qualify_event_name(event_name: str, parcours: str) -> str` (existant), `_detect_event_type(name: str) -> str` (existant).
- Produces: aucune nouvelle signature.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_wiclax.py` :

```python
def test_parse_competitor_event_type_suit_le_sport_de_l_epreuve():
    """Le sport vient du nom d'épreuve, la taille du parcours.

    Les parcours ChronoWest ne nomment pas le sport (« S Duo », « M Solo ») : les
    classer seuls faisait retomber le classifieur sur son défaut `triathlon` et un
    swimrun était importé en triathlon-s.
    """
    comp = _el('<E d="1" n="LES PHELIPOPOV ." x="X" ca="V4" p="S Duo"/>')
    r = _parse_competitor(comp, "http://x", "RED OUF Swimrun 2026", "swimrun")
    assert r.event_type == "swimrun-s"
    assert r.event_name == "RED OUF Swimrun 2026 - S Duo"


def test_parse_competitor_event_type_parcours_nommant_le_sport():
    """Non-régression ChronoSmetron : un parcours qui nomme le sport reste prioritaire."""
    comp = _el('<E d="6159" v="3" p="Triathlon L"/>')
    r = _parse_competitor(comp, "http://x", "Triathlon de la Roche", "triathlon")
    assert r.event_type == "triathlon-l"


def test_parse_competitor_event_type_parcours_autre_sport():
    """Un parcours d'un autre sport dans une épreuve triathlon garde sa discipline."""
    comp = _el('<E d="7" v="7" p="Duathlon jeunes"/>')
    r = _parse_competitor(comp, "http://x", "Triathlon de Vertou 2026", "triathlon")
    assert r.event_type == "duathlon"
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_wiclax.py -k event_type -v
```

Attendu : `test_parse_competitor_event_type_suit_le_sport_de_l_epreuve` **FAIL** avec
`AssertionError: assert 'triathlon-s' == 'swimrun-s'`. Les deux autres passent déjà.

- [ ] **Step 3: Implémenter**

Dans `backend/app/scrapers/wiclax.py`, `_parse_competitor` — remplacer le bloc `if p_attr:` :

```python
    p_attr = comp.get("p") or comp.get("P") or ""
    if p_attr:
        event_type = _detect_event_type(p_attr)
        result.is_relay = "relais" in p_attr.lower() or "relay" in p_attr.lower()
        event_name = _qualify_event_name(event_name, p_attr)
```

par :

```python
    p_attr = comp.get("p") or comp.get("P") or ""
    if p_attr:
        result.is_relay = "relais" in p_attr.lower() or "relay" in p_attr.lower()
        event_name = _qualify_event_name(event_name, p_attr)
        # On classe le nom *qualifié*, pas le parcours nu : beaucoup de parcours ne
        # nomment pas le sport (« S Duo », « M Solo » chez ChronoWest) et le
        # classifieur retombe alors sur son défaut `triathlon` — un swimrun finissait
        # en triathlon-s. Le sport vient du nom d'épreuve, la taille du parcours ; un
        # parcours qui nomme explicitement une autre discipline (« Duathlon jeunes »)
        # reste prioritaire, les multisports étant testés avant le triathlon.
        event_type = _detect_event_type(event_name)
```

Conserver les commentaires existants sur `_qualify_event_name` (issue #21) au-dessus du bloc.

- [ ] **Step 4: Lancer toute la suite (non-régression ChronoSmetron)**

```bash
pytest tests/test_wiclax.py -v && ruff check .
```

Attendu : **tous** PASS, y compris les tests historiques qui asservissent l'`event_type` au parcours (`test_parse_competitor_e_format_with_parcours`,
`test_parse_competitor_event_name_qualified_by_parcours`,
`test_scrape_event_all_youth_run_bike_run_splits`). Si l'un d'eux casse, **ne pas l'ajuster** : c'est le signal d'une régression ChronoSmetron — s'arrêter et remonter le cas.

- [ ] **Step 5: Consigner l'écart dans la spec**

Dans `docs/superpowers/specs/2026-07-12-chronowest-wiclax-design.md`, ajouter une section `### E.` après la section `### D.`, et **retirer** de « Hors périmètre » la puce « Classification » (qui devient partiellement traitée) :

```markdown
### E. `event_type` : classer le nom qualifié, pas le parcours nu

Découvert à la planification. `_parse_competitor` écrasait l'`event_type` par
`classify_event_type(p)`. Le classifieur retombant sur `triathlon` par défaut
(`classify.py`, étape 4), les parcours ChronoWest qui ne nomment pas le sport
(« S Duo », « M Solo ») faisaient importer le **RED OUF Swimrun en triathlon-s**.

Correctif : classer le nom qualifié (« RED OUF Swimrun 2026 - S Duo ») → sport
depuis le nom d'épreuve, taille depuis le parcours. Vérifié sans aucun changement
sur ChronoSmetron (Relais S/M/L, 6-9 Ans → types identiques).
```

- [ ] **Step 6: Commit**

```bash
git add app/scrapers/wiclax.py tests/test_wiclax.py ../docs/superpowers/specs/2026-07-12-chronowest-wiclax-design.md
git commit -m "fix(scrapers): classer le nom qualifié wiclax (un swimrun n'est plus un triathlon)"
```

---

### Task 5 : Fixture `.clax` ChronoWest + test de parsing bout-en-bout

Verrouille le fait que le format ChronoWest est bien celui de ChronoSmetron : concurrents dans `<Engages><E d=…>`, temps dans `<Resultats><R d=…>`, et surtout les `<E>` **parasites** de `<Equipes>` (ce sont des clubs, pas des athlètes) qui ne doivent pas se retrouver dans les résultats.

**Files:**
- Create: `backend/tests/fixtures/chronowest_red_ouf_reduit.clax`
- Test: `backend/tests/test_wiclax.py`

**Interfaces:**
- Consumes: `scrape_event_all(url) -> list[ScrapedResult]`, `_fetch_clax` (monkeypatché — c'est le pattern déjà en place dans ce fichier de tests).
- Produces: rien.

- [ ] **Step 1: Créer la fixture**

`backend/tests/fixtures/chronowest_red_ouf_reduit.clax` — extrait réduit du RED OUF Swimrun 2026 (structure et attributs réels, 4 engagés au lieu de 162) :

```xml
<?xml version="1.0" encoding="utf-8"?>
<Epreuve vMaj="10" vMin="2" nom="RED OUF Swimrun 2026" dt1="2026-06-28" sport="6">
  <Parcours>
    <Pcs nom="S Duo" dosdeb="1" dosfin="28" distance="12000"/>
    <Pcs nom="M Solo" dosdeb="152" dosfin="183" distance="18500"/>
  </Parcours>
  <Equipes>
    <E n="QUIBERON TRIATHLON" x="2"/>
    <E n="CAUDAN NATATION" x="2"/>
  </Equipes>
  <Engages>
    <E d="1" n="LES PHELIPOPOV&#160;." a="1970" x="X" ca="V4" p="S Duo" na="FR"/>
    <E d="2" n="LES TITOUILLES&#160;." a="1970" x="M" ca="V4" p="S Duo" na="FR"/>
    <E d="152" n="Jean DUPONT" a="1985" x="M" ca="S3H" p="M Solo" na="FR"/>
    <E d="153" n="Marie MARTIN" a="1990" x="F" ca="S2F" p="M Solo" na="FR" np="1"/>
  </Engages>
  <Resultats>
    <R d="1" t="01h47'59" m="8,26"/>
    <R d="2" t="01h49'04" m="8,02"/>
    <R d="152" t="Abandon"/>
  </Resultats>
</Epreuve>
```

- [ ] **Step 2: Écrire le test qui échoue**

Ajouter à `backend/tests/test_wiclax.py` :

```python
# ---------------------------------------------------------------------------
# Parsing d'un .clax ChronoWest réel (réduit)
# ---------------------------------------------------------------------------


def test_scrape_event_all_clax_chronowest(monkeypatch):
    """Le .clax ChronoWest a le même format que ChronoSmetron.

    Verrouille aussi l'immunité aux <E> parasites : ceux de <Equipes> sont des
    clubs, pas des athlètes. Ils n'ont pas d'attribut `d` et doivent être ignorés
    (le scraper itère largement via root.iter("E")).
    """
    root = ET.fromstring(_fixture("chronowest_red_ouf_reduit.clax"))
    monkeypatch.setattr(
        "app.scrapers.wiclax._fetch_clax",
        lambda _url: (root, "http://x", "RED OUF Swimrun 2026", "swimrun", date(2026, 6, 28)),
    )
    results = scrape_event_all("https://chronowest.fr/resultats/red-ouf-2026/")

    # Les 2 <E> de <Equipes> (clubs, sans `d`) ne sont pas des participants.
    assert len(results) == 4
    by_bib = {r.bib_number: r for r in results}
    assert set(by_bib) == {"1", "2", "152", "153"}

    # Temps ChronoWest au format "01h47'59" → normalisé.
    assert by_bib["1"].total_time == "01:47:59"
    assert by_bib["2"].total_time == "01:49:04"

    # Rangs calculés au tri, par parcours (le .clax ne les stocke pas).
    assert by_bib["1"].rank_overall == 1
    assert by_bib["2"].rank_overall == 2

    # <R t="Abandon"> → DNF ; np="1" sans <R> → DNS. Hygiène dans les deux cas.
    assert by_bib["152"].status == "DNF"
    assert by_bib["153"].status == "DNS"
    for bib in ("152", "153"):
        assert by_bib[bib].total_time == ""
        assert by_bib[bib].rank_overall is None

    # Le sport vient du nom d'épreuve, la taille du parcours (Task 4).
    assert by_bib["1"].event_type == "swimrun-s"
    assert by_bib["152"].event_type == "swimrun-m"
    assert by_bib["1"].event_name == "RED OUF Swimrun 2026 - S Duo"
    assert by_bib["1"].event_date == date(2026, 6, 28)
```

Ajouter `from datetime import date` aux imports du fichier de tests.

- [ ] **Step 3: Lancer le test pour vérifier qu'il échoue**

```bash
pytest tests/test_wiclax.py::test_scrape_event_all_clax_chronowest -v
```

Attendu : **FAIL** — `FileNotFoundError` si la fixture manque, sinon un échec d'assertion. (Si la fixture est créée à l'étape 1, le test doit passer directement : le parseur est déjà correct. C'est **le** résultat attendu — il verrouille un comportement, il ne pilote pas une implémentation.)

- [ ] **Step 4: Lancer toute la suite unitaire**

```bash
pytest -m "not integration" -q && ruff check .
```

Attendu : suite verte (≈130 tests + les nouveaux), ruff sans erreur.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/chronowest_red_ouf_reduit.clax tests/test_wiclax.py
git commit -m "test(scrapers): fixture .clax ChronoWest réduite (Engages/Resultats/Equipes)"
```

---

### Task 6 : Test d'intégration réseau + documentation

**Files:**
- Modify: `backend/tests/test_integration_scrapers.py:19-27` (`LIVE_URLS`)
- Modify: `AGENTS.md` (section « Fournisseurs supportés »)

**Interfaces:**
- Consumes: `registry.detect_provider`, `registry.scrape_event_all`.
- Produces: rien.

- [ ] **Step 1: Ajouter l'URL réelle**

Dans `backend/tests/test_integration_scrapers.py`, ajouter une entrée au dict `LIVE_URLS` :

```python
    "wiclax": "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
```

Le dict est indexé par **nom de provider** et `test_detection` asserte
`detect_provider(url) == provider` — or ChronoWest est servi par le provider
`wiclax`, la clé `"chronowest"` casserait cette assertion. Ajouter donc un test
dédié à la fin du fichier, à côté des autres tests spécifiques :

```python
@pytest.mark.integration
def test_chronowest_deploiement_wiclax():
    """chronowest.fr = déploiement WordPress + iframe G-Live (issue #35).

    Épreuve terminée et stable. Ne PAS utiliser /resultats/armorun-2025/ :
    son .clax a été réinitialisé pour l'édition 2026 (pas encore courue) et ne
    contient plus ni <Engages> ni <Resultats> — 0 résultat, alors que le scraper
    fonctionne.
    """
    url = "https://chronowest.fr/resultats/trail-des-2-ponts-2026/"
    assert registry.detect_provider(url) == "wiclax"
    results = registry.scrape_event_all(url)
    assert len(results) > 100, f"chronowest : seulement {len(results)} participants"
    assert any(r.athlete_name and r.total_time for r in results)
    assert all(r.event_type == "trail" for r in results if r.event_type)


@pytest.mark.integration
def test_chronowest_apostrophe_dans_le_nom_de_fichier():
    """Non-régression du src d'iframe tronqué : LOC'orrida 2026.clax → 404."""
    results = registry.scrape_event_all("https://chronowest.fr/resultats/locorrida-2026/")
    assert results, "locorrida : aucun participant (src d'iframe tronqué à l'apostrophe ?)"


@pytest.mark.integration
def test_chronowest_swimrun_nest_pas_un_triathlon():
    """Les parcours (« S Duo », « M Solo ») ne nomment pas le sport : il vient du
    nom d'épreuve, sinon le classifieur retombe sur triathlon."""
    results = registry.scrape_event_all("https://chronowest.fr/resultats/red-ouf-2026/")
    assert results
    types = {r.event_type for r in results}
    assert types <= {"swimrun", "swimrun-s", "swimrun-m", "swimrun-l"}, types
```

- [ ] **Step 2: Lancer les tests d'intégration (réseau réel)**

```bash
pytest -m integration -k chronowest -v
```

Attendu : 3 PASS. En cas d'échec réseau (site indisponible), relancer ; en cas
d'échec d'assertion, c'est une régression réelle.

- [ ] **Step 3: Vérifier la non-régression des autres providers**

```bash
pytest -m integration -v
```

Attendu : toute la suite d'intégration verte — en particulier `wiclax`
(ChronoSmetron), qui traverse le code modifié aux tasks 2, 3 et 4.

- [ ] **Step 4: Mettre à jour la documentation**

Dans `AGENTS.md`, section « Fournisseurs supportés », remplacer :

```markdown
Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète).
```

par :

```markdown
Klikego, Breizh Chrono, TimePulse, Wiclax/G-Live (individuel + épreuve complète).
Wiclax/G-Live couvre plusieurs déploiements : `wiclax-results.com`,
`chronosmetron.com` et `chronowest.fr` (WordPress + iframe G-Live). Un nouveau
déploiement tiers = un host dans `WiclaxProvider._HOSTS`.
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_integration_scrapers.py ../AGENTS.md
git commit -m "test(scrapers): intégration chronowest + doc des déploiements Wiclax"
```

---

## Vérification finale

- [ ] **Suite unitaire complète**

```bash
pytest -m "not integration" -q
```
Attendu : verte, aucun test ignoré silencieusement.

- [ ] **Suite d'intégration complète**

```bash
pytest -m integration -q
```
Attendu : verte (tous les providers, ChronoSmetron inclus).

- [ ] **Lint**

```bash
ruff check .
```
Attendu : `All checks passed!`

- [ ] **Bout-en-bout via l'API** — importer une épreuve ChronoWest dans une base de dev et vérifier qu'elle apparaît avec le bon type :

```bash
uvicorn app.main:app --reload --port 8001
# puis, dans un autre terminal :
curl -X POST localhost:8001/api/v1/scrape -H 'Content-Type: application/json' \
  -d '{"url": "https://chronowest.fr/resultats/red-ouf-2026/"}'
```
Attendu : l'import démarre (provider `wiclax`, pas `playwright`) et les courses
créées sont de type `swimrun-*`.
