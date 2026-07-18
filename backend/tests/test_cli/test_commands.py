import json
from contextlib import contextmanager
from types import SimpleNamespace

from typer.testing import CliRunner

from app.cli import app, reports
from app.cli.commands import import_sheet as cmd_import
from app.cli.commands import rescrape_db as cmd_rescrape
from app.repositories import course_repository
from app.services import import_service
from app.services.bulk_import_service import SheetOutcome
from app.services.progress import NullReporter
from app.services.rescrape_service import RescrapeOutcome

runner = CliRunner()


@contextmanager
def _fausse_session():
    yield None


class _EchoTubeFerme:
    """`typer.echo` dont **stdout** est un tube fermé (`… | head -2`).

    Fidèle au scénario réel : seul stdout casse (le lecteur a fermé le tube),
    stderr reste ouvert sur le terminal de l'opérateur.
    """

    def __init__(self) -> None:
        self.stderr: list[str] = []

    def __call__(self, message: str = "", err: bool = False, **kwargs) -> None:
        if not err:
            raise BrokenPipeError(32, "Broken pipe")
        self.stderr.append(message)


def _brancher_tube_ferme(monkeypatch) -> _EchoTubeFerme:
    faux_echo = _EchoTubeFerme()
    monkeypatch.setattr(reports.typer, "echo", faux_echo)
    return faux_echo


class _SessionFactice:
    """Session inerte : `run_batch` ne fait que la rollback entre deux épreuves."""

    def rollback(self) -> None:
        pass


@contextmanager
def _fausse_session_db():
    yield _SessionFactice()


def _iter_en_echec(db, url, settings, force=False):
    """Toute épreuve tentée échoue — site tiers down (zéro réseau, zéro DB)."""
    yield {"phase": "error", "message": "503 Service Unavailable"}


class _ServiceEspion:
    """Double de service : capture les arguments reçus et renvoie l'outcome fourni.

    Une `lambda *a, **k` avalerait tout : impossible alors de voir qu'une option
    Typer n'arrive jamais au service (ou arrive inversée). On capture donc.
    """

    def __init__(self, outcome):
        self.outcome = outcome
        self.args: tuple = ()
        self.kwargs: dict = {}

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self.outcome


def _brancher_import(monkeypatch, outcome: SheetOutcome) -> _ServiceEspion:
    """Neutralise session + téléchargement CSV, et espionne le service."""
    espion = _ServiceEspion(outcome)
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: "a,b\n")
    monkeypatch.setattr(cmd_import.bulk_import_service, "run_import_sheet", espion)
    return espion


def _brancher_rescrape(monkeypatch, outcome: RescrapeOutcome) -> _ServiceEspion:
    espion = _ServiceEspion(outcome)
    monkeypatch.setattr(cmd_rescrape, "session_scope", _fausse_session)
    monkeypatch.setattr(cmd_rescrape.rescrape_service, "run_rescrape_db", espion)
    return espion


# --- import-sheet ------------------------------------------------------------


def test_import_sheet_dry_run_affiche_le_rapport(monkeypatch):
    _brancher_import(monkeypatch, SheetOutcome(unique_supported=4, rows_without_link=1))

    result = runner.invoke(app, ["import-sheet", "--dry-run"])

    assert result.exit_code == 0
    assert "IMPORT SHEET (dry-run)" in result.stdout
    assert "Liens supportés uniques   : 4" in result.stdout


