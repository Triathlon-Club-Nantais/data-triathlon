"""Commande `rescrape-db` : options Typer, câblage, affichage. Zéro logique métier."""
import typer

from app.cli.progress import select_reporter
from app.cli.reports import emit_outcome, render_rescrape_report
from app.cli.url_sources import charger_urls, valider_ciblage_exclusif, valider_single_heat
from app.cli.validators import valider_max_concurrent_hosts, valider_provider
from app.core.config import get_settings
from app.core.database import session_scope
from app.services import rescrape_service


def _redirection_source_passive(cible: rescrape_service.PassiveTarget) -> str:
    """La substitution d'une URL passive, dite pour être corrigeable à la source.

    Le batch continue : ce message n'est pas une erreur, mais la trace de ce qui
    a été redressé. C'est elle qui permet de corriger le **fichier** d'URLs, que
    la CLI ne peut pas réécrire — sans elle, la liste resterait fausse pour
    toujours.
    """
    if not cible.active_url:
        return (
            f"« {cible.url} » est une source passive de l'épreuve "
            f"« {cible.course_name} », qui n'a aucune source active : elle est "
            "re-scrapée telle quelle."
        )
    return (
        f"« {cible.url} » est une source passive de l'épreuve "
        f"« {cible.course_name} » : re-scrape de sa source active "
        f"« {cible.active_url} »."
    )


def rescrape_db(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Liste les épreuves sans scraper ni persister."
    ),
    older_than: int | None = typer.Option(
        None, "--older-than",
        help="Ne re-scrape que les épreuves scrapées il y a plus de N jours.",
    ),
    provider: str | None = typer.Option(
        None, "--provider", callback=valider_provider,
        help="Restreint à un provider (défaut : tous).",
    ),
    url: list[str] = typer.Option(
        [], "--url",
        help="Cible une épreuve précise (répétable). Court-circuite la base.",
    ),
    urls_from: str | None = typer.Option(
        None, "--urls-from",
        help="Fichier d'URLs (une par ligne), ou « - » pour lire stdin.",
    ),
    limit: int | None = typer.Option(None, "--limit", help="Borne le nombre d'épreuves."),
    delay: float = typer.Option(
        1.0, "--delay", help="Pause de politesse entre scrapes (s)."
    ),
    max_concurrent_hosts: int = typer.Option(
        4, "--max-concurrent-hosts", callback=valider_max_concurrent_hosts,
        help="Plafond de chronométreurs traités en même temps.",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
    no_progress: bool = typer.Option(
        False, "--no-progress", help="Aucun affichage de progression."
    ),
    plain: bool = typer.Option(
        False, "--plain", help="Progression ligne à ligne même dans un terminal."
    ),
    single_heat: bool = typer.Option(
        False, "--single-heat",
        help=(
            "Klikego : n'importe que le heat désigné par le ?heat= de --url "
            "(échappatoire, aucun fan-out). Exige --url avec ?heat=X."
        ),
    ),
) -> None:
    """Re-scrape des épreuves (toute la base, ou celles ciblées par `--url`).

    Une épreuve = une source **active** unique. Elle porte souvent plusieurs
    courses en base (heats Breizh Chrono, variantes individuel/relais) : le
    rapport et --limit comptent des épreuves, pas des lignes de la table course.
    Les sources **passives** d'une épreuve fusionnée ne sont jamais scrapées
    (#282) : `--provider` nomme le provider de l'active, et une URL passive
    passée à `--url` est remplacée par l'active de son épreuve.

    Deux modes de sélection, exclusifs l'un de l'autre : par filtre sur la base
    (`--provider`, `--older-than`), ou par URL explicite (`--url`,
    `--urls-from`). Le second court-circuite la base — c'est ce qui permet de
    rejouer une épreuve en échec à l'import, absente de la table `course` :

        … import-sheet --json | jq -r '.failures[].url' \\
          | … rescrape-db --urls-from -
    """
    valider_ciblage_exclusif(url=url, urls_from=urls_from, provider=provider, older_than=older_than)
    valider_single_heat(
        single_heat=single_heat, url=url, urls_from=urls_from,
        provider=provider, older_than=older_than,
    )
    urls = charger_urls(url, urls_from)

    settings = get_settings()
    reporter = select_reporter(no_progress=no_progress or dry_run, plain=plain)

    with session_scope() as db:
        # Le seul redressement de cette commande qui exige la base, et il ne
        # pouvait pas être un callback Typer pour cette raison : « cette URL
        # est-elle passive ? » ne se lit que dans `course_sources`.
        #
        # Une passive n'est jamais scrapée telle quelle quand son épreuve a une
        # active (#282) : ce serait importer le classement d'un autre
        # chronométreur dans l'épreuve. Mais le lot n'est plus **refusé** pour
        # autant : une URL périmée dans un fichier de soixante-dix ne doit pas
        # coûter les soixante-neuf autres. On substitue, et on le dit.
        #
        # Sans active — épreuve saisie à la main (#283) —, la passive part telle
        # quelle : elle est la seule publication connue, aucun doublon n'est
        # possible, et refuser ne scraperait rien du tout.
        cibles = urls or []
        passives = rescrape_service.find_passive_targets(db, cibles)
        if passives:
            for cible in passives:
                # stderr : stdout est le canal `--json`, une phrase française
                # l'invaliderait.
                typer.echo(_redirection_source_passive(cible), err=True)
            # Les doublons que la substitution peut créer (l'active déjà dans le
            # lot) sont absorbés en aval par `_items_depuis_urls`, qui dédoublonne.
            actives = {c.url: c.active_url for c in passives if c.active_url}
            urls = [actives.get(soumise, soumise) for soumise in cibles]

        outcome = rescrape_service.run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay, reporter=reporter, urls=urls,
            single_heat=single_heat, max_concurrent_hosts=max_concurrent_hosts,
        )

    emit_outcome(
        outcome,
        render_rescrape_report(outcome, dry_run=dry_run),
        json_output=json_output,
    )
