"""
Configuration du logging applicatif.

Appeler `setup_logging()` une fois au démarrage. Chaque module obtient ensuite
son logger via `logging.getLogger(__name__)`.
"""
import logging
import sys

from app.core.config import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    """Configure le root logger selon les réglages (niveau, format)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
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
