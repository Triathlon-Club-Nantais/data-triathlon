"""Rendu et émission des bilans de batch. Aucune logique métier : de la mise en forme."""
import json
from dataclasses import asdict

import typer

from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome

Outcome = SheetOutcome | RescrapeOutcome

#: Interruption clavier (convention shell : 128 + SIGINT).
EXIT_INTERROMPU = 130
#: Échec applicatif : aucune des épreuves ciblées n'a abouti.
EXIT_ECHEC_TOTAL = 1

_LIGNE_ECHEC_TOTAL = (
    "Échec total : aucune des épreuves ciblées n'a abouti (code de sortie "
    f"{EXIT_ECHEC_TOTAL})."
)


def _titre(base: str, *, dry_run: bool, interrupted: bool) -> str:
    if dry_run:
        return f"=== {base} (dry-run) ==="
    if interrupted:
        return f"=== {base} (interrompu — bilan partiel) ==="
    return f"=== {base} ==="


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lignes = [_titre("IMPORT SHEET", dry_run=dry_run, interrupted=outcome.interrupted)]
    lignes.append(f"Liens supportés uniques : {outcome.unique_supported}")
    lignes.append(f"Lignes sans lien        : {outcome.rows_without_link}")
    if not dry_run:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
        if outcome.echec_total:
            lignes.append(_LIGNE_ECHEC_TOTAL)
    if outcome.ignored_by_host:
        lignes.append("Liens non supportés (suivis dans #33) :")
        for host, count in sorted(outcome.ignored_by_host.items()):
            lignes.append(f"  - {host} : {count}")
    return "\n".join(lignes)


def render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible pour rescrape-db.

    On compte des **épreuves** (URLs uniques), pas des courses : depuis la dédup
    par `source_url`, une épreuve porte N courses en base (les heats Breizh
    Chrono, les variantes individuel/relais…). Afficher « courses » ici ferait
    croire à une perte de données à qui compare au `SELECT count(*) FROM course`
    (base de dev : 53 courses pour 12 épreuves).
    """
    lignes = [_titre("RESCRAPE DB", dry_run=dry_run, interrupted=outcome.interrupted)]
    lignes.append(f"Épreuves ciblées : {outcome.total}")
    if dry_run:
        for url in outcome.dry_run_urls:
            lignes.append(f"  - {url}")
    else:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
        if outcome.echec_total:
            lignes.append(_LIGNE_ECHEC_TOTAL)
    return "\n".join(lignes)


def emit_outcome(outcome: Outcome, rapport: str, *, json_output: bool) -> None:
    """Émet le bilan, puis sort en code non nul si le batch a mal fini.

    `--json` est **exclusif** : stdout ne contient alors QUE la ligne JSON, pour
    que `… --json | jq` fonctionne. Le rapport texte bascule sur **stderr**, là
    où sort déjà la progression : un humain le voit toujours, le pipe reste pur.
    Sans `--json`, le rapport texte sort sur stdout comme avant.

    Le bilan est **toujours émis avant** de sortir en erreur : ni un Ctrl-C ni un
    échec total ne doivent faire perdre le travail déjà persisté.

    Codes de sortie, dans cet ordre de priorité :

    - `130` — batch interrompu au clavier. **Prioritaire** sur l'échec total :
      l'interruption est une action de l'opérateur, pas une panne, et le batch a
      été coupé avant d'avoir tenté toutes ses épreuves — « tout a échoué » n'y
      est pas établi. Un cron ne s'interrompt pas tout seul : ce code désigne un
      humain, pas un incident.
    - `1` — échec total : aucune épreuve n'a abouti alors qu'il y en avait à
      traiter (cf. `batch.est_echec_total`). Sans lui, un cron dont les 53
      épreuves échouent sortait en 0 et n'alertait jamais. Un batch
      **partiellement** réussi reste un succès (code 0).
    """
    typer.echo(rapport, err=json_output)
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))
    if outcome.interrupted:
        raise typer.Exit(code=EXIT_INTERROMPU)
    if outcome.echec_total:
        raise typer.Exit(code=EXIT_ECHEC_TOTAL)
