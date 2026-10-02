"""Lanceur de dev : choix du port et publication du port pour le frontend."""

import json
import socket

import pytest
from alembic import command
from alembic.config import Config

import scripts.dev_server as dev_server
from scripts.dev_server import (
    BIND_HOST,
    CLIENT_HOST,
    PORT_FILE_NAME,
    backend_dir,
    base_de_dev_a_jour,
    find_free_port,
    main,
    read_port_file,
    remove_port_file,
    resolve_forced_port,
    worktree_root,
    write_port_file,
)


@pytest.fixture
def port_libre():
    """Un port que l'OS vient d'attribuer puis libérer."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ── Choix du port ────────────────────────────────────────────────────────────


def test_find_free_port_rend_un_port_reellement_bindable():
    """Un port éphémère tiré par l'OS : il doit être libre juste après le tirage."""
    port = find_free_port()

    assert 1024 < port < 65536
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((BIND_HOST, port))  # ne lève pas : le port est bien libre


def test_deux_tirages_consecutifs_ne_collisionnent_pas():
    """La raison d'être de la bascule sur le port 0 : deux worktrees démarrés au
    même instant tombaient sur le même « premier port libre à partir de 8001 ».
    L'OS, lui, ne rend pas deux fois le même port éphémère tant que le premier
    socket est ouvert.
    """
    with socket.socket() as premier:
        premier.bind((BIND_HOST, 0))
        assert find_free_port() != premier.getsockname()[1]


# ── Adresse d'écoute ─────────────────────────────────────────────────────────


def test_uvicorn_ecoute_toutes_les_interfaces(monkeypatch, tmp_path, port_libre):
    """Écouter le seul loopback rendrait l'API injoignable depuis l'extérieur d'un
    conteneur — c'est déjà `--host 0.0.0.0` en production (Dockerfile, render.yaml)."""
    import uvicorn

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dev_server, "worktree_root", lambda: tmp_path)
    monkeypatch.setenv("DEV_BACKEND_PORT", str(port_libre))
    appels = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: appels.append(kw))

    assert main() == 0
    assert appels == [{"host": "0.0.0.0", "port": port_libre, "reload": True}]


def test_l_url_publiee_est_une_adresse_de_connexion(tmp_path):
    """`0.0.0.0` désigne les interfaces d'écoute, jamais une cible joignable : le front
    et le navigateur reçoivent donc le loopback, quelle que soit l'adresse d'écoute."""
    assert BIND_HOST == "0.0.0.0"
    assert CLIENT_HOST == "127.0.0.1"

    chemin = write_port_file(tmp_path, 8042, pid=4242)

    assert json.loads(chemin.read_text(encoding="utf-8"))["url"] == "http://127.0.0.1:8042"


# ── Variables d'environnement ────────────────────────────────────────────────


def test_resolve_forced_port_absent_par_defaut():
    assert resolve_forced_port({}) is None


def test_resolve_forced_port_lit_dev_backend_port():
    assert resolve_forced_port({"DEV_BACKEND_PORT": "9123"}) == 9123


def test_une_valeur_de_port_non_numerique_est_rejetee_explicitement():
    with pytest.raises(ValueError, match="DEV_BACKEND_PORT"):
        resolve_forced_port({"DEV_BACKEND_PORT": "abc"})


# ── Publication du port ──────────────────────────────────────────────────────


def test_write_port_file_ecrit_port_url_et_pid(tmp_path):
    chemin = write_port_file(tmp_path, 8042, pid=4242)

    assert chemin == tmp_path / PORT_FILE_NAME
    charge = json.loads(chemin.read_text(encoding="utf-8"))
    assert charge == {"port": 8042, "url": "http://127.0.0.1:8042", "pid": 4242}


def test_read_port_file_rend_none_si_absent(tmp_path):
    assert read_port_file(tmp_path) is None


def test_read_port_file_rend_none_sur_un_fichier_corrompu(tmp_path):
    (tmp_path / PORT_FILE_NAME).write_text("{ pas du json", encoding="utf-8")

    assert read_port_file(tmp_path) is None


def test_remove_port_file_supprime_le_fichier_du_processus_courant(tmp_path):
    write_port_file(tmp_path, 8042, pid=4242)

    assert remove_port_file(tmp_path, pid=4242) is True
    assert not (tmp_path / PORT_FILE_NAME).exists()


def test_remove_port_file_laisse_le_fichier_d_un_autre_processus(tmp_path):
    """Un redémarrage concurrent a réécrit le fichier : notre arrêt ne doit pas l'effacer."""
    write_port_file(tmp_path, 8043, pid=999)

    assert remove_port_file(tmp_path, pid=4242) is False
    assert read_port_file(tmp_path) == {
        "port": 8043,
        "url": "http://127.0.0.1:8043",
        "pid": 999,
    }


def test_remove_port_file_sur_fichier_absent_ne_leve_pas(tmp_path):
    assert remove_port_file(tmp_path, pid=4242) is False


# ── Racine du worktree ───────────────────────────────────────────────────────


def test_worktree_root_pointe_la_racine_du_depot():
    """Le fichier de port doit atterrir à la racine du worktree, pas dans backend/."""
    racine = worktree_root()

    assert (racine / "backend" / "scripts" / "dev_server.py").is_file()
    assert (racine / "frontend" / "package.json").is_file()


# ── Niveau de schéma Alembic (#338) ──────────────────────────────────────────


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    """URL SQLite jetable, vue par `alembic/env.py` via `get_settings()`.

    `alembic/env.py` réécrit toujours `sqlalchemy.url` depuis `get_settings()` —
    passer l'URL à `Config.set_main_option` ne suffit donc pas pour piloter
    `command.upgrade`/`command.downgrade` ; il faut passer par la variable
    d'environnement, comme le fait la fixture homonyme de `tests/test_migrations.py`.
    """
    from app.core.config import get_settings

    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def _config_pour_les_scripts() -> Config:
    """Config Alembic pointant les vrais scripts de migration du dépôt."""
    cfg = Config(str(backend_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir() / "alembic"))
    return cfg


def test_base_de_dev_a_jour_est_vrai_quand_la_base_est_au_head(sqlite_url):
    command.upgrade(_config_pour_les_scripts(), "head")

    assert base_de_dev_a_jour(sqlite_url) is True


def test_base_de_dev_a_jour_est_faux_quand_la_base_a_une_migration_de_retard(sqlite_url):
    cfg = _config_pour_les_scripts()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")  # une révision avant le head courant

    assert base_de_dev_a_jour(sqlite_url) is False


def test_base_de_dev_a_jour_est_faux_sur_une_base_vierge_sans_alembic_version(sqlite_url):
    """Aucune migration jouée du tout — `alembic_version` n'existe même pas."""
    assert base_de_dev_a_jour(sqlite_url) is False
