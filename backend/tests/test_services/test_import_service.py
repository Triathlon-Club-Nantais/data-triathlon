from collections import Counter
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.exceptions import ProviderNotSupportedError
from app.core.time import utcnow
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.scrapers.base import FanoutTrace, ScrapedResult
from app.services import admin_actions, import_service, quality


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(bib, nom, prenom="Jean", **kw) -> ScrapedResult:
    # `source_url` = URL de l'épreuve importée, comme le posent tous les
    # scrapers réels sur chacun de leurs résultats. Depuis #156,
    # `mapping.get_or_create_course` la retient en priorité pour `Course.source_url`
    # (clé de cache TTL) — un placeholder distinct (l'ancien "http://detail")
    # casserait le cache re-scrape de `_cached_result`.
    base = dict(
        source_url=URL,
        provider="klikego",
        athlete_name=nom,
        athlete_firstname=prenom,
        bib_number=bib,
        event_name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        total_time="01:59:00",
    )
    base.update(kw)
    return ScrapedResult(**base)


URL ="https://www.klikego.com/resultats/event/123"


def _counters(out: dict) -> dict:
    """Sous-ensemble compteurs, indépendant du reste du contrat.

    Les tests historiques comparent `imported`/`updated`/`skipped`/`reconciled` en
    dict strict — ajouter `courses` (#135) casserait chacun sans rien apprendre.
    Ce filtre garde le sens (l'assertion porte sur les seuls compteurs) et laisse
    le contrat s'étendre sans re-toucher les tests.
    """
    return {k: out[k] for k in ("imported", "updated", "skipped", "reconciled")}


def test_import_creates_entities(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 2, "updated": 0, "skipped": 0, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_import_ne_resout_la_course_qu_une_fois_par_lot(db_session, patch_scraper, monkeypatch):
    """`_Persister.add()` doit consulter son cache avant `mapping.get_or_create_course` (#759).

    Sans cache, chaque participation d'une même course re-résout la course depuis
    zéro (doublon, get_or_create, attach) — mesuré à ~7000 requêtes sur une course
    à 2396 participants en prod.
    """
    original = import_service.mapping.get_or_create_course
    appels = []

    def _compte(db, scraped, event_url):
        appels.append(scraped.bib_number)
        return original(db, scraped, event_url)

    monkeypatch.setattr(import_service.mapping, "get_or_create_course", _compte)

    patch_scraper([_result(str(i), "DUPONT", prenom=f"P{i}") for i in range(5)])
    import_service.import_event(db_session, URL, _settings())

    assert len(appels) == 1


def test_reimport_is_cached_and_skips(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    import_service.import_event(db_session, URL, _settings())

    # 2e import immédiat → court-circuité par le cache TTL
    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert out["imported"] == 0
    assert out["skipped"] == 2


def test_reimport_after_cache_dedups_by_bib(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Force l'expiration du cache → re-scrape, mais le dossard 1 existe déjà
    course = course_repository.get_latest_by_source_url(db_session, URL)
    course.scraped_at = utcnow() - timedelta(days=40)
    db_session.flush()

    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 1, "updated": 0, "skipped": 1, "reconciled": 0}


def test_reimport_respecte_un_club_corrige_a_la_main(db_session, patch_scraper):
    """#439, SC-008 — la correction manuelle du club survit à un réimport complet.

    Les deux coureurs de l'épreuve sont traités par le **même** appel de
    `resolve` : celui dont le club a été corrigé garde sa valeur, l'autre suit le
    chronométreur. C'est le seul test qui éprouve l'invariant sur le chemin réel
    d'import plutôt que sur le repository seul.
    """
    patch_scraper(
        [
            _result("1", "VERROU", prenom="Vera", club="ASPTT NANTES"),
            _result("2", "SUIVEUR", prenom="Sam", club="ASPTT NANTES"),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    auteur = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    verrouille = athlete_repository.get_by_identity(db_session, "VERROU", "Vera", None)
    admin_actions.update_athlete(
        db_session,
        athlete_id=verrouille.id,
        champs={"club": "TRI CLUB NANTAIS"},
        user_id=auteur.id,
    )

    # Le chronométreur, lui, ignore la correction et publie son propre libellé.
    patch_scraper(
        [
            _result("1", "VERROU", prenom="Vera", club="ASPTT NANTES 44"),
            _result("2", "SUIVEUR", prenom="Sam", club="ASPTT NANTES 44"),
        ]
    )
    import_service.import_event(db_session, URL, _settings(), force=True)

    assert athlete_repository.get(db_session, verrouille.id).club == "TRI CLUB NANTAIS"
    suiveur = athlete_repository.get_by_identity(db_session, "SUIVEUR", "Sam", None)
    assert suiveur.club == "ASPTT NANTES 44"


def test_reimport_backfills_empty_gender_but_keeps_known_one(db_session, patch_scraper):
    """#964: batch resolution fills an empty gender from a later import and
    never overwrites a gender already set, same rule as `resolve`."""
    patch_scraper(
        [
            _result("1", "SANSEXE", prenom="Alex", gender=""),
            _result("2", "GENRE", prenom="Lou", gender="M"),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    patch_scraper(
        [
            _result("1", "SANSEXE", prenom="Alex", gender="F"),
            _result("2", "GENRE", prenom="Lou", gender="F"),
        ]
    )
    import_service.import_event(db_session, URL, _settings(), force=True)

    assert athlete_repository.get_by_identity(db_session, "SANSEXE", "Alex", None).gender == "F"
    assert athlete_repository.get_by_identity(db_session, "GENRE", "Lou", None).gender == "M"


def test_import_calcule_l_indice_de_fiabilite(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT", rank_overall=1), _result("2", "MARTIN", rank_overall=2)])
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    assert course.is_reliable is True
    assert course.quality_issues == {}


def test_import_denormalise_les_compteurs_de_participants(db_session, patch_scraper):
    """#623 — `_Persister.finalize` écrit `participation_count`/`tcn_count`,
    même patron que l'indice de fiabilité juste au-dessus : c'est ce qui
    permet à `GET /courses/events` de les lire sans plus jamais joindre
    `participations`."""
    patch_scraper([
        _result("1", "DUPONT", rank_overall=1, club="Triathlon Club Nantais"),
        _result("2", "MARTIN", rank_overall=2, club="ASPTT"),
    ])
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    assert course.participation_count == 2
    assert course.tcn_count == 1


def test_import_denormalise_exclut_une_participation_en_attente_preexistante(
    db_session, patch_scraper
):
    """Une saisie manuelle en attente (#270) sur la même épreuve, préexistante
    à l'import, n'entre dans aucun des deux compteurs — sa seule sortie est
    `admin_actions.validate_participation`, jamais un import."""
    course = course_repository.get_or_create(
        db_session, name="Triathlon de Nantes", event_date=date(2026, 5, 16),
        event_type="triathlon-m", source_url=URL, provider="klikego",
    )
    athlete = athlete_repository.get_or_create(
        db_session, nom="ATTENTE", prenom="Léa", club="Triathlon Club Nantais"
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="99",
        club="Triathlon Club Nantais", is_pending_validation=True,
    )
    db_session.flush()
    patch_scraper([_result("1", "DUPONT", rank_overall=1, club="ASPTT")])

    # `force=True` : `get_or_create` ci-dessus vient de poser `scraped_at` à
    # maintenant (défaut du modèle), donc la course est déjà « fraîche » —
    # sans lui, `_cached_result` court-circuiterait le scrape entièrement.
    import_service.import_event(db_session, URL, _settings(), force=True)

    db_session.refresh(course)
    assert course.participation_count == 1
    assert course.tcn_count == 0


def test_import_signale_une_course_suspecte(db_session, patch_scraper):
    # Dossard 1 en double dans la source → la 2e ligne est jetée, jamais persistée.
    # « DQ » est hors de la nomenclature finisher/DNF/DNS/DSQ.
    patch_scraper(
        [
            _result("1", "DUPONT", rank_overall=1),
            _result("1", "MARTIN"),
            _result("3", "DURAND", status="DQ", total_time=""),
        ]
    )
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 2, "updated": 0, "skipped": 1, "reconciled": 0}

    course = course_repository.get_latest_by_source_url(db_session, URL)
    assert course.is_reliable is False
    assert course.quality_issues == {
        quality.ANOMALY_DUPLICATE_BIB: 1,
        quality.ANOMALY_UNKNOWN_STATUS: 1,
    }


def test_reimport_apres_cache_ne_compte_pas_les_dossards_deja_en_base(
    db_session, patch_scraper
):
    """Un dossard déjà persisté est un skip bénin, pas un doublon de la source."""
    patch_scraper([_result("1", "DUPONT", rank_overall=1)])
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    course.scraped_at = utcnow() - timedelta(days=40)  # force l'expiration du cache
    db_session.flush()

    patch_scraper([_result("1", "DUPONT", rank_overall=1), _result("2", "MARTIN", rank_overall=2)])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 1, "updated": 0, "skipped": 1, "reconciled": 0}

    db_session.refresh(course)
    assert course.is_reliable is True
    assert course.quality_issues == {}


def _expire_cache(db_session, url=URL):
    """Vieillit la course pour forcer un vrai re-scraping au prochain import."""
    from datetime import timedelta

    from app.core.time import utcnow
    from app.repositories import course_repository

    course = course_repository.get_latest_by_source_url(db_session, url)
    course.scraped_at = utcnow() - timedelta(days=40)
    db_session.flush()


# ── Participations sans dossard — le dédoublonnage ne peut pas s'appuyer sur le bib
#
# Certains chronométreurs n'attribuent pas de dossard (Sportinnovation : 5 599
# participations sans bib, dont des finishers). Le repli se fait sur l'athlète,
# en multiset : la même personne peut légitimement figurer plusieurs fois dans
# la source (257 cas réels), et ces occurrences doivent survivre au réimport.

def test_import_sans_dossard_cree_les_participations(db_session, patch_scraper):
    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 2, "updated": 0, "skipped": 0, "reconciled": 0}


def test_reimport_sans_dossard_est_idempotent(db_session, patch_scraper):
    """Le bug : sans dossard, chaque réimport recréait les participations."""
    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "CASROUGE", "Patrice"), _result("", "HOCHET", "Joséphine")])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 0, "updated": 0, "skipped": 2, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_import_sans_dossard_conserve_les_homonymes(db_session, patch_scraper):
    """Deux lignes pour le même athlète sans dossard → deux participations."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 2, "updated": 0, "skipped": 0, "reconciled": 0}


def test_reimport_sans_dossard_conserve_le_nombre_d_homonymes(db_session, patch_scraper):
    """Réimport de 2 homonymes : ni doublon, ni perte — on reste à 2."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 0, "updated": 0, "skipped": 2, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def test_reimport_sans_dossard_ajoute_une_occurrence_supplementaire(db_session, patch_scraper):
    """La source gagne une 3e ligne pour le même athlète → une seule création."""
    patch_scraper([_result("", "LACOTTE", "Anais"), _result("", "LACOTTE", "Anais")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "LACOTTE", "Anais")] * 3)
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 1, "updated": 0, "skipped": 2, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 3