def test_import_sheet_json_n_emet_que_du_json_sur_stdout(monkeypatch):
    """`--json` est exclusif : stdout doit être parsable tel quel (`| jq`)."""
    _brancher_import(monkeypatch, SheetOutcome(imported=7, skipped=2, unique_supported=1))

    result = runner.invoke(app, ["import-sheet", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["imported"] == 7  # tout stdout, pas juste sa fin
    assert "IMPORT SHEET" in result.stderr  # le rapport texte reste visible, sur stderr
    assert "IMPORT SHEET" not in result.stdout


def test_import_sheet_json_embarque_le_detail_des_erreurs(monkeypatch):
    """Le détail des échecs (URL + cause) doit survivre à la sérialisation `asdict`."""
    from app.services.batch import BatchFailure

    _brancher_import(
        monkeypatch,
        SheetOutcome(
            errors=1, unique_supported=2, processed=2, imported=3,
            failures=[BatchFailure(url="https://k/boom", label="klikego · A", message="404")],
        ),
    )

    result = runner.invoke(app, ["import-sheet", "--json"])

    assert result.exit_code == 0
    charge = json.loads(result.stdout)
    assert charge["failures"] == [
        {"url": "https://k/boom", "label": "klikego · A", "message": "404"}
    ]


def test_import_sheet_sans_json_le_rapport_sort_sur_stdout(monkeypatch):
    _brancher_import(monkeypatch, SheetOutcome(imported=7, unique_supported=1))

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 0
    assert "IMPORT SHEET" in result.stdout


def test_import_sheet_interrompu_sort_en_130(monkeypatch):
    _brancher_import(
        monkeypatch, SheetOutcome(imported=3, unique_supported=9, interrupted=True)
    )

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 130
    assert "Participants ajoutés      : 3" in result.stdout  # le bilan partiel est bien affiché


def test_import_sheet_json_interrompu_emet_quand_meme_le_json(monkeypatch):
    """Ctrl-C + `--json` : la charge JSON doit sortir AVANT l'exit 130.

    Sinon un cron qui pipe vers `jq` perdrait silencieusement le bilan partiel.
    """
    _brancher_import(
        monkeypatch, SheetOutcome(imported=3, unique_supported=9, interrupted=True)
    )

    result = runner.invoke(app, ["import-sheet", "--json"])

    assert result.exit_code == 130
    charge = json.loads(result.stdout)  # stdout reste parsable tel quel
    assert charge["imported"] == 3
    assert charge["interrupted"] is True


def test_import_sheet_echec_total_sort_en_code_non_nul(monkeypatch):
    """Toutes les épreuves en échec (site tiers down) ⇒ le cron doit alerter."""
    _brancher_import(monkeypatch, SheetOutcome(unique_supported=3, errors=3))

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 1
    assert "Épreuves en erreur        : 3" in result.stdout  # le bilan reste émis avant la sortie
    assert "Échec total" in result.stdout


def test_import_sheet_echec_total_json_emet_quand_meme_le_json(monkeypatch):
    """Échec total + `--json` : la charge JSON sort AVANT l'exit non nul."""
    _brancher_import(monkeypatch, SheetOutcome(unique_supported=3, errors=3))

    result = runner.invoke(app, ["import-sheet", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"] == 3  # stdout reste parsable tel quel


def test_import_sheet_succes_partiel_sort_en_zero(monkeypatch):
    """Quelques échecs sur 10 épreuves : ce n'est pas un échec du batch."""
    _brancher_import(
        monkeypatch, SheetOutcome(unique_supported=10, imported=42, errors=3)
    )

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 0
    assert "Échec total" not in result.stdout


def test_import_sheet_aucune_epreuve_a_traiter_sort_en_zero(monkeypatch):
    """Sheet vide / `--limit 0` : rien à faire n'est pas un échec."""
    _brancher_import(monkeypatch, SheetOutcome(unique_supported=0))

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 0


def test_import_sheet_epreuves_reussies_sans_rien_importer_sort_en_zero(monkeypatch):
    """Tous les participants déjà en base (`imported=0`, `skipped=N`) : c'est un succès."""
    _brancher_import(monkeypatch, SheetOutcome(unique_supported=4, imported=0, skipped=180))

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 0


def test_import_sheet_interruption_prime_sur_l_echec_total(monkeypatch):
    """Interrompu ET rien de réussi : 130 (action de l'opérateur), pas 1 (panne)."""
    _brancher_import(
        monkeypatch, SheetOutcome(unique_supported=2, errors=2, interrupted=True)
    )

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 130


def test_import_sheet_dry_run_coupe_la_progression(monkeypatch):
    """Un dry-run ne scrape rien : le service doit recevoir un NullReporter."""
    espion = _brancher_import(monkeypatch, SheetOutcome(unique_supported=1))

    result = runner.invoke(app, ["import-sheet", "--dry-run"])

    assert result.exit_code == 0
    assert isinstance(espion.kwargs["reporter"], NullReporter)


def test_import_sheet_transmet_les_options_au_service(monkeypatch):
    """Le câblage options Typer → service : une inversion doit se voir ici."""
    espion = _ServiceEspion(SheetOutcome(unique_supported=1))
    urls_telechargees: list[str] = []
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session)
    monkeypatch.setattr(
        cmd_import.sheet_source, "download_csv",
        lambda url: urls_telechargees.append(url) or "nom,lien\n",
    )
    monkeypatch.setattr(cmd_import.bulk_import_service, "run_import_sheet", espion)

    result = runner.invoke(app, [
        "import-sheet",
        "--limit", "3",
        "--only-provider", "klikego",
        "--delay", "0",
        "--sheet-url", "https://exemple.test/feuille.csv",
    ])

    assert result.exit_code == 0
    assert urls_telechargees == ["https://exemple.test/feuille.csv"]
    assert espion.args[1] == "nom,lien\n"  # le CSV téléchargé arrive au service
    assert espion.kwargs["limit"] == 3
    assert espion.kwargs["only_provider"] == "klikego"
    assert espion.kwargs["delay"] == 0.0
    assert espion.kwargs["dry_run"] is False


def test_import_sheet_only_provider_inconnu_echoue(monkeypatch):
    """`--only-provider klikgo` (faute de frappe) ne doit pas filtrer 0 lien en silence."""
    espion = _brancher_import(monkeypatch, SheetOutcome(unique_supported=1))

    result = runner.invoke(app, ["import-sheet", "--only-provider", "klikgo"])

    assert result.exit_code != 0
    assert espion.kwargs == {}  # échoué avant tout travail : le service n'est pas appelé
    assert "klikgo" in result.stderr
    assert "klikego" in result.stderr  # les valeurs acceptées sont listées
    assert "timepulse" in result.stderr
    assert result.stdout == ""  # contrat stdout : aucune pollution


def test_import_sheet_only_provider_valide_passe(monkeypatch):
    espion = _brancher_import(monkeypatch, SheetOutcome(unique_supported=1))

    result = runner.invoke(app, ["import-sheet", "--only-provider", "timepulse"])

    assert result.exit_code == 0
    assert espion.kwargs["only_provider"] == "timepulse"


def test_import_sheet_sans_only_provider_passe(monkeypatch):
    """Option absente = « tous les providers » : le service reçoit None."""
    espion = _brancher_import(monkeypatch, SheetOutcome(unique_supported=1))

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 0
    assert espion.kwargs["only_provider"] is None


# --- rescrape-db -------------------------------------------------------------


def test_rescrape_db_dry_run_affiche_les_urls(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1, dry_run_urls=["https://k/1"]))

    result = runner.invoke(app, ["rescrape-db", "--dry-run"])

    assert result.exit_code == 0
    assert "Épreuves ciblées          : 1" in result.stdout
    assert "https://k/1" in result.stdout


def test_rescrape_db_json_n_emet_que_du_json_sur_stdout(monkeypatch):
    """`python -m app.cli rescrape-db --json | jq` doit fonctionner."""
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=9, imported=5, skipped=1))

    result = runner.invoke(app, ["rescrape-db", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["imported"] == 5
    assert "RESCRAPE DB" in result.stderr
    assert "RESCRAPE DB" not in result.stdout


def test_rescrape_db_json_embarque_les_echecs(monkeypatch):
    """La boucle de rejeu (`--json | jq -r '.failures[].url'`) en dépend."""
    from app.services.batch import BatchFailure

    _brancher_rescrape(
        monkeypatch,
        RescrapeOutcome(
            total=2, errors=1, imported=3,
            failures=[BatchFailure(url="https://k/1", label="klikego · A", message="503")],
        ),
    )

    result = runner.invoke(app, ["rescrape-db", "--json"])

    assert result.exit_code == 0
    charge = json.loads(result.stdout)
    assert charge["failures"] == [
        {"url": "https://k/1", "label": "klikego · A", "message": "503"}
    ]


def test_rescrape_db_interrompu_sort_en_130(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=9, imported=2, interrupted=True))

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 130
    assert "Participants ajoutés      : 2" in result.stdout  # le bilan partiel est bien affiché


def test_rescrape_db_echec_total_sort_en_code_non_nul(monkeypatch):
    """Les 53 épreuves du cron échouent : code non nul, sinon le cron n'alerte jamais."""
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=53, errors=53))

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 1
    assert "Épreuves en erreur        : 53" in result.stdout  # le bilan reste émis avant la sortie
    assert "Échec total" in result.stdout


