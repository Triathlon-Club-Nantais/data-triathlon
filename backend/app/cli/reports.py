"""Rendu et émission des bilans de batch. Aucune logique métier : de la mise en forme."""
import json
import os
import sys
from dataclasses import asdict

import typer

from app.services.bulk_import_service import SheetOutcome
from app.services.club_members_service import MembersSyncReport
from app.services.geocode_service import GeocodeOutcome
from app.services.member_emails_service import MemberEmailsImportReport
from app.services.rescrape_service import RescrapeOutcome
from app.services.retention_service import RetentionOutcome
from app.services.weather_service import WeatherOutcome

Outcome = SheetOutcome | RescrapeOutcome | GeocodeOutcome | WeatherOutcome

#: Interruption clavier (convention shell : 128 + SIGINT).
EXIT_INTERRUPTED = 130
#: Échec applicatif : aucune des épreuves ciblées n'a abouti.
EXIT_TOTAL_FAILURE = 1

_TOTAL_FAILURE_LINE = (
    "Échec total : aucune des épreuves ciblées n'a abouti (code de sortie "
    f"{EXIT_TOTAL_FAILURE})."
)


#: Largeur de la colonne des libellés (le plus long : « Participants déjà en base »).
_COL = 25


def _line(label: str, value: object) -> str:
    return f"{label:<{_COL}} : {value}"


def _counter_lines(outcome: Outcome) -> list[str]:
    """Les compteurs du batch, **unité nommée dans chaque libellé**.

    Un bilan croise deux unités : des **épreuves** (ciblées, traitées, en
    erreur) et des **participants** (ajoutés, déjà en base). Les libellés
    d'origine — « Importées / Ignorées » — les taisaient, et se lisaient donc
    dans l'unité de la ligne du dessus : « Épreuves ciblées : 42 / Ignorées :
    5820 » donnait « 5820 épreuves ignorées », un non-sens qui a réellement
    dérouté un opérateur. On nomme l'unité plutôt que de compter sur le contexte.

    « Épreuves traitées » n'apparaît que si le batch a été interrompu : mené à
    son terme, `processed` égale le nombre d'épreuves ciblées, déjà affiché.
    """
    lines = []
    if outcome.interrupted:
        lines.append(_line("Épreuves traitées", outcome.processed))
    lines.append(_line("Épreuves en erreur", outcome.errors))
    lines.append(_line("Participants ajoutés", outcome.imported))
    lines.append(_line("Participants mis à jour", outcome.updated))
    lines.append(_line("Participants déjà en base", outcome.skipped))
    if outcome.is_total_failure:
        lines.append(_TOTAL_FAILURE_LINE)
    return lines


def _title(base: str, *, dry_run: bool, interrupted: bool) -> str:
    if dry_run:
        return f"=== {base} (dry-run) ==="
    if interrupted:
        return f"=== {base} (interrompu — bilan partiel) ==="
    return f"=== {base} ==="


def _failure_lines(outcome: Outcome) -> list[str]:
    """Le détail des épreuves fautives, commun aux deux commandes.

    Le compteur « Épreuves en erreur : N » dit *combien* ; ce bloc dit
    *lesquelles* et *pourquoi*, sans avoir à rejouer le batch. Il alimente aussi
    la boucle de rejeu de `rescrape-db --urls-from -`. Deux rendus divergeaient
    sans raison : `run_batch` collecte ces échecs pour les deux commandes.
    """
    if not outcome.failures:
        return []
    lines = ["Épreuves en erreur (détail) :"]
    lines.extend(f"  - {f.url} : {f.message}" for f in outcome.failures)
    return lines


def _passive_source_lines(outcome: Outcome) -> list[str]:
    """Les URLs enregistrées en sources secondaires, communes aux deux commandes (#283).

    Elles ne laissent **aucune trace dans les compteurs** : ni erreur, ni
    participant ajouté. Sans ce bloc, l'opérateur d'un import Sheet de 300 lignes
    ne peut pas distinguer « cette URL a atterri sur une épreuve déjà connue »
    d'un import ordinaire à zéro nouveauté. Masqué quand il n'a rien à dire, même
    parti pris que le bloc de réconciliation.
    """
    if not outcome.passive_sources:
        return []
    lines = [
        _line("Sources enregistrées", len(outcome.passive_sources)),
        "Sources enregistrées, non principales (détail) :",
    ]
    lines.extend(f"  - {s.url} : {s.message}" for s in outcome.passive_sources)
    return lines