def test_reimport_melange_avec_et_sans_dossard(db_session, patch_scraper):
    """Les deux clés cohabitent sur une même course sans interférer."""
    patch_scraper([_result("1", "DUPONT"), _result("", "CASROUGE", "Patrice")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("1", "DUPONT"),                  # skip par dossard
        _result("", "CASROUGE", "Patrice"),      # skip par athlète
        _result("2", "MARTIN"),                  # nouveau, avec dossard
        _result("", "HOCHET", "Joséphine"),      # nouveau, sans dossard
    ])
    out = import_service.import_event(db_session, URL, _settings())
    assert _counters(out) == {"imported": 2, "updated": 0, "skipped": 2, "reconciled": 0}
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 4


def test_reimport_sans_dossard_unique_met_a_jour(db_session, patch_scraper):
    """Un athlète sans dossard en un seul exemplaire est mis à jour."""
    patch_scraper([_result("", "CASROUGE", "Patrice", total_time="01:10:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "CASROUGE", "Patrice", total_time="01:09:30")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 0, "updated": 1, "skipped": 0, "reconciled": 0}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert parts[0].total_time == "01:09:30"


def test_reimport_sans_dossard_ambigu_ne_met_pas_a_jour(db_session, patch_scraper):
    """Deux exemplaires du même athlète sans dossard : appariement impossible → skip,
    aucune valeur réécrite (comportement multiset conservé)."""
    patch_scraper([
        _result("", "LACOTTE", "Anais", total_time="01:20:00"),
        _result("", "LACOTTE", "Anais", total_time="01:20:00"),
    ])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("", "LACOTTE", "Anais", total_time="01:19:00"),
        _result("", "LACOTTE", "Anais", total_time="01:18:00"),
    ])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 0, "updated": 0, "skipped": 2, "reconciled": 0}

    times = sorted(
        p.total_time for p in participation_repository.list_participations(db_session, page_size=100)
    )
    assert times == ["01:20:00", "01:20:00"]  # inchangés : on ne devine pas l'appariement


def test_unsupported_provider_raises(db_session, monkeypatch):
    def _raise(url, **kwargs):
        raise ValueError("Import non supporté")

    monkeypatch.setattr(import_service, "registry_scrape_event_all", _raise)
    with pytest.raises(ProviderNotSupportedError):
        import_service.import_event(db_session, URL, _settings())


def test_force_bypasse_le_cache_ttl(db_session, patch_scraper):
    """Avec force=True, on re-scrape même si la course est fraîche (cache non expiré)."""
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Course fraîche → sans force, le cache court-circuite le re-scraping.
    out = import_service.import_event(db_session, URL, _settings())
    assert out.get("cached") is True

    # Avec force=True → re-scrape malgré la fraîcheur ; le dossard 2 est nouveau.
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 1, "updated": 0, "skipped": 1, "reconciled": 0}


def test_iter_import_event_force_bypasse_le_cache_ttl(db_session, patch_scraper):
    """Même garde que ci-dessus, mais sur le **générateur** — le chemin de prod.

    `rescrape-db` ne passe pas par `import_event` : `batch.run_batch` consomme
    `iter_import_event(force=True)`. C'est donc ici que se joue le bypass du
    cache TTL. Sans ce test, inverser la garde (`if not force:` → `if force:`)
    transformerait le rescrape en no-op silencieux sur toute course fraîche
    (bilan « Importées : 0 », indiscernable d'un rescrape sans nouveauté).
    """
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    # Course fraîche, sans force → le générateur court-circuite le scraping.
    phases = list(import_service.iter_import_event(db_session, URL, _settings()))
    assert [p["phase"] for p in phases] == ["done"]
    assert phases[-1]["cached"] is True

    # force=True → la phase `scraping` a bien lieu malgré la fraîcheur, et le
    # dossard 2 (nouveau) est importé : le cache n'a pas été consulté.
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])
    phases = list(
        import_service.iter_import_event(db_session, URL, _settings(), force=True)
    )
    assert "scraping" in [p["phase"] for p in phases]
    final = phases[-1]
    assert final["phase"] == "done"
    assert (final["imported"], final["skipped"]) == (1, 1)
    assert "cached" not in final
    assert len(participation_repository.list_participations(db_session, page_size=100)) == 2


def _patch_fanout_cache_probe_capture(monkeypatch):
    """Route un provider fan-out vers `registry_scrape_event_all` et capture le
    `cache_probe` qui lui est effectivement passé."""
    from app.scrapers import registry

    provider = registry.KlikegoProvider()
    provider.last_trace = FanoutTrace(heats_enumerated=1)
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: provider)

    captured = {}

    def fake_scrape(url, *, cache_probe=None, on_heat_start=None, **kwargs):
        captured["cache_probe"] = cache_probe
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)
    return captured


def test_import_event_force_desarme_le_cache_probe_fan_out(db_session, monkeypatch):
    """#810 — `force=True` doit aussi désarmer `cache_probe` (cache **par heat**),
    pas seulement le cache TTL global (`_cached_result`).

    Sans ça, `rescrape-db --url` sur une épreuve fan-out (Klikego, Wiclax,
    RaceResult…) scrapée il y a moins de 30 j saute silencieusement tous ses
    heats jugés frais : `updated: 0` alors qu'un rescrape a été explicitement
    demandé.
    """
    captured = _patch_fanout_cache_probe_capture(monkeypatch)

    import_service.import_event(db_session, URL, _settings(), force=True)

    assert captured["cache_probe"] is None


def test_import_event_sans_force_garde_le_cache_probe_fan_out(db_session, monkeypatch):
    """Contrôle négatif : sans `force`, `cache_probe` doit rester actif."""
    captured = _patch_fanout_cache_probe_capture(monkeypatch)

    import_service.import_event(db_session, URL, _settings())

    assert captured["cache_probe"] is not None


def test_iter_import_event_force_desarme_le_cache_probe_fan_out(db_session, monkeypatch):
    """Même garde que ci-dessus, sur le générateur — le chemin réellement
    consommé par `rescrape-db` (`batch.run_batch` → `iter_import_event`)."""
    captured = _patch_fanout_cache_probe_capture(monkeypatch)

    list(import_service.iter_import_event(db_session, URL, _settings(), force=True))

    assert captured["cache_probe"] is None


def test_iter_import_event_sans_force_garde_le_cache_probe_fan_out(db_session, monkeypatch):
    """Contrôle négatif : sans `force`, `cache_probe` doit rester actif."""
    captured = _patch_fanout_cache_probe_capture(monkeypatch)

    list(import_service.iter_import_event(db_session, URL, _settings()))

    assert captured["cache_probe"] is not None


# ── Garde-fou : une épreuve sans nom n'est jamais persistée ──────────────────


def test_import_refuses_event_without_name(db_session, patch_scraper):
    """Un scrape qui ne trouve pas le nom de l'épreuve échoue, sans rien écrire.

    Sans ce garde-fou, une course sans nom se retrouve en base (cas réel de la
    course 103, importée depuis une URL `coureur.jsp` sans slug) : illisible
    dans l'UI, et invisible à la recherche.
    """
    from app.core.exceptions import ScraperError

    patch_scraper([_result("1", "DUPONT", event_name=""), _result("2", "MARTIN", event_name="")])

    with pytest.raises(ScraperError):
        import_service.import_event(db_session, URL, _settings())

    assert course_repository.list_all(db_session) == []
    assert participation_repository.list_participations(db_session, page_size=100) == []


def test_iter_import_refuses_event_without_name(db_session, patch_scraper):
    """Même refus côté SSE : une phase `error` explicite, aucune course créée."""
    patch_scraper([_result("1", "DUPONT", event_name="")])

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert phases[-1]["phase"] == "error"
    assert "nom" in phases[-1]["message"].lower()
    assert course_repository.list_all(db_session) == []


# ── Réconciliation d'identité au re-scrape (issue #66) ───────────────────────

def test_dossard_connu_athlete_divergent_est_reconcilie(db_session, patch_scraper):
    """La graphie fautive stockée est réassignée vers la graphie corrigée."""
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())

    # Même dossard, identité corrigée. force=True : re-scrape malgré le cache frais.
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 1
    assert out["imported"] == 0
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("LE BERRE", "Audrey")


def test_dossard_connu_meme_athlete_reste_un_skip(db_session, patch_scraper):
    """Identité inchangée : aucune réassignation, `skipped` comme aujourd'hui."""
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    import_service.import_event(db_session, URL, _settings())

    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert out["skipped"] == 1


def test_reconciliation_fusionne_vers_un_athlete_existant(db_session, patch_scraper):
    """La cible corrigée existe déjà (autre course) → fusion, pas de création."""
    from app.repositories import athlete_repository

    # La graphie fautive, sur l'épreuve à re-scraper.
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())
    # La graphie correcte existe déjà, portée par une autre épreuve.
    url2 = "https://www.klikego.com/resultats/event/999"
    patch_scraper([_result("7", "LE BERRE", "Audrey", event_name="Autre Tri")])
    import_service.import_event(db_session, url2, _settings())

    nb_athletes = len(athlete_repository.search(db_session, page_size=500))

    # Re-scrape de la 1re épreuve : la graphie fautive fusionne vers l'existante.
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))
    done = phases[-1]

    assert done["reconciled"] == 1
    assert done["reassignments"][0].fusion is True
    assert done["reassignments"][0].ancien == "BERRE | Audrey LE"
    assert done["reassignments"][0].nouveau == "LE BERRE | Audrey"
    # Aucun athlète créé : fusion, pas renommage.
    assert len(athlete_repository.search(db_session, page_size=500)) == nb_athletes


