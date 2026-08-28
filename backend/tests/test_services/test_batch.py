import threading
import time
from contextlib import contextmanager
from dataclasses import fields
from datetime import date

from app.core.config import Settings
from app.models.athlete import Athlete
from app.services import batch, import_service
from app.services.batch import CHAMPS_COMMUNS, BatchItem, BatchTotals
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


# --- _group_by_host -----------------------------------------------------------


def test_group_by_host_regroupe_par_chronometreur_et_preserve_l_ordre():
    items = [
        BatchItem(url="https://www.klikego.com/e/1", label="klikego · A"),
        BatchItem(url="https://www.breizhchrono.com/e/1", label="breizhchrono · A"),
        BatchItem(url="https://www.klikego.com/e/2", label="klikego · B"),
    ]

    groups = batch._group_by_host(items)

    assert [host for host, _ in groups] == ["klikego", "breizhchrono"]
    assert [item.label for item in dict(groups)["klikego"]] == ["klikego · A", "klikego · B"]
    assert [item.label for item in dict(groups)["breizhchrono"]] == ["breizhchrono · A"]


def test_group_by_host_ne_fusionne_jamais_deux_domaines_d_un_provider_multi_domaines():
    """Wiclax publie sur trois domaines distincts : les regrouper par domaine
    littéral romprait la politesse envers ce chronométreur (cf. Clarifications
    de spec.md) — ils doivent porter le **même** `host_key`."""
    items = [
        BatchItem(url="https://www.wiclax-results.com/e/1", label="wiclax · A"),
        BatchItem(url="https://www.chronowest.fr/e/1", label="wiclax · B"),
        BatchItem(url="https://www.chronosmetron.com/e/1", label="wiclax · C"),
    ]

    groups = batch._group_by_host(items)

    assert len(groups) == 1
    host, group_items = groups[0]
    assert host == "wiclax"
    assert [item.label for item in group_items] == ["wiclax · A", "wiclax · B", "wiclax · C"]


def test_group_by_host_donne_un_groupe_distinct_par_url_inconnue():
    """Deux URLs non reconnues par le registre ne doivent pas être fusionnées
    sous une même clé vide — sinon elles se sérialiseraient l'une l'autre sans
    raison (aucun chronométreur réel ne les relie)."""
    items = [
        BatchItem(url="https://inconnu-a.example/e/1", label="A"),
        BatchItem(url="https://inconnu-b.example/e/1", label="B"),
    ]

    groups = batch._group_by_host(items)

    assert len(groups) == 2
    assert {host for host, _ in groups} == {"inconnu-a.example", "inconnu-b.example"}


def _phases_ok(db, url, settings, force=False, persist=True, **kwargs):
    """Simule iter_import_event pour une épreuve de 30 participants."""
    yield {"phase": "scraping", "message": "Récupération des participants…"}
    yield {"phase": "saving", "total": 30, "imported": 0, "skipped": 0, "progress": 0}
    yield {"phase": "saving", "total": 30, "imported": 20, "skipped": 0, "progress": 20}
    yield {"phase": "saving", "total": 30, "imported": 28, "skipped": 2, "progress": 30}
    yield {"phase": "done", "imported": 28, "skipped": 2, "total": 30}


# --- concurrence entre chronométreurs (US1) -----------------------------------


def test_run_batch_traite_deux_chronometreurs_en_meme_temps(
    db_session_concurrent, monkeypatch, concurrency_gauge
):
    release = threading.Barrier(2, timeout=10)

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        with concurrency_gauge.track():
            release.wait()
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [
        BatchItem(url="https://host-a.example/e/1", label="A"),
        BatchItem(url="https://host-b.example/e/1", label="B"),
    ]
    totals = batch.run_batch(db_session_concurrent, items, _settings(), force=False, delay=0.0)

    assert concurrency_gauge.peak == 2
    assert totals.imported == 2


def test_run_batch_respecte_le_plafond_de_concurrence(
    db_session_concurrent, monkeypatch, concurrency_gauge
):
    """k+1 chronométreurs, `max_concurrent_hosts=k` : au plus k tournent en
    même temps — le pic observé le confirme, la barrière garantit qu'il est
    bien atteint (pas un minutage qui pourrait le manquer par chance)."""
    k = 2
    release = threading.Barrier(k, timeout=10)

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        with concurrency_gauge.track():
            if "sync" in url:
                release.wait()
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [BatchItem(url=f"https://host-{i}.example/e/sync", label=str(i)) for i in range(k)]
    items.append(BatchItem(url="https://host-last.example/e/plain", label="last"))

    batch.run_batch(
        db_session_concurrent, items, _settings(), force=False, delay=0.0, max_concurrent_hosts=k,
    )

    assert concurrency_gauge.peak == k