def _reconciliation_lines(outcome: RescrapeOutcome) -> list[str]:
    """Le bilan de réconciliation d'identité (issue #66), borné aux réassignations.

    Unités nommées : on compte des **participations** et des **athlètes**, jamais
    des « lignes ». Masqué quand rien n'a été réconcilié.
    """
    if not outcome.reconciled:
        return []
    lines = [
        _line("Participations réconciliées", outcome.reconciled),
        _line("Athlètes fusionnés", outcome.merged),
        _line("Athlètes orphelins supprimés", outcome.orphans_removed),
        "Identités réconciliées (détail) :",
    ]
    lines.extend(
        f"  - {r.ancien}  ->  {r.nouveau}   ({r.participations} participations)"
        for r in outcome.reconciliations
    )
    return lines


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lines = [_title("IMPORT SHEET", dry_run=dry_run, interrupted=outcome.interrupted)]
    lines.append(_line("Liens supportés uniques", outcome.unique_supported))
    lines.append(_line("Lignes sans lien", outcome.rows_without_link))
    if not dry_run:
        lines.extend(_counter_lines(outcome))
        lines.extend(_failure_lines(outcome))
        lines.extend(_passive_source_lines(outcome))
    if outcome.ignored_by_host:
        lines.append("Liens non supportés (suivis dans #33) :")
        for host, count in sorted(outcome.ignored_by_host.items()):
            lines.append(f"  - {host} : {count}")
    return "\n".join(lines)