def test_reconciliation_ne_vide_jamais_le_prenom(db_session, patch_scraper):
    """Garde des ambigus : une correction qui viderait le prénom est refusée."""
    # Prénom stocké en majuscules par un fournisseur à champs séparés.
    patch_scraper([_result("1", "BERGE", "LOLA")])
    import_service.import_event(db_session, URL, _settings())

    # Le re-scrape produirait ("LOLA BERGE", "") — destruction du prénom.
    patch_scraper([_result("1", "LOLA BERGE", "")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert out["skipped"] == 1
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("BERGE", "LOLA")


def test_reconciliation_refusee_ne_cree_pas_d_orphelin(db_session, patch_scraper):
    """Garde des ambigus : une réconciliation refusée (prénom vidé) ne crée
    aucune fiche d'athlète orpheline.

    Sur le chemin web/SSE (`persist=True`), rien ne balaie les orphelins avant
    le prochain `rescrape-db` : résoudre l'athlète corrigé *avant* la garde
    laissait donc une fiche « LOLA BERGE |  » commitée et vide en base.
    """
    from app.repositories import athlete_repository

    patch_scraper([_result("1", "BERGE", "LOLA")])
    import_service.import_event(db_session, URL, _settings())
    nb_athletes = len(athlete_repository.search(db_session, page_size=500))

    # Le re-scrape produirait ("LOLA BERGE", "") — correction refusée.
    patch_scraper([_result("1", "LOLA BERGE", "")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert len(athlete_repository.search(db_session, page_size=500)) == nb_athletes
    assert athlete_repository.get_by_identity(db_session, "LOLA BERGE", "", None) is None


def test_reconciliation_dossard_en_double_ne_compte_qu_une_fois(db_session, patch_scraper):
    """Anti double-comptage : 2 lignes source pour un dossard préexistant réconcilié
    → 1 seule réconciliation, quoi qu'il arrive aux valeurs.

    Les deux `skipped` sont sur l'autre axe (valeurs) : la 1re ligne n'a rien à
    corriger, la 2e est une contradiction de la source — même dossard, deux
    lignes dans un même scrape — donc perdue et comptée en anomalie de fiabilité.
    """
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())

    # Re-scrape : la graphie corrigée apparaît deux fois pour le même dossard.
    patch_scraper([_result("1", "LE BERRE", "Audrey"), _result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 1
    assert out["skipped"] == 2
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("LE BERRE", "Audrey")
    course = course_repository.get_latest_by_source_url(db_session, URL)
    assert course.quality_issues == {quality.ANOMALY_DUPLICATE_BIB: 1}


def test_reconciliation_renommage_a_le_flag_fusion_false(db_session, patch_scraper):
    """Renommage (cible corrigée créée, pas préexistante) → fusion is False."""
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())

    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))
    done = phases[-1]

    assert done["reconciled"] == 1
    assert done["reassignments"][0].fusion is False
    assert done["reassignments"][0].ancien == "BERRE | Audrey LE"
    assert done["reassignments"][0].nouveau == "LE BERRE | Audrey"


def test_persist_false_scrape_mais_n_ecrit_rien(db_session, patch_scraper):
    """Dry-run : le scrape a lieu, les compteurs sont calculés, rien n'est persisté."""
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])

    out = import_service.import_event(db_session, URL, _settings(), persist=False)

    assert out["imported"] == 2  # calculé
    db_session.expire_all()
    assert participation_repository.list_participations(db_session, page_size=100) == []
    assert course_repository.list_all(db_session) == []


def test_iter_persist_false_annule_la_transaction(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT")])

    phases = list(
        import_service.iter_import_event(db_session, URL, _settings(), persist=False)
    )

    assert phases[-1]["phase"] == "done"
    assert phases[-1]["imported"] == 1
    db_session.expire_all()
    assert participation_repository.list_participations(db_session, page_size=100) == []


# ── Upsert prudent par dossard — un réimport corrige les lignes existantes au
# lieu de les ignorer (fusion prudente : la source n'écrase que ses valeurs
# non vides).


def test_reimport_rafraichit_un_temps_corrige(db_session, patch_scraper):
    """Un temps corrigé à la source met à jour la participation existante."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=5)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:58:30", rank_overall=3)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 0, "updated": 1, "skipped": 0, "reconciled": 0}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert parts[0].total_time == "01:58:30"
    assert parts[0].rank_overall == 3


def test_reimport_valeur_vide_n_ecrase_pas(db_session, patch_scraper):
    """Une valeur vide venue de la source ne remplace jamais une valeur en base."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    # Source temporairement amputée du temps total.
    patch_scraper([_result("1", "DUPONT", total_time="")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 0, "updated": 0, "skipped": 1, "reconciled": 0}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert parts[0].total_time == "01:59:00"  # survit
    assert parts[0].status == "finisher"       # re-dérivé du temps FUSIONNÉ


def test_reimport_ligne_identique_compte_en_skipped(db_session, patch_scraper):
    """Une ligne inchangée ne déclenche aucun UPDATE : elle compte en skipped."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=2)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=2)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 0, "updated": 0, "skipped": 1, "reconciled": 0}


def test_is_empty_distingue_false_et_zero_des_valeurs_vides():
    """`False` et `0` ne sont pas « vides » : ils peuvent corriger une valeur en base."""
    assert import_service._is_empty(None) is True
    assert import_service._is_empty("") is True
    assert import_service._is_empty({}) is True
    assert import_service._is_empty(False) is False
    assert import_service._is_empty(0) is False


def test_merge_fields_ecrit_false_sur_true_et_ignore_vide_et_cles():
    """Champ non vide et différent → retenu ; `is_relay=False` corrige un `True` ;
    valeur vide ignorée ; clé d'appariement jamais réécrite."""
    existing = SimpleNamespace(is_relay=True, total_time="01:00:00", bib_number="1")
    changes = import_service._merge_fields(
        existing, {"is_relay": False, "total_time": "", "bib_number": "9"}
    )
    assert changes == {"is_relay": False}


def test_reimport_statut_explicite_ecrase(db_session, patch_scraper):
    """Un statut affirmé par le scraper écrase celui en base."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", status="DSQ")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 0, "updated": 1, "skipped": 0, "reconciled": 0}
    assert participation_repository.list_participations(db_session, page_size=100)[0].status == "DSQ"


@pytest.mark.parametrize("status", ["DNS", "DNF", "DSQ"])
def test_reimport_explicit_non_finisher_clears_rank_and_time(db_session, patch_scraper, status):
    """#962: scrapers empty rank and time on an explicit non-finisher; a rescrape
    must carry that over instead of keeping the previous import's values."""
    patch_scraper([_result(
        "1", "DUPONT", total_time="01:59:00", rank_overall=5, rank_category=2,
        rank_gender=4, swim_time="00:30:00",
    )])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="", status=status)])
    import_service.import_event(db_session, URL, _settings(), force=True)

    part = participation_repository.list_participations(db_session, page_size=100)[0]
    assert part.status == status
    assert (part.rank_overall, part.rank_category, part.rank_gender) == (None, None, None)
    assert part.total_time is None
    if status == "DNS":
        assert not part.splits
    else:
        assert part.splits


def test_reimport_ajoute_un_nouveau_dossard_et_met_a_jour_l_ancien(db_session, patch_scraper):
    """Mélange : dossard connu corrigé (updated) + dossard neuf (imported)."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("1", "DUPONT", total_time="01:58:00"),  # updated
        _result("2", "MARTIN", total_time="02:05:00"),  # imported
    ])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert _counters(out) == {"imported": 1, "updated": 1, "skipped": 0, "reconciled": 0}


def test_iter_import_event_expose_updated(db_session, patch_scraper):
    """Les phases `saving` et `done` du générateur SSE portent `updated`."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:58:00")])
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))

    saving = [p for p in phases if p["phase"] == "saving"]
    assert saving and all("updated" in p for p in saving)
    done = phases[-1]
    assert done["phase"] == "done"
    assert (done["imported"], done["updated"], done["skipped"]) == (0, 1, 0)


def test_iter_import_event_accuse_de_commit_perdu_confirme_en_base(db_session, patch_scraper, monkeypatch):
    """#704 : un `commit()` qui aboutit côté serveur mais dont l'accusé de
    réception se perd (connexion recyclée en prod) ne doit pas annoncer
    `error` — les données sont bel et bien écrites, une phase `done` fidèle
    doit sortir plutôt qu'un faux échec qui pousse à ré-importer."""
    patch_scraper([_result("1", "DUPONT")])
    original_commit = db_session.commit

    def _commit_puis_accuse_perdu():
        original_commit()
        raise RuntimeError("connexion recyclée après commit abouti")

    monkeypatch.setattr(db_session, "commit", _commit_puis_accuse_perdu)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    done = phases[-1]
    assert done["phase"] == "done"
    assert done["imported"] == 1
    assert course_repository.get_latest_by_source_url(db_session, URL) is not None


def test_iter_import_event_deadlock_est_rejoue(db_session, patch_scraper, monkeypatch):
    """#771 : un deadlock Postgres (concurrence `rescrape-db` entre chronométreurs,
    #690) ne doit pas perdre l'épreuve entière — rien n'a été commité, un
    nouvel essai suffit."""
    monkeypatch.setattr(import_service.time, "sleep", lambda *_: None)
    patch_scraper([_result("1", "DUPONT")])
    original_commit = db_session.commit
    appels: list[int] = []

    def _commit_deadlock_puis_ok():
        appels.append(1)
        if len(appels) == 1:
            raise OperationalError(
                "UPDATE athletes ...", {}, SimpleNamespace(pgcode="40P01")
            )
        original_commit()

    monkeypatch.setattr(db_session, "commit", _commit_deadlock_puis_ok)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    done = phases[-1]
    assert done["phase"] == "done"
    assert done["imported"] == 1
    assert len(appels) == 2
    assert course_repository.get_latest_by_source_url(db_session, URL) is not None


def test_iter_import_event_deadlock_persistant_reste_une_erreur(
    db_session, patch_scraper, monkeypatch,
):
    """#771 : au-delà de `_DEADLOCK_MAX_ATTEMPTS`, un deadlock qui persiste
    reste une erreur — pas de ré-essai infini, l'épreuve échoue proprement."""
    monkeypatch.setattr(import_service.time, "sleep", lambda *_: None)
    patch_scraper([_result("1", "DUPONT")])
    appels: list[int] = []

    def _commit_deadlock_toujours():
        appels.append(1)
        raise OperationalError("UPDATE athletes ...", {}, SimpleNamespace(pgcode="40P01"))

    monkeypatch.setattr(db_session, "commit", _commit_deadlock_toujours)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert phases[-1]["phase"] == "error"
    assert len(appels) == import_service._DEADLOCK_MAX_ATTEMPTS
    assert course_repository.get_latest_by_source_url(db_session, URL) is None


def test_iter_import_event_erreur_non_deadlock_n_est_pas_rejouee(
    db_session, patch_scraper, monkeypatch,
):
    """#771 : seul un deadlock Postgres (`40P01`) déclenche un ré-essai — toute
    autre erreur reste traitée en un seul essai, comme avant #771."""
    patch_scraper([_result("1", "DUPONT")])
    appels: list[int] = []

    def _commit_erreur_non_deadlock():
        appels.append(1)
        raise OperationalError(
            "UPDATE athletes ...", {}, SimpleNamespace(pgcode="23505")
        )

    monkeypatch.setattr(db_session, "commit", _commit_erreur_non_deadlock)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert phases[-1]["phase"] == "error"
    assert len(appels) == 1