def test_rescrape_db_echec_total_json_emet_quand_meme_le_json(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=53, errors=53))

    result = runner.invoke(app, ["rescrape-db", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"] == 53
    assert "RESCRAPE DB" not in result.stdout  # stdout reste le JSON seul


def test_rescrape_db_succes_partiel_sort_en_zero(monkeypatch):
    _brancher_rescrape(
        monkeypatch, RescrapeOutcome(total=50, imported=120, skipped=8, errors=4)
    )

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 0
    assert "Échec total" not in result.stdout


def test_rescrape_db_aucune_epreuve_a_traiter_sort_en_zero(monkeypatch):
    """Aucune course au filtre (`--older-than`, `--limit 0`) : pas un échec."""
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=0))

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 0


def test_rescrape_db_dry_run_sort_en_zero(monkeypatch):
    """Un dry-run ne scrape rien : il ne peut jamais être un échec total."""
    _brancher_rescrape(
        monkeypatch, RescrapeOutcome(total=53, dry_run_urls=["https://k/1"])
    )

    result = runner.invoke(app, ["rescrape-db", "--dry-run"])

    assert result.exit_code == 0


def test_rescrape_db_interruption_prime_sur_l_echec_total(monkeypatch):
    """Interrompu ET rien de réussi : 130 (opérateur) l'emporte sur 1 (panne)."""
    _brancher_rescrape(
        monkeypatch, RescrapeOutcome(total=2, errors=2, interrupted=True)
    )

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 130