def test_run_batch_bilan_identique_sous_concurrence_ou_non(
    db_session, db_session_concurrent, monkeypatch
):
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [
        BatchItem(url="https://host-a.example/e/1", label="A"),
        BatchItem(url="https://host-b.example/e/1", label="B"),
        BatchItem(url="https://host-c.example/e/1", label="C"),
    ]

    sequentiel = batch.run_batch(
        db_session, items, _settings(), force=False, delay=0.0, max_concurrent_hosts=1,
    )
    parallele = batch.run_batch(
        db_session_concurrent, items, _settings(), force=False, delay=0.0,
    )

    for champ in CHAMPS_COMMUNS:
        valeur_sequentielle = getattr(sequentiel, champ)
        valeur_parallele = getattr(parallele, champ)
        if champ in ("failures", "passive_sources", "reassignments"):
            assert sorted(valeur_sequentielle, key=str) == sorted(valeur_parallele, key=str), champ
        else:
            assert valeur_sequentielle == valeur_parallele, champ


def test_run_batch_l_echec_d_un_groupe_n_affecte_pas_un_autre_groupe_concurrent(
    db_session_concurrent, monkeypatch, concurrency_gauge
):
    release = threading.Barrier(2, timeout=10)

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        with concurrency_gauge.track():
            release.wait()
        if "boom" in url:
            yield {"phase": "error", "message": "timeout scrape"}
            return
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [
        BatchItem(url="https://host-boom.example/e/1", label="boom"),
        BatchItem(url="https://host-ok.example/e/1", label="ok"),
    ]

    totals = batch.run_batch(db_session_concurrent, items, _settings(), force=False, delay=0.0)

    assert concurrency_gauge.peak == 2  # elles ont bien tourné en même temps
    assert totals.errors == 1
    assert totals.imported == 28  # l'autre groupe a terminé normalement, sans être affecté
    assert totals.failures == [
        batch.BatchFailure(
            url="https://host-boom.example/e/1", label="boom", message="timeout scrape",
        ),
    ]


def test_run_batch_ctrl_c_multi_hotes_stoppe_les_nouvelles_epreuves(
    db_session_concurrent, monkeypatch, fake_reporter
):
    """Un groupe reçoit le Ctrl-C ; l'autre, déjà en cours au même instant, va à
    son terme ; un troisième, pas encore démarré, ne démarre jamais.

    `release` ne garantit que le démarrage simultané de "stop" et "ok" — pas
    l'ordre dans lequel leurs workers se libèrent ensuite. Sans
    `stop_processed`, "ok" (import complet) peut libérer son worker avant que
    "stop" (exception quasi immédiate) ait posé `stop_event`, et le worker
    libre récupère alors "jamais" dans la queue de l'executor avant que
    l'interruption soit prise en compte — flaky sous contention CPU (CI).
    `stop_processed` force "ok" à attendre que le log d'interruption ait été
    émis avant de terminer, ce qui rend l'ordre déterministe.
    """
    release = threading.Barrier(2, timeout=10)
    stop_processed = threading.Event()
    original_warning = batch.logger.warning

    def _warning_spy(msg, *args, **kwargs):
        if msg == "Interruption clavier — arrêt du batch":
            stop_processed.set()
        return original_warning(msg, *args, **kwargs)

    monkeypatch.setattr(batch.logger, "warning", _warning_spy)

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        release.wait()
        if "stop" in url:
            raise KeyboardInterrupt
        assert stop_processed.wait(timeout=5), (
            "le groupe stop n'a pas signalé l'interruption à temps"
        )
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [
        BatchItem(url="https://host-stop.example/e/1", label="stop"),
        BatchItem(url="https://host-ok.example/e/1", label="ok"),
        BatchItem(url="https://host-jamais.example/e/1", label="jamais"),
    ]

    totals = batch.run_batch(
        db_session_concurrent, items, _settings(), force=False, delay=0.0,
        reporter=fake_reporter, max_concurrent_hosts=2,
    )

    assert totals.interrupted is True
    assert totals.imported == 28  # le groupe "ok" a terminé normalement
    assert not any(call[0] == "item_start" and call[2] == "jamais" for call in fake_reporter.calls)


