# Choix import unique / fanout complet à l'ajout d'une course — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Laisser l'utilisateur choisir, à l'ajout d'une course (`/ajouter`), entre importer uniquement l'URL collée ou fan-outer l'événement entier — pour les 8 providers fan-out du registre.

**Architecture:** `import_event`/`iter_import_event`/`_scrape_all` (`backend/app/services/import_service.py`) acceptent déjà et propagent `single_heat: bool` — seul le CLI (`rescrape-db --single-heat`) l'atteint aujourd'hui. Ce plan relie ce paramètre déjà câblé à `POST /scrape/event`/`/scrape/event/stream` via `ScrapeRequest`, comble le seul gap de comportement (`ChronoplaceProvider` n'acceptait pas `single_heat`), ajoute `targets_single_heat` sur `FanoutProvider` pour que le backend calcule seul un défaut sûr, et câble un contrôle à deux options côté `TcnScrapeForm`.

**Tech Stack:** Backend Python 3.13 / FastAPI / Pydantic v2 (pytest, `-m "not integration"`). Frontend Next.js 16 / TypeScript / Vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-08-28-scrape-single-heat-toggle-design.md`

## Global Constraints

- **Copie publique** : ne jamais écrire « course » dans un libellé visible par l'utilisateur — le mot public est « épreuve » (Principe I, `frontend/AGENTS.md`). Les libellés du contrôle utilisent donc « page » et « épreuve(s) », jamais « course ».
- **Périmètre** : les 8 providers fan-out (`FanoutProvider`) — pas seulement Klikego/BreizhChrono.
- **Défaut** : `single_heat=True` (import unique) sauf pour Klikego/BreizhChrono sur une URL sans sélecteur de heat, où le défaut est `False` (fanout) — chemin `heat=""` jamais exécuté en production, cf. spec.
- **Aucun changement** au CLI (`rescrape-db --single-heat`), au `batch`, ni au re-scrape admin (#118) : ils gardent leur propre valeur explicite ou le défaut `False` actuel du service.
- Tests unitaires backend sans réseau (`pytest -m "not integration"` / `rtk uv run pytest -m "not integration"`), tests frontend `npm test` (vitest).

---

## Task 1: `FanoutProvider.targets_single_heat` — Klikego et BreizhChrono

**Files:**
- Modify: `backend/app/scrapers/registry.py:130-181` (classe `FanoutProvider`), `:203-270` (`KlikegoProvider`), `:273-344` (`BreizhChronoProvider`)
- Test: `backend/tests/test_registry.py` (nouvelle section après la ligne 573, `# ── BreizhChronoProvider fan-out (issue #707) ──`)

**Interfaces:**
- Produces: `FanoutProvider.targets_single_heat(url: str) -> bool` (défaut `False`), surchargée par `KlikegoProvider` et `BreizhChronoProvider`. Consommée par Task 3 (`/scrape/detect`).

- [ ] **Step 1: Write the failing tests**

Ajouter dans `backend/tests/test_registry.py`, juste avant `def test_breizhchrono_provider_is_fanout_provider():` (ligne 568) :

```python
# ── targets_single_heat (#698) ───────────────────────────────────────────────


def test_fanout_provider_targets_single_heat_faux_par_defaut():
    """Les providers fan-out sans sélecteur de sous-unité dans l'URL (Wiclax,
    RaceResult, OkTime, Sporthive, ChronoWeb, ProLiveSport, Chronoplace) héritent
    du défaut `False` — leur `single_heat=True` vaut « pas de fan-out », jamais
    « cibler cette sous-unité précise »."""
    from app.scrapers.registry import WiclaxProvider

    assert WiclaxProvider().targets_single_heat("https://wiclax-results.com/x") is False


def test_klikego_targets_single_heat_vrai_avec_heat():
    from app.scrapers.registry import KlikegoProvider

    url = "https://www.klikego.com/resultats/mesquer/1677015306084-12?heat=triathlon-s-indiv"
    assert KlikegoProvider().targets_single_heat(url) is True


def test_klikego_targets_single_heat_faux_sans_heat():
    from app.scrapers.registry import KlikegoProvider

    assert KlikegoProvider().targets_single_heat(
        "https://www.klikego.com/resultats/foo/1234-5"
    ) is False


def test_breizhchrono_targets_single_heat_vrai_chemin_classique():
    from app.scrapers.registry import BreizhChronoProvider

    url = "https://resultats.breizhchrono.com/resultats-courses/tri-mesquer-2026-42/triathlon-m"
    assert BreizhChronoProvider().targets_single_heat(url) is True


def test_breizhchrono_targets_single_heat_faux_chemin_classique_sans_heat():
    from app.scrapers.registry import BreizhChronoProvider

    url = "https://resultats.breizhchrono.com/resultats-courses/tri-42"
    assert BreizhChronoProvider().targets_single_heat(url) is False


def test_breizhchrono_targets_single_heat_vrai_live_avec_heat():
    from app.scrapers.registry import BreizhChronoProvider

    url = (
        "https://live.breizhchrono.com/external/live5/classements.jsp"
        "?version=new&reference=1488071608761-688&heat=triathlon-distance-olympique"
    )
    assert BreizhChronoProvider().targets_single_heat(url) is True


def test_breizhchrono_targets_single_heat_faux_live_sans_heat():
    from app.scrapers.registry import BreizhChronoProvider

    url = "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488071608761-688"
    assert BreizhChronoProvider().targets_single_heat(url) is False


```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_registry.py -k targets_single_heat -v`
Expected: FAIL — `AttributeError: 'WiclaxProvider' object has no attribute 'targets_single_heat'` (et pareil pour Klikego/BreizhChrono).

- [ ] **Step 3: Implement `targets_single_heat`**

Dans `backend/app/scrapers/registry.py`, ajouter la méthode à `FanoutProvider` (après `def __init__` ligne 152, avant `def scrape_event_all` ligne 154) :

```python
    def targets_single_heat(self, url: str) -> bool:
        """Vrai si l'URL cible déjà une sous-unité précise (#698).

        Défaut `False` : la plupart des providers fan-out n'ont aucun sélecteur
        de sous-unité dans l'URL (Wiclax, RaceResult, OkTime, Sporthive,
        ChronoWeb, ProLiveSport, Chronoplace) — leur `single_heat=True` vaut
        « pas de fan-out », jamais « cibler cette sous-unité précise ». Seuls
        Klikego et BreizhChrono la surchargent : `GET /scrape/detect` s'en sert
        pour ne proposer « import unique » par défaut que sur une URL où ce
        chemin est réellement testé.
        """
        return False

```

Dans `KlikegoProvider` (`registry.py:203-270`), ajouter juste après `_parse_url` (après la ligne 233, avant `def scrape_event_all` ligne 235) :

```python
    def targets_single_heat(self, url: str) -> bool:
        """Vrai si l'URL porte déjà un `?heat=` non vide (#698)."""
        _, heat_query, _, _ = self._parse_url(url)
        return bool(heat_query)

```

Dans `BreizhChronoProvider` (`registry.py:273-344`), ajouter juste après la docstring de classe (ligne 289, avant `def scrape_event_all` ligne 291) :

```python
    def targets_single_heat(self, url: str) -> bool:
        """Vrai si l'URL fixe déjà un heat — chemin classique ou `?heat=` live
        (#698). Même détection que `scrape_event_all`, sans effet de bord."""
        from app.scrapers.breizhchrono import _parse_bc_url, _parse_live_url

        if _url_host(url) == breizhchrono.LIVE_HOST:
            _, heat = _parse_live_url(url)
            return bool(heat)
        _, heat, _ = _parse_bc_url(url)
        return bool(heat)

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_registry.py -k targets_single_heat -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/scrapers/registry.py tests/test_registry.py
git commit -m "feat(scrapers): ajoute targets_single_heat sur Klikego/BreizhChrono (#698)"
```

---

## Task 2: `ChronoplaceProvider` — combler le seul gap `single_heat`

**Files:**
- Modify: `backend/app/scrapers/registry.py:409-434` (`ChronoplaceProvider`)
- Test: `backend/tests/test_chronoplace.py` (fin de fichier, après la ligne 935)

**Interfaces:**
- Consumes: `chronoplace.scrape_event_all(url)` (déjà présent, `backend/app/scrapers/chronoplace.py:493`, pré-fanout, plus appelé par la classe avant ce lot), `FanoutTrace` (déjà importé dans `registry.py`).
- Produces: `ChronoplaceProvider.scrape_event_all(url, *, cache_probe=None, on_heat_start=None, single_heat=False)` — signature désormais alignée sur les 7 autres providers fan-out.

- [ ] **Step 1: Write the failing test**

Ajouter à la fin de `backend/tests/test_chronoplace.py` (après `test_registry_expose_last_trace_apres_scrape`, ligne 935) :

```python


def test_chronoplace_provider_single_heat_uses_classic_scrape(monkeypatch):
    """`single_heat=True` (#698) retombe sur le contrat historique — l'épreuve
    visée par l'URL seule, sans ses onglets sœurs — même patron que
    `ChronoWebProvider.scrape_event_all`. Seule échappatoire que Chronoplace
    n'avait pas encore : les 7 autres providers fan-out l'avaient déjà."""
    from app.scrapers.registry import ChronoplaceProvider

    def fanout_refuse(*a, **k):
        raise AssertionError("scrape_event_fanout ne doit pas être appelé")

    monkeypatch.setattr(chronoplace, "scrape_event_fanout", fanout_refuse)
    monkeypatch.setattr(chronoplace, "scrape_event_all", lambda url: ["r1"])

    provider = ChronoplaceProvider()
    results = provider.scrape_event_all(URL_494, single_heat=True)

    assert results == ["r1"]
    assert provider.last_trace.heats_enumerated == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_chronoplace.py -k single_heat -v`
Expected: FAIL — `TypeError: ChronoplaceProvider.scrape_event_all() got an unexpected keyword argument 'single_heat'`.

- [ ] **Step 3: Implement**

Dans `backend/app/scrapers/registry.py`, remplacer le bloc `ChronoplaceProvider` (lignes 409-434) :

```python
class ChronoplaceProvider(FanoutProvider):
    """Chronoplace — fan-out par épreuve (cache TTL par sous-unité, épique #195).

    Une URL pointe une épreuve, mais la page liste ses sœurs (onglets) : chaque
    onglet est une sous-unité, avec sa propre `source_url` canonique. Le
    fan-out expose sa progression dans `self.last_trace`.
    """
    name = "chronoplace"
    _HOSTS = ("chronoplace.fr",)

    _module = chronoplace

    def scrape_event_all(
        self, url: str,
        *,
        cache_probe: Callable[[str], bool] | None = None,
        on_heat_start: Callable[[str, str, int, int], None] | None = None,
        single_heat: bool = False,
    ) -> list[ScrapedResult]:
        """Fan-out par défaut ; `single_heat=True` (#698) retombe sur l'épreuve
        visée par l'URL seule, sans ses onglets sœurs — même patron que
        `ChronoWebProvider.scrape_event_all`. Chronoplace n'a pas de sélecteur
        de sous-unité dans l'URL : `targets_single_heat` reste le défaut
        `False` de `FanoutProvider`, comme les 5 autres providers fan-out sans
        sélecteur d'URL.
        """
        if single_heat:
            self.last_trace = FanoutTrace()
            return chronoplace.scrape_event_all(url)
        results, trace = chronoplace.scrape_event_fanout(
            url, cache_probe=cache_probe, on_heat_start=on_heat_start,
        )
        self.last_trace = trace
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_chronoplace.py -k single_heat -v`
Expected: PASS.

Run aussi la suite complète du fichier pour non-régression : `cd backend && uv run pytest tests/test_chronoplace.py -v`
Expected: tous PASS (le test existant `test_registry_expose_last_trace_apres_scrape` doit rester vert — il n'appelle pas `single_heat`).

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/scrapers/registry.py tests/test_chronoplace.py
git commit -m "feat(scrapers): ajoute l'échappatoire single_heat à Chronoplace (#698)"
```

---

## Task 3: `GET /scrape/detect` expose `fanout` et `default_single_heat`

**Files:**
- Modify: `backend/app/api/v1/scrape.py:17` (import), `:125-140` (`detect`)
- Modify: `backend/tests/test_api/test_scrape_api.py:23-50` (3 assertions existantes à étoffer)
- Test: `backend/tests/test_api/test_scrape_api.py` (nouveaux tests après la ligne 50)

**Interfaces:**
- Consumes: `registry.get_provider`, `registry.FanoutProvider`, `registry.KlikegoProvider`, `registry.BreizhChronoProvider`, `FanoutProvider.targets_single_heat` (Task 1).
- Produces: réponse JSON de `GET /scrape/detect` = `{provider: str, supported: bool, fanout: bool, default_single_heat: bool}`. Consommée par Task 6 (frontend).

- [ ] **Step 1: Write the failing tests**

Dans `backend/tests/test_api/test_scrape_api.py`, remplacer les lignes 23-50 :

```python
def test_detect(client):
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://www.klikego.com/x"})
    assert resp.json() == {
        "provider": "klikego", "supported": True,
        "fanout": True, "default_single_heat": False,
    }


@pytest.mark.parametrize(
    ("url", "provider", "fanout"),
    [
        ("https://www.ironman.com/races/im703-vichy/results", "competitor", False),
        ("https://my.raceresult.com/406211/results", "raceresult", True),
        ("https://chronoplace.fr/evenement/x", "chronoplace", True),
    ],
)
def test_detect_expose_le_support_des_providers_recents(client, url, provider, fanout):
    """`supported` est dérivé du registre, jamais d'une liste à tenir à jour.

    Le front affichait « Non supporté (competitor) » sur une URL ironman.com :
    il portait sa propre liste de providers, figée à six noms — Competitor,
    RaceResult et Chronoplace en étaient absents (même piège de définition
    dupliquée que #76). C'est l'API qui tranche désormais.

    `fanout`/`default_single_heat` (#698) : aucun des trois n'est Klikego ni
    BreizhChrono, donc `default_single_heat` vaut toujours `True` ici, que le
    provider soit fan-out ou non.
    """
    resp = client.get("/api/v1/scrape/detect", params={"url": url})
    assert resp.json() == {
        "provider": provider, "supported": True,
        "fanout": fanout, "default_single_heat": True,
    }


def test_detect_url_inconnue_reste_non_supportee(client):
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://chronopuce.test/x"})
    assert resp.json() == {
        "provider": "", "supported": False,
        "fanout": False, "default_single_heat": True,
    }


def test_detect_expose_default_single_heat_vrai_klikego_avec_heat(client):
    """URL Klikego portant déjà `?heat=` : `single_heat=True` est un chemin
    testé, le front peut proposer « import unique » coché par défaut (#698)."""
    resp = client.get(
        "/api/v1/scrape/detect",
        params={"url": "https://www.klikego.com/resultats/foo/1?heat=triathlon-m"},
    )
    assert resp.json() == {
        "provider": "klikego", "supported": True,
        "fanout": True, "default_single_heat": True,
    }


def test_detect_expose_default_single_heat_faux_sans_selecteur_breizhchrono(client):
    """URL BreizhChrono nue (sans heat) : `single_heat=True` viserait un chemin
    jamais exécuté en production — le front ne le pré-coche pas (#698)."""
    resp = client.get(
        "/api/v1/scrape/detect",
        params={"url": "https://resultats.breizhchrono.com/resultats-courses/tri-42"},
    )
    assert resp.json() == {
        "provider": "breizhchrono", "supported": True,
        "fanout": True, "default_single_heat": False,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_api/test_scrape_api.py -k detect -v`
Expected: FAIL — `AssertionError` (le corps de réponse ne porte pas encore `fanout`/`default_single_heat`).

- [ ] **Step 3: Implement**

Dans `backend/app/api/v1/scrape.py`, ligne 17, remplacer :

```python
from app.scrapers import detect_provider, is_supported, provider_names
```

par :

```python
from app.scrapers import detect_provider, is_supported, provider_names, registry
```

Puis remplacer la fonction `detect` (lignes 125-140) :

```python
@router.get("/scrape/detect")
def detect(url: HttpUrl):
    """Provider détecté + support réel + portée du fan-out, dérivés du registre.

    `supported` est renvoyé pour que le front n'ait pas à tenir sa propre liste
    de providers : la sienne avait divergé et affichait « Non supporté » sur
    Competitor, RaceResult et Chronoplace.

    `fanout`/`default_single_heat` (#698) servent le choix « import unique /
    fanout complet » du front (`TcnScrapeForm`) sans qu'il tienne sa propre
    liste de providers fan-out : `fanout` vaut `isinstance(provider,
    FanoutProvider)` ; `default_single_heat` vaut `True` pour tout provider
    (fan-out ou non), sauf Klikego/BreizhChrono sur une URL sans sélecteur de
    heat, seul cas où `single_heat=True` est un chemin non testé en
    production (cf. `targets_single_heat`, spec #698).

    `HttpUrl` (#634) : même patron que `ScrapeRequest.url` (#49) et
    `PendingProviderCreate.url` (#398) — troisième et dernière route tracée
    par #251. Le front filtre déjà par `startsWith("http")` avant d'appeler
    cette route (`ProviderDetector.tsx`), donc sans coût pour l'appelant
    légitime.
    """
    raw = str(url)
    provider = registry.get_provider(raw)
    fanout = isinstance(provider, registry.FanoutProvider)
    if fanout and isinstance(provider, (registry.KlikegoProvider, registry.BreizhChronoProvider)):
        default_single_heat = provider.targets_single_heat(raw)
    else:
        default_single_heat = True
    return {
        "provider": detect_provider(raw),
        "supported": is_supported(raw),
        "fanout": fanout,
        "default_single_heat": default_single_heat,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_api/test_scrape_api.py -k detect -v`
Expected: 8 PASS (5 mises à jour/parametrées + 3 nouvelles — le décompte exact dépend du dépliage `pytest -v`, mais aucun FAIL/ERROR).

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/api/v1/scrape.py tests/test_api/test_scrape_api.py
git commit -m "feat(api): /scrape/detect expose fanout et default_single_heat (#698)"
```

---

## Task 4: `ScrapeRequest.single_heat` — relais jusqu'à `import_service`

**Files:**
- Modify: `backend/app/schemas/scrape.py` (`ScrapeRequest`)
- Modify: `backend/app/api/v1/scrape.py:42-60` (`scrape_event`), `:74-101` (`scrape_event_stream`)
- Modify: `backend/tests/test_api/test_scrape_api.py:126, 172, 214` (3 `fake_iter_import_event` à rendre tolérants à `single_heat`)
- Test: `backend/tests/test_api/test_scrape_api.py` (nouveaux tests)

**Interfaces:**
- Consumes: `import_service.import_event(db, url, settings, force=False, persist=True, *, single_heat=False)`, `import_service.iter_import_event(...)` (signatures déjà existantes, inchangées).
- Produces: `ScrapeRequest.single_heat: bool = True`. Consommé par Task 6 (frontend, corps POST).

- [ ] **Step 1: Write the failing tests**

Dans `backend/tests/test_api/test_scrape_api.py`, corriger les 3 occurrences de `fake_iter_import_event` (lignes 126, 172, 214) pour qu'elles tolèrent un `single_heat` inattendu tant que Task 4 n'est pas implémentée — remplacer chacune des 3 occurrences de :

```python
    def fake_iter_import_event(db, url, settings, force=False, persist=True):
```

par :

```python
    def fake_iter_import_event(db, url, settings, force=False, persist=True, **kwargs):
```

(Les 3 occurrences sont textuellement identiques — un seul remplacement `replace_all`.)

Puis ajouter, à la fin du fichier :

```python


def test_scrape_event_single_heat_defaut_vrai_si_omis(client, monkeypatch):
    """Le schéma par défaut à `True` (#698) : import unique si le front
    n'envoie rien — moins de surprise sur le volume importé."""
    from app.services import import_service

    captured = {}

    def fake_import_event(db, url, settings, force=False, persist=True, *, single_heat=False):
        captured["single_heat"] = single_heat
        return {
            "imported": 0, "updated": 0, "skipped": 0, "reconciled": 0,
            "passive_sources": [], "courses": [],
        }

    monkeypatch.setattr(import_service, "import_event", fake_import_event)
    client.post("/api/v1/scrape/event", json={"url": "https://www.klikego.com/x"})
    assert captured["single_heat"] is True


def test_scrape_event_forwards_single_heat(client, monkeypatch):
    """`single_heat` du corps de requête atteint `import_service.import_event` (#698)."""
    from app.services import import_service

    captured = {}

    def fake_import_event(db, url, settings, force=False, persist=True, *, single_heat=False):
        captured["single_heat"] = single_heat
        return {
            "imported": 0, "updated": 0, "skipped": 0, "reconciled": 0,
            "passive_sources": [], "courses": [],
        }

    monkeypatch.setattr(import_service, "import_event", fake_import_event)
    client.post(
        "/api/v1/scrape/event",
        json={"url": "https://www.klikego.com/x", "single_heat": False},
    )
    assert captured["single_heat"] is False


def test_scrape_event_stream_forwards_single_heat(client, monkeypatch):
    """Même relais côté SSE (#698)."""
    from app.services import import_service

    captured = {}

    def fake_iter_import_event(
        db, url, settings, force=False, persist=True, *, single_heat=False,
    ):
        captured["single_heat"] = single_heat
        yield {
            "phase": "done", "imported": 0, "updated": 0, "skipped": 0,
            "reconciled": 0, "reassignments": [], "passive_sources": [],
            "total": 0, "courses": [],
        }

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)
    with client.stream(
        "POST", "/api/v1/scrape/event/stream",
        json={"url": "https://www.klikego.com/x", "single_heat": False},
    ) as resp:
        list(resp.iter_text())
    assert captured["single_heat"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_api/test_scrape_api.py -k single_heat -v`
Expected: FAIL — `captured["single_heat"]` reste `False` par défaut de la fake (l'API n'envoie encore rien).

- [ ] **Step 3: Implement**

Dans `backend/app/schemas/scrape.py`, ajouter le champ à `ScrapeRequest`, après `url: HttpUrl` :

```python
    #: Choix « import unique / fanout complet » (#698). Défaut `True` : moins
    #: de surprise sur le volume importé qu'un fanout automatique. Pour
    #: Klikego/BreizhChrono sans sélecteur de sous-unité dans l'URL, le front
    #: pré-coche `False` (voir `GET /scrape/detect`, `default_single_heat`),
    #: mais rien ici ne l'impose : c'est un choix utilisateur, pas une règle
    #: serveur.
    single_heat: bool = True
```

Dans `backend/app/api/v1/scrape.py`, dans `scrape_event` (ligne 49), remplacer :

```python
    result = import_service.import_event(db, str(body.url), settings)
```

par :

```python
    result = import_service.import_event(
        db, str(body.url), settings, single_heat=body.single_heat,
    )
```

Dans `scrape_event_stream`, dans `generate()` (ligne 99), remplacer :

```python
            for event in import_service.iter_import_event(db, str(body.url), settings):
```

par :

```python
            for event in import_service.iter_import_event(
                db, str(body.url), settings, single_heat=body.single_heat,
            ):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_api/test_scrape_api.py -v`
Expected: tous PASS (fichier complet, pour vérifier qu'aucune des 3 fakes corrigées ne casse ses tests d'origine).

- [ ] **Step 5: Commit**

```bash
cd backend
git add app/schemas/scrape.py app/api/v1/scrape.py tests/test_api/test_scrape_api.py
git commit -m "feat(api): relaie single_heat de ScrapeRequest à import_service (#698)"
```

- [ ] **Step 6: Full backend regression**

Run: `cd backend && uv run pytest -m "not integration"`
Expected: 0 FAIL (hors éventuels échecs pré-existants sans rapport, déjà connus — `test_auth`).

---

## Task 5: Frontend — `useImportStream`/`sse.ts` propagent `singleHeat`

**Files:**
- Modify: `frontend/lib/api/sse.ts:36-66` (`importEventStream`)
- Modify: `frontend/hooks/useImportStream.ts` (`start`)
- Test: `frontend/lib/api/sse.test.ts`, `frontend/hooks/useImportStream.test.ts`

**Interfaces:**
- Produces: `importEventStream(url: string, signal?: AbortSignal, singleHeat?: boolean): AsyncGenerator<ImportProgressEvent>` (défaut `true`, body POST `{url, single_heat: singleHeat}`). `useImportStream().start(url: string, singleHeat?: boolean): Promise<void>` (défaut `true`).
- Consumed by: Task 6 (`TcnScrapeForm`).

- [ ] **Step 1: Write the failing tests**

Ajouter à `frontend/lib/api/sse.test.ts`, dans le `describe("importEventStream", ...)` existant (après le test « parse des frames SSE… », avant la fermeture du describe) :

```ts
  it("envoie single_heat dans le corps POST (#698)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFromChunks(['data: {"phase":"done","imported":0,"skipped":0,"total":0}\n\n']),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    for await (const _ of importEventStream("http://x", undefined, false)) { /* noop */ }

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      url: "http://x", single_heat: false,
    });
    vi.unstubAllGlobals();
  });

  it("single_heat vaut true par défaut si omis", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: streamFromChunks(['data: {"phase":"done","imported":0,"skipped":0,"total":0}\n\n']),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    for await (const _ of importEventStream("http://x")) { /* noop */ }

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      url: "http://x", single_heat: true,
    });
    vi.unstubAllGlobals();
  });