def test_rescrape_db_dry_run_coupe_la_progression(monkeypatch):
    """Un dry-run ne scrape rien : le service doit recevoir un NullReporter."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--dry-run"])

    assert result.exit_code == 0
    assert isinstance(espion.kwargs["reporter"], NullReporter)


def test_rescrape_db_transmet_les_options_au_service(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, [
        "rescrape-db",
        "--limit", "4",
        "--provider", "timepulse",
        "--older-than", "30",
        "--delay", "0",
    ])

    assert result.exit_code == 0
    assert espion.kwargs["limit"] == 4
    assert espion.kwargs["provider"] == "timepulse"
    assert espion.kwargs["older_than"] == 30
    assert espion.kwargs["delay"] == 0.0
    assert espion.kwargs["dry_run"] is False


def test_rescrape_db_provider_inconnu_echoue(monkeypatch):
    """`--provider kliego` affichait « Épreuves ciblées : 0 » et sortait en 0."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--provider", "kliego"])

    assert result.exit_code != 0
    assert espion.kwargs == {}  # échoué avant d'ouvrir la moindre Session
    assert "kliego" in result.stderr
    assert "klikego" in result.stderr  # les valeurs acceptées sont listées
    assert "breizhchrono" in result.stderr
    assert result.stdout == ""  # contrat stdout : aucune pollution


def test_rescrape_db_provider_inconnu_echoue_aussi_en_json(monkeypatch):
    """Même avec `--json`, l'erreur reste sur stderr : stdout ne porte rien."""
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--provider", "kliego", "--json"])

    assert result.exit_code != 0
    assert result.stdout == ""


def test_rescrape_db_provider_valide_passe(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--provider", "klikego"])

    assert result.exit_code == 0
    assert espion.kwargs["provider"] == "klikego"


def test_rescrape_db_sans_provider_passe(monkeypatch):
    """Option absente = « tous les providers » : le service reçoit None."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 0
    assert espion.kwargs["provider"] is None


def test_playwright_n_est_pas_un_provider_ciblable(monkeypatch):
    """Le fallback des URLs non reconnues n'est pas une valeur qu'on peut cibler."""
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--provider", "playwright"])

    assert result.exit_code != 0


def test_rescrape_db_url_transmise_au_service(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=2))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--url", "https://k/2"]
    )

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == ["https://k/1", "https://k/2"]


def test_rescrape_db_urls_from_fichier(monkeypatch, tmp_path):
    fichier = tmp_path / "echecs.txt"
    fichier.write_text("https://k/1\n# commentaire\n\n", encoding="utf-8")
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", str(fichier)])

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == ["https://k/1"]


def test_rescrape_db_urls_from_stdin(monkeypatch):
    """`… --json | jq -r '.failures[].url' | … --urls-from -`, sans fichier."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", "-"], input="https://k/1\n")

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == ["https://k/1"]