def test_run_batch_echec_d_ouverture_de_session_de_groupe_ne_perd_pas_le_bilan(
    db_session_concurrent, monkeypatch
):
    """Un groupe dont la Session ne peut pas s'ouvrir (pool épuisé, coupure
    transitoire) doit compter en échec — pas faire perdre le bilan de tout
    le batch en laissant l'exception s'échapper de `run_batch`."""

    def _sessionmaker_factice(*args, **kwargs):
        def _leve(*a, **k):
            raise RuntimeError("pool épuisé")
        return _leve

    monkeypatch.setattr(batch, "sessionmaker", _sessionmaker_factice)

    items = [BatchItem(url="https://host-a.example/e/1", label="A")]

    totals = batch.run_batch(db_session_concurrent, items, _settings(), force=False, delay=0.0)

    assert totals.errors == 1
    assert totals.processed == 1
    assert totals.failures == [
        batch.BatchFailure(
            url="https://host-a.example/e/1", label="A", message="pool épuisé",
        ),
    ]


# --- politesse par chronométreur, y compris multi-domaines (US2) --------------


def test_run_batch_politesse_intra_hote_preservee_avec_un_autre_hote_en_parallele(
    db_session_concurrent, monkeypatch
):
    """Aucune implémentation propre à cette story : elle verrouille par test ce
    que le regroupement (Foundational) et le modèle un-thread-par-groupe (US1)
    garantissent déjà par construction."""
    ordre: list[str] = []
    appels: list[float] = []
    monkeypatch.setattr(batch.time, "sleep", lambda s: appels.append(s))

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        ordre.append(url)
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [
        BatchItem(url="https://host-same.example/e/1", label="A"),
        BatchItem(url="https://host-other.example/e/1", label="B"),
        BatchItem(url="https://host-same.example/e/2", label="C"),
    ]

    batch.run_batch(db_session_concurrent, items, _settings(), force=False, delay=2.5)

    memes_hote = [url for url in ordre if "host-same" in url]
    assert memes_hote == [
        "https://host-same.example/e/1", "https://host-same.example/e/2",
    ]  # ordre préservé au sein du même hôte
    # Un seul délai de politesse : s'il y en avait zéro, les deux épreuves du
    # même hôte auraient été traitées comme deux groupes séparés (bug de
    # regroupement) ; s'il y en avait deux, le délai se serait appliqué au
    # mauvais endroit (ex. après le dernier élément d'un groupe).
    assert appels == [2.5]


def test_run_batch_deux_domaines_d_un_provider_multi_domaines_ne_partent_jamais_en_parallele(
    db_session_concurrent, monkeypatch, concurrency_gauge
):
    """Wiclax publie sur trois domaines distincts (research.md) : ils doivent
    former un seul groupe de politesse, jamais deux scrapes en même temps."""

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        with concurrency_gauge.track():
            time.sleep(0.05)  # élargit la fenêtre : un chevauchement réel serait vu
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    items = [
        BatchItem(url="https://www.wiclax-results.com/e/1", label="wiclax · A"),
        BatchItem(url="https://www.chronowest.fr/e/1", label="wiclax · B"),
        BatchItem(url="https://www.chronosmetron.com/e/1", label="wiclax · C"),
    ]

    batch.run_batch(db_session_concurrent, items, _settings(), force=False, delay=0.0)

    assert concurrency_gauge.peak == 1


def test_run_batch_relaie_la_progression_intra_epreuve(db_session, monkeypatch, fake_reporter):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="klikego · A")], _settings(),
        force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.imported == 28
    assert totals.skipped == 2
    assert totals.errors == 0
    assert fake_reporter.calls == [
        ("batch_start", 1),
        ("item_start", 0, "klikego · A", "k"),
        ("item_progress", 0, 30, "k"),
        ("item_progress", 20, 30, "k"),
        ("item_progress", 30, 30, "k"),
        ("item_done", 28, 2, None, "k"),
        ("batch_end",),
    ]


