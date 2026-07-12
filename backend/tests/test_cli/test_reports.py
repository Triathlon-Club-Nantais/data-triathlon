from app.cli.reports import render_rescrape_report, render_sheet_report
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome


def test_rapport_sheet_dry_run_masque_les_compteurs_d_import():
    out = SheetOutcome(unique_supported=3, rows_without_link=2)
    texte = render_sheet_report(out, dry_run=True)

    assert "IMPORT SHEET (dry-run)" in texte
    assert "Liens supportés uniques : 3" in texte
    assert "Lignes sans lien        : 2" in texte
    assert "Importées" not in texte


def test_rapport_sheet_liste_les_ignores_par_host():
    out = SheetOutcome(
        imported=5, skipped=1, errors=1, unique_supported=2,
        ignored_by_host={"inconnu.example": 3},
    )
    texte = render_sheet_report(out, dry_run=False)

    assert "Importées : 5" in texte
    assert "En erreur : 1" in texte
    assert "inconnu.example : 3" in texte


def test_rapport_sheet_signale_l_interruption():
    out = SheetOutcome(imported=5, unique_supported=10, interrupted=True)
    texte = render_sheet_report(out, dry_run=False)

    assert "interrompu" in texte.lower()


def test_rapport_rescrape_dry_run_liste_les_urls():
    out = RescrapeOutcome(total=2, dry_run_urls=["https://k/1", "https://k/2"])
    texte = render_rescrape_report(out, dry_run=True)

    assert "RESCRAPE DB (dry-run)" in texte
    # « épreuves », pas « courses » : depuis la dédup, `total` compte des URLs
    # uniques — une épreuve porte N courses en base (heats).
    assert "Épreuves ciblées : 2" in texte
    assert "Courses ciblées" not in texte
    assert "https://k/1" in texte


def test_rapport_rescrape_signale_l_interruption():
    out = RescrapeOutcome(total=10, imported=3, interrupted=True)
    texte = render_rescrape_report(out, dry_run=False)

    assert "interrompu" in texte.lower()
    assert "Importées : 3" in texte