def render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible pour rescrape-db.

    On compte des **épreuves** (URLs uniques), pas des courses : depuis la dédup
    par `source_url`, une épreuve porte N courses en base (les heats Breizh
    Chrono, les variantes individuel/relais…). Afficher « courses » ici ferait
    croire à une perte de données à qui compare au `SELECT count(*) FROM course`
    (base de dev : 53 courses pour 12 épreuves).
    """
    lines = [_title("RESCRAPE DB", dry_run=dry_run, interrupted=outcome.interrupted)]
    lines.append(_line("Épreuves ciblées", outcome.total))
    if dry_run:
        for url in outcome.dry_run_urls:
            lines.append(f"  - {url}")
    else:
        lines.extend(_counter_lines(outcome))
        lines.extend(_failure_lines(outcome))
        lines.extend(_passive_source_lines(outcome))
    lines.extend(_reconciliation_lines(outcome))
    if outcome.orphan_purge_failed:
        lines.append(
            "Purge des athlètes orphelins : échec (import concurrent), rattrapée au prochain run."
        )
    return "\n".join(lines)


def render_geocode_report(outcome: GeocodeOutcome, *, dry_run: bool) -> str:
    """Rapport texte pour `geocode-courses` (#579).

    En dry-run, seule la liste des épreuves ciblées est rendue — aucun appel
    Nominatim n'a eu lieu, il n'y a donc ni géocodées ni en erreur à compter.
    """
    lines = [_title("GÉOCODAGE DES ÉPREUVES", dry_run=dry_run, interrupted=outcome.interrupted)]
    lines.append(_line("Épreuves ciblées", outcome.total))
    if dry_run:
        for name in outcome.dry_run_names:
            lines.append(f"  - {name}")
        return "\n".join(lines)
    if outcome.interrupted:
        lines.append(_line("Épreuves traitées", outcome.processed))
    lines.append(_line("Épreuves géocodées", outcome.geocoded))
    lines.append(_line("Épreuves en erreur", outcome.errors))
    if outcome.is_total_failure:
        lines.append(_TOTAL_FAILURE_LINE)
    lines.extend(_failure_lines(outcome))
    return "\n".join(lines)


def render_weather_report(outcome: WeatherOutcome, *, dry_run: bool) -> str:
    """Rapport texte pour `weather-courses` (#1370), sur le patron du géocodage."""
    lines = [_title("MÉTÉO DES ÉPREUVES", dry_run=dry_run, interrupted=outcome.interrupted)]
    lines.append(_line("Épreuves ciblées", outcome.total))
    if dry_run:
        lines.extend(f"  - {name}" for name in outcome.dry_run_names)
        return "\n".join(lines)
    if outcome.interrupted:
        lines.append(_line("Épreuves traitées", outcome.processed))
    lines.append(_line("Épreuves renseignées", outcome.fetched))
    lines.append(_line("Épreuves en erreur", outcome.errors))
    if outcome.is_total_failure:
        lines.append(_TOTAL_FAILURE_LINE)
    lines.extend(_failure_lines(outcome))
    return "\n".join(lines)


def render_retention_report(outcome: RetentionOutcome) -> str:
    """Purge de rétention (#1158) : ce qui a été supprimé, ou le serait en dry-run."""
    verb = "à supprimer" if outcome.dry_run else "supprimés"
    return "\n".join([
        _title("PURGE DE RÉTENTION", dry_run=outcome.dry_run, interrupted=False),
        _line(f"Signalements {verb}", outcome.feedback),
        _line(f"Entrées du journal {verb}", outcome.admin_log),
        _line(f"Profils jeunes {verb}", outcome.profiles),
        _line(f"Licenciés de saisons anciennes {verb}", outcome.club_members),
        _line(
            f"Adresses d'adhérents de saisons anciennes {'à supprimer' if outcome.dry_run else 'supprimées'}",
            outcome.member_emails,
        ),
        _line(f"Comptes inactifs depuis 5 ans {verb}", outcome.accounts_deleted),
        _line("Comptes inactifs conservés (cités par le club)", outcome.accounts_skipped),
    ])


def render_orphans_report(removed: int) -> str:
    """Balayage des athlètes orphelins (#1271)."""
    return "\n".join([
        _title("ATHLÈTES ORPHELINS", dry_run=False, interrupted=False),
        _line("Athlètes orphelins supprimés", removed),
    ])


def render_timepulse_duplicates_report(rows: list[dict], *, deleted: bool) -> str:
    """Épreuves timepulse remplacées par leurs parcours qualifiés (#1004)."""
    lines = ["=== ÉPREUVES TIMEPULSE REMPLACÉES ==="]
    if not rows:
        lines.append("Aucune épreuve à supprimer.")
        return "\n".join(lines)
    for row in rows:
        replacements = ", ".join(str(i) for i in row["covered_by"])
        lines.append(f"{row['course_id']}  {row['name']}  →  {replacements}")
    lines.append(
        f"{len(rows)} épreuve(s) supprimée(s)." if deleted
        else f"{len(rows)} épreuve(s) à supprimer : relancer avec --yes --by-email <adresse>."
    )
    return "\n".join(lines)


def render_gender_backfill_report(rows: list[dict], *, applied: bool) -> str:
    """Fiches dont le sexe vide est rattrapé (#1201)."""
    women = sum(1 for row in rows if row["gender"] == "F")
    lines = ["=== SEXE DES FICHES ATHLÈTES ===" + ("" if applied else " (simulation)")]
    lines.append(f"{len(rows)} fiche(s) {'remplie(s)' if applied else 'à remplir'} : {len(rows) - women} M, {women} F.")
    if not applied and rows:
        lines.append("Relancer avec --yes pour écrire.")
    return "\n".join(lines)


def render_relay_twins_report(rows: list[dict], *, deleted: bool) -> str:
    """Épreuves solo remplacées par leur jumelle relais (#1195, #1197)."""
    lines = ["=== ÉPREUVES SOLO DOUBLÉES PAR LEUR RELAIS ==="]
    if not rows:
        lines.append("Aucune épreuve à supprimer.")
        return "\n".join(lines)
    for row in rows:
        lines.append(f"{row['course_id']}  {row['name']}  →  {row['covered_by']}")
    lines.append(
        f"{len(rows)} épreuve(s) supprimée(s)." if deleted
        else f"{len(rows)} épreuve(s) à supprimer : relancer avec --yes --by-email <adresse>."
    )
    return "\n".join(lines)


def render_reconciliation_report(report: dict) -> str:
    """Bilan de la reprise des doublons d'athlètes (#906), simulée ou appliquée."""
    applied = report.get("applied", False)
    lines = ["=== REPRISE DES FICHES D'ATHLÈTES ===" + ("" if applied else " (simulation)")]
    for family, counts in report.get("families", {}).items():
        details = ", ".join(f"{key} {value}" for key, value in counts.items())
        lines.append(f"{family} : {details}")
    operations = report.get("operations", [])
    if applied:
        lines.append(f"{report.get('done', 0)} opération(s) appliquée(s) sur {len(operations)}.")
        for error in report.get("errors", []):
            lines.append(f"ÉCHEC {error['operation']} : {error['error']}")
        if report.get("interrupted"):
            lines.append("Interrompue : relancer pour reprendre, rien de fait ne sera refait.")
    else:
        lines.append(
            f"{len(operations)} opération(s) prévue(s) : appliquer ce plan avec "
            "--yes --by-email <adresse> --plan-from <cette simulation en --json>."
            if operations else "Rien à faire."
        )
    lines.append(f"{len(report.get('review', []))} cas laissé(s) en revue (/admin/identites).")
    return "\n".join(lines)


def render_challenge_requalification_report(rows: list[dict], *, converted: bool) -> str:
    """Épreuves requalifiées en classements Challenge (#1008)."""
    lines = ["=== CLASSEMENTS CHALLENGE ==="]
    if not rows:
        lines.append("Aucune épreuve à requalifier.")
        return "\n".join(lines)
    for row in rows:
        linked = ", ".join(str(i) for i in row["linked_course_ids"])
        lines.append(f"{row['course_id']}  {row['name']}  ({row['rows']} lignes)  →  {linked}")
    lines.append(
        f"{len(rows)} épreuve(s) requalifiée(s)." if converted
        else f"{len(rows)} épreuve(s) à requalifier : relancer avec --yes --by-email <adresse>."
    )
    return "\n".join(lines)


def render_club_labels_report(labels: list[dict]) -> str:
    """Inventaire des libellés de club, marqués reconnus (✓) ou non (✗).

    Le filtre club match à l'égalité sur une liste blanche : une variante non
    répertoriée sort des compteurs **sans aucun signal**. Ce rapport est le
    filet — il rend visible ce que le filtre ne voit pas.
    """
    lines = ["=== LIBELLÉS CLUB ==="]
    if not labels:
        lines.append("Aucun libellé de club en base.")
        return "\n".join(lines)

    width = max(len(str(row["participations"])) for row in labels)
    for row in labels:
        mark = "✓" if row["is_tcn"] else "✗"
        lines.append(f"  {row['participations']:>{width}}  {mark}  {row['club']}")

    lines.append("")
    lines.append(_line("Libellés distincts", len(labels)))
    lines.append(_line("Libellés du club", sum(1 for row in labels if row["is_tcn"])))
    lines.append(
        _line(
            "Participations du club",
            sum(row["participations"] for row in labels if row["is_tcn"]),
        )
    )
    return "\n".join(lines)


def _silence_stream(*, err: bool) -> None:
    """Redirige vers /dev/null le **descripteur** du flux dont le tube est fermé.

    Rattraper `BrokenPipeError` ne suffit pas : le tampon de `sys.stdout` garde
    les octets non écrits, et l'interpréteur les re-flushe à l'arrêt
    (`Py_FinalizeEx`). Le tube étant toujours fermé, ce flush final échoue à son
    tour : Python affiche « Exception ignored … BrokenPipeError » et **force le
    code de sortie à 120**, écrasant le nôtre. En faisant pointer le descripteur
    sur /dev/null, ce dernier flush réussit en silence et notre code survit.

    Sous CliRunner (ou toute sortie capturée en mémoire) il n'y a pas de
    descripteur : `fileno()` lève, on ignore — il n'y a alors ni tube ni arrêt
    d'interpréteur à protéger.
    """
    stream = sys.stderr if err else sys.stdout
    try:
        fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(fd, stream.fileno())
        finally:
            os.close(fd)
    except (OSError, ValueError, AttributeError):
        # Pas de descripteur (sortie capturée en mémoire) : il n'y a ni tube ni
        # flush d'arrêt à protéger, cf. la docstring.
        pass


def _echo(message: str, *, err: bool = False) -> bool:
    """Écrit une ligne. Renvoie `False` si le flux est fermé (tube coupé).

    `python -m app.cli rescrape-db | head -2` ferme le tube avant qu'on ait fini
    d'écrire : `typer.echo` lève alors `BrokenPipeError`. Non rattrapée, elle
    remonte jusqu'à Click, qui la convertit en **exit 1** — indiscernable de
    l'échec total qu'on vient d'introduire — et le bilan est perdu au passage.
    Or un tuyau fermé est un incident d'**affichage** : il ne doit ni faire
    perdre le bilan, ni mentir sur le résultat du batch (0 / 1 / 130).

    Seul `BrokenPipeError` est rattrapé, et rien d'autre : `KeyboardInterrupt`
    est une `BaseException`, elle continue de remonter (Ctrl-C reste possible
    pendant l'émission).
    """
    try:
        typer.echo(message, err=err)
        return True
    except BrokenPipeError:
        _silence_stream(err=err)
        return False


def emit_outcome(outcome: Outcome, report: str, *, json_output: bool) -> None:
    """Émet le bilan, puis sort en code non nul si le batch a mal fini.

    `--json` est **exclusif** : stdout ne contient alors QUE la ligne JSON, pour
    que `… --json | jq` fonctionne. Le rapport texte bascule sur **stderr**, là
    où sort déjà la progression : un humain le voit toujours, le pipe reste pur.
    Sans `--json`, le rapport texte sort sur stdout comme avant.

    Le bilan est **toujours émis avant** de sortir en erreur : ni un Ctrl-C ni un
    échec total ne doivent faire perdre le travail déjà persisté.

    **Tube fermé** (`… | head -2`) : l'émission est tolérante (cf. `_echo`). Si
    stdout est coupé, le rapport texte bascule sur stderr — le tube est mort, le
    terminal, lui, est toujours là. Aucun repli en sens inverse sous `--json` :
    stdout ne doit porter QUE la ligne JSON. Si les deux flux sont coupés
    (`2>&1 | head`), on renonce en silence, mais le code de sortie reste juste.

    Codes de sortie, dans cet ordre de priorité :

    - `130` — batch interrompu au clavier. **Prioritaire** sur l'échec total :
      l'interruption est une action de l'opérateur, pas une panne, et le batch a
      été coupé avant d'avoir tenté toutes ses épreuves — « tout a échoué » n'y
      est pas établi. Un cron ne s'interrompt pas tout seul : ce code désigne un
      humain, pas un incident.
    - `1` — échec total : aucune épreuve n'a abouti alors qu'il y en avait à
      traiter (cf. `batch.is_total_failure`). Sans lui, un cron dont les 53
      épreuves échouent sortait en 0 et n'alertait jamais. Un batch
      **partiellement** réussi reste un succès (code 0).
    """
    emitted = _echo(report, err=json_output)
    if json_output:
        _echo(json.dumps(asdict(outcome), ensure_ascii=False))
    elif not emitted:
        _echo(report, err=True)  # stdout coupé : le bilan se replie sur stderr
    if outcome.interrupted:
        raise typer.Exit(code=EXIT_INTERRUPTED)
    if outcome.is_total_failure:
        raise typer.Exit(code=EXIT_TOTAL_FAILURE)


def emit_report(report: str, payload: dict, *, json_output: bool) -> None:
    """Émet un rapport d'inventaire, sans code de sortie à porter.

    Pendant de `emit_outcome` pour les commandes qui ne pilotent pas de batch :
    même règle sur stdout (`--json` le garde pur), mais rien à signaler par le
    code de retour — un inventaire ne peut pas « échouer partiellement ».
    """
    emitted = _echo(report, err=json_output)
    if json_output:
        _echo(json.dumps(payload, ensure_ascii=False))
    elif not emitted:
        _echo(report, err=True)  # stdout coupé : le rapport se replie sur stderr


def render_members_sync_report(report: MembersSyncReport) -> str:
    """Synchro des licenciés FFTri (#1202)."""
    return "\n".join([
        "=== LICENCIÉS DU CLUB ===",
        f"Saison {report.season}",
        _line("Licenciés lus", report.total),
        _line("Rattachés à une fiche", report.linked),
        _line("Sans fiche", report.unlinked),
        _line("Plusieurs fiches possibles", report.ambiguous),
    ])


def render_member_emails_import_report(report: MemberEmailsImportReport) -> str:
    """Import de l'export AssoConnect (#1334)."""
    return "\n".join([
        "=== ADRESSES D'ADHÉRENTS ===",
        f"Saison {report.season}",
        _line("Adresses ajoutées", report.added),
        _line("Adresses retirées", report.removed),
        _line("Adresses inchangées", report.unchanged),
        _line("Lignes ignorées", report.ignored),
    ])
