from app.cli.reports import render_rescrape_report, render_sheet_report
from app.services.batch import BatchFailure
from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome


def test_rapport_sheet_dry_run_masque_les_compteurs_d_import():
    out = SheetOutcome(unique_supported=3, rows_without_link=2)
    texte = render_sheet_report(out, dry_run=True)

    assert "IMPORT SHEET (dry-run)" in texte
    assert "Liens supportés uniques   : 3" in texte
    assert "Lignes sans lien          : 2" in texte
    assert "Participants" not in texte


def test_rapport_sheet_liste_les_ignores_par_host():
    out = SheetOutcome(
        imported=5, skipped=1, errors=1, unique_supported=2, processed=2,
        ignored_by_host={"inconnu.example": 3},
    )
    texte = render_sheet_report(out, dry_run=False)

    assert "Participants ajoutés      : 5" in texte
    assert "Épreuves en erreur        : 1" in texte
    assert "inconnu.example : 3" in texte


def test_rapport_sheet_liste_le_detail_des_epreuves_en_erreur():
    """Le compteur dit *combien* ; le détail dit *lesquelles* et *pourquoi*."""
    out = SheetOutcome(
        imported=5, errors=2, unique_supported=7, processed=7,
        failures=[
            BatchFailure(url="https://k/boom", label="klikego · A", message="timeout scrape"),
            BatchFailure(url="https://t/nope", label="timepulse · B", message="404"),
        ],
    )
    texte = render_sheet_report(out, dry_run=False)

    assert "Épreuves en erreur        : 2" in texte
    assert "Épreuves en erreur (détail) :" in texte
    assert "  - https://k/boom : timeout scrape" in texte
    assert "  - https://t/nope : 404" in texte


def test_rapport_sheet_sans_echec_n_affiche_pas_la_section_detail():
    out = SheetOutcome(imported=5, errors=0, unique_supported=5, processed=5)
    texte = render_sheet_report(out, dry_run=False)

    assert "(détail)" not in texte


def test_rapport_sheet_dry_run_masque_le_detail_des_erreurs():
    """Un dry-run ne scrape rien : pas d'échec réel à lister."""
    out = SheetOutcome(unique_supported=3, rows_without_link=1)
    texte = render_sheet_report(out, dry_run=True)

    assert "(détail)" not in texte


def test_rapport_sheet_signale_l_interruption():
    out = SheetOutcome(imported=5, unique_supported=10, processed=2, interrupted=True)
    texte = render_sheet_report(out, dry_run=False)

    assert "interrompu" in texte.lower()


def test_rapport_rescrape_dry_run_liste_les_urls():
    out = RescrapeOutcome(total=2, dry_run_urls=["https://k/1", "https://k/2"])
    texte = render_rescrape_report(out, dry_run=True)

    assert "RESCRAPE DB (dry-run)" in texte
    # « épreuves », pas « courses » : depuis la dédup, `total` compte des URLs
    # uniques — une épreuve porte N courses en base (heats).
    assert "Épreuves ciblées          : 2" in texte
    assert "Courses ciblées" not in texte
    assert "https://k/1" in texte


def test_rapport_rescrape_signale_l_interruption():
    out = RescrapeOutcome(total=10, imported=3, processed=2, interrupted=True)
    texte = render_rescrape_report(out, dry_run=False)

    assert "interrompu" in texte.lower()
    assert "Participants ajoutés      : 3" in texte


def test_rescrape_report_liste_les_echecs():
    """« Épreuves en erreur : 2 » dit *combien*, pas *lesquelles*. Sans le
    détail, une troisième tentative suppose de relire le terminal à la main."""
    outcome = RescrapeOutcome(
        total=3, errors=2, imported=10,
        failures=[
            BatchFailure(url="https://k/1", label="klikego · A", message="503"),
            BatchFailure(url="https://k/2", label="klikego · B", message="timeout"),
        ],
    )

    rapport = render_rescrape_report(outcome, dry_run=False)

    assert "Épreuves en erreur (détail) :" in rapport
    assert "  - https://k/1 : 503" in rapport
    assert "  - https://k/2 : timeout" in rapport


def test_rescrape_report_sans_echec_n_affiche_pas_le_bloc():
    rapport = render_rescrape_report(RescrapeOutcome(total=3, imported=10), dry_run=False)

    assert "détail" not in rapport


# --- unités des compteurs ----------------------------------------------------
#
# Le bilan croise deux unités : des **épreuves** (ciblées, traitées, en erreur)
# et des **participants** (ajoutés, déjà en base). Les libellés doivent le dire,
# sinon « Épreuves ciblées : 42 / Ignorées : 5820 » se lit « 5820 épreuves
# ignorées » — un non-sens qui a réellement dérouté un opérateur.


def test_rapport_rescrape_nomme_l_unite_de_chaque_compteur():
    out = RescrapeOutcome(total=42, processed=42, imported=0, skipped=5820, errors=0)
    texte = render_rescrape_report(out, dry_run=False)

    assert "Épreuves ciblées          : 42" in texte
    assert "Épreuves en erreur        : 0" in texte
    assert "Participants ajoutés      : 0" in texte
    assert "Participants déjà en base : 5820" in texte
    # Les anciens libellés muets sur l'unité ne doivent plus réapparaître.
    assert "Importées" not in texte
    assert "Ignorées" not in texte


def test_rapport_rescrape_interrompu_dit_combien_d_epreuves_ont_ete_traitees():
    """« 7 des 42 » situe le Ctrl-C ; sans ça, le bilan partiel est illisible."""
    out = RescrapeOutcome(
        total=42, processed=7, imported=0, skipped=5820, interrupted=True
    )
    texte = render_rescrape_report(out, dry_run=False)

    assert "Épreuves traitées         : 7" in texte


def test_rapport_rescrape_complet_ne_repete_pas_le_compte_des_traitees():
    """Batch mené à son terme : traitées == ciblées, la ligne n'apporte rien."""
    out = RescrapeOutcome(total=42, processed=42, imported=10, skipped=100)
    texte = render_rescrape_report(out, dry_run=False)

    assert "Épreuves traitées" not in texte


def test_rapport_sheet_interrompu_dit_combien_d_epreuves_ont_ete_traitees():
    out = SheetOutcome(
        unique_supported=300, processed=12, imported=40, skipped=900, interrupted=True
    )
    texte = render_sheet_report(out, dry_run=False)

    assert "Liens supportés uniques   : 300" in texte
    assert "Épreuves traitées         : 12" in texte
    assert "Participants déjà en base : 900" in texte


def test_rescrape_report_affiche_les_participants_mis_a_jour():
    out = RescrapeOutcome(total=3, imported=1, updated=7, skipped=900, processed=3)
    texte = render_rescrape_report(out, dry_run=False)
    assert "Participants mis à jour   : 7" in texte
    # Ordre : ajoutés → mis à jour → déjà en base.
    assert texte.index("ajoutés") < texte.index("mis à jour") < texte.index("déjà en base")


def test_sheet_report_affiche_les_participants_mis_a_jour():
    out = SheetOutcome(unique_supported=2, imported=3, updated=4, skipped=5, processed=2)
    texte = render_sheet_report(out, dry_run=False)
    assert "Participants mis à jour   : 4" in texte
