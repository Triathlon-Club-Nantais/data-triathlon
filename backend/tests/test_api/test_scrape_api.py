import json
from datetime import date

import pytest

from app.scrapers.base import ScrapedResult


def _result(bib, nom):
    return ScrapedResult(
        source_url="http://detail",
        provider="klikego",
        athlete_name=nom,
        athlete_firstname="Jean",
        bib_number=bib,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        total_time="01:59:00",
    )


def test_detect(client):
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://www.klikego.com/x"})
    assert resp.json() == {
        "provider": "klikego", "supported": True,
        "fanout": True, "default_single_heat": False,
    }


@pytest.mark.parametrize(
    ("url", "provider", "fanout", "default_single_heat"),
    [
        ("https://www.ironman.com/races/im703-vichy/results", "competitor", False, True),
        ("https://my.raceresult.com/406211/results", "raceresult", True, False),
        ("https://chronoplace.fr/evenement/x", "chronoplace", True, False),
    ],
)
def test_detect_expose_le_support_des_providers_recents(
    client, url, provider, fanout, default_single_heat,
):
    """`supported` est dérivé du registre, jamais d'une liste à tenir à jour.

    Le front affichait « Non supporté (competitor) » sur une URL ironman.com :
    il portait sa propre liste de providers, figée à six noms — Competitor,
    RaceResult et Chronoplace en étaient absents (même piège de définition
    dupliquée que #76). C'est l'API qui tranche désormais.

    `fanout`/`default_single_heat` (#698) : Competitor n'est pas fan-out, donc
    `default_single_heat` y vaut `True` (rien à fan-outer). RaceResult et
    Chronoplace le sont, et n'ont aucun sélecteur de sous-unité dans leur URL :
    leur `single_heat=True` rendrait le même volume de participants que le
    fan-out en perdant la `source_url` par sous-unité et son cache — le défaut
    y est donc `False`, c'est-à-dire le fan-out (revue finale #698).
    """
    resp = client.get("/api/v1/scrape/detect", params={"url": url})
    assert resp.json() == {
        "provider": provider, "supported": True,
        "fanout": fanout, "default_single_heat": default_single_heat,
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


def test_detect_expose_default_single_heat_vrai_prolivesport_avec_race(client):
    """URL ProLiveSport portant un jeton `race` : `scrape_event_all` cible et
    filtre cette course, le front peut pré-cocher « import unique » (#698)."""
    resp = client.get(
        "/api/v1/scrape/detect",
        params={
            "url": (
                "https://www.prolivesport.fr/index.php"
                "?chap=event&sub=liveV3&eventId=979&race=Triathlon%20M"
            )
        },
    )
    assert resp.json() == {
        "provider": "prolivesport", "supported": True,
        "fanout": True, "default_single_heat": True,
    }


def test_detect_expose_default_single_heat_faux_prolivesport_sans_race(client):
    """URL ProLiveSport sans jeton `race` : `_resolve_race` retomberait sur la
    première course de l'événement — un défaut, pas une cible choisie. Le
    fan-out reste donc le défaut proposé (#698)."""
    resp = client.get(
        "/api/v1/scrape/detect",
        params={
            "url": "https://www.prolivesport.fr/index.php?chap=event&sub=liveV3&eventId=979"
        },
    )
    assert resp.json() == {
        "provider": "prolivesport", "supported": True,
        "fanout": True, "default_single_heat": False,
    }


def test_detect_prolivesport_url_de_serie_ne_leve_pas_500(client):
    """`prolivesport._parse_url` **lève** sur une page de série (aucun
    `eventId`). `targets_single_heat` avale ce refus : la détection répond, et
    c'est le scrape qui expliquera pourquoi cette URL n'est pas importable."""
    resp = client.get(
        "/api/v1/scrape/detect",
        params={"url": "https://www.prolivesport.fr/fftri/grand-prix-duathlon"},
    )
    assert resp.status_code == 200
    assert resp.json()["default_single_heat"] is False


def test_detect_raceresult_avec_contest_dans_url_reste_fanout(client):
    """Un `contest=` dans l'URL RaceResult ne change **rien** au scrape.

    Vérifié en revue finale de #698 : `raceresult.scrape_event_all(url)` passe
    par `_run_pipeline`, qui ne lit de l'URL que l'identifiant d'épreuve
    (`_resolve_event_id`) et énumère ensuite **toutes** les listes annoncées par
    la config. Le contest de l'URL n'est jamais parsé, donc `single_heat=True`
    rendrait le même volume qu'un fan-out en perdant le découpage par contest.
    Le défaut reste le fan-out, avec ou sans ce paramètre.
    """
    resp = client.get(
        "/api/v1/scrape/detect",
        params={"url": "https://my.raceresult.com/406211/results?contest=3"},
    )
    assert resp.json() == {
        "provider": "raceresult", "supported": True,
        "fanout": True, "default_single_heat": False,
    }


def test_detect_masque_la_bascule_sur_une_url_breizhchrono_deja_ciblee(client):
    """URL BreizhChrono fixant déjà un heat → `fanout: false`, donc pas de choix.

    `BreizhChronoProvider.scrape_event_all` teste `if heat or single_heat:` :
    sur une telle URL, il fait le scrape mono-heat **même** avec
    `single_heat=False`. Offrir « tout l'événement » serait donc un mensonge —
    la réponse masque le contrôle plutôt que de laisser le backend ignorer le
    choix en silence (revue finale #698). Le provider reste bel et bien un
    `FanoutProvider` : c'est le contrat de la réponse qui change, pas le
    registre.
    """
    resp = client.get(
        "/api/v1/scrape/detect",
        params={
            "url": (
                "https://resultats.breizhchrono.com/resultats-courses"
                "/tri-mesquer-2026-42/triathlon-m"
            )
        },
    )
    assert resp.json() == {
        "provider": "breizhchrono", "supported": True,
        "fanout": False, "default_single_heat": True,
    }


def test_detect_sur_host_ipv6_malforme_ne_leve_pas_500(client):
    """Un host IPv6 malformé reste un 422 de Pydantic, jamais une 500.

    Avant #634, cette entrée passait la porte (`url: str`) et atterrissait sur
    `WiclaxProvider.matches`, protégé par son propre `urlparse` (finding
    Important n°2, revue #49 — toujours couvert par `test_registry.py` et
    `test_import_service.py` au niveau du registre). Depuis #634, `HttpUrl`
    rejette la forme avant même d'atteindre le registre."""
    resp = client.get("/api/v1/scrape/detect", params={"url": "https://[oops/x"})
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://169.254.169.254/",
        "javascript:alert(1)",
        "pas-une-url",
        "",
    ],
)
def test_detect_schema_non_http_rejete_a_la_porte(client, url):
    """422 de Pydantic, même patron que `test_schema_non_http_rejete_a_la_porte`
    pour `/scrape/event` (#49) — appliqué ici par #634."""
    resp = client.get("/api/v1/scrape/detect", params={"url": url})
    assert resp.status_code == 422