def test_iter_import_event_commit_reellement_echoue_reste_une_erreur(db_session, patch_scraper, monkeypatch):
    """Garde-fou du fix #704 : une vraie panne de commit, où rien n'atteint la
    base, doit continuer à annoncer `error` — la re-vérification ne doit pas
    transformer tout échec de commit en faux succès."""
    patch_scraper([_result("1", "DUPONT")])

    def _commit_echoue_vraiment():
        raise RuntimeError("connexion perdue avant tout commit")

    monkeypatch.setattr(db_session, "commit", _commit_echoue_vraiment)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert phases[-1]["phase"] == "error"
    assert course_repository.get_latest_by_source_url(db_session, URL) is None


def test_iter_import_event_re_verification_qui_echoue_reste_une_erreur(
    db_session, patch_scraper, monkeypatch,
):
    """Garde-fou du fix #704 : si la re-vérification post-commit échoue à son
    tour (connexion vraiment perdue, pas seulement un accusé égaré), le flux
    SSE doit quand même terminer sur une phase `error` explicite — jamais une
    exception non gérée qui laisse le front bloqué sur `saving`."""
    patch_scraper([_result("1", "DUPONT")])

    def _commit_echoue_vraiment():
        raise RuntimeError("connexion perdue avant tout commit")

    def _get_echoue(db, course_id):
        raise RuntimeError("connexion aussi perdue pour la re-vérification")

    monkeypatch.setattr(db_session, "commit", _commit_echoue_vraiment)
    monkeypatch.setattr(import_service.course_repository, "get", _get_echoue)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert phases[-1]["phase"] == "error"


def test_cached_return_porte_updated_zero(db_session, patch_scraper):
    """Le retour court-circuité par le cache TTL porte `updated: 0`."""
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert out["updated"] == 0


def test_import_event_expose_les_courses_touchees(db_session, patch_scraper):
    """`import_event` renvoie `courses: [{id, name, event_type, is_relay}]` pour
    câbler les boutons « Voir les résultats » du front (#135), avec `is_relay`
    ajouté (#195) pour distinguer indiv et relais dans le sélecteur.
    """
    patch_scraper([_result("1", "DUPONT")])
    out = import_service.import_event(db_session, URL, _settings())

    assert len(out["courses"]) == 1
    course = out["courses"][0]
    assert set(course) == {"id", "name", "event_type", "is_relay"}
    assert course["event_type"] == "triathlon-m"
    assert course["is_relay"] is False
    assert isinstance(course["id"], int) and course["id"] > 0


def test_cached_return_porte_les_courses(db_session, patch_scraper):
    """Sur le court-circuit cache, `courses` porte la course représentative :
    le front peut proposer le même bouton même quand rien n'a été ré-importé.
    """
    patch_scraper([_result("1", "DUPONT")])
    first = import_service.import_event(db_session, URL, _settings())
    course_id = first["courses"][0]["id"]

    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert len(out["courses"]) == 1
    assert out["courses"][0]["id"] == course_id


def test_cached_return_porte_toutes_les_heats(db_session, patch_scraper):
    """Sur une URL multi-heats (Wiclax, Klikego…), le chemin cache doit
    remonter **toutes** les courses créées, pas la seule représentative de
    `get_latest_by_source_url` — sinon le sélecteur du front (#135)
    n'offrirait qu'un accès à une seule course, et `skipped` compterait les
    participants d'une seule heat au lieu du total (bandeau doublon
    mensonger).
    """
    patch_scraper([
        _result("1", "DUPONT", event_name="Triathlon S", event_type="triathlon-s"),
        _result("2", "MARTIN", event_name="Triathlon S", event_type="triathlon-s"),
        _result("10", "DURAND", event_name="Triathlon M", event_type="triathlon-m"),
    ])
    first = import_service.import_event(db_session, URL, _settings())
    assert len(first["courses"]) == 2  # deux heats bien créées

    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    # Toutes les heats sont rendues au sélecteur, dans l'ordre `scraped_at desc`.
    assert {c["name"] for c in out["courses"]} == {"Triathlon S", "Triathlon M"}
    # `skipped` = somme sur toutes les heats, pas une seule.
    assert out["skipped"] == 3


def test_cached_skipped_compte_les_participations_sans_dossard(db_session, patch_scraper):
    """Le `skipped` du cache TTL compte **toutes** les participations, avec ou
    sans dossard — pas seulement celles portant un bib."""
    patch_scraper([_result("1", "DUPONT"), _result(None, "SANSBIB")])
    first = import_service.import_event(db_session, URL, _settings())
    assert first["imported"] == 2

    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert out["skipped"] == 2


# ── Validation d'URL — seule garde du batch CLI, qui n'a pas de schéma Pydantic (#49)


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
    "https://[oops/x",         # host IPv6 malformé : `urlparse` lève `ValueError`
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


# ── Fan-out counters — SSE `done` étendu (issue #156, FR-008) ────────────────


def test_scrape_all_streaming_use_cache_probe_false_desarme_la_sonde_par_heat(
    db_session, monkeypatch,
):
    """#118 (R2) — `use_cache_probe=False` doit atteindre le chemin **streamé**.

    `_scrape_all` a déjà ce paramètre (#285) ; `_scrape_all_streaming` ne
    l'exposait pas encore. Sans lui, un re-scrape demandé sur une épreuve
    fan-out fraîchement importée sauterait tous ses heats jugés frais — le
    classement resterait inchangé malgré la demande explicite.
    """
    from app.scrapers import registry

    provider = registry.KlikegoProvider()
    provider.last_trace = FanoutTrace(heats_enumerated=1)
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: provider)

    captured = {}

    def fake_scrape(url, *, cache_probe=None, on_heat_start=None, **kwargs):
        captured["cache_probe"] = cache_probe
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)

    gen = import_service._scrape_all_streaming(
        URL, db_session, _settings(), use_cache_probe=False
    )
    list(gen)  # draine les yields intermédiaires, ignore (results, trace)

    assert "cache_probe" in captured, "le dispatcher fan-out doit être invoqué"
    assert captured["cache_probe"] is None


def test_scrape_all_streaming_cache_probe_utilise_une_session_dediee_au_thread(
    db_session, monkeypatch,
):
    """#566 point 1 — `cache_probe` ne doit jamais toucher la Session de l'appelant.

    Elle s'exécute sur le thread de travail, indépendant du cycle de vie de
    `db_session` (possédée par le générateur SSE, fermable par l'appelant à
    tout moment sur déconnexion). Une Session dédiée, ouverte et fermée dans
    le thread, élimine l'usage concurrent d'un objet non thread-safe.
    """
    from app.scrapers import registry

    provider = registry.KlikegoProvider()
    provider.last_trace = FanoutTrace(heats_enumerated=1)
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: provider)

    class _FakeThreadSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    thread_sessions = []

    def fake_session_local():
        session = _FakeThreadSession()
        thread_sessions.append(session)
        return session

    monkeypatch.setattr(import_service, "SessionLocal", fake_session_local)

    captured = {}

    def fake_scrape(url, *, cache_probe=None, on_heat_start=None, **kwargs):
        captured["cache_probe"] = cache_probe
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)

    gen = import_service._scrape_all_streaming(URL, db_session, _settings())
    list(gen)  # draine les yields intermédiaires, ignore (results, trace)

    assert captured["cache_probe"] is not None
    assert len(thread_sessions) == 1, "une seule Session dédiée doit être ouverte"
    assert thread_sessions[0].closed, "la Session du thread doit être fermée à la fin du scrape"


def _fake_klikego_provider(monkeypatch, enumerated: int, cached: int, failures: list[dict]):
    """Fait que `registry.get_provider(url)` rend un KlikegoProvider avec last_trace prédéfinie."""
    from app.scrapers import registry

    provider = registry.KlikegoProvider()
    provider.last_trace = FanoutTrace(
        heats_enumerated=enumerated,
        heats_cached=cached,
        failures=list(failures),
    )
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: provider)
    return provider


def test_iter_import_event_exposes_fanout_counters(db_session, patch_scraper, monkeypatch):
    """SSE `done` porte les 5 clés FR-008 avec l'invariant enumerated = imported + cached + failed."""
    # 8 heats à la source, 2 en cache TTL, 1 en échec → 5 imported (5 ScrapedResult)
    patch_scraper([
        _result(str(i), f"NOM{i}") for i in range(1, 6)
    ])
    _fake_klikego_provider(monkeypatch, enumerated=8, cached=2, failures=[
        {"heat_slug": "triathlon-xs-relais", "reason": "boom"}
    ])

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))
    done = phases[-1]

    assert done["phase"] == "done"
    assert done["heats_enumerated"] == 8
    assert done["heats_cached"] == 2
    assert done["heats_failed"] == 1
    assert done["heats_imported"] == 5
    assert done["failures"] == [{"heat_slug": "triathlon-xs-relais", "reason": "boom"}]
    # Invariant explicite
    assert done["heats_enumerated"] == done["heats_imported"] + done["heats_cached"] + done["heats_failed"]


def test_iter_import_event_zero_results_still_carries_counters(db_session, patch_scraper, monkeypatch):
    """Un scrape qui rend 0 ScrapedResult (aucun heat OK) porte quand même les compteurs."""
    patch_scraper([])
    _fake_klikego_provider(monkeypatch, enumerated=3, cached=0, failures=[
        {"heat_slug": "a", "reason": "boom-a"},
        {"heat_slug": "b", "reason": "boom-b"},
        {"heat_slug": "c", "reason": "boom-c"},
    ])

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))
    done = phases[-1]

    assert done["phase"] == "done"
    assert done["heats_enumerated"] == 3
    assert done["heats_failed"] == 3
    assert done["heats_imported"] == 0
    assert done["heats_cached"] == 0
    assert len(done["failures"]) == 3


def test_import_event_returns_fanout_counters(db_session, patch_scraper, monkeypatch):
    """Le retour sync de `import_event()` porte les mêmes 5 clés (parité avec SSE)."""
    patch_scraper([_result("1", "DUPONT")])
    _fake_klikego_provider(monkeypatch, enumerated=1, cached=0, failures=[])

    out = import_service.import_event(db_session, URL, _settings())

    assert out["heats_enumerated"] == 1
    assert out["heats_imported"] == 1
    assert out["heats_cached"] == 0
    assert out["heats_failed"] == 0
    assert out["failures"] == []


