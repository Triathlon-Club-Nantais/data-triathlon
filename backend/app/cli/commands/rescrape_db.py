"""Commande `rescrape-db` : options Typer, câblage, affichage. Zéro logique métier."""
import typer

from app.cli.progress import select_reporter
from app.cli.reports import emit_outcome, render_rescrape_report
from app.cli.url_sources import charger_urls, valider_ciblage_exclusif, valider_single_heat
from app.cli.validators import valider_provider
from app.core.config import get_settings
from app.core.database import session_scope
from app.services import rescrape_service

#: Convention Click / Typer, comme `grant-role`, `allow-email` et
#: `revoke-sessions` : `2` = erreur d'usage.
USAGE = 2


def _refus_source_passive(cible: rescrape_service.PassiveTarget) -> str:
    """Le refus d'une URL passive, formulé pour être corrigeable sans lire le code."""
    if not cible.active_url:
        return (
            f"« {cible.url} » est une source passive de l'épreuve "
            f"« {cible.course_name} », qui n'a aucune source active : il n'y a "
            "rien à re-scraper."
        )
    return (
        f"« {cible.url} » est une source passive de l'épreuve "
        f"« {cible.course_name} ». Sa source active est « {cible.active_url} » — "
        "ciblez celle-là."
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
    passée à `--url` est refusée.

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
        # Le seul refus de cette commande qui exige la base, et il ne pouvait pas
        # être un callback Typer pour cette raison : « cette URL est-elle passive ? »
        # ne se lit que dans `course_sources`. Reste une **erreur d'usage** (code
        # 2) et non un échec de batch — l'opérateur a désigné la mauvaise URL,
        # rien n'a été tenté. Précédent : `revoke-sessions --email <inconnue>`,
        # qui se constate aussi en base et sort en 2.
        #
        # Refus **global** : on ne scrape pas les URLs valides du lot. Un bilan
        # partiel doublé d'un code 2 ne se lirait ni comme un succès ni comme un
        # refus, et l'opérateur relancerait sans savoir ce qui a déjà tourné.
        passives = rescrape_service.find_passive_targets(db, urls or [])
        if passives:
            for cible in passives:
                # stderr, comme toute erreur d'usage de cette commande : stdout
                # est le canal `--json`, une phrase française l'invaliderait.
                typer.echo(_refus_source_passive(cible), err=True)
            raise typer.Exit(USAGE)

        outcome = rescrape_service.run_rescrape_db(
            db, settings,
            dry_run=dry_run, older_than=older_than, provider=provider,
            limit=limit, delay=delay, reporter=reporter, urls=urls,
            single_heat=single_heat,
        )

    emit_outcome(
        outcome,
        render_rescrape_report(outcome, dry_run=dry_run),
        json_output=json_output,
    )
