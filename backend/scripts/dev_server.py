"""Lanceur de développement du backend : port dynamique, publié pour le frontend.

Pourquoi ce script plutôt qu'un `uvicorn --port 8001` en dur : plusieurs worktrees
du dépôt tournent en parallèle, et un port figé fait échouer le second démarrage
sur « Address already in use ». On prend donc le premier port libre à partir de
8001, et on le publie dans `.dev-backend.json` à la racine du worktree.

C'est ce fichier que lit `frontend/scripts/dev.mjs` pour brancher le front sur le
backend de SON worktree. Sans lui, le front se rabattait sur `localhost:8001`
en dur (`next.config.ts`, `lib/api/server.ts`) et lisait donc, en silence, la base
du worktree d'à côté.

L'écoute couvre toutes les interfaces (`0.0.0.0`), comme en production : sur le seul
loopback, l'API serait injoignable depuis l'extérieur d'un conteneur. L'URL publiée,
elle, reste en `127.0.0.1` — `0.0.0.0` désigne des interfaces d'écoute, pas une cible
joignable (cf. BIND_HOST / CLIENT_HOST).

Réservé au développement : en production, le port vient de `$PORT` (cf. Dockerfile).

Variables d'environnement :
    DEV_BACKEND_PORT       force un port précis et court-circuite le scan
    DEV_BACKEND_PORT_BASE  point de départ du scan (défaut : 8001)
"""

import json
import os
import socket
import sys
from collections.abc import Mapping
from pathlib import Path

PORT_FILE_NAME = ".dev-backend.json"
DEFAULT_BASE_PORT = 8001
DEFAULT_SPAN = 50

# Deux adresses, deux rôles — les confondre casse un cas ou l'autre.
#
# BIND_HOST : où l'on écoute. Toutes les interfaces, comme en production
# (`--host 0.0.0.0` dans le Dockerfile et render.yaml) : le seul loopback rendrait
# l'API injoignable depuis l'extérieur d'un conteneur, ou depuis un autre appareil
# du réseau local. C'est aussi l'adresse que le scan de ports bind, sans quoi il
# déclarerait libre un port qu'uvicorn ne pourrait pas prendre (service écoutant
# sur la seule IP de l'interface).
#
# CLIENT_HOST : ce qu'on publie comme cible joignable. `0.0.0.0` n'est pas une
# adresse de destination — elle ne se résout pas hors de Linux — donc le loopback.
BIND_HOST = "0.0.0.0"
CLIENT_HOST = "127.0.0.1"

# Nombre de reprises si le port choisi est pris entre le scan et le bind d'uvicorn
# (deux worktrees démarrés au même instant). Le scan seul ne garantit pas l'exclusivité.
BIND_ATTEMPTS = 3


def worktree_root() -> Path:
    """Racine du worktree — `backend/scripts/dev_server.py` remonte de trois crans."""
    return Path(__file__).resolve().parents[2]


def backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


# ── Choix du port ────────────────────────────────────────────────────────────


def _is_free(port: int, host: str = BIND_HOST) -> bool:
    with socket.socket() as sock:
        # Sans SO_REUSEADDR, un port en TIME_WAIT passerait pour occupé.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_free_port(
    base: int = DEFAULT_BASE_PORT, span: int = DEFAULT_SPAN, host: str = BIND_HOST
) -> int:
    """Premier port libre dans `[base, base + span)`."""
    for port in range(base, base + span):
        if _is_free(port, host):
            return port
    raise RuntimeError(f"aucun port libre entre {base} et {base + span - 1}")


def should_retry_after_exit(
    port: int, forced: int | None, tentative: int, host: str = BIND_HOST
) -> bool:
    """Une sortie `SystemExit` d'uvicorn vaut-elle une reprise sur un autre port ?

    Uvicorn quitte par `sys.exit()` quand le bind échoue — le cas qu'on veut rattraper,
    le port ayant été pris entre notre scan et le sien — mais **aussi** sur d'autres
    pannes de démarrage (app introuvable, config invalide). Retenter à l'aveugle
    masquerait la vraie cause derrière trois démarrages sur trois ports différents :
    on ne repart donc que si le port est effectivement occupé.
    """
    if forced is not None or tentative >= BIND_ATTEMPTS - 1:
        return False
    return not _is_free(port, host)


# ── Variables d'environnement ────────────────────────────────────────────────


def _as_port(env: Mapping[str, str], key: str, defaut: int | None) -> int | None:
    brut = env.get(key, "").strip()
    if not brut:
        return defaut
    try:
        return int(brut)
    except ValueError as exc:
        raise ValueError(f"{key} doit être un entier, reçu : {brut!r}") from exc


def resolve_forced_port(env: Mapping[str, str]) -> int | None:
    return _as_port(env, "DEV_BACKEND_PORT", None)


def resolve_base_port(env: Mapping[str, str]) -> int:
    port = _as_port(env, "DEV_BACKEND_PORT_BASE", DEFAULT_BASE_PORT)
    assert port is not None  # le défaut n'est jamais None
    return port


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

    root = worktree_root()
    forced = resolve_forced_port(os.environ)
    base = resolve_base_port(os.environ)

    for tentative in range(BIND_ATTEMPTS):
        port = forced if forced is not None else find_free_port(base)
        write_port_file(root, port)
        print(
            f"→ backend sur http://{CLIENT_HOST}:{port} "
            f"(écoute {BIND_HOST}, port publié dans {PORT_FILE_NAME})"
        )
        try:
            uvicorn.run("app.main:app", host=BIND_HOST, port=port, reload=True)
            return 0
        except SystemExit:
            # Reprise réservée au port occupé (cf. should_retry_after_exit) : toute
            # autre panne de démarrage doit remonter telle quelle, pas être masquée.
            if not should_retry_after_exit(port, forced, tentative):
                raise
            base = port + 1
        finally:
            remove_port_file(root)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
