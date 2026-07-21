from datetime import date

from app.core.config import Settings
from app.models.athlete import Athlete
from app.services import batch, import_service
from app.services.batch import BatchItem


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _phases_ok(db, url, settings, force=False, persist=True):
    """Simule iter_import_event pour une épreuve de 30 participants."""
    yield {"phase": "scraping", "message": "Récupération des participants…"}
    yield {"phase": "saving", "total": 30, "imported": 0, "skipped": 0, "progress": 0}
    yield {"phase": "saving", "total": 30, "imported": 20, "skipped": 0, "progress": 20}
    yield {"phase": "saving", "total": 30, "imported": 28, "skipped": 2, "progress": 30}
    yield {"phase": "done", "imported": 28, "skipped": 2, "total": 30}


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
        ("item_start", 0, "klikego · A"),
        ("item_progress", 0, 30),
        ("item_progress", 20, 30),
        ("item_progress", 30, 30),
        ("item_done", 28, 2, None),
        ("batch_end",),
    ]


def test_run_batch_phase_error_compte_une_erreur_sans_interrompre(
    db_session, monkeypatch, fake_reporter
):
    def _phases(db, url, settings, force=False, persist=True):
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
    assert ("item_done", 0, 0, "timeout scrape") in fake_reporter.calls


def test_run_batch_collecte_le_detail_des_echecs(db_session, monkeypatch):
    """`errors` dit *combien* ; `failures` dit *lesquelles* et *pourquoi*.

    On veut pouvoir diagnostiquer (ou rescraper) les épreuves fautives sans
    rejouer le batch : chaque échec retient son URL et son message.
    """
    def _phases(db, url, settings, force=False, persist=True):
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
    def _phases(db, url, settings, force=False, persist=True):
        raise RuntimeError("bug inattendu")
        yield  # pragma: no cover — fait de _phases un générateur

    monkeypatch.setattr(import_service, "iter_import_event", _phases)

    totals = batch.run_batch(
        db_session, [BatchItem(url="https://k/1", label="A")], _settings(),
        force=False, delay=0.0,
    )

    assert totals.errors == 1
    assert totals.imported == 0


def test_run_batch_ctrl_c_conserve_le_travail_deja_fait(db_session, monkeypatch, fake_reporter):
    def _phases(db, url, settings, force=False, persist=True):
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
    def _phases(db, url, settings, force=False, persist=True):
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
    def _phases(db, url, settings, force=False, persist=True):
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

    def _phases(db, url, settings, force=False, persist=True):
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

    def _phases(db, url, settings, force=False, persist=True):
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

    def _phases(db, url, settings, force=False, persist=True):
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
        def item_start(self, index, label): raise BrokenPipeError("tube fermé")
        def item_progress(self, done, total): raise BrokenPipeError("tube fermé")
        def item_done(self, imported, skipped, error): raise BrokenPipeError("tube fermé")
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
        def item_start(self, index, label): raise KeyboardInterrupt
        def item_progress(self, done, total): pass
        def item_done(self, imported, skipped, error): pass
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

    def _phases_cached(db, url, settings, force=False, persist=True):
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

    def _iter(db, url, settings, force=False, persist=True):
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


# --- règle « échec total » ----------------------------------------------------


def test_est_echec_total_quand_toutes_les_epreuves_echouent():
    assert batch.est_echec_total(epreuves=53, errors=53) is True


def test_est_echec_total_faux_sur_un_succes_partiel():
    """Quelques échecs sur 50 : le batch reste un succès."""
    assert batch.est_echec_total(epreuves=50, errors=3) is False


def test_est_echec_total_faux_quand_il_n_y_avait_rien_a_traiter():
    """Sheet vide, `--limit 0`, filtre sans résultat : rien à faire n'est pas un échec."""
    assert batch.est_echec_total(epreuves=0, errors=0) is False