def test_run_batch_phase_error_compte_une_erreur_sans_interrompre(
    db_session, monkeypatch, fake_reporter
):
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        if "boom" in url:
            yield {"phase": "error", "message": "timeout scrape"}
            return
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/boom", label="A"), BatchItem(url="https://k/ok", label="B")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.errors == 1
    assert totals.imported == 28  # la 2e épreuve a bien été traitée
    assert ("item_done", 0, 0, "timeout scrape", "k") in fake_reporter.calls


def test_run_batch_collecte_le_detail_des_echecs(db_session, monkeypatch):
    """`errors` dit *combien* ; `failures` dit *lesquelles* et *pourquoi*.

    On veut pouvoir diagnostiquer (ou rescraper) les épreuves fautives sans
    rejouer le batch : chaque échec retient son URL et son message.
    """
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        if "crash" in url:
            raise RuntimeError("bug inattendu")  # exception réelle → filet de run_batch
        yield {"phase": "error", "message": "timeout scrape"}  # phase error explicite

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [
            BatchItem(url="https://k/boom", label="klikego · A"),
            BatchItem(url="https://k/crash", label="klikego · B"),
        ],
        _settings(), force=False, delay=0.0,
    )

    assert totals.errors == 2
    assert totals.failures == [
        batch.BatchFailure(url="https://k/boom", label="klikego · A", message="timeout scrape"),
        batch.BatchFailure(url="https://k/crash", label="klikego · B", message="bug inattendu"),
    ]


def test_run_batch_sans_echec_ne_collecte_rien(db_session, monkeypatch):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.failures == []


def test_run_batch_une_exception_reelle_compte_aussi_une_erreur(db_session, monkeypatch):
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        raise RuntimeError("bug inattendu")
        yield  # pragma: no cover — fait de _phases un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.errors == 1
    assert totals.imported == 0


def test_run_batch_une_exception_a_message_vide_compte_une_erreur(db_session, monkeypatch):
    """`str(ValueError())` vaut `""` : sans repli sur le nom de la classe, le
    `if result.error:` de `run_batch` est faux et l'épreuve est comptée en
    succès (zéro participant) au lieu d'une erreur.
    """
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        raise ValueError
        yield  # pragma: no cover — fait de _phases un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.errors == 1
    assert totals.imported == 0
    assert totals.failures == [
        batch.BatchFailure(url="https://k/1", label="A", message="ValueError"),
    ]


def test_run_batch_ctrl_c_conserve_le_travail_deja_fait(db_session, monkeypatch, fake_reporter):
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        if "stop" in url:
            raise KeyboardInterrupt
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/ok", label="A"), BatchItem(url="https://k/stop", label="B"),
         BatchItem(url="https://k/jamais", label="C")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.interrupted is True
    assert totals.imported == 28   # la 1re épreuve est conservée
    assert totals.errors == 0      # une interruption n'est pas une erreur
    assert ("item_start", 2, "C") not in fake_reporter.calls  # la 3e n'a pas démarré
    assert fake_reporter.calls[-1] == ("batch_end",)          # les barres sont bien fermées


def test_run_batch_compte_les_epreuves_traitees(db_session, monkeypatch):
    """`processed` compte des **épreuves**, là où `imported`/`skipped` comptent des participants.

    Sans lui, un bilan interrompu affiche « Épreuves ciblées : 42 » et des
    milliers de participants ignorés, sans dire combien des 42 ont réellement
    été tentées : l'opérateur ne peut pas situer où le Ctrl-C a coupé.
    """
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/1", label="A"), BatchItem(url="https://k/2", label="B")],
        _settings(), force=False, delay=0.0,
    )

    assert totals.processed == 2       # deux épreuves
    assert totals.imported == 56       # 28 participants chacune : une autre unité


def test_run_batch_ctrl_c_ne_compte_pas_l_epreuve_coupee_en_traitee(db_session, monkeypatch):
    """Une épreuve interrompue en plein vol n'a pas été traitée : elle ne compte pas.

    Le Ctrl-C tombe pendant la 2e des trois épreuves ⇒ une seule est allée au bout.
    """
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        if "stop" in url:
            raise KeyboardInterrupt
        yield from _phases_ok(db, url, settings, force)

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/ok", label="A"), BatchItem(url="https://k/stop", label="B"),
         BatchItem(url="https://k/jamais", label="C")],
        _settings(), force=False, delay=0.0,
    )

    assert totals.interrupted is True
    assert totals.processed == 1


