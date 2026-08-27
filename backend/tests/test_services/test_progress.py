from app.services.progress import NullReporter, ProgressReporter


def test_null_reporter_respecte_le_protocol():
    assert isinstance(NullReporter(), ProgressReporter)


def test_null_reporter_est_muet_et_ne_leve_rien(capsys):
    reporter = NullReporter()
    reporter.batch_start(2)
    reporter.item_start(0, "klikego · https://k/1", "klikego")
    reporter.item_progress(10, 100, "klikego")
    reporter.item_done(10, 0, None, "klikego")
    reporter.batch_end()

    capture = capsys.readouterr()
    assert capture.out == ""
    assert capture.err == ""


def test_progress_reporter_porte_une_identite_de_groupe():
    """Sous exécution concurrente, plusieurs épreuves sont « en cours » à la
    fois : `index`/`label` seuls ne suffisent plus à savoir laquelle chaque
    appel concerne — il faut l'identité du chronométreur qui la traite."""
    reporter = NullReporter()

    # Ne doit pas lever : NullReporter accepte le nouveau paramètre sans effet.
    reporter.batch_start(2)
    reporter.item_start(0, "klikego · A", "klikego")
    reporter.item_progress(1, 2, "klikego")
    reporter.item_done(1, 0, None, "klikego")
    reporter.batch_end()
