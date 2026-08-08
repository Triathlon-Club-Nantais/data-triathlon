"""Lancement et suivi des batches — `contracts/admin-batches.md` (#47).

Le dialogue avec la plateforme est déjà éprouvé dans
`test_services/test_batch_runs.py` ; ici on n'éprouve que la couche HTTP :
gardes, validation des options, traduction des erreurs. Les trois fonctions du
service sont donc remplacées, jamais son transport.

Le fichier vit sous `test_auth/` et non `test_api/` : ce dernier ouvre d'office
une session superutilisateur (son `conftest.py`), ce qui rendrait les cas 401 et
403 intestables.
"""
from dataclasses import replace
from datetime import datetime

import pytest

from app.core.permissions import P
from app.services import batch_runs

URL = "/api/v1/admin/batches"


@pytest.fixture(autouse=True)
def jeton_present(monkeypatch):
    """Le cas nominal : l'instance est configurée pour lancer des batches."""
    from app.core.config import get_settings

    monkeypatch.setenv("GITHUB_BATCH_TOKEN", "gh-jeton-de-test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _run(**surcharges) -> batch_runs.BatchRun:
    return replace(
        batch_runs.BatchRun(
            id=1284,
            label="batch · production · rescrape · b7c1f2e4",
            state="completed",
            outcome="success",
            started_at=datetime.fromisoformat("2026-08-08T18:00:23Z"),
            duration_s=240,
            triggered_by="ui",
            report_available=True,
            external_url="https://github.com/Un-Club/un-depot/actions/runs/1284",
        ),
        **surcharges,
    )


@pytest.fixture
def plateforme(monkeypatch):
    """Remplace les trois fonctions du service et enregistre les appels."""
    etat = {"runs": [], "report": {"processed": 3}, "dispatches": []}

    def _dispatch(settings, **options):
        etat["dispatches"].append(options)
        return "b7c1f2e4"

    monkeypatch.setattr(batch_runs, "dispatch_batch", _dispatch)
    monkeypatch.setattr(batch_runs, "list_runs", lambda s, **kw: etat["runs"])
    monkeypatch.setattr(batch_runs, "fetch_report", lambda s, rid, **kw: etat["report"])
    return etat


# ── Refus ────────────────────────────────────────────────────────────────────


def test_sans_session_le_lancement_est_refuse(client):
    assert client.post(URL, json={"mode": "rescrape"}).status_code == 401


def test_sans_le_pouvoir_le_lancement_est_refuse(client, ouvrir_session, plateforme):
    """`batch:read` ne suffit pas : relire un bilan ne touche à rien, lancer une
    reprise réécrit les résultats de centaines d'épreuves."""
    ouvrir_session(P.BATCH_READ)

    assert client.post(URL, json={"mode": "rescrape"}).status_code == 403


def test_sans_le_pouvoir_la_consultation_est_refusee(client, ouvrir_session):
    ouvrir_session(P.BATCH_RUN)

    assert client.get(URL).status_code == 403


def test_un_second_batch_est_refuse_pendant_qu_un_autre_tourne(
    client, ouvrir_session, plateforme
):
    """La garde immédiate, doublée par le verrou de concurrence du workflow —
    celui-ci voit aussi les lancements faits hors de l'interface."""
    ouvrir_session(P.BATCH_RUN)
    plateforme["runs"] = [_run(state="running", outcome=None)]

    reponse = client.post(URL, json={"mode": "rescrape"})

    assert reponse.status_code == 409
    assert not plateforme["dispatches"], "rien ne doit partir vers la plateforme"


def test_un_batch_en_attente_bloque_aussi(client, ouvrir_session, plateforme):
    ouvrir_session(P.BATCH_RUN)
    plateforme["runs"] = [_run(state="pending", outcome=None)]

    assert client.post(URL, json={"mode": "rescrape"}).status_code == 409


@pytest.mark.parametrize(
    "corps",
    [
        {"mode": "rescrape", "provider": "un-chronometreur-inconnu"},
        {"mode": "rescrape", "older_than": 0},
        {"mode": "rescrape", "older_than": 3651},
        {"mode": "rescrape", "limit": 0},
        {"mode": "rescrape", "limit": 501},
        {"mode": "un-mode-inconnu"},
    ],
)
def test_une_option_hors_catalogue_est_refusee(client, ouvrir_session, plateforme, corps):
    """Catalogue fermé (FR-003) : aucune chaîne de l'utilisateur ne devient un
    argument de ligne de commande."""
    ouvrir_session(P.BATCH_RUN)

    assert client.post(URL, json=corps).status_code == 422
    assert not plateforme["dispatches"]


def test_sans_jeton_le_lancement_se_dit_non_configure(
    client, ouvrir_session, plateforme, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setenv("GITHUB_BATCH_TOKEN", "")
    get_settings.cache_clear()
    ouvrir_session(P.BATCH_RUN)
    monkeypatch.setattr(
        batch_runs, "list_runs",
        lambda s, **kw: (_ for _ in ()).throw(batch_runs.BatchNotConfiguredError),
    )

    reponse = client.post(URL, json={"mode": "rescrape"})

    assert reponse.status_code == 503
    assert "configur" in reponse.json()["detail"].lower()


# ── Parcours nominal ─────────────────────────────────────────────────────────


def test_lancer_une_reprise_filtree(client, ouvrir_session, plateforme):
    ouvrir_session(P.BATCH_RUN)

    reponse = client.post(
        URL,
        json={"mode": "rescrape", "provider": "klikego", "older_than": 30,
              "limit": 50, "dry_run": True},
    )

    assert reponse.status_code == 202
    assert reponse.json() == {"correlation_id": "b7c1f2e4", "state": "pending"}
    assert plateforme["dispatches"] == [
        {"mode": "rescrape", "provider": "klikego", "older_than": 30,
         "limit": 50, "dry_run": True}
    ]


def test_la_base_visee_n_est_jamais_acceptee_du_client(
    client, ouvrir_session, plateforme
):
    """`target` dans le corps permettrait à l'administration de la preview
    d'écrire chez les adhérents.

    Refusé, et non ignoré : un 422 dit que la demande n'a pas été honorée, là où
    un silence laisserait croire qu'elle l'a été.
    """
    ouvrir_session(P.BATCH_RUN)

    reponse = client.post(URL, json={"mode": "rescrape", "target": "production"})

    assert reponse.status_code == 422
    assert not plateforme["dispatches"]


def test_lister_les_lancements(client, ouvrir_session, plateforme):
    ouvrir_session(P.BATCH_READ)
    plateforme["runs"] = [_run()]

    reponse = client.get(URL)

    assert reponse.status_code == 200
    ligne = reponse.json()[0]
    assert ligne["id"] == 1284
    assert ligne["state"] == "completed"
    assert ligne["outcome"] == "success"
    assert ligne["triggered_by"] == "ui"
    assert ligne["report_available"] is True


def test_une_plateforme_injoignable_ne_rend_pas_une_liste_vide(
    client, ouvrir_session, monkeypatch
):
    ouvrir_session(P.BATCH_READ)
    monkeypatch.setattr(
        batch_runs, "list_runs",
        lambda s, **kw: (_ for _ in ()).throw(batch_runs.BatchPlatformError),
    )

    assert client.get(URL).status_code == 503


def test_le_bilan_est_rendu_tel_quel(client, ouvrir_session, plateforme):
    """La charge `--json` de la CLI est déjà un contrat stable : l'API la
    transmet sans la remodeler."""
    ouvrir_session(P.BATCH_READ)
    plateforme["report"] = {"unique_supported": 117, "processed": 117, "errors": 3}

    reponse = client.get(f"{URL}/1284/report")

    assert reponse.status_code == 200
    assert reponse.json() == plateforme["report"]


def test_un_lancement_sans_bilan_rend_404(client, ouvrir_session, monkeypatch):
    ouvrir_session(P.BATCH_READ)
    monkeypatch.setattr(
        batch_runs, "fetch_report",
        lambda s, rid, **kw: (_ for _ in ()).throw(batch_runs.BatchReportNotFoundError),
    )

    assert client.get(f"{URL}/1284/report").status_code == 404


# ── Téléversement d'un fichier (US2) ─────────────────────────────────────────


COLONNES_URL = "/api/v1/admin/sheets/columns"
FROM_FILE_URL = f"{URL}/from-file"
LIEN = "https://www.klikego.com/resultats/une-course"
AUTRE = "https://www.breizhchrono.com/resultats/course"


def _csv(texte: str) -> bytes:
    return texte.encode("utf-8")


def _envoi(contenu: bytes, nom="epreuves.csv"):
    return {"file": (nom, contenu, "text/csv")}


def test_les_colonnes_sont_rendues_avec_leur_compte_de_liens(
    client, ouvrir_session
):
    ouvrir_session(P.BATCH_RUN)
    contenu = _csv(f"Nom,Lien\nCourse A,{LIEN}\nCourse B,{AUTRE}\n")

    reponse = client.post(COLONNES_URL, files=_envoi(contenu))

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["row_count"] == 2
    assert corps["suggested_index"] == 1
    lien = corps["columns"][1]
    assert lien["header"] == "Lien"
    assert lien["link_count"] == 2
    assert lien["samples"] == [LIEN, AUTRE]
    assert corps["columns"][0]["link_count"] == 0


def test_la_colonne_presuggeree_est_la_plus_fournie(client, ouvrir_session):
    ouvrir_session(P.BATCH_RUN)
    contenu = _csv(f"Note,Lien\n{LIEN},{LIEN}\n,{AUTRE}\n")

    corps = client.post(COLONNES_URL, files=_envoi(contenu)).json()

    assert corps["suggested_index"] == 1


def test_aucune_colonne_n_est_presuggeree_sans_lien(client, ouvrir_session):
    """Le cas d'un classeur dont les liens sont des hyperliens sans texte (D8) :
    l'écran doit le dire, pas présélectionner au hasard."""
    ouvrir_session(P.BATCH_RUN)

    corps = client.post(COLONNES_URL, files=_envoi(_csv("Nom,Date\nA,2026\n"))).json()

    assert corps["suggested_index"] is None


def test_la_lecture_des_colonnes_exige_le_pouvoir_de_lancer(
    client, ouvrir_session
):
    """`batch:run` et non `batch:read` : ce n'est pas une consultation, c'est
    la première moitié d'un lancement."""
    ouvrir_session(P.BATCH_READ)

    assert client.post(COLONNES_URL, files=_envoi(_csv("a\n"))).status_code == 403


def test_une_extension_inconnue_est_refusee(client, ouvrir_session):
    ouvrir_session(P.BATCH_RUN)

    reponse = client.post(COLONNES_URL, files=_envoi(_csv("x"), "epreuves.pdf"))

    assert reponse.status_code == 422
    assert ".csv" in reponse.json()["detail"]


def test_un_fichier_trop_volumineux_est_refuse(client, ouvrir_session):
    """Compté **à la lecture**, jamais d'après `Content-Length` : un en-tête
    déclaré par le client ne garde rien (D9)."""
    ouvrir_session(P.BATCH_RUN)
    enorme = _csv("Nom,Lien\n" + ("a" * 1024 + "\n") * 2100)

    assert client.post(COLONNES_URL, files=_envoi(enorme)).status_code == 413


def test_lancer_depuis_un_fichier_et_une_colonne(client, ouvrir_session, plateforme):
    ouvrir_session(P.BATCH_RUN)
    contenu = _csv(f"Nom,Lien\nA,{LIEN}\nB,{AUTRE}\n")

    reponse = client.post(
        FROM_FILE_URL, files=_envoi(contenu), data={"url_column": 1, "dry_run": "true"}
    )

    assert reponse.status_code == 202
    corps = reponse.json()
    assert corps["correlation_id"] == "b7c1f2e4"
    assert corps["epreuves"] == 2
    assert plateforme["dispatches"] == [
        {"mode": "urls", "urls": [LIEN, AUTRE], "dry_run": True}
    ]


def test_les_liens_non_supportes_sont_annonces_et_jamais_soumis(
    client, ouvrir_session, plateforme
):
    """Ni un succès ni un échec : ils ne partent pas. Les taire ferait chercher
    des épreuves manquantes dans le bilan."""
    ouvrir_session(P.BATCH_RUN)
    inconnu = "https://chrono-maison.example/r/42"
    contenu = _csv(f"Nom,Lien\nA,{LIEN}\nB,{inconnu}\n")

    corps = client.post(
        FROM_FILE_URL, files=_envoi(contenu), data={"url_column": 1}
    ).json()

    assert corps["epreuves"] == 1
    assert corps["ignored_by_host"] == {"chrono-maison.example": 1}
    assert plateforme["dispatches"][0]["urls"] == [LIEN]


def test_une_colonne_hors_bornes_est_refusee(client, ouvrir_session, plateforme):
    ouvrir_session(P.BATCH_RUN)
    contenu = _csv(f"Nom,Lien\nA,{LIEN}\n")

    reponse = client.post(
        FROM_FILE_URL, files=_envoi(contenu), data={"url_column": 7}
    )

    assert reponse.status_code == 422
    assert "colonne" in reponse.json()["detail"].lower()
    assert not plateforme["dispatches"]


def test_une_colonne_sans_lien_exploitable_est_refusee(
    client, ouvrir_session, plateforme
):
    ouvrir_session(P.BATCH_RUN)
    contenu = _csv("Nom,Lien\nA,à venir\n")

    reponse = client.post(
        FROM_FILE_URL, files=_envoi(contenu), data={"url_column": 0}
    )

    assert reponse.status_code == 422
    assert not plateforme["dispatches"]


def test_plus_de_cinq_cents_urls_sont_refusees_sans_troncature(
    client, ouvrir_session, plateforme
):
    """Refus explicite plutôt que troncature silencieuse : un lot tronqué se
    termine en vert, et les épreuves manquantes ne se voient nulle part."""
    ouvrir_session(P.BATCH_RUN)
    lignes = "\n".join(f"C{n},https://www.klikego.com/resultats/c{n}" for n in range(501))
    contenu = _csv(f"Nom,Lien\n{lignes}\n")

    reponse = client.post(
        FROM_FILE_URL, files=_envoi(contenu), data={"url_column": 1}
    )

    assert reponse.status_code == 422
    assert "500" in reponse.json()["detail"]
    assert not plateforme["dispatches"]


def test_le_fichier_televerse_n_est_jamais_ecrit_sur_disque(
    client, ouvrir_session, plateforme, monkeypatch
):
    """SC-005 / FR-011 — la seule preuve vérifiable : la plateforme n'offre pas
    de shell pour aller regarder. On surveille donc `open()` lui-même.

    Le tampon de `starlette` est un `SpooledTemporaryFile` et reste en mémoire
    sous son seuil ; ce qui est proscrit ici est une écriture **applicative**.
    """
    import os

    # `os.open` et non `builtins.open` : c'est le point de passage **commun**.
    # Une sonde posée sur `builtins.open` laisse filer `tempfile`, qui descend
    # directement à `os.open` — vérifié en injectant un `NamedTemporaryFile`
    # dans la route, que la première version de ce test n'a pas vu.
    ouvertures: list[tuple[str, int]] = []
    vrai_open = os.open

    def _open_surveille(chemin, flags, *args, **kwargs):
        ouvertures.append((str(chemin), flags))
        return vrai_open(chemin, flags, *args, **kwargs)

    ouvrir_session(P.BATCH_RUN)
    contenu = _csv(f"Nom,Lien\nA,{LIEN}\n")

    monkeypatch.setattr(os, "open", _open_surveille)
    client.post(FROM_FILE_URL, files=_envoi(contenu), data={"url_column": 1})
    monkeypatch.undo()

    ecritures = [
        chemin
        for chemin, flags in ouvertures
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
    ]
    assert not ecritures, f"le téléversement a écrit sur disque : {ecritures}"


def test_un_bilan_expire_rend_410(client, ouvrir_session, monkeypatch):
    """410 et non 404 : « plus jamais », et non « pas encore »."""
    ouvrir_session(P.BATCH_READ)
    monkeypatch.setattr(
        batch_runs, "fetch_report",
        lambda s, rid, **kw: (_ for _ in ()).throw(batch_runs.BatchReportExpiredError),
    )

    assert client.get(f"{URL}/1284/report").status_code == 410
