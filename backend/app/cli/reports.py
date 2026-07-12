"""Rendu et émission des bilans de batch. Aucune logique métier : de la mise en forme."""
import json
from dataclasses import asdict

import typer

from app.services.bulk_import_service import SheetOutcome
from app.services.rescrape_service import RescrapeOutcome

Outcome = SheetOutcome | RescrapeOutcome


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
    if outcome.ignored_by_host:
        lignes.append("Liens non supportés (suivis dans #33) :")
        for host, count in sorted(outcome.ignored_by_host.items()):
            lignes.append(f"  - {host} : {count}")
    return "\n".join(lignes)


def render_rescrape_report(outcome: RescrapeOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible pour rescrape-db."""
    lignes = [_titre("RESCRAPE DB", dry_run=dry_run, interrupted=outcome.interrupted)]
    lignes.append(f"Courses ciblées : {outcome.total}")
    if dry_run:
        for url in outcome.dry_run_urls:
            lignes.append(f"  - {url}")
    else:
        lignes.append(f"Importées : {outcome.imported}")
        lignes.append(f"Ignorées  : {outcome.skipped}")
        lignes.append(f"En erreur : {outcome.errors}")
    return "\n".join(lignes)


def emit_outcome(outcome: Outcome, rapport: str, *, json_output: bool) -> None:
    """Émet le bilan puis sort en 130 si le batch a été interrompu.

    `--json` est **exclusif** : stdout ne contient alors QUE la ligne JSON, pour
    que `… --json | jq` fonctionne. Le rapport texte bascule sur **stderr**, là
    où sort déjà la progression : un humain le voit toujours, le pipe reste pur.
    Sans `--json`, le rapport texte sort sur stdout comme avant.
    """
    typer.echo(rapport, err=json_output)
    if json_output:
        typer.echo(json.dumps(asdict(outcome), ensure_ascii=False))
    if outcome.interrupted:
        raise typer.Exit(code=130)