def test_iter_import_event_done_liste_les_courses_cachees_du_fanout(
    db_session, patch_scraper, monkeypatch,
):
    """Fan-out avec heats cachés : le SSE `done` remonte les courses des heats
    re-scrapés **et** des heats sautés.

    Sans ce complément, un ré-import sur un événement partiellement caché
    ferait perdre au sélecteur de fin d'import (#135) l'accès aux heats déjà
    en base — l'opérateur y verrait « 3 courses importées » alors que
    l'événement en compte 5, et n'aurait aucun bouton vers les 2 heats cachés.
    """
    # 1er passage : 3 heats, tous scrapés → 3 courses en base.
    patch_scraper([
        _result("1", "A", event_name="Mesquer", event_type="triathlon-s",
                source_url=URL + "?heat=triathlon-s-indiv"),
        _result("2", "B", event_name="Mesquer", event_type="triathlon-xs",
                source_url=URL + "?heat=triathlon-xs-indiv"),
        _result("3", "C", event_name="Mesquer", event_type="swimrun-s",
                source_url=URL + "?heat=swim-run-s-duo"),
    ])
    _fake_klikego_provider(monkeypatch, enumerated=3, cached=0, failures=[])
    import_service.import_event(db_session, URL, _settings())

    # 2e passage : cache_probe rend 2 heats frais → 1 seul re-scrapé, mais le
    # `done` doit lister les 3 courses.
    patch_scraper([
        _result("2", "B", event_name="Mesquer", event_type="triathlon-xs",
                source_url=URL + "?heat=triathlon-xs-indiv"),
    ])
    cached_trace = FanoutTrace(
        heats_enumerated=3, heats_cached=2, failures=[],
        cached_urls=[URL + "?heat=triathlon-s-indiv", URL + "?heat=swim-run-s-duo"],
    )
    provider = _fake_klikego_provider(monkeypatch, enumerated=3, cached=2, failures=[])
    provider.last_trace = cached_trace

    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))
    done = phases[-1]

    assert done["phase"] == "done"
    assert len(done["courses"]) == 3, (
        f"Attendu 3 courses (1 re-scrapée + 2 cachées), obtenu {done['courses']}"
    )
    event_types = {c["event_type"] for c in done["courses"]}
    assert event_types == {"triathlon-s", "triathlon-xs", "swimrun-s"}


def test_iter_import_event_streame_les_evenements_de_scraping_par_heat(
    db_session, monkeypatch,
):
    """Fan-out Klikego : le SSE émet un `scraping` par heat avec heat_index/total.

    Sans ces yields intermédiaires, la phase `scraping` reste figée 30-40 s sur
    « Récupération des participants… » — l'opérateur croit que la requête est
    bloquée. Le contrat vérifié ici : chaque heat non caché fait remonter un
    event `scraping` avec heat_index 1..N et heats_total = N, dans l'ordre.
    """
    # 3 heats à scraper. `registry_scrape_event_all` invoque `on_heat_start`
    # dans un ordre déterministe avant de retourner le résultat.
    def fake_scrape(url, *, cache_probe=None, on_heat_start=None, **kwargs):
        if on_heat_start is not None:
            on_heat_start("triathlon-s-indiv", "Triathlon S", 1, 3)
            on_heat_start("swim-run-m-duo", "SwimRun M duo", 2, 3)
            on_heat_start("triathlon-xs-indiv", "Triathlon XS", 3, 3)
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)
    _fake_klikego_provider(monkeypatch, enumerated=3, cached=0, failures=[])

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    scraping = [p for p in phases if p["phase"] == "scraping"]
    # 1 event d'ouverture (message initial) + 3 events par heat.
    assert len(scraping) == 4
    assert scraping[0].get("message"), "premier event = message générique"
    per_heat = scraping[1:]
    assert [p["heat_index"] for p in per_heat] == [1, 2, 3]
    assert all(p["heats_total"] == 3 for p in per_heat)
    assert [p["heat_slug"] for p in per_heat] == [
        "triathlon-s-indiv", "swim-run-m-duo", "triathlon-xs-indiv",
    ]
    assert [p["heat_label"] for p in per_heat] == [
        "Triathlon S", "SwimRun M duo", "Triathlon XS",
    ]


def test_iter_import_event_streame_la_progression_de_detail_phase_c(
    db_session, monkeypatch,
):
    """`on_detail_progress` (#583) émet des events `scraping` porteurs de
    `detail_done`/`detail_total`, en plus des events par heat.

    Sans eux, un heat de 250 participants restait figé plusieurs minutes entre
    deux events `on_heat_start`.
    """
    def fake_scrape(url, *, cache_probe=None, on_heat_start=None, on_detail_progress=None):
        if on_heat_start is not None:
            on_heat_start("triathlon-s-indiv", "Triathlon S", 1, 1)
        if on_detail_progress is not None:
            on_detail_progress("triathlon-s-indiv", "Triathlon S", 1, 1, 10, 50)
            on_detail_progress("triathlon-s-indiv", "Triathlon S", 1, 1, 50, 50)
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)
    _fake_klikego_provider(monkeypatch, enumerated=1, cached=0, failures=[])

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    scraping = [p for p in phases if p["phase"] == "scraping"]
    detail_events = [p for p in scraping if "detail_done" in p]
    assert [e["detail_done"] for e in detail_events] == [10, 50]
    assert all(e["detail_total"] == 50 for e in detail_events)
    assert all(e["heat_slug"] == "triathlon-s-indiv" for e in detail_events)
    assert all(e["heat_index"] == 1 and e["heats_total"] == 1 for e in detail_events)


def test_iter_import_event_single_heat_streame_la_progression_de_detail(
    db_session, monkeypatch,
):
    """`single_heat=True` garde la progression de la phase C (#698).

    L'ancienne branche appelait `_scrape_all` directement : le flux SSE restait
    muet entre « Récupération des participants… » et la phase `saving`, alors
    qu'un seul heat Klikego peut compter ~250 finishers et que la phase C est
    justement la partie lente (#583).
    """
    def fake_scrape(url, *, single_heat=False, on_detail_progress=None, **kwargs):
        assert single_heat is True
        assert kwargs.get("cache_probe") is None, "une sous-unité demandée ne se saute pas"
        on_detail_progress("triathlon-s", "triathlon-s", 1, 1, 10, 40)
        on_detail_progress("triathlon-s", "triathlon-s", 1, 1, 40, 40)
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)
    _fake_klikego_provider(monkeypatch, enumerated=1, cached=0, failures=[])

    phases = list(
        import_service.iter_import_event(db_session, URL, _settings(), single_heat=True)
    )

    scraping = [p for p in phases if p["phase"] == "scraping"]
    detail_events = [p for p in scraping if "detail_done" in p]
    assert [e["detail_done"] for e in detail_events] == [10, 40]
    assert all(e["detail_total"] == 40 for e in detail_events)
    assert all(e["heat_index"] == 1 and e["heats_total"] == 1 for e in detail_events)
    assert phases[-1]["phase"] == "done"


def test_iter_import_event_single_heat_hors_klikego_reste_un_seul_event(
    db_session, monkeypatch,
):
    """Un fan-out sans phase C à rapporter garde le chemin bloquant (#698).

    Wiclax n'accepte pas `on_detail_progress` dans sa signature : le lui passer
    lèverait. Il n'y a rien à streamer, donc un seul event `scraping` — mais le
    couple `(results, trace)` doit rester identique au chemin nominal.
    """
    from app.scrapers import registry

    captured = {}

    def fake_scrape(url, *, single_heat=False, cache_probe=None, on_heat_start=None):
        captured["single_heat"] = single_heat
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)
    provider = registry.WiclaxProvider()
    provider.last_trace = FanoutTrace(heats_enumerated=1)
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: provider)

    phases = list(
        import_service.iter_import_event(db_session, URL, _settings(), single_heat=True)
    )

    assert captured["single_heat"] is True
    assert len([p for p in phases if p["phase"] == "scraping"]) == 1
    assert phases[-1]["phase"] == "done"


def test_scrape_all_streaming_wiring_on_detail_progress_seulement_pour_klikego(
    db_session, monkeypatch,
):
    """`on_detail_progress` n'est câblé que pour Klikego (#583).

    C'est le seul fournisseur dont la phase C par participant justifie une
    notification par lot ; un autre fan-out (`FanoutProvider.scrape_event_all`,
    ex. Wiclax) ne l'accepte pas dans sa signature — le lui passer lèverait.
    """
    from app.scrapers import registry

    captured = {}

    def fake_scrape(url, *, cache_probe=None, on_heat_start=None):
        # Signature stricte : lèverait un TypeError si on_detail_progress
        # était passé, comme le vrai `FanoutProvider.scrape_event_all`.
        captured["called"] = True
        return [_result("1", "DUPONT")]

    monkeypatch.setattr(import_service, "registry_scrape_event_all", fake_scrape)
    provider = registry.WiclaxProvider()
    provider.last_trace = FanoutTrace(heats_enumerated=1)
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: provider)

    phases = list(import_service.iter_import_event(db_session, URL, _settings()))

    assert captured.get("called") is True
    assert phases[-1]["phase"] == "done"


def test_iter_import_event_scraping_non_klikego_reste_un_seul_event(
    db_session, patch_scraper, monkeypatch,
):
    """Provider non-fan-out : un seul event `scraping`, pas de progression par heat.

    Un Wiclax, TimePulse, ou n'importe quel provider mono-course garde le
    comportement historique — le streaming par heat est spécifique à Klikego.
    """
    patch_scraper([_result("1", "DUPONT")])
    # `get_provider` retourne None pour une URL non-Klikego → chemin non-fan-out.
    non_klikego_url = "https://www.timepulse.fr/course/42/classement"
    monkeypatch.setattr(import_service.registry, "get_provider", lambda url: None)

    phases = list(
        import_service.iter_import_event(db_session, non_klikego_url, _settings())
    )

    scraping = [p for p in phases if p["phase"] == "scraping"]
    assert len(scraping) == 1
    assert "heat_index" not in scraping[0]


# ── Persist par lot (#706) ───────────────────────────────────────────────────


def _queries_for_persist(db_session, *, n: int, marker: str) -> list[str]:
    """Persiste `n` lignes neuves sur une course dédiée à `marker`, et renvoie
    le texte de toutes les requêtes SQL émises — même patron que
    `test_course_merge.py::test_the_query_count_does_not_grow_with_the_number_of_results`.
    """
    results = [
        _result(
            str(i), f"NOM{marker}{i}",
            event_name=f"Triathlon {marker}", source_url=f"https://www.klikego.com/{marker}",
        )
        for i in range(n)
    ]
    queries: list[str] = []

    def _record(conn, cursor, statement, *rest):
        queries.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _record)
    try:
        import_service.persist_results(db_session, f"https://www.klikego.com/{marker}", results)
    finally:
        event.remove(engine, "before_cursor_execute", _record)
    return queries


