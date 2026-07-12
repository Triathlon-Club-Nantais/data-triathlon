from app.services.progress import NullReporter, ProgressReporter


def test_null_reporter_respecte_le_protocol():
    assert isinstance(NullReporter(), ProgressReporter)


def test_null_reporter_est_muet_et_ne_leve_rien(capsys):
    reporter = NullReporter()
    reporter.batch_start(2)
    reporter.item_start(0, "klikego · https://k/1")
    reporter.item_progress(10, 100)
    reporter.item_done(10, 0, None)
    reporter.batch_end()

    capture = capsys.readouterr()
    assert capture.out == ""
    assert capture.err == ""
