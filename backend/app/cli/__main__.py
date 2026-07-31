"""Point d'entrée `python -m app.cli`."""
from app.cli import (
    app,
    configure_cli_logging,
    configure_cli_tracing,
    shutdown_cli_tracing,
)

if __name__ == "__main__":
    # Le process (et lui seul) configure le logging : sur stderr, pour ne jamais
    # polluer stdout, réservé au rapport et à la ligne `--json`.
    configure_cli_logging()
    configure_cli_tracing()
    try:
        app()
    finally:
        # `app()` sort par SystemExit : sans ce `finally`, les spans du dernier
        # import ne seraient jamais exportés.
        shutdown_cli_tracing()