def test_persist_results_la_lecture_des_athletes_ne_croit_pas_lineairement(db_session):
    """FR-001, FR-006 — la résolution (lecture) des athlètes est bornée par le
    nombre de tranches, pas par le nombre de lignes.

    Ce test porte sur les `SELECT ... FROM athletes`, pas sur le total brut de
    requêtes : sur SQLite, un flush portant plusieurs `INSERT` neufs n'est pas
    compilé en une seule instruction (contrairement à Postgres via
    `insertmanyvalues`, cf. `research.md`) — chaque ligne créée reste une
    requête distincte, et `get_or_create_course` (hors périmètre de #706, cf.
    `spec.md` § Assumptions) en ajoute une par ligne. Aucun de ces deux
    éléments n'est concerné par cette feature ; seule la lecture l'est, et
    c'est elle qui doit rester plate."""
    small = _queries_for_persist(db_session, n=10, marker="petitelect")
    big = _queries_for_persist(db_session, n=1200, marker="grandelect")

    def _select_athletes(queries: list[str]) -> list[str]:
        return [
            q for q in queries
            if q.strip().upper().startswith("SELECT") and "FROM ATHLETES" in q.upper()
        ]

    assert len(_select_athletes(big)) <= len(_select_athletes(small)) + 4, (
        f"{len(_select_athletes(small))} SELECT athletes pour 10 lignes, "
        f"{len(_select_athletes(big))} pour 1200 : la résolution semble encore "
        "émettre un SELECT par ligne plutôt que par tranche"
    )


def test_resolve_pending_appelle_les_fonctions_de_lot_par_tranche_pas_par_ligne(
    db_session, monkeypatch,
):
    """FR-001, FR-002, FR-006 — vérifie directement, via des espions sur les
    fonctions de repository, que `_Persister` les appelle un nombre de fois
    borné par le nombre de tranches (≈500 lignes), jamais une fois par ligne.

    Complète le test précédent : celui-ci isole le comportement du code de
    `_Persister` (l'objet de cette feature) de ce que SQLAlchemy/le dialecte
    font ensuite du SQL — une garantie qui tient quel que soit le dialecte,
    contrairement au comptage brut de requêtes SQL.
    """
    calls: Counter[str] = Counter()
    original_get_by_identities = athlete_repository.get_by_identities_batch
    original_create_athletes = athlete_repository.create_batch
    original_create_participations = participation_repository.create_batch

    def _spy_get_by_identities(db, paires):
        calls["get_by_identities_batch"] += 1
        return original_get_by_identities(db, paires)

    def _spy_create_athletes(db, fields):
        calls["athlete_create_batch"] += 1
        return original_create_athletes(db, fields)

    def _spy_create_participations(db, fields):
        calls["participation_create_batch"] += 1
        return original_create_participations(db, fields)

    monkeypatch.setattr(athlete_repository, "get_by_identities_batch", _spy_get_by_identities)
    monkeypatch.setattr(athlete_repository, "create_batch", _spy_create_athletes)
    monkeypatch.setattr(participation_repository, "create_batch", _spy_create_participations)

    results = [_result(str(i), f"LOT{i}") for i in range(1200)]
    import_service.persist_results(db_session, "https://www.klikego.com/lot706", results)

    # 1200 lignes / tranche de ~500 → 3 tranches (500, 500, 200) : quelques
    # appels seulement, jamais 1200.
    assert calls["get_by_identities_batch"] <= 5
    assert calls["athlete_create_batch"] <= 5
    assert calls["participation_create_batch"] <= 5


def test_finalize_ne_recharge_plus_les_participations_d_une_deuxieme_fois(db_session):
    """FR-003 — `_index_course` charge déjà les participations de la course ;
    `finalize()` ne doit plus émettre un second `SELECT ... FROM participations`
    pour la même course."""
    queries = _queries_for_persist(db_session, n=5, marker="finalize")

    reloads = [
        q for q in queries
        if q.strip().upper().startswith("SELECT") and "FROM PARTICIPATIONS" in q.upper()
    ]
    assert len(reloads) == 1, (
        f"{len(reloads)} requêtes SELECT...FROM participations pour une course : "
        "finalize() semble encore recharger une deuxième fois"
    )


def test_import_volumineux_produit_les_memes_compteurs_que_ligne_a_ligne(db_session, patch_scraper):
    """FR-004 — un scrape qui franchit une frontière de tranche (> 500 lignes)
    et mêle dossard déjà connu (chemin `_reconcile`), dossard neuf et sans
    dossard produit les mêmes compteurs que le comportement ligne à ligne."""
    premiers = [_result(str(i), f"CONNU{i}") for i in range(520)]
    patch_scraper(premiers)
    premier_import = import_service.import_event(db_session, URL, _settings())
    assert _counters(premier_import) == {
        "imported": 520, "updated": 0, "skipped": 0, "reconciled": 0,
    }

    _expire_cache(db_session)

    # Réimport : les 520 premiers dossards sont déjà connus (chemin
    # `_reconcile`), 520 nouveaux dossards neufs, et 10 lignes sans dossard —
    # de quoi franchir une frontière de tranche sur les trois chemins de
    # résolution à la fois.
    reimport = [_result(str(i), f"CONNU{i}") for i in range(520)]
    reimport += [_result(str(500 + i), f"NEUF{i}") for i in range(520, 1040)]
    reimport += [_result("", f"SANSDOSSARD{i}") for i in range(10)]
    patch_scraper(reimport)

    out = import_service.import_event(db_session, URL, _settings())

    # 520 dossards déjà connus (identiques → skip), 520 dossards neufs +
    # 10 lignes sans dossard, toutes nouvelles → imported.
    assert _counters(out) == {
        "imported": 530, "updated": 0, "skipped": 520, "reconciled": 0,
    }


def test_deux_lignes_du_meme_scrape_pour_le_meme_athlete_neuf_ne_creent_qu_une_fiche(
    db_session, patch_scraper,
):
    """Edge case de `spec.md` — collision intra-lot : deux lignes du même
    scrape désignent le même athlète neuf (même nom/prénom), sans dossard.
    Le comportement ligne à ligne crée deux participations pour un seul
    athlète (cf. `test_import_sans_dossard_conserve_les_homonymes`) — FR-004
    exige que la résolution par lot produise exactement le même résultat, et
    surtout **pas** deux fiches `Athlete` distinctes pour la même identité."""
    patch_scraper(
        [
            _result("", "COLLISION", prenom="Ada"),
            _result("", "COLLISION", prenom="Ada"),
        ]
    )

    out = import_service.import_event(db_session, URL, _settings())

    assert _counters(out) == {"imported": 2, "updated": 0, "skipped": 0, "reconciled": 0}
    athletes = athlete_repository.search(db_session, name="Collision")
    assert len(athletes) == 1


def test_deux_reconciliations_du_meme_scrape_vers_la_meme_identite_neuve_distinguent_creation_et_fusion(
    db_session, patch_scraper,
):
    """Edge case le plus risqué de la mise en lot (#706) : deux dossards
    distincts, déjà connus sous deux graphies fautives différentes, sont
    corrigés dans le même scrape vers la **même** identité neuve — un cas de
    collision sur le chemin `_reconcile`, pas sur le chemin dossard neuf déjà
    couvert ci-dessus.

    Ligne à ligne, seule la **première** ligne traitée crée la fiche corrigée
    (`fusion=False`, renommage) ; la seconde la retrouve déjà flushée
    (`fusion=True`, fusion). La résolution par lot doit reproduire cet ordre
    — pas marquer les deux `fusion=False`, ce qui arriverait si le
    dédoublonnage de création ne trackait pas qui a « consommé » la création
    en premier (cf. `_resolve_pending`, `creation_consumed`)."""
    patch_scraper(
        [_result("1", "BERRE", "Audrey LE"), _result("2", "BERR", "Audrey LE")]
    )
    import_service.import_event(db_session, URL, _settings())

    patch_scraper(
        [_result("1", "LE BERRE", "Audrey"), _result("2", "LE BERRE", "Audrey")]
    )
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))
    done = phases[-1]

    assert done["reconciled"] == 2
    by_ancien = {r.ancien: r for r in done["reassignments"]}
    assert by_ancien["BERRE | Audrey LE"].fusion is False
    assert by_ancien["BERR | Audrey LE"].fusion is True
    assert by_ancien["BERRE | Audrey LE"].nouveau == "LE BERRE | Audrey"
    assert by_ancien["BERR | Audrey LE"].nouveau == "LE BERRE | Audrey"

    # Une seule fiche cible, et les deux participations y pointent — pas
    # `search` (sous-chaîne mot à mot) qui retrouverait aussi les fiches
    # fautives orphelines, non nettoyées par la réconciliation (comportement
    # existant, hors périmètre de #706).
    cible = athlete_repository.get_by_identity(db_session, "LE BERRE", "Audrey", None)
    assert cible is not None
    course = course_repository.get_latest_by_source_url(db_session, URL)
    rows = participation_repository.list_for_course(db_session, course.id)
    assert {row.athlete_id for row in rows} == {cible.id}


# ── Relais attribué à ses équipiers (#894) : le rescrape ne défait rien ──────
#
# `_Persister` est le point d'écriture unique des trois entrées (rescrape d'une
# épreuve, `rescrape-db`, import web SSE) : le couvrir ici couvre les trois.


def _relais_attribue(db_session, patch_scraper, monkeypatch, bib, nom, prenom=""):
    # Importé sans découpage (avant #895), puis composé à la main : c'est la
    # composition posée par un administrateur que le rescrape doit garder.
    _import_before_895(
        db_session, patch_scraper, monkeypatch,
        [_result(bib, nom, prenom, is_relay=True, event_type="triathlon-s")],
    )
    course = course_repository.get_latest_by_source_url(db_session, URL)
    (ligne,) = participation_repository.list_for_course(db_session, course.id)
    jean = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    paul = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul")
    auteur = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    admin_actions.set_teammates(
        db_session, participation_id=ligne.id, teammates=[jean.id, paul.id], user_id=auteur.id
    )
    db_session.commit()
    _expire_cache(db_session)
    return course, ligne, jean, paul


def _composition_intacte(db_session, course, ligne, jean, paul):
    rows = participation_repository.list_for_course(db_session, course.id)
    assert [row.id for row in rows] == [ligne.id]
    assert rows[0].athlete_id == jean.id
    assert [a.id for a in rows[0].teammates] == [jean.id, paul.id]


