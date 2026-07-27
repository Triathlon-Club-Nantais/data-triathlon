"""Lanceur de dev : choix du port et publication du port pour le frontend."""

import json
import socket

import pytest

import scripts.dev_server as dev_server
from scripts.dev_server import (
    BIND_ATTEMPTS,
    BIND_HOST,
    CLIENT_HOST,
    PORT_FILE_NAME,
    _is_free,
    find_free_port,
    main,
    read_port_file,
    remove_port_file,
    resolve_base_port,
    resolve_forced_port,
    should_retry_after_exit,
    worktree_root,
    write_port_file,
)


@pytest.fixture
def port_occupe():
    """Occupe réellement un port et le rend, pour éprouver le scan sans le simuler."""
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    yield sock.getsockname()[1]
    sock.close()


@pytest.fixture
def port_libre():
    """Un port que l'OS vient d'attribuer puis libérer."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ── Choix du port ────────────────────────────────────────────────────────────


def test_find_free_port_rend_le_port_de_base_quand_il_est_libre(port_libre):
    assert find_free_port(base=port_libre, span=1) == port_libre


def test_find_free_port_saute_un_port_deja_pris(port_occupe):
    assert find_free_port(base=port_occupe, span=5) == port_occupe + 1


def test_find_free_port_echoue_si_toute_la_plage_est_prise(port_occupe):
    with pytest.raises(RuntimeError, match="aucun port libre"):
        find_free_port(base=port_occupe, span=1)


# ── Adresse d'écoute ─────────────────────────────────────────────────────────


def test_le_scan_voit_un_port_pris_sur_le_seul_loopback(port_occupe):
    """Le scan bind l'adresse d'écoute d'uvicorn (`0.0.0.0`), pas le loopback.

    Il faut donc qu'un port occupé sur le seul `127.0.0.1` soit tout de même vu pris :
    sans cela, le scan déclarerait libre un port qu'uvicorn ne pourrait pas binder.
    """
    assert _is_free(port_occupe) is False


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


# ── Reprise après une sortie d'uvicorn ───────────────────────────────────────


def test_reprise_si_le_port_a_ete_pris_entre_le_scan_et_le_bind(port_occupe):
    assert should_retry_after_exit(port_occupe, forced=None, tentative=0) is True


def test_pas_de_reprise_si_le_port_est_libre(port_libre):
    """Port libre = la panne n'est pas un conflit de bind : la vraie cause doit remonter,
    et non se cacher derrière trois démarrages sur trois ports."""
    assert should_retry_after_exit(port_libre, forced=None, tentative=0) is False


def test_pas_de_reprise_sur_un_port_impose(port_occupe):
    assert should_retry_after_exit(port_occupe, forced=port_occupe, tentative=0) is False


def test_pas_de_reprise_a_la_derniere_tentative(port_occupe):
    assert (
        should_retry_after_exit(port_occupe, forced=None, tentative=BIND_ATTEMPTS - 1)
        is False
    )


# ── Variables d'environnement ────────────────────────────────────────────────


def test_resolve_forced_port_absent_par_defaut():
    assert resolve_forced_port({}) is None


def test_resolve_forced_port_lit_dev_backend_port():
    assert resolve_forced_port({"DEV_BACKEND_PORT": "9123"}) == 9123


def test_resolve_base_port_vaut_8001_par_defaut():
    assert resolve_base_port({}) == 8001


def test_resolve_base_port_lit_dev_backend_port_base():
    assert resolve_base_port({"DEV_BACKEND_PORT_BASE": "9000"}) == 9000


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
