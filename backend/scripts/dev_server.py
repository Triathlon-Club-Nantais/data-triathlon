"""Lanceur de développement du backend : port dynamique, publié pour le frontend.

Pourquoi ce script plutôt qu'un `uvicorn --port 8001` en dur : plusieurs worktrees
du dépôt tournent en parallèle, et un port figé fait échouer le second démarrage
sur « Address already in use ». On laisse donc l'OS attribuer un port éphémère,
et on le publie dans `.dev-backend.json` à la racine du worktree.

C'est ce fichier que lit `frontend/scripts/dev.mjs` pour brancher le front sur le
backend de SON worktree. Sans lui, le front se rabattait sur `localhost:8001`
en dur (`next.config.ts`, `lib/api/server.ts`) et lisait donc, en silence, la base
du worktree d'à côté.

L'écoute couvre toutes les interfaces (`0.0.0.0`), comme en production : sur le seul
loopback, l'API serait injoignable depuis l'extérieur d'un conteneur. L'URL publiée,
elle, reste en `127.0.0.1` — `0.0.0.0` désigne des interfaces d'écoute, pas une cible
joignable (cf. BIND_HOST / CLIENT_HOST).

Réservé au développement : en production, le port vient de `$PORT` (cf. Dockerfile).

Variable d'environnement :
    DEV_BACKEND_PORT  force un port précis, pour un dev qui veut une URL stable
"""

import json
import os
import socket
import sys
from collections.abc import Mapping
from pathlib import Path

PORT_FILE_NAME = ".dev-backend.json"

# Deux adresses, deux rôles — les confondre casse un cas ou l'autre.
#
# BIND_HOST : où l'on écoute. Toutes les interfaces, comme en production
# (`--host 0.0.0.0` dans le Dockerfile et render.yaml) : le seul loopback rendrait
# l'API injoignable depuis l'extérieur d'un conteneur, ou depuis un autre appareil
# du réseau local. C'est aussi l'adresse sur laquelle on tire le port éphémère,
# sans quoi on obtiendrait un port libre sur le loopback qu'uvicorn ne pourrait
# pas prendre sur toutes les interfaces.
#
# CLIENT_HOST : ce qu'on publie comme cible joignable. `0.0.0.0` n'est pas une
# adresse de destination — elle ne se résout pas hors de Linux — donc le loopback.
BIND_HOST = "0.0.0.0"  # noqa: S104 — serveur de dev, exposition au réseau local voulue
CLIENT_HOST = "127.0.0.1"


def worktree_root() -> Path:
    """Racine du worktree — `backend/scripts/dev_server.py` remonte de trois crans."""
    return Path(__file__).resolve().parents[2]


def backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


# ── Niveau de schéma Alembic ─────────────────────────────────────────────────


def base_de_dev_a_jour(database_url: str) -> bool:
    """La base ouverte par `database_url` est-elle au(x) head(s) Alembic du dépôt ?

    Compare la révision effectivement appliquée (`MigrationContext.get_current_heads`,
    lue sur la connexion ouverte) à la révision de tête attendue par les scripts de
    migration (`ScriptDirectory.get_heads`, lue depuis `alembic.ini`). N'exécute
    aucune migration : c'est un constat, pas une correction — cf. #338.
    """
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    cfg = Config(str(backend_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir() / "alembic"))
    heads = set(ScriptDirectory.from_config(cfg).get_heads())

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()

    return current == heads


# ── Choix du port ────────────────────────────────────────────────────────────


def find_free_port(host: str = BIND_HOST) -> int:
    """Port libre attribué par l'OS (bind sur le port 0).

    Remplace un scan à partir de 8001 : c'est ce **point de départ déterministe**
    qui faisait entrer en collision deux worktrees démarrés au même instant (deux
    scans concurrents trouvent le même premier port libre), et qui imposait une
    boucle de reprise à trois essais. Un port éphémère supprime la cause, donc le
    rattrapage.
    """
    with socket.socket() as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


# ── Variables d'environnement ────────────────────────────────────────────────


def resolve_forced_port(env: Mapping[str, str]) -> int | None:
    """Port imposé par `DEV_BACKEND_PORT`, ou None. Une valeur illisible est une
    erreur explicite : la retomber en silence sur un port éphémère donnerait une
    URL différente de celle demandée, sans le dire."""
    brut = env.get("DEV_BACKEND_PORT", "").strip()
    if not brut:
        return None
    try:
        return int(brut)
    except ValueError as exc:
        raise ValueError(f"DEV_BACKEND_PORT doit être un entier, reçu : {brut!r}") from exc


# ── Publication du port ──────────────────────────────────────────────────────


def port_file_path(root: Path) -> Path:
    return root / PORT_FILE_NAME


def write_port_file(root: Path, port: int, pid: int | None = None) -> Path:
    """Publie le port. Écriture atomique : un lecteur ne voit jamais un JSON tronqué."""
    chemin = port_file_path(root)
    charge = {
        "port": port,
        "url": f"http://{CLIENT_HOST}:{port}",
        "pid": pid or os.getpid(),
    }
    tmp = chemin.with_suffix(".tmp")
    tmp.write_text(json.dumps(charge), encoding="utf-8")
    os.replace(tmp, chemin)
    return chemin


def read_port_file(root: Path) -> dict | None:
    """Charge publiée, ou None si le fichier est absent ou illisible."""
    try:
        return json.loads(port_file_path(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def remove_port_file(root: Path, pid: int | None = None) -> bool:
    """Retire le fichier, sauf s'il appartient à un autre processus.

    Le garde-fou compte : un redémarrage concurrent a pu réécrire le fichier
    entre-temps, et l'arrêt du processus précédent ne doit pas l'effacer.
    """
    charge = read_port_file(root)
    if charge is None:
        return False
    if charge.get("pid") != (pid or os.getpid()):
        return False
    port_file_path(root).unlink(missing_ok=True)
    return True


# ── Point d'entrée ───────────────────────────────────────────────────────────


def main() -> int:
    import uvicorn

    # Le cwd décide de l'import `app.main` et du chemin de la base SQLite
    # (`sqlite:///./triathlon.db`) : on l'ancre, quel que soit le répertoire d'appel.
    os.chdir(backend_dir())
    sys.path.insert(0, str(backend_dir()))

    from app.core.config import get_settings

    if not base_de_dev_a_jour(get_settings().database_url):
        print(
            "⚠ Base de dev en retard sur les migrations Alembic — "
            "lance `uv run alembic upgrade head` (depuis backend/) pour la mettre à jour."
        )

    root = worktree_root()
    port = resolve_forced_port(os.environ) or find_free_port()
    write_port_file(root, port)
    print(
        f"→ backend sur http://{CLIENT_HOST}:{port} "
        f"(écoute {BIND_HOST}, port publié dans {PORT_FILE_NAME})"
    )
    try:
        uvicorn.run("app.main:app", host=BIND_HOST, port=port, reload=True)
        return 0
    finally:
        remove_port_file(root)


if __name__ == "__main__":
    raise SystemExit(main())
