"""Rendu et émission des bilans de batch. Aucune logique métier : de la mise en forme."""
import json
import os
import sys
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


#: Largeur de la colonne des libellés (le plus long : « Participants déjà en base »).
_COL = 25


def _ligne(libelle: str, valeur: object) -> str:
    return f"{libelle:<{_COL}} : {valeur}"


def _lignes_compteurs(outcome: Outcome) -> list[str]:
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
    lignes = []
    if outcome.interrupted:
        lignes.append(_ligne("Épreuves traitées", outcome.processed))
    lignes.append(_ligne("Épreuves en erreur", outcome.errors))
    lignes.append(_ligne("Participants ajoutés", outcome.imported))
    lignes.append(_ligne("Participants déjà en base", outcome.skipped))
    if outcome.echec_total:
        lignes.append(_LIGNE_ECHEC_TOTAL)
    return lignes


def _titre(base: str, *, dry_run: bool, interrupted: bool) -> str:
    if dry_run:
        return f"=== {base} (dry-run) ==="
    if interrupted:
        return f"=== {base} (interrompu — bilan partiel) ==="
    return f"=== {base} ==="


def _lignes_echecs(outcome: Outcome) -> list[str]:
    """Le détail des épreuves fautives, commun aux deux commandes.

    Le compteur « Épreuves en erreur : N » dit *combien* ; ce bloc dit
    *lesquelles* et *pourquoi*, sans avoir à rejouer le batch. Il alimente aussi
    la boucle de rejeu de `rescrape-db --urls-from -`. Deux rendus divergeaient
    sans raison : `run_batch` collecte ces échecs pour les deux commandes.
    """
    if not outcome.failures:
        return []
    lignes = ["Épreuves en erreur (détail) :"]
    lignes.extend(f"  - {f.url} : {f.message}" for f in outcome.failures)
    return lignes


def _lignes_reconciliation(outcome: RescrapeOutcome) -> list[str]:
    """Le bilan de réconciliation d'identité (issue #66), borné aux réassignations.

    Unités nommées : on compte des **participations** et des **athlètes**, jamais
    des « lignes ». Masqué quand rien n'a été réconcilié.
    """
    if not outcome.reconciled:
        return []
    lignes = [
        _ligne("Participations réconciliées", outcome.reconciled),
        _ligne("Athlètes fusionnés", outcome.merged),
        _ligne("Athlètes orphelins supprimés", outcome.orphans_removed),
        "Identités réconciliées (détail) :",
    ]
    lignes.extend(
        f"  - {r.ancien}  ->  {r.nouveau}   ({r.participations} participations)"
        for r in outcome.reconciliations
    )
    return lignes


def render_sheet_report(outcome: SheetOutcome, *, dry_run: bool) -> str:
    """Rapport texte lisible : compteurs + table des ignorés groupés par host."""
    lignes = [_titre("IMPORT SHEET", dry_run=dry_run, interrupted=outcome.interrupted)]
    lignes.append(_ligne("Liens supportés uniques", outcome.unique_supported))
    lignes.append(_ligne("Lignes sans lien", outcome.rows_without_link))
    if not dry_run:
        lignes.extend(_lignes_compteurs(outcome))
        lignes.extend(_lignes_echecs(outcome))
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
    lignes.append(_ligne("Épreuves ciblées", outcome.total))
    if dry_run:
        for url in outcome.dry_run_urls:
            lignes.append(f"  - {url}")
    else:
        lignes.extend(_lignes_compteurs(outcome))
        lignes.extend(_lignes_echecs(outcome))
    lignes.extend(_lignes_reconciliation(outcome))
    return "\n".join(lignes)


def _museler_le_flux(*, err: bool) -> None:
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
    flux = sys.stderr if err else sys.stdout
    try:
        fd = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(fd, flux.fileno())
        finally:
            os.close(fd)
    except (OSError, ValueError, AttributeError):
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
        _museler_le_flux(err=err)
        return False


def emit_outcome(outcome: Outcome, rapport: str, *, json_output: bool) -> None:
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
      traiter (cf. `batch.est_echec_total`). Sans lui, un cron dont les 53
      épreuves échouent sortait en 0 et n'alertait jamais. Un batch
      **partiellement** réussi reste un succès (code 0).
    """
    emis = _echo(rapport, err=json_output)
    if json_output:
        _echo(json.dumps(asdict(outcome), ensure_ascii=False))
    elif not emis:
        _echo(rapport, err=True)  # stdout coupé : le bilan se replie sur stderr
    if outcome.interrupted:
        raise typer.Exit(code=EXIT_INTERROMPU)
    if outcome.echec_total:
        raise typer.Exit(code=EXIT_ECHEC_TOTAL)