def test_rescrape_db_sans_url_reste_en_mode_base(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 0
    assert espion.kwargs["urls"] is None


def test_rescrape_db_liste_vide_cible_zero_epreuve(monkeypatch, tmp_path):
    """Fichier vide → « rien à faire », code 0 : la boucle de rejeu converge."""
    fichier = tmp_path / "vide.txt"
    fichier.write_text("", encoding="utf-8")
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=0))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", str(fichier)])

    assert result.exit_code == 0
    assert espion.kwargs["urls"] == []


def test_rescrape_db_url_avec_provider_est_une_erreur_d_usage(monkeypatch):
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--provider", "klikego"]
    )

    assert result.exit_code == 2
    assert espion.args == ()  # aucun travail engagé


def test_rescrape_db_url_avec_older_than_est_une_erreur_d_usage(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--older-than", "30"]
    )

    assert result.exit_code == 2


def test_rescrape_db_url_non_http_est_une_erreur_d_usage(monkeypatch):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--url", "pas-une-url"])

    assert result.exit_code == 2


def test_rescrape_db_urls_from_introuvable_est_une_erreur_d_usage(monkeypatch, tmp_path):
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(app, ["rescrape-db", "--urls-from", str(tmp_path / "absent.txt")])

    assert result.exit_code == 2


def test_rescrape_db_urls_from_stdin_avec_provider_ne_lit_pas_stdin(monkeypatch):
    """L'exclusivité doit être validée avant toute lecture de stdin (`--urls-from -`).

    Un terminal interactif attendrait sinon une saisie qui sera de toute façon
    jetée : le rejet doit être immédiat, sans lire quoi que ce soit.
    """

    def _charger_urls_espion(*args, **kwargs):
        raise AssertionError(
            "charger_urls ne doit pas être appelé avant valider_ciblage_exclusif"
        )

    monkeypatch.setattr(cmd_rescrape, "charger_urls", _charger_urls_espion)
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--urls-from", "-", "--provider", "klikego"]
    )

    assert result.exit_code == 2


def test_rescrape_db_url_reste_compatible_avec_limit(monkeypatch):
    """`--limit` ne sélectionne rien : il borne la liste finale."""
    espion = _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1))

    result = runner.invoke(
        app, ["rescrape-db", "--url", "https://k/1", "--url", "https://k/2", "--limit", "1"]
    )

    assert result.exit_code == 0
    assert espion.kwargs["limit"] == 1


# --- tube fermé (`… | head -2`) ----------------------------------------------


def test_rescrape_db_tube_ferme_ne_fausse_pas_le_code_de_sortie(monkeypatch):
    """`rescrape-db | head -2` sur un batch partiellement réussi doit sortir en 0.

    Sans filet, le `BrokenPipeError` de l'émission remonte jusqu'à Click, qui le
    convertit en exit 1 : indiscernable de l'échec total, alors que le batch a
    réussi. Et le bilan est perdu — y compris sur stderr.
    """
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=3, imported=12, errors=2))
    faux_echo = _brancher_tube_ferme(monkeypatch)

    result = runner.invoke(app, ["rescrape-db"])

    assert result.exit_code == 0  # 2 erreurs sur 3 : succès partiel, pas un échec
    # stdout est mort : le bilan se replie sur stderr plutôt que de disparaître.
    assert any("Participants ajoutés      : 12" in ligne for ligne in faux_echo.stderr)


def test_import_sheet_tube_ferme_preserve_l_echec_total(monkeypatch):
    """Tube fermé ET échec total : le code 1 est celui du batch, pas celui du tube."""
    _brancher_import(monkeypatch, SheetOutcome(unique_supported=3, errors=3))
    faux_echo = _brancher_tube_ferme(monkeypatch)

    result = runner.invoke(app, ["import-sheet"])

    assert result.exit_code == 1
    assert any("Échec total" in ligne for ligne in faux_echo.stderr)


def test_rescrape_db_tube_ferme_en_json_conserve_le_code_de_sortie(monkeypatch):
    """`--json | head -1` : la ligne JSON est perdue, mais ni le code ni le rapport.

    Aucun repli du JSON sur stdout ou d'un rapport texte sur stdout : le contrat
    « stdout ne porte que le JSON » tient même quand le tube casse.
    """
    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=3, imported=12, errors=2))
    faux_echo = _brancher_tube_ferme(monkeypatch)

    result = runner.invoke(app, ["rescrape-db", "--json"])

    assert result.exit_code == 0
    assert any("RESCRAPE DB" in ligne for ligne in faux_echo.stderr)