@pytest.mark.parametrize("bib", ["7", ""], ids=["avec-dossard", "sans-dossard"])
def test_rescrape_garde_la_composition_d_un_relais_attribue(db_session, patch_scraper, monkeypatch, bib):
    course, ligne, jean, paul = _relais_attribue(
        db_session, patch_scraper, monkeypatch, bib, "DUPONT Jean / MARTIN Paul"
    )

    patch_scraper([
        _result(bib, "DUPONT Jean / MARTIN Paul", "", is_relay=True, event_type="triathlon-s")
    ])
    import_service.import_event(db_session, URL, _settings())

    _composition_intacte(db_session, course, ligne, jean, paul)
    assert athlete_repository.get_by_identity(db_session, "DUPONT Jean / MARTIN Paul", "", None) is None


@pytest.mark.parametrize(
    ("nom", "prenom", "nom_rescrape", "prenom_rescrape"),
    [
        pytest.param("DUPONT JEAN / MARTIN", "PAUL", "DUPONT JEAN / MARTIN", "PAUL", id="nom-decoupe"),
        pytest.param(
            "DUPONT Jean / MARTIN Paul", "", "dupont jean /  MARTIN paul", "", id="casse-et-espaces"
        ),
        pytest.param("DUPONT Jéan & MARTIN Paul", "", "DUPONT Jean & MARTIN Paul", "", id="accents"),
    ],
)
def test_rescrape_sans_dossard_apparie_par_le_nom_d_equipe(
    db_session, patch_scraper, monkeypatch, nom, prenom, nom_rescrape, prenom_rescrape
):
    course, ligne, jean, paul = _relais_attribue(db_session, patch_scraper, monkeypatch, "", nom, prenom)

    patch_scraper([
        _result("", nom_rescrape, prenom_rescrape, is_relay=True, event_type="triathlon-s")
    ])
    import_service.import_event(db_session, URL, _settings())

    _composition_intacte(db_session, course, ligne, jean, paul)


def test_rescrape_avec_dossard_ne_reconcilie_pas_un_relais_attribue(
    db_session, patch_scraper, monkeypatch
):
    # Nom d'équipe découpé en nom + prénom (timepulse) : `_reconcile_blocked`,
    # qui ne protège que d'un prénom vidé, laisserait passer la réconciliation.
    course, ligne, jean, paul = _relais_attribue(
        db_session, patch_scraper, monkeypatch, "7", "DUPONT JEAN / MARTIN", "PAUL"
    )

    patch_scraper([
        _result("7", "DUPONT JEAN / MARTIN", "PAUL", is_relay=True, event_type="triathlon-s")
    ])
    import_service.import_event(db_session, URL, _settings())

    _composition_intacte(db_session, course, ligne, jean, paul)
    assert athlete_repository.get_by_identity(db_session, "DUPONT JEAN / MARTIN", "PAUL", None) is None


def test_rescrape_met_a_jour_les_valeurs_d_un_relais_attribue(
    db_session, patch_scraper, monkeypatch
):
    course, ligne, jean, paul = _relais_attribue(
        db_session, patch_scraper, monkeypatch, "7", "DUPONT Jean / MARTIN Paul"
    )

    patch_scraper([
        _result(
            "7", "DUPONT Jean / MARTIN Paul", "", is_relay=True, event_type="triathlon-s",
            total_time="01:45:00",
        )
    ])
    import_service.import_event(db_session, URL, _settings())

    assert participation_repository.get(db_session, ligne.id).total_time == "01:45:00"


# ── Relais nommés découpés à l'import (#895) ──────────────────────────────────


def _relay(bib, nom, prenom, **kw) -> ScrapedResult:
    return _result(bib, nom, prenom, is_relay=True, event_type="triathlon-s", **kw)


def _only_relay_row(db_session, url=URL):
    course = course_repository.get_latest_by_source_url(db_session, url)
    (row,) = participation_repository.list_for_course(db_session, course.id)
    return row


def _names(athletes):
    return [(athlete.nom, athlete.prenom) for athlete in athletes]


def test_import_splits_parallel_lists_relay(db_session, patch_scraper):
    patch_scraper([_relay("7", "CANNIOU/OLIVIER", "Cedric/Leclerc")])

    out = import_service.import_event(db_session, URL, _settings())

    row = _only_relay_row(db_session)
    assert _names(row.teammates) == [("CANNIOU", "Cedric"), ("OLIVIER", "Leclerc")]
    assert row.athlete_id == row.teammates[0].id
    assert row.team_name == "CANNIOU/OLIVIER Cedric/Leclerc"
    assert athlete_repository.get_by_identity(
        db_session, "CANNIOU/OLIVIER", "Cedric/Leclerc", None
    ) is None
    assert out["imported"] == 1


def test_import_split_reuses_existing_athlete_without_touching_clubs(db_session, patch_scraper):
    existing = athlete_repository.get_or_create(
        db_session, nom="MASSONNEAU", prenom="Pierre", club="TRI CLUB"
    )
    db_session.commit()
    patch_scraper([_relay("", "MASSONNEAU PIERRE", "/ BESANCON FABIEN .", club="TEAM TCC")])

    import_service.import_event(db_session, URL, _settings())

    row = _only_relay_row(db_session)
    first, second = row.teammates
    assert first.id == existing.id
    assert first.club == "TRI CLUB"
    assert (second.nom, second.prenom, second.gender, second.club) == (
        "BESANCON", "FABIEN", "", None
    )
    assert row.club == "TEAM TCC"
    assert athlete_repository.get_by_identity(
        db_session, "MASSONNEAU PIERRE", "/ BESANCON FABIEN .", None
    ) is None


def test_import_split_finds_an_existing_athlete_published_firstname_first(
    db_session, patch_scraper
):
    """All-caps « PRÉNOM NOM » reads as « NOM PRÉNOM »: the existing fiche decides the order."""
    existing = athlete_repository.get_or_create(
        db_session, nom="KERMARREC", prenom="Lucie", club="TRIATHLON CLUB NANTAIS"
    )
    db_session.commit()
    patch_scraper([_relay("13", "LUCIE KERMARREC", "/ FANNY LERAY .")])

    import_service.import_event(db_session, URL, _settings())

    first, second = _only_relay_row(db_session).teammates
    assert first.id == existing.id
    assert (second.nom, second.prenom) == ("FANNY", "LERAY")
    assert athlete_repository.get_by_identity(db_session, "LUCIE", "KERMARREC", None) is None


@pytest.mark.parametrize("tranche", [500, 1], ids=["un-lot", "tranche-unitaire"])
def test_import_splits_several_relays_in_one_batch(db_session, patch_scraper, monkeypatch, tranche):
    monkeypatch.setattr(import_service, "_TRANCHE_SIZE", tranche)
    patch_scraper([
        _relay("7", "CANNIOU/OLIVIER", "Cedric/Leclerc"),
        _relay("", "MASSONNEAU PIERRE", "/ BESANCON FABIEN ."),
        _result("12", "DURAND", "Luc", event_name="Course individuelle"),
    ])

    import_service.import_event(db_session, URL, _settings())

    relay_course = course_repository.get_by_identity(
        db_session, "Triathlon de Nantes", date(2026, 5, 16), "triathlon-s", True
    )
    rows = participation_repository.list_for_course(db_session, relay_course.id)
    assert sorted(_names(row.teammates) for row in rows) == [
        [("CANNIOU", "Cedric"), ("OLIVIER", "Leclerc")],
        [("MASSONNEAU", "PIERRE"), ("BESANCON", "FABIEN")],
    ]
    solo = athlete_repository.get_by_identity(db_session, "DURAND", "Luc", None)
    (solo_row,) = solo.participations
    assert solo_row.teammates == [] and solo_row.team_name is None


def test_import_keeps_group_names_as_team_athletes(db_session, patch_scraper):
    patch_scraper([
        _relay("1", "TEAM GV", "."),
        _relay("2", "LES BARBAPAPAS", "Alex et Margot"),
        _relay("3", "LE BRAS LUC", "/ LE PAGE GUULLAUME ."),
    ])

    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    rows = participation_repository.list_for_course(db_session, course.id)
    assert sorted((row.athlete.nom, row.athlete.prenom) for row in rows) == [
        ("LE BRAS LUC", "/ LE PAGE GUULLAUME ."), ("LES BARBAPAPAS", "Alex et Margot"),
        ("TEAM GV", "."),
    ]
    assert all(row.teammates == [] and row.team_name is None for row in rows)

    group = next(row for row in rows if row.athlete.nom == "TEAM GV")
    jean = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    paul = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul")
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    admin_actions.set_teammates(
        db_session, participation_id=group.id, teammates=[jean.id, paul.id], user_id=admin.id
    )
    assert _names(group.teammates) == [("DUPONT", "Jean"), ("MARTIN", "Paul")]


def test_import_does_not_split_when_a_teammate_already_races_on_the_course(
    db_session, patch_scraper
):
    patch_scraper([_relay("1", "DUPONT", "Jean")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_relay("1", "DUPONT", "Jean"), _relay("2", "DUPONT Jean / MARTIN Paul", "")])
    out = import_service.import_event(db_session, URL, _settings())

    assert out["imported"] == 1
    team = athlete_repository.get_by_identity(db_session, "DUPONT Jean / MARTIN Paul", "", None)
    (row,) = team.participations
    assert row.teammates == []
    assert athlete_repository.get_by_identity(db_session, "MARTIN", "Paul", None) is None


def test_import_does_not_split_two_lines_sharing_a_new_teammate(db_session, patch_scraper):
    patch_scraper([
        _relay("1", "DUPONT Jean / MARTIN Paul", ""),
        _relay("2", "DURAND Luc / MARTIN Paul", ""),
    ])

    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    rows = {
        row.bib_number: row
        for row in participation_repository.list_for_course(db_session, course.id)
    }
    assert _names(rows["1"].teammates) == [("DUPONT", "Jean"), ("MARTIN", "Paul")]
    assert rows["2"].teammates == []
    assert (rows["2"].athlete.nom, rows["2"].athlete.prenom) == ("DURAND Luc / MARTIN Paul", "")


def test_import_never_splits_outside_relays(db_session, patch_scraper, monkeypatch):
    def forbidden(_published):
        raise AssertionError("split_relay_teammates appelée hors relais")

    monkeypatch.setattr(import_service, "split_relay_teammates", forbidden)
    patch_scraper([
        _result("1", "CHAIGNEAU BENJAMIN", "/ LENOIR-LEDOUX CHRISTELLE ."),
        _result("2", "LES PATATALO", "Gaelle et Laure"),
        _result("3", "DUBOIS-HERRY", "Anne-Sophie"),
    ])

    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_latest_by_source_url(db_session, URL)
    rows = participation_repository.list_for_course(db_session, course.id)
    assert sorted((row.athlete.nom, row.athlete.prenom) for row in rows) == [
        ("CHAIGNEAU BENJAMIN", "/ LENOIR-LEDOUX CHRISTELLE ."),
        ("DUBOIS-HERRY", "Anne-Sophie"),
        ("LES PATATALO", "Gaelle et Laure"),
    ]
    assert all(row.teammates == [] and row.team_name is None for row in rows)