def test_run_batch_une_epreuve_en_erreur_reste_une_epreuve_traitee(db_session, monkeypatch):
    """Tentée et échouée = traitée. Sinon `traitées` mentirait sur ce qui a été tenté."""
    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "error", "message": "timeout scrape"}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/boom", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.errors == 1
    assert totals.processed == 1


def test_run_batch_transmet_force_au_generateur(db_session, monkeypatch):
    vus: list[bool] = []

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        vus.append(force)
        yield {"phase": "done", "imported": 1, "skipped": 0, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=True, delay=0.0,
    )

    assert vus == [True]


def test_run_batch_sans_reporter_ne_leve_pas(db_session, monkeypatch):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.imported == 28  # NullReporter par défaut


def test_run_batch_assainit_la_session_apres_une_exception_brute(
    db_session, monkeypatch, fake_reporter
):
    """Une exception brute (pas le chemin persistance de `iter_import_event`, qui
    fait déjà son propre rollback) ne doit pas poisonner la Session pour les
    épreuves suivantes — sans quoi elles échouent en cascade avec
    `PendingRollbackError`, même si elles n'ont rien à voir avec la 1re panne.
    """

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        if "boom" in url:
            # Simule une coupure DB brute : IntegrityError qui remonte sans
            # rollback, comme le SELECT non protégé de `_cached_result`.
            db.add(Athlete(nom="Dupont", prenom="Jean", birth_date=date(1990, 1, 1)))
            db.add(Athlete(nom="Dupont", prenom="Jean", birth_date=date(1990, 1, 1)))
            db.flush()
            return
        # 2e épreuve : une vraie requête sur la même Session — lève
        # PendingRollbackError si la Session n'a pas été assainie entre-temps.
        db.query(Athlete).count()
        yield {"phase": "done", "imported": 5, "skipped": 1, "total": 6}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/boom", label="A"), BatchItem(url="https://k/ok", label="B")],
        _settings(), force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.errors == 1
    assert totals.imported == 5  # la 2e épreuve a bien pu utiliser la Session
    assert totals.skipped == 1


def test_run_batch_saving_puis_error_ne_credite_pas_les_compteurs(
    db_session, monkeypatch, fake_reporter
):
    """Chemin réel de `iter_import_event` : des phases `saving` avec des
    compteurs non nuls, suivies d'une phase `error` sur son rollback interne —
    ces compteurs partiels ne doivent pas être crédités au batch.
    """

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "saving", "total": 30, "imported": 10, "skipped": 1, "progress": 15}
        yield {"phase": "error", "message": "coupure réseau pendant l'enregistrement"}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.errors == 1
    assert totals.imported == 0
    assert totals.skipped == 0


def test_run_batch_un_reporter_qui_leve_ne_fait_pas_perdre_le_bilan(db_session, monkeypatch):
    """`… | head -20` ferme le tube : le reporter lève `BrokenPipeError` en plein
    batch. L'affichage est accessoire, les données ne le sont pas — le batch doit
    aller au bout et rendre son `BatchTotals`, pas une traceback.
    """

    class ReporterCasse:
        """Tube fermé : tout écrit échoue."""

        def batch_start(self, total): raise BrokenPipeError("tube fermé")
        def item_start(self, index, label, host): raise BrokenPipeError("tube fermé")
        def item_progress(self, done, total, host): raise BrokenPipeError("tube fermé")
        def item_done(self, imported, skipped, error, host): raise BrokenPipeError("tube fermé")
        def batch_end(self): raise BrokenPipeError("tube fermé")

    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session,
        [BatchItem(url="https://k/1", label="A"), BatchItem(url="https://k/2", label="B")],
        _settings(), force=False, delay=0.0, reporter=ReporterCasse(),
    )

    assert totals.imported == 56  # les 2 épreuves ont bien été traitées
    assert totals.skipped == 4
    assert totals.errors == 0  # un affichage cassé n'est pas une épreuve en échec
    assert totals.interrupted is False


def test_run_batch_un_reporter_qui_leve_ne_masque_pas_le_ctrl_c(db_session, monkeypatch):
    """Le filet du reporter ne doit pas avaler `KeyboardInterrupt` (BaseException)."""

    class ReporterCtrlC:
        def batch_start(self, total): pass
        def item_start(self, index, label, host): raise KeyboardInterrupt
        def item_progress(self, done, total, host): pass
        def item_done(self, imported, skipped, error, host): pass
        def batch_end(self): pass

    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0, reporter=ReporterCtrlC(),
    )

    assert totals.interrupted is True  # le Ctrl-C a bien remonté jusqu'à run_batch