```

(`for await` sur une variable non utilisée : ajouter `// eslint-disable-next-line @typescript-eslint/no-unused-vars` juste au-dessus de chaque boucle, comme au test « lève une erreur si la réponse n'est pas ok » du même fichier.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run lib/api/sse.test.ts`
Expected: FAIL — le corps envoyé ne porte pas encore `single_heat`.

- [ ] **Step 3: Implement**

Dans `frontend/lib/api/sse.ts`, remplacer la signature et le corps de `importEventStream` (lignes 36-45) :

```ts
export async function* importEventStream(
  url: string,
  signal?: AbortSignal,
  singleHeat: boolean = true,
): AsyncGenerator<ImportProgressEvent> {
  const res = await fetch(`${BASE}/scrape/event/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, single_heat: singleHeat }),
    signal,
  });
```

Dans `frontend/hooks/useImportStream.ts`, remplacer la signature de `start` :

```ts
  const start = useCallback(async (url: string, singleHeat: boolean = true) => {
```

et l'appel à `importEventStream` à l'intérieur :

```ts
      for await (const ev of importEventStream(url, controle.signal, singleHeat)) {
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run lib/api/sse.test.ts hooks/useImportStream.test.ts`
Expected: tous PASS (les tests existants de `useImportStream.test.ts` appellent `start(url)` à un seul argument — inchangés, `singleHeat` valant `true` par défaut).

- [ ] **Step 5: Commit**

```bash
cd frontend
git add lib/api/sse.ts hooks/useImportStream.ts lib/api/sse.test.ts
git commit -m "feat(scrape): propage singleHeat d'useImportStream à l'API (#698)"
```

---

## Task 6: `TcnScrapeForm` — contrôle « import unique / fanout complet »

**Files:**
- Modify: `frontend/lib/api/client.ts` (`apiClient.detectProvider`)
- Modify: `frontend/components/scrape/TcnScrapeForm.tsx` (état + JSX + `submit`)
- Modify: `frontend/components/scrape/TcnScrapeForm.test.tsx:257, 479` (2 assertions à étoffer d'un second argument)
- Test: `frontend/components/scrape/TcnScrapeForm.test.tsx` (nouveau describe)

**Interfaces:**
- Consumes: `useImportStream().start(url, singleHeat)` (Task 5), réponse `GET /scrape/detect` élargie (Task 3, via `apiClient.detectProvider`).
- Produces: contrôle visible uniquement quand `fanout === true`, `singleHeat` initialisé à `default_single_heat` à chaque détection, envoyé à `importStream.start`.

- [ ] **Step 1: Write the failing tests**

Dans `frontend/lib/api/client.ts`, élargir le type de retour de `detectProvider` (nécessaire pour que les nouveaux tests typent) — remplacer :

```ts
  detectProvider: (url: string) =>
    request<{ provider: string; supported: boolean }>(
      `/scrape/detect${toQuery({ url })}`,
    ),
```

par :

```ts
  detectProvider: (url: string) =>
    request<{
      provider: string; supported: boolean;
      fanout?: boolean; default_single_heat?: boolean;
    }>(`/scrape/detect${toQuery({ url })}`),
```

(Champs optionnels : les tests existants mockent `{provider, supported}` seul, sans les deux nouveaux champs — ils restent valides.)

Dans `frontend/components/scrape/TcnScrapeForm.test.tsx`, corriger les deux assertions existantes qui portent sur un seul argument de `importMock.start` (`fanout` absent du mock par défaut → `singleHeat` retombe sur `true`) :

Ligne 257, remplacer :

```ts
    expect(importMock.start).toHaveBeenCalledWith("https://www.klikego.com/resultats/x");
```

par :

```ts
    expect(importMock.start).toHaveBeenCalledWith("https://www.klikego.com/resultats/x", true);
```

Ligne 479, même remplacement (occurrence identique, `replace_all` couvre les deux à la fois).

Puis ajouter un nouveau describe, après le describe `"TcnScrapeForm — un seul verdict avant d'essayer (#492, ACT-6)"` (après la ligne 391, avant `describe("TcnScrapeForm — le champ URL au doigt (#492, ACT-5)"...)`) :

```ts
describe("TcnScrapeForm — portée de l'import (#698)", () => {
  it("n'affiche pas le contrôle pour un provider sans fanout", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "timepulse", supported: true, fanout: false, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://timepulse.fr/x");
    await waitFor(() => expect(apiClient.detectProvider).toHaveBeenCalled());
    expect(screen.queryByRole("radiogroup", { name: /Portée de l'import/ })).not.toBeInTheDocument();
  });

  it("affiche le contrôle et pré-coche « import unique » quand le serveur le recommande", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "wiclax", supported: true, fanout: true, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://wiclax-results.com/x");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /uniquement cette page/ })).toBeChecked(),
    );
    expect(screen.getByRole("radio", { name: /tout l.événement/ })).not.toBeChecked();
  });

  it("pré-coche « fanout complet » quand le serveur le recommande (Klikego sans sélecteur)", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "klikego", supported: true, fanout: true, default_single_heat: false,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://www.klikego.com/resultats/foo/1");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /tout l.événement/ })).toBeChecked(),
    );
    await userEvent.click(screen.getByRole("button", { name: /Enregistrer les résultats/ }));
    expect(importMock.start).toHaveBeenCalledWith(
      "https://www.klikego.com/resultats/foo/1", false,
    );
  });

  it("permet de basculer vers le fanout complet, et `start` reçoit `false`", async () => {
    vi.mocked(apiClient.detectProvider).mockResolvedValue({
      provider: "wiclax", supported: true, fanout: true, default_single_heat: true,
    });
    renderForm();
    await userEvent.type(champUrl(), "https://wiclax-results.com/x");
    await waitFor(() =>
      expect(screen.getByRole("radio", { name: /tout l.événement/ })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("radio", { name: /tout l.événement/ }));
    await userEvent.click(screen.getByRole("button", { name: /Enregistrer les résultats/ }));
    expect(importMock.start).toHaveBeenCalledWith("https://wiclax-results.com/x", false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run components/scrape/TcnScrapeForm.test.tsx`
Expected: FAIL sur les 2 assertions étoffées (arité) et sur les 4 nouveaux tests (aucun `radiogroup` rendu).

- [ ] **Step 3: Implement**

Dans `frontend/components/scrape/TcnScrapeForm.tsx`, remplacer le bloc état (lignes 30-37) :

```tsx
  const [providerUnsupported, setProviderUnsupported] = useState(false);
  const handleProviderDetected = useCallback(
    (detected: { provider: string; supported: boolean } | null) => {
      setProviderUnsupported(detected !== null && !detected.supported);
    },
    [],
  );
```

par :

```tsx
  const [providerUnsupported, setProviderUnsupported] = useState(false);
  // Portée de l'import (#698) : le contrôle ne s'affiche que si `fanout` est
  // vrai, et `singleHeat` est réinitialisé au défaut serveur à chaque
  // nouvelle détection — le front ne recalcule jamais ce défaut lui-même,
  // même principe que `providerUnsupported`.
  const [fanout, setFanout] = useState(false);
  const [singleHeat, setSingleHeat] = useState(true);
  const handleProviderDetected = useCallback(
    (
      detected: {
        provider: string;
        supported: boolean;
        fanout?: boolean;
        default_single_heat?: boolean;
      } | null,
    ) => {
      setProviderUnsupported(detected !== null && !detected.supported);
      setFanout(detected?.fanout ?? false);
      setSingleHeat(detected?.default_single_heat ?? true);
    },
    [],
  );
```

Remplacer `submit` :

```tsx
  const submit = useCallback(() => {
    const v = url.trim();
    if (!v || running) return;
    if (!isHttpUrl(v)) return;
    // La touche Entrée ne contourne pas le bouton désactivé : sans cette garde,
    // le clavier lance l'import que le verdict vient d'exclure (ACT-6).
    if (providerUnsupported) return;
    reportedRef.current = null;
    refreshedRef.current = null;
    soumiseRef.current = v;
    setManual(false);
    setSecondes(0);
    setSaved(null);
    captureEvent("results_import_started", { url: v });
    importStream.start(v, singleHeat);
  }, [url, running, providerUnsupported, singleHeat, importStream]);
```

Puis, dans le JSX, insérer le contrôle juste après le `<div style={{ marginTop: 8 }}>` qui enveloppe `<ProviderDetector />` (donc entre sa balise fermante et le commentaire `{/* providerUnsupported dans disabled… */}` qui précède le `<Button>`) :

```tsx
            {fanout && (
              <div
                role="radiogroup"
                aria-label="Portée de l'import"
                style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4, fontSize: 14 }}
              >
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="radio"
                    name="scrape-scope"
                    checked={singleHeat}
                    onChange={() => setSingleHeat(true)}
                    disabled={running}
                  />
                  Importer uniquement cette page
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input
                    type="radio"
                    name="scrape-scope"
                    checked={!singleHeat}
                    onChange={() => setSingleHeat(false)}
                    disabled={running}
                  />
                  Importer tout l&apos;événement (toutes ses épreuves)
                </label>
              </div>
            )}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run components/scrape/TcnScrapeForm.test.tsx`
Expected: tous PASS.

- [ ] **Step 5: Full frontend regression + typecheck**

Run: `cd frontend && npm test`
Expected: 0 FAIL.

Run: `cd frontend && npm run build`
Expected: build OK (TypeScript strict + RSC) — vérifie que les champs optionnels de `detectProvider` et le nouvel état ne cassent aucun typage ailleurs.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add lib/api/client.ts components/scrape/TcnScrapeForm.tsx components/scrape/TcnScrapeForm.test.tsx
git commit -m "feat(scrape): ajoute le choix import unique / fanout complet à TcnScrapeForm (#698)"
```

---

## Final checklist

- [ ] `cd backend && uv run pytest -m "not integration"` — 0 FAIL (hors échecs pré-existants sans rapport)
- [ ] `cd backend && uv run ruff check .` — clean
- [ ] `cd frontend && npm test` — 0 FAIL
- [ ] `cd frontend && npm run lint` — clean
- [ ] `cd frontend && npm run build` — OK
- [ ] Vérification manuelle (`npm run dev` + backend) : coller une URL Wiclax/RaceResult → contrôle visible, « import unique » coché ; coller une URL Klikego nue → contrôle visible, « fanout complet » coché ; coller une URL Klikego `?heat=` → « import unique » coché ; coller une URL Timepulse/Competitor → aucun contrôle.
- [ ] Suivre `superpowers:requesting-code-review` → `superpowers:verification-before-completion` → `superpowers:finishing-a-development-branch` (la branche touche `frontend/` : insérer `ui-ux-review` après la revue de code, sur déclenchement de l'utilisateur).
