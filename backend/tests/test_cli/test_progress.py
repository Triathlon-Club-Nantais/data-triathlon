import io
import sys

from rich.console import Console

from app.cli import progress as cli_reporters
from app.cli.progress import PlainReporter, RichReporter, select_reporter, truncate
from app.services.progress import NullReporter, ProgressReporter


def _console_capturante() -> tuple[Console, io.StringIO]:
    """Console Rich qui écrit dans un tampon en se croyant dans un terminal.

    `force_terminal` est indispensable : sans lui Rich n'émet aucune barre.
    """
    tampon = io.StringIO()
    return Console(file=tampon, force_terminal=True, width=100), tampon


def _totaux_par_tache(reporter: RichReporter) -> dict[int, float | None]:
    return {tache.id: tache.total for tache in reporter._progress.tasks}


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


def test_rich_reporter_console_par_defaut_sur_stderr():
    console = RichReporter()._progress.console

    assert console.stderr is True         # stdout reste réservé au rapport final / --json
    assert console.file is sys.stderr
    assert console.file is not sys.stdout


def test_rich_reporter_scenario_complet_n_ecrit_rien_sur_stdout(capsys):
    # Console par défaut : c'est elle qui doit viser stderr. Hors terminal (cas de
    # capsys), les barres n'émettent rien — seul le `console.print` de l'erreur sort.
    reporter = RichReporter()

    reporter.batch_start(2)
    reporter.item_start(0, "klikego · Triathlon de Nantes")
    reporter.item_progress(20, 30)
    reporter.item_done(28, 2, None)
    reporter.item_start(1, "timepulse · Duathlon de Rezé")
    reporter.item_done(0, 0, "timeout scrape")
    reporter.batch_end()

    capture = capsys.readouterr()
    assert capture.out == ""                    # stdout doit rester parsable si on redirige
    assert "timeout scrape" in capture.err      # l'erreur, elle, est bien rapportée


def test_rich_reporter_affiche_l_erreur_malgre_les_barres_transitoires():
    # Les barres sont `transient=True` : elles s'effacent en fin de batch. L'erreur,
    # imprimée hors de la zone des barres, doit survivre à cet effacement.
    console, tampon = _console_capturante()
    reporter = RichReporter(console=console)

    reporter.batch_start(1)
    reporter.item_start(0, "timepulse · Duathlon de Rezé")
    reporter.item_progress(5, 42)
    reporter.item_done(0, 0, "timeout scrape")
    reporter.batch_end()

    sortie = tampon.getvalue()
    assert "timeout scrape" in sortie
    assert "Duathlon de Rezé" in sortie


def test_rich_reporter_repart_en_indetermine_a_chaque_epreuve():
    # Avant le scrape, le nombre de participants est inconnu : la barre de l'épreuve
    # doit être indéterminée, et surtout pas hériter du total de l'épreuve précédente.
    console, _ = _console_capturante()
    reporter = RichReporter(console=console)

    reporter.batch_start(2)
    reporter.item_start(0, "A")
    reporter.item_progress(20, 30)
    reporter.item_done(28, 2, None)
    reporter.item_start(1, "B")

    totaux = _totaux_par_tache(reporter)
    assert totaux[reporter._item_task] is None   # et non 30, le total de l'épreuve A
    assert totaux[reporter._batch_task] == 2     # la barre du batch, elle, ne bouge pas

    reporter.batch_end()


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