def test_run_batch_referme_la_transaction_de_lecture_de_chaque_epreuve(db_session, monkeypatch):
    """Chemins « cached » et « error » de `iter_import_event` : le SELECT du cache
    TTL (`_cached_result`) ouvre une transaction que personne ne referme. Sur
    Supabase, un `import-sheet` relancé sur un Sheet déjà importé la laissait
    `idle in transaction` pendant tout le run.
    """

    def _phases_cached(db, url, settings, force=False, persist=True, **kwargs):
        db.query(Athlete).count()  # le SELECT de `_cached_result` : ouvre la transaction
        yield {"phase": "done", "imported": 0, "skipped": 3, "total": 3, "cached": True}

    monkeypatch.setattr(import_service, "iter_import_event", _phases_cached)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.skipped == 3
    assert db_session.in_transaction() is False  # aucune transaction ne survit à l'épreuve


def test_run_batch_pause_entre_epreuves_mais_pas_apres_la_derniere(
    db_session, monkeypatch, fake_reporter
):
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    appels: list[float] = []
    monkeypatch.setattr(batch.time, "sleep", lambda s: appels.append(s))

    items = [
        BatchItem(url="https://k/1", label="A"),
        BatchItem(url="https://k/2", label="B"),
        BatchItem(url="https://k/3", label="C"),
    ]
    batch.run_batch(db_session, items, _settings(), force=False, delay=2.5, reporter=fake_reporter)

    assert appels == [2.5, 2.5]


def test_run_batch_cumule_les_reconciliations(db_session, monkeypatch):
    from app.services import batch, import_service
    from app.services.import_service import Reassignment

    def _iter(db, url, settings, force=False, persist=True, **kwargs):
        yield {
            "phase": "done", "imported": 0, "skipped": 0, "total": 1,
            "reconciled": 1,
            "reassignments": [Reassignment("BERRE | Audrey LE", "LE BERRE | Audrey", False)],
        }

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    items = [batch.BatchItem(url="https://k/1", label="klikego · A")]
    totals = batch.run_batch(db_session, items, _settings(), force=True, delay=0.0)

    assert totals.reconciled == 1
    assert totals.reassignments == [
        Reassignment("BERRE | Audrey LE", "LE BERRE | Audrey", False)
    ]


def test_run_batch_cumule_updated(db_session, monkeypatch):
    from app.services import batch, import_service

    def _fake_iter(db, url, settings, force, persist=True, **kwargs):
        yield {"phase": "saving", "total": 1, "imported": 0, "updated": 1, "skipped": 0, "progress": 1}
        yield {"phase": "done", "imported": 0, "updated": 1, "skipped": 2, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _fake_iter)

    totals = batch.run_batch(
        db_session,
        [batch.BatchItem(url="http://a", label="a"), batch.BatchItem(url="http://b", label="b")],
        _settings(),
        force=True,
        delay=0,
    )
    assert totals.updated == 2
    assert totals.imported == 0
    assert totals.skipped == 4
    assert totals.errors == 0


def test_run_batch_borne_une_unite_de_travail_par_epreuve(db_session, monkeypatch):
    """C'est le branchement qui rend un N+1 d'import visible : « 1812 requêtes
    pour 1810 participants » ne se lit que si l'unité de mesure est l'épreuve."""
    monkeypatch.setattr(import_service, "iter_import_event", _phases_ok)

    unites: list[str] = []

    @contextmanager
    def _espion(label):
        unites.append(label)
        yield None

    monkeypatch.setattr(batch, "measure_queries", _espion)

    batch.run_batch(
        db_session,
        [
            batch.BatchItem(url="https://k/1", label="klikego · A"),
            batch.BatchItem(url="https://k/2", label="klikego · B"),
        ],
        _settings(),
        force=False,
        delay=0.0,
    )

    assert unites == ["klikego · A", "klikego · B"]


