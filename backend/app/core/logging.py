"""
Configuration du logging applicatif.

Appeler `setup_logging()` une fois au démarrage — c'est le rôle du point d'entrée
du process (API web, CLI), jamais celui d'un module importé. Chaque module obtient
ensuite son logger via `logging.getLogger(__name__)`.

Le flux de sortie est paramétrable : l'API web garde stdout (agrégé par Render),
tandis que la CLI doit impérativement router ses logs sur **stderr** — stdout y est
réservé au rapport et à la ligne `--json`, qui doivent rester parsables (`| jq`).
"""
import logging
import sys
from typing import TextIO

from app.core.config import get_settings

_CONFIGURED = False


def setup_logging(stream: TextIO | None = None) -> None:
    """Configure le root logger selon les réglages (niveau, format).

    `stream` : flux de sortie des logs (défaut `sys.stdout`, comportement
    historique de l'API web). La CLI passe `sys.stderr` — cf. `app/cli/__init__.py`.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    if settings.log_json:
        fmt = (
            '{"time":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    _CONFIGURED = True
