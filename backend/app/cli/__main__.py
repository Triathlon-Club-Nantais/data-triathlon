"""Point d'entrée `python -m app.cli`."""
from app.cli import app, configure_cli_logging

if __name__ == "__main__":
    # Le process (et lui seul) configure le logging : sur stderr, pour ne jamais
    # polluer stdout, réservé au rapport et à la ligne `--json`.
    configure_cli_logging()
    app()