def test_unite_de_travail_ouverte_meme_sur_une_epreuve_en_echec(db_session, monkeypatch):
    """Le filet `try`/`except` vit *dans* l'unité de mesure : une épreuve qui
    plante est justement celle qu'on veut mesurer."""
    def _phases(db, url, settings, force=False, persist=True):
        raise RuntimeError("bug inattendu")
        yield  # inatteignable, mais fait de la fonction un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    unites: list[str] = []

    @contextmanager
    def _espion(label):
        unites.append(label)
        yield None

    monkeypatch.setattr(batch, "measure_queries", _espion)

    totals = batch.run_batch(
        db_session,
        [batch.BatchItem(url="https://k/crash", label="A")],
        _settings(),
        force=False,
        delay=0.0,
    )

    assert totals.errors == 1
    assert unites == ["A"]


# --- règle « échec total » ----------------------------------------------------


def test_est_echec_total_quand_toutes_les_epreuves_echouent():
    assert batch.est_echec_total(epreuves=53, errors=53) is True


def test_est_echec_total_faux_sur_un_succes_partiel():
    """Quelques échecs sur 50 : le batch reste un succès."""
    assert batch.est_echec_total(epreuves=50, errors=3) is False


def test_est_echec_total_faux_quand_il_n_y_avait_rien_a_traiter():
    """Sheet vide, `--limit 0`, filtre sans résultat : rien à faire n'est pas un échec."""
    assert batch.est_echec_total(epreuves=0, errors=0) is False


def test_les_champs_communs_existent_des_deux_cotes():
    """Garde-fou de `copy_totals` : il recopie par `setattr`.

    Un champ renommé d'un seul côté ne lèverait pas — il **créerait** un attribut
    parasite sur l'Outcome et laisserait le compteur d'origine à zéro, sans que
    rien ne rougisse. Ce test est ce qui rend la recopie factorisée sûre.

    Ces sept champs sont aussi la forme **plate** de la sortie `--json` : le
    pipeline `import-sheet --json | jq -r '.failures[].url' | rescrape-db
    --urls-from -` en dépend.
    """
    for classe in (BatchTotals, SheetOutcome, RescrapeOutcome):
        champs = {f.name for f in fields(classe)}
        assert set(CHAMPS_COMMUNS) <= champs, f"{classe.__name__} : {set(CHAMPS_COMMUNS) - champs}"


def test_a_registered_passive_source_travels_from_the_done_phase_to_the_totals(
    db_session, monkeypatch, fake_reporter
):
    """#283, AC5 — le signalement traverse `_ItemResult` puis `BatchTotals`.

    Le contrat de recopie est `CHAMPS_COMMUNS` : un champ qui n'y figure pas
    n'atteint jamais l'`Outcome` de la commande, donc ni le rapport texte ni la
    charge `--json`. C'est le patron de `failures`, épinglé pour la même raison.
    """
    from app.services.import_service import PassiveSource

    signalee = PassiveSource(
        url="https://resultats.breizhchrono.com/r/1",
        course_name="Triathlon de Mesquer",
        message="« Triathlon de Mesquer » est déjà en base : …",
    )

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "done", "imported": 0, "skipped": 42, "total": 42,
               "passive_sources": [signalee]}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="klikego · A")], _settings(),
        force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.passive_sources == [signalee]
    assert "passive_sources" in CHAMPS_COMMUNS


def test_a_registered_passive_source_is_neither_an_error_nor_an_import(
    db_session, monkeypatch, fake_reporter
):
    """« Ni succès d'import, ni échec » (AC5), pris au mot sur les deux compteurs.

    Précédent : `ignored_by_host`, tenu hors d'`echec_total` parce que ces liens
    n'ont jamais été tentés. Ici l'épreuve *a* été traitée — elle n'a simplement
    rien importé de neuf, ce qui reste un succès (`est_echec_total` compare des
    épreuves, pas des participants).
    """
    from app.services.import_service import PassiveSource

    def _phases(db, url, settings, force=False, persist=True, **kwargs):
        yield {"phase": "done", "imported": 0, "updated": 0, "skipped": 12, "total": 12,
               "passive_sources": [PassiveSource(url=url, course_name="Mesquer", message="…")]}

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="klikego · A")], _settings(),
        force=False, delay=0.0, reporter=fake_reporter,
    )

    assert totals.errors == 0
    assert totals.imported == 0
    assert totals.failures == []
    assert SheetOutcome(unique_supported=1, errors=0).echec_total is False