def test_import_keeps_hyphenated_teammate_names(db_session, patch_scraper):
    patch_scraper([_relay("7", "PINSON/ROCHEFORT-CUNIN", "Eric/Emmanuel")])

    import_service.import_event(db_session, URL, _settings())

    assert _names(_only_relay_row(db_session).teammates) == [
        ("PINSON", "Eric"), ("ROCHEFORT-CUNIN", "Emmanuel"),
    ]


def _import_before_895(db_session, patch_scraper, monkeypatch, results):
    """État d'une épreuve importée avant #895 : relais portés par leur fiche d'équipe."""
    with monkeypatch.context() as patch:
        patch.setattr(import_service, "split_relay_teammates", lambda _published: None)
        patch_scraper(results)
        import_service.import_event(db_session, URL, _settings())
    db_session.commit()
    _expire_cache(db_session)


@pytest.mark.parametrize("bib", ["7", ""], ids=["avec-dossard", "sans-dossard"])
def test_rescrape_splits_a_relay_imported_before_895(db_session, patch_scraper, monkeypatch, bib):
    line = _relay(bib, "MASSONNEAU PIERRE", "/ BESANCON FABIEN .")
    _import_before_895(db_session, patch_scraper, monkeypatch, [line])
    before = _only_relay_row(db_session)
    team_id = before.athlete_id

    patch_scraper([line])
    out = import_service.import_event(db_session, URL, _settings())

    row = _only_relay_row(db_session)
    assert row.id == before.id
    assert _names(row.teammates) == [("MASSONNEAU", "PIERRE"), ("BESANCON", "FABIEN")]
    assert row.athlete_id == row.teammates[0].id
    assert row.team_name == "MASSONNEAU PIERRE / BESANCON FABIEN ."
    assert athlete_repository.get(db_session, team_id) is None
    assert (out["imported"], out["updated"]) == (0, 1)


def test_rescrape_keeps_a_team_athlete_that_still_has_other_results(
    db_session, patch_scraper, monkeypatch
):
    line = _relay("7", "MASSONNEAU PIERRE", "/ BESANCON FABIEN .")
    _import_before_895(db_session, patch_scraper, monkeypatch, [line])
    team_id = _only_relay_row(db_session).athlete_id
    other = course_repository.get_or_create(
        db_session, name="Autre relais", event_date=date(2026, 6, 1), event_type="triathlon-s"
    )
    participation_repository.create(
        db_session, athlete_id=team_id, course_id=other.id, bib_number="3", is_relay=True
    )
    db_session.commit()

    patch_scraper([line])
    import_service.import_event(db_session, URL, _settings())

    team = athlete_repository.get(db_session, team_id)
    assert [p.course_id for p in team.participations] == [other.id]


def test_rescrape_of_split_relays_is_idempotent(db_session, patch_scraper):
    from app.models.athlete import Athlete

    lines = [
        _relay("7", "CANNIOU/OLIVIER", "Cedric/Leclerc"),
        _relay("", "MASSONNEAU PIERRE", "/ BESANCON FABIEN ."),
    ]
    patch_scraper(lines)
    import_service.import_event(db_session, URL, _settings())
    course = course_repository.get_latest_by_source_url(db_session, URL)

    def snapshot():
        rows = participation_repository.list_for_course(db_session, course.id)
        return sorted((row.id, row.athlete_id, tuple(a.id for a in row.teammates)) for row in rows)

    first = snapshot()
    athletes = db_session.query(Athlete).count()
    for _ in range(2):
        _expire_cache(db_session)
        patch_scraper(lines)
        out = import_service.import_event(db_session, URL, _settings())
        assert out["imported"] == 0
        assert snapshot() == first
        assert db_session.query(Athlete).count() == athletes


def test_rescrape_keeps_a_composition_set_by_an_admin(db_session, patch_scraper):
    line = _relay("7", "DUPONT Jean / MARTIN Paul", "")
    patch_scraper([line])
    import_service.import_event(db_session, URL, _settings())
    row = _only_relay_row(db_session)
    jean, paul = row.teammates
    luc = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Luc")
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    admin_actions.set_teammates(
        db_session, participation_id=row.id, teammates=[paul.id, jean.id, luc.id],
        user_id=admin.id,
    )
    db_session.commit()
    _expire_cache(db_session)

    patch_scraper([line])
    import_service.import_event(db_session, URL, _settings())

    assert [a.id for a in _only_relay_row(db_session).teammates] == [paul.id, jean.id, luc.id]


# ── Retours de revue (#895) ───────────────────────────────────────────────────


def _relay_rows(db_session):
    course = course_repository.get_latest_by_source_url(db_session, URL)
    return participation_repository.list_for_course(db_session, course.id)


def test_rescrape_does_not_duplicate_a_team_with_several_bibless_rows(
    db_session, patch_scraper, monkeypatch
):
    lines = [
        _relay("", "DUPONT Jean / MARTIN Paul", "", total_time="01:00:00"),
        _relay("", "DUPONT Jean / MARTIN Paul", "", total_time="01:10:00"),
    ]
    _import_before_895(db_session, patch_scraper, monkeypatch, lines)

    patch_scraper(lines)
    out = import_service.import_event(db_session, URL, _settings())

    assert len(_relay_rows(db_session)) == 2
    assert out["imported"] == 0


def test_split_fallback_keeps_the_reconcile_guard(db_session, patch_scraper, monkeypatch):
    # #66 : une correction qui viderait le prénom ne réconcilie jamais, même quand
    # le découpage retombe sur le chemin d'avant #895 (MARTIN PAUL déjà présent).
    _import_before_895(db_session, patch_scraper, monkeypatch, [
        _relay("7", "DUPONT JEAN", "/ MARTIN PAUL"), _relay("8", "MARTIN", "PAUL"),
    ])

    patch_scraper([_relay("7", "DUPONT JEAN / MARTIN PAUL", ""), _relay("8", "MARTIN", "PAUL")])
    out = import_service.import_event(db_session, URL, _settings())

    assert out["reconciled"] == 0
    assert athlete_repository.get_by_identity(
        db_session, "DUPONT JEAN / MARTIN PAUL", "", None
    ) is None


def test_guard_holds_when_the_individual_line_comes_in_a_later_tranche(
    db_session, patch_scraper, monkeypatch
):
    monkeypatch.setattr(import_service, "_TRANCHE_SIZE", 1)
    patch_scraper([_relay("1", "DUPONT Jean / MARTIN Paul", ""), _relay("2", "DUPONT", "Jean")])

    import_service.import_event(db_session, URL, _settings())

    jean = athlete_repository.get_by_identity(db_session, "DUPONT", "Jean", None)
    rows = _relay_rows(db_session)
    assert [row.bib_number for row in rows if jean.id in {row.athlete_id, *(a.id for a in row.teammates)}] == ["2"]


def test_resplit_purges_the_team_athlete_even_without_field_change(
    db_session, patch_scraper, monkeypatch
):
    line = _relay("7", "DUPONT Jean / MARTIN Paul", "")
    _import_before_895(db_session, patch_scraper, monkeypatch, [line])
    (row,) = _relay_rows(db_session)
    # `reassign_participation` vide une composition mais garde `team_name`.
    row.team_name = "DUPONT Jean / MARTIN Paul"
    team_id = row.athlete_id
    db_session.commit()

    patch_scraper([line])
    import_service.import_event(db_session, URL, _settings())
    db_session.expire_all()

    assert athlete_repository.get(db_session, team_id) is None


# ── Revue de la PR parapluie #1001 ────────────────────────────────────────────


def _compose(db_session, participation, *names):
    athletes = [athlete_repository.get_or_create(db_session, nom=nom, prenom=prenom)
                for nom, prenom in names]
    admins = user_repository.find_by_email(db_session, "admin@exemple.fr")
    admin = admins[0] if admins else user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    admin_actions.set_teammates(
        db_session, participation_id=participation.id,
        teammates=[athlete.id for athlete in athletes], user_id=admin.id,
    )


@pytest.mark.parametrize("order", [1, -1], ids=["meme-ordre", "ordre-inverse"])
def test_rescrape_does_not_cross_two_composed_relays_with_the_same_team_name(
    db_session, patch_scraper, order
):
    lines = [
        _relay("", "LES COPAINS", "", total_time="01:00:00"),
        _relay("", "LES COPAINS", "", total_time="01:10:00"),
    ]
    patch_scraper(lines)
    import_service.import_event(db_session, URL, _settings())
    first, second = sorted(_relay_rows(db_session), key=lambda row: row.total_time)
    _compose(db_session, first, ("DUPONT", "Jean"), ("MARTIN", "Paul"))
    _compose(db_session, second, ("DURAND", "Luc"), ("PETIT", "Marc"))
    db_session.commit()
    _expire_cache(db_session)

    patch_scraper(lines[::order])
    import_service.import_event(db_session, URL, _settings())

    rows = {row.id: row for row in _relay_rows(db_session)}
    assert set(rows) == {first.id, second.id}
    assert rows[first.id].total_time == "01:00:00"
    assert rows[second.id].total_time == "01:10:00"
    assert athlete_repository.get_by_identity(db_session, "LES COPAINS", "", None) is None


def test_rescrape_finds_a_composed_relay_whose_course_only_is_a_relay(db_session, patch_scraper):
    # Heat klikego : l'épreuve est retrouvée par son URL (règle R, #289) même après
    # que l'admin l'a marquée relais, alors que la ligne publiée ne l'est pas.
    heat_url = "https://www.klikego.com/resultats/mesquer/1677015306084-12?heat=duo"
    line = _result("", "LES COPAINS", "", event_type="triathlon-s", source_url=heat_url)
    patch_scraper([line])
    import_service.import_event(db_session, heat_url, _settings())
    course = course_repository.get_latest_by_source_url(db_session, heat_url)
    (row,) = participation_repository.list_for_course(db_session, course.id)
    course.is_relay = True
    db_session.flush()
    _compose(db_session, row, ("DUPONT", "Jean"), ("MARTIN", "Paul"))
    db_session.commit()
    _expire_cache(db_session, heat_url)

    patch_scraper([line])
    out = import_service.import_event(db_session, heat_url, _settings())

    assert [r.id for r in participation_repository.list_for_course(db_session, course.id)] == [
        row.id
    ]
    assert out["imported"] == 0
    assert athlete_repository.get_by_identity(db_session, "LES COPAINS", "", None) is None
