"""Commande `weekend-digest` : poste sur Slack les résultats TCN du week-end (#1363). Zéro logique métier.

Lancée par le seul passage planifié du lundi (`.github/workflows/batch.yml`).
"""
import logging
from datetime import datetime

import typer

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.time import utcnow
from app.services import weekend_digest as weekend_digest_service

logger = logging.getLogger(__name__)


def weekend_digest(
    day: datetime | None = typer.Option(None, "--date", formats=["%Y-%m-%d"], help="Jour de lancement (défaut : aujourd'hui)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Affiche le message sans le poster."),
) -> None:
    """Poste le récap des résultats TCN du week-end écoulé."""
    settings = get_settings()
    webhook_url = settings.slack_digest_webhook_url.get_secret_value()
    if not webhook_url and not dry_run:
        logger.warning("SLACK_DIGEST_WEBHOOK_URL est vide : aucun récap du week-end n'est envoyé.")
        return

    launch_day = (day or utcnow()).date()
    with session_scope() as db:
        text = weekend_digest_service.build(db, launch_day, base_url=settings.auth_redirect_base_url)
    if text is None:
        logger.info("Aucune épreuve TCN le week-end précédant le %s, rien n'est envoyé.", launch_day)
        return
    if dry_run:
        typer.echo(text)
        return

    try:
        weekend_digest_service.send(text, webhook_url)
    except weekend_digest_service.DigestDeliveryError as error:
        logger.error("Récap du week-end non envoyé : %s", error)
        raise typer.Exit(1) from None
    typer.echo("Récapitulatif du week-end envoyé sur Slack.")
