from app import cli_reporters
from app.cli_reporters import PlainReporter, RichReporter, select_reporter, truncate
from app.services.progress import NullReporter, ProgressReporter


def test_les_reporters_respectent_le_protocol():
    assert isinstance(PlainReporter(), ProgressReporter)
    assert isinstance(RichReporter(), ProgressReporter)


def test_truncate_borne_le_libelle():
    assert truncate("court") == "court"
    long = "k · https://www.klikego.com/" + "a" * 100
    assert len(truncate(long)) == 60
    assert truncate(long).endswith("…")


def test_plain_reporter_une_ligne_par_epreuve_sans_ansi():
    lignes: list[str] = []
    reporter = PlainReporter(write=lignes.append)

    reporter.batch_start(2)
    reporter.item_start(0, "klikego · Triathlon de Nantes")
    reporter.item_progress(20, 30)
    reporter.item_done(28, 2, None)
    reporter.item_start(1, "timepulse · Duathlon de Rezé")
    reporter.item_done(0, 0, "timeout scrape")
    reporter.batch_end()

    texte = "\n".join(lignes)
    assert "\x1b" not in texte  # aucun code ANSI : lisible dans un log
    assert "[1/2]" in texte
    assert "scraping en cours" in texte  # le log ne reste pas muet pendant le scrape
    assert "28 importés, 2 ignorés" in texte
    assert "[2/2]" in texte
    assert "ERREUR : timeout scrape" in texte


def test_plain_reporter_ecrit_sur_stderr_pas_stdout(capsys):
    reporter = PlainReporter()
    reporter.batch_start(1)

    capture = capsys.readouterr()
    assert capture.out == ""      # stdout reste propre pour --json
    assert "1 épreuve" in capture.err


def test_select_reporter_null_si_no_progress():
    assert isinstance(select_reporter(no_progress=True), NullReporter)


def test_select_reporter_plain_hors_tty(monkeypatch):
    monkeypatch.setattr(cli_reporters, "_stderr_is_tty", lambda: False)
    assert isinstance(select_reporter(), PlainReporter)


def test_select_reporter_rich_en_tty(monkeypatch):
    monkeypatch.setattr(cli_reporters, "_stderr_is_tty", lambda: True)
    assert isinstance(select_reporter(), RichReporter)


def test_select_reporter_plain_force_meme_en_tty(monkeypatch):
    monkeypatch.setattr(cli_reporters, "_stderr_is_tty", lambda: True)
    assert isinstance(select_reporter(plain=True), PlainReporter)