def test_tube_ferme_ne_masque_pas_le_ctrl_c(monkeypatch):
    """Filet étroit : `_echo` n'attrape que `BrokenPipeError`, jamais une BaseException.

    Un Ctrl-C pendant l'émission du bilan doit continuer de remonter — sinon on
    avalerait l'interruption de l'opérateur au motif d'un problème d'affichage.
    """
    def _echo_interrompu(message="", err=False, **kwargs):
        raise KeyboardInterrupt

    _brancher_rescrape(monkeypatch, RescrapeOutcome(total=1, imported=1))
    monkeypatch.setattr(reports.typer, "echo", _echo_interrompu)

    result = runner.invoke(app, ["rescrape-db"])

    assert isinstance(result.exception, KeyboardInterrupt | SystemExit)
    assert result.exit_code != 0


# --- dénominateur d'`echec_total` sous `--limit` -----------------------------
#
# Ces deux tests traversent la **vraie** chaîne commande → service → run_batch
# (seuls le scrape et la Session sont doublés) : ce sont les seuls à épingler le
# dénominateur de l'échec total, que les tests à service espionné ne voient pas.


def test_import_sheet_limit_toutes_les_epreuves_tentees_echouent_sort_en_1(monkeypatch):
    """`--limit 5` sur un Sheet de 300 liens, les 5 épreuves tentées échouent ⇒ exit 1.

    Épingle le **dénominateur** d'`echec_total` : `unique_supported` doit compter
    les épreuves réellement soumises au batch (donc **après** le slice `--limit`),
    et non les 300 liens uniques du Sheet. Le calculer avant le slice — la
    « correction » que suggère le Minor d'affichage ouvert sur ce compteur —
    donnerait `errors=5` contre `unique_supported=300` : plus d'échec total, exit
    0, et le cron n'alerterait plus jamais alors que tout ce qu'il a tenté a
    échoué.
    """
    csv_text = "nom,Donne-nous un lien pour accéder aux résultats.\n" + "".join(
        f"x,https://www.klikego.com/resultats/course-{i}/16745231637-{i}\n"
        for i in range(300)
    )
    monkeypatch.setattr(cmd_import, "session_scope", _fausse_session_db)
    monkeypatch.setattr(cmd_import.sheet_source, "download_csv", lambda url: csv_text)
    monkeypatch.setattr(import_service, "iter_import_event", _iter_en_echec)

    result = runner.invoke(app, ["import-sheet", "--limit", "5", "--delay", "0"])

    assert result.exit_code == 1
    assert "Liens supportés uniques   : 5" in result.stdout  # les épreuves soumises
    assert "Épreuves en erreur        : 5" in result.stdout
    assert "Échec total" in result.stdout


def test_rescrape_db_limit_toutes_les_epreuves_tentees_echouent_sort_en_1(monkeypatch):
    """`--limit 5` sur 53 épreuves en base, les 5 tentées échouent ⇒ exit 1.

    Même piège que pour `import-sheet` : `RescrapeOutcome.total` est le
    dénominateur de l'échec total. Compté avant le slice `--limit` (53), il
    noierait les 5 erreurs et rendrait le code de sortie muet.
    """
    courses = [
        SimpleNamespace(
            source_url=f"https://www.klikego.com/resultats/course-{i}/16745-{i}",
            provider="klikego",
            name=f"Épreuve {i}",
        )
        for i in range(53)
    ]
    monkeypatch.setattr(cmd_rescrape, "session_scope", _fausse_session_db)
    monkeypatch.setattr(course_repository, "iter_all", lambda db, **kwargs: courses)
    monkeypatch.setattr(import_service, "iter_import_event", _iter_en_echec)

    result = runner.invoke(app, ["rescrape-db", "--limit", "5", "--delay", "0"])

    assert result.exit_code == 1
    assert "Épreuves ciblées          : 5" in result.stdout  # les épreuves soumises au batch
    assert "Épreuves en erreur        : 5" in result.stdout
    assert "Échec total" in result.stdout