def test_providers_derive_du_registre(client):
    """Le sélecteur de fournisseur du batch lit cette route, pas une liste en dur.

    Même source que la validation de `--provider` : `playwright` en est donc
    absent (fallback, pas cible), et un provider ajouté au registre y apparaît
    sans toucher au front.
    """
    from app.scrapers import provider_names

    noms = client.get("/api/v1/scrape/providers").json()["providers"]
    assert noms == provider_names()
    assert "klikego" in noms
    assert "playwright" not in noms


def test_import_event(client, monkeypatch):
    from app.services import import_service

    monkeypatch.setattr(
        import_service, "registry_scrape_event_all",
        lambda url, **kwargs: [_result("1", "DUPONT"), _result("2", "MARTIN")],
    )
    resp = client.post("/api/v1/scrape/event", json={"url": "https://www.klikego.com/x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 2
    assert body["updated"] == 0
    assert body["skipped"] == 0
    assert body["cached"] is False
    # Une seule Course pour deux participants au même triathlon.
    assert len(body["courses"]) == 1
    assert body["courses"][0]["name"] == "Triathlon de Nantes"
    assert body["courses"][0]["event_type"] == "triathlon-m"


def test_import_event_stream_serializes_reassignments(client, monkeypatch):
    """Régression : la phase `done` du SSE porte des `Reassignment` (dataclass
    frozen, non sérialisable par `json.dumps` nu) dès qu'une réconciliation a
    eu lieu. Sans le `default=` sur `json.dumps` dans scrape.py, ce test
    échoue avec un TypeError (« Object of type Reassignment is not JSON
    serializable ») levé pendant la consommation du flux.
    """
    from app.services import import_service

    def fake_iter_import_event(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        yield {
            "phase": "done",
            "imported": 1,
            "skipped": 0,
            "reconciled": 1,
            "reassignments": [
                import_service.Reassignment(
                    ancien="DUPOND | Jean", nouveau="DUPONT | Jean", fusion=True
                ),
            ],
            "total": 1,
        }

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)

    with client.stream(
        "POST", "/api/v1/scrape/event/stream", json={"url": "https://www.klikego.com/x"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    frames = [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    done = next(f for f in frames if f["phase"] == "done")
    assert done["reassignments"] == [
        {"ancien": "DUPOND | Jean", "nouveau": "DUPONT | Jean", "fusion": True}
    ]


def test_import_event_stream_emet_un_padding_initial(client, monkeypatch):
    """Le SSE ouvre par ~2 KB de padding pour casser le buffering navigateur.

    Sans lui, Chrome/Firefox retiennent le body du `fetch()` jusqu'à ~1-2 KB
    avant de rendre le premier chunk lisible via `Response.body.getReader()`.
    Un import Klikego fan-out qui met 35 s à émettre son 1er événement
    utile paraît alors bloqué côté UI (« Récupération des participants… »
    figé). Contrat vérifié : la première ligne du body commence par `:`
    (commentaire SSE, ignoré par le parseur) et pèse au moins 2 KB.
    """
    from app.services import import_service

    def fake_iter_import_event(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "done", "imported": 0, "updated": 0, "skipped": 0,
               "reconciled": 0, "reassignments": [], "total": 0, "courses": []}

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)

    with client.stream(
        "POST", "/api/v1/scrape/event/stream", json={"url": "https://www.klikego.com/x"}
    ) as resp:
        assert resp.status_code == 200
        # `Content-Encoding: identity` bloque la compression gzip par le proxy
        # Next.js dev — sinon les 8 events fan-out sortaient bufférisés dans
        # le compresseur pendant 4 s. `no-transform` du Cache-Control est le
        # second garde de RFC 7234.
        assert resp.headers.get("content-encoding") == "identity"
        assert "no-transform" in resp.headers.get("cache-control", "")
        body = "".join(resp.iter_text())

    # Le padding est la première frame (avant le premier `data: …`) et fait
    # au moins 2 KB pour dépasser le seuil de flush des navigateurs.
    first_frame = body.split("\n\n", 1)[0]
    assert first_frame.startswith(":"), "premier chunk = commentaire SSE"
    assert len(first_frame) >= 2048, (
        f"padding trop court ({len(first_frame)} octets) — les navigateurs "
        "retiennent ~1-2 KB avant de rendre le premier chunk lisible"
    )


def test_import_event_stream_emet_un_battement_sur_phase_longue(client, monkeypatch):
    """Sans mécanisme de heartbeat, une pause entre deux phases (#705 — scraping
    fan-out ralenti, ou persistance lente) laisse le flux SSE totalement
    silencieux assez longtemps pour qu'un proxy d'infra (Vercel/Render) coupe
    la connexion pour inactivité, sans que le flux n'atteigne jamais `done` ni
    `error` côté client. Contrat : une ligne de commentaire SSE (`: heartbeat`,
    ignorée par le parseur front comme le padding initial) est émise si aucun
    événement métier n'arrive dans l'intervalle configuré.
    """
    import time as time_module

    from app.api.v1 import scrape
    from app.services import import_service

    monkeypatch.setattr(scrape, "_SSE_HEARTBEAT_INTERVAL_SECONDS", 0.05)

    def fake_iter_import_event(db, url, settings, force=False, persist=True):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        time_module.sleep(0.2)  # > intervalle de battement : simule la pause
        yield {"phase": "done", "imported": 0, "updated": 0, "skipped": 0,
               "reconciled": 0, "reassignments": [], "total": 0, "courses": []}

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)

    with client.stream(
        "POST", "/api/v1/scrape/event/stream", json={"url": "https://www.klikego.com/x"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    frames = body.split("\n\n")
    heartbeats = [f for f in frames if f.strip() == ": heartbeat"]
    assert heartbeats, "aucun battement émis pendant la pause"


def test_import_event_stream_emet_error_si_iter_import_event_leve(client, monkeypatch):
    """Le thread producteur du battement (#705) ne doit pas avaler une
    exception inattendue en cours d'itération : sans phase `error` émise,
    le flux se termine en 200 bien formé mais tronqué (ni `done` ni `error`),
    et `useImportStream` reste bloqué sur « running: true » indéfiniment —
    pire que l'ancien comportement, où la même exception coupait la connexion
    et remontait comme une panne réseau côté client.
    """
    from app.services import import_service

    def fake_iter_import_event(db, url, settings, force=False, persist=True):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        raise RuntimeError("boom")

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)

    with client.stream(
        "POST", "/api/v1/scrape/event/stream", json={"url": "https://www.klikego.com/x"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    frames = [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert frames[-1]["phase"] == "error"


def test_import_event_stream_expose_les_courses_touchees(client, monkeypatch):
    """Le SSE `done` porte `courses: [{id, name, event_type}]` — le front en
    tire des boutons « Voir les résultats » (#135). Contrat stable : présent
    aussi bien sur l'import réel que sur le court-circuit cache.

    On monkeypatche `iter_import_event` (comme `…serializes_reassignments`
    juste au-dessus) plutôt que le scraper : le SSE utilise `SessionLocal()`
    en dur, hors du `Depends(get_db)`, donc l'override de conftest ne s'y
    applique pas — laisser `_cached_result` tourner ferait taper la vraie
    base (« no such table: courses » en CI). La sérialisation par
    `json.dumps(default=…)` est déjà couverte par ce voisin.
    """
    from app.services import import_service

    def fake_iter_import_event(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "scraping", "message": "Récupération des participants…"}
        yield {
            "phase": "done",
            "imported": 2,
            "updated": 0,
            "skipped": 0,
            "reconciled": 0,
            "reassignments": [],
            "total": 2,
            "courses": [
                {"id": 42, "name": "Triathlon de Nantes", "event_type": "triathlon-m"},
            ],
        }

    monkeypatch.setattr(import_service, "iter_import_event", fake_iter_import_event)

    with client.stream(
        "POST", "/api/v1/scrape/event/stream", json={"url": "https://www.klikego.com/x"}
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    frames = [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    done = next(f for f in frames if f["phase"] == "done")
    assert len(done["courses"]) == 1
    course = done["courses"][0]
    assert set(course) == {"id", "name", "event_type"}
    assert course["name"] == "Triathlon de Nantes"
    assert course["event_type"] == "triathlon-m"


def test_import_event_expose_updated_counter(client, monkeypatch):
    """Le compteur `updated` (upsert) doit être exposé dans la réponse — pas seulement
    calculé en interne : `ImportResult` doit le déclarer, sinon Pydantic le tait."""
    from app.services import import_service

    monkeypatch.setattr(
        import_service, "registry_scrape_event_all",
        lambda url, **kwargs: [_result("1", "DUPONT")],
    )
    resp = client.post("/api/v1/scrape/event", json={"url": "https://www.klikego.com/x"})
    assert resp.status_code == 200
    body = resp.json()
    assert "updated" in body
    assert body["imported"] == 1
    assert body["updated"] == 0
    assert body["skipped"] == 0
    assert body["cached"] is False


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

    def fake_scrape(url, **kwargs):
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


@pytest.mark.parametrize("url, attendu", [
    # Port par défaut supprimé — cas réel, cf. `_ROUTAGE_LEGITIME` de test_registry.py.
    (
        "https://my.raceresult.com:443/399938/results",
        "https://my.raceresult.com/399938/results",
    ),
    # Espaces du chemin percent-encodés.
    (
        "https://chronosmetron.wiclax-results.com/Triathlon de la Roche 2026/",
        "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    ),
    # Caractères non-ASCII percent-encodés.
    (
        "https://www.klikego.com/résultats/été",
        "https://www.klikego.com/r%C3%A9sultats/%C3%A9t%C3%A9",
    ),
])
def test_httpurl_normalise_la_cle_de_cache(url, attendu):
    """Épingle la normalisation de `HttpUrl` (mesurée sur pydantic 2.13.4) :
    `source_url` en dérive sur ces trois familles d'entrée. Pas un bug — le
    commentaire de `ScrapeRequest.url` documente la conséquence exacte (cache
    TTL inefficace sur ces URLs, mais pas de doublon de course) — mais si
    pydantic change de comportement, ce test doit le signaler."""
    from app.schemas.scrape import ScrapeRequest

    assert str(ScrapeRequest(url=url).url) == attendu


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
