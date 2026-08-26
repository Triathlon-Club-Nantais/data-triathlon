"""Point d'entrée `python -m app.cli`."""
from app.cli import app, configure_cli_logging, load_counter_scope

if __name__ == "__main__":
    # Le process (et lui seul) configure le logging : sur stderr, pour ne jamais
    # polluer stdout, réservé au rapport et à la ligne `--json`.
    configure_cli_logging()
    # Et lui seul remplit le registre de la portée des compteurs (#95) : sans
    # ce chargement, la CLI se prononcerait sur les défauts du code plutôt que
    # sur ce qui est configuré — `club-labels` dirait qu'un libellé déclaré en
    # base manque encore.
    load_counter_scope()
    app()
