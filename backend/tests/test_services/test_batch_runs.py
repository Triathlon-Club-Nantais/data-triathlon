"""Dialogue avec la plateforme d'exécution des batches (#47).

Aucun réseau : le transport est un `httpx.MockTransport`, injecté par la même
couture que le transport gardé de production (`core/http.client()` enveloppe le
`transport=` reçu au lieu de le remplacer, cf. sa docstring).

Ce que ces tests tiennent avant tout, c'est **`target`**. La base visée ne vient
jamais du client : elle vient du réglage `GITHUB_BATCH_TARGET` de l'instance.
L'accepter d'ailleurs laisserait l'administration de la preview écrire chez les
adhérents.
"""
import io
import json
import zipfile

import httpx
import pytest

from app.core.config import Settings
from app.services import batch_runs

API_VERSION = "2022-11-28"


def _settings(**surcharges) -> Settings:
    """Réglages d'une instance configurée pour lancer des batches."""
    valeurs = {
        "github_batch_token": "gh-jeton-de-test",
        "github_repository": "Un-Club/un-depot",
        "github_workflow_file": "batch.yml",
        "github_batch_target": "production",
    }
    valeurs.update(surcharges)
    return Settings(**valeurs)


def _capture():
    """(handler 204, liste des requêtes vues)."""
    vues: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        vues.append(request)
        return httpx.Response(204)

    return handler, vues


def _dispatch(handler, settings=None, **options) -> str:
    return batch_runs.dispatch_batch(
        settings or _settings(),
        transport=httpx.MockTransport(handler),
        **({"mode": "rescrape"} | options),
    )


def test_l_url_de_dispatch_est_construite_depuis_les_reglages():
    handler, vues = _capture()

    _dispatch(handler)

    assert str(vues[0].url) == (
        "https://api.github.com/repos/Un-Club/un-depot"
        "/actions/workflows/batch.yml/dispatches"
    )
    assert vues[0].method == "POST"


def test_les_en_tetes_portent_le_jeton_et_la_version_d_api():
    """`X-GitHub-Api-Version` n'est pas décoratif : sans elle, la plateforme
    sert la version courante, qui peut changer sous nos pieds."""
    handler, vues = _capture()

    _dispatch(handler)

    entetes = vues[0].headers
    assert entetes["authorization"] == "Bearer gh-jeton-de-test"
    assert entetes["accept"] == "application/vnd.github+json"
    assert entetes["x-github-api-version"] == API_VERSION


def test_le_corps_porte_la_branche_par_defaut_et_les_huit_entrees():
    """Le contrat du workflow énumère huit entrées. Toutes sont envoyées, même
    vides : une entrée absente prendrait le défaut du workflow, qui n'est pas
    toujours la valeur neutre — `target` vaut `preview` par défaut."""
    handler, vues = _capture()

    _dispatch(handler)

    corps = json.loads(vues[0].content)
    assert corps["ref"] == "main"
    assert set(corps["inputs"]) == {
        "target", "mode", "provider", "older_than",
        "limit", "urls", "dry_run", "correlation_id",
    }


def test_la_cible_vient_du_reglage_de_l_instance():
    handler, vues = _capture()

    _dispatch(handler, settings=_settings(github_batch_target="preview"))

    assert json.loads(vues[0].content)["inputs"]["target"] == "preview"


def test_la_cible_ne_peut_pas_etre_imposee_par_l_appelant():
    """La garde de FR-013 : l'administration de la preview ne doit pas pouvoir
    écrire en production. `dispatch_batch` n'expose aucun paramètre `target`,
    et en recevoir un est une erreur de programmation, pas une option."""
    handler, _ = _capture()

    with pytest.raises(TypeError):
        _dispatch(handler, target="production")


def test_les_options_sont_transmises_en_chaines():
    """L'API de dispatch refuse un entier ou un booléen dans `inputs` : toute
    valeur y voyage en chaîne, et c'est le workflow qui la retypera."""
    handler, vues = _capture()

    _dispatch(handler, provider="klikego", older_than=30, limit=50, dry_run=True)

    entrees = json.loads(vues[0].content)["inputs"]
    assert entrees["provider"] == "klikego"
    assert entrees["older_than"] == "30"
    assert entrees["limit"] == "50"
    assert entrees["dry_run"] == "true"
    assert all(isinstance(v, str) for v in entrees.values())


def test_une_option_absente_part_vide_et_non_none():
    handler, vues = _capture()

    _dispatch(handler)

    entrees = json.loads(vues[0].content)["inputs"]
    assert entrees["provider"] == ""
    assert entrees["older_than"] == ""
    assert entrees["limit"] == ""
    assert entrees["urls"] == ""
    assert entrees["dry_run"] == "false"


def test_les_urls_partent_une_par_ligne():
    """Le workflow les repasse à `--urls-from -` : une par ligne est le format
    que la CLI lit sur stdin."""
    handler, vues = _capture()

    _dispatch(handler, mode="urls", urls=["https://a.test/r", "https://b.test/r"])

    assert json.loads(vues[0].content)["inputs"]["urls"] == (
        "https://a.test/r\nhttps://b.test/r"
    )


def test_le_correlation_id_est_rendu_et_envoye():
    """Le dispatch ne rend **aucun** identifiant d'exécution : ce jeton est le
    seul lien entre la demande et l'exécution qu'elle a créée."""
    handler, vues = _capture()

    correlation_id = _dispatch(handler)

    assert len(correlation_id) == 8
    assert int(correlation_id, 16) >= 0  # huit caractères hexadécimaux
    assert json.loads(vues[0].content)["inputs"]["correlation_id"] == correlation_id


def test_deux_lancements_ne_partagent_pas_leur_correlation_id():
    handler, _ = _capture()

    assert _dispatch(handler) != _dispatch(handler)


# ── Liste des exécutions ─────────────────────────────────────────────────────


def _run(**surcharges) -> dict:
    """Une exécution, à la forme rendue par la plateforme (mesurée sur l'API)."""
    return {
        "id": 31270838117,
        "name": "batch · production · rescrape · b7c1f2e4",
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "run_started_at": "2026-08-08T18:00:23Z",
        "updated_at": "2026-08-08T18:04:23Z",
        "html_url": "https://github.com/Un-Club/un-depot/actions/runs/31270838117",
    } | surcharges


def _handler_liste(runs, artefacts=None, vues=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if vues is not None:
            vues.append(request)
        if "/artifacts" in request.url.path:
            return httpx.Response(200, json={"artifacts": artefacts or []})
        return httpx.Response(200, json={"workflow_runs": runs})

    return handler


def _list_runs(runs, artefacts=None, vues=None, settings_=None, **kwargs):
    return batch_runs.list_runs(
        settings_ or _settings(),
        transport=httpx.MockTransport(_handler_liste(runs, artefacts, vues)),
        **kwargs,
    )


@pytest.mark.parametrize(
    "statut, attendu",
    [
        ("completed", "completed"),
        ("in_progress", "running"),
        ("queued", "pending"),
        ("waiting", "pending"),
        ("requested", "pending"),
        # Un statut que la plateforme ajouterait demain ne doit pas faire tomber
        # l'écran : tout ce qui n'est ni terminé ni en cours est en attente.
        ("un_statut_inconnu", "pending"),
    ],
)
def test_le_statut_amont_devient_un_etat(statut, attendu):
    assert _list_runs([_run(status=statut, conclusion=None)])[0].state == attendu


@pytest.mark.parametrize(
    "conclusion, attendu",
    [
        ("success", "success"),
        ("cancelled", "cancelled"),
        ("failure", "failure"),
        # Trois conclusions distinctes en amont, un seul sens ici : ça n'a pas
        # abouti. Le pourquoi est dans le bilan, pas dans cette énumération.
        ("timed_out", "failure"),
        ("startup_failure", "failure"),
        ("action_required", "failure"),
    ],
)
def test_la_conclusion_amont_devient_un_resultat(conclusion, attendu):
    runs = _list_runs([_run(conclusion=conclusion)])
    assert runs[0].outcome == attendu


def test_une_execution_non_terminee_n_a_pas_de_resultat():
    runs = _list_runs([_run(status="in_progress", conclusion=None)])
    assert runs[0].outcome is None
    assert runs[0].duration_s is None


@pytest.mark.parametrize(
    "evenement, nom, attendu",
    [
        ("schedule", "batch · production · rescrape · ", "schedule"),
        ("workflow_dispatch", "batch · production · rescrape · b7c1f2e4", "ui"),
        # Un lancement depuis l'onglet Actions ne porte aucun identifiant de
        # corrélation : c'est le seul discriminant dont on dispose, la
        # plateforme ne dit pas *qui* a cliqué.
        ("workflow_dispatch", "batch · production · rescrape · ", "manual"),
    ],
)
def test_l_origine_du_lancement_est_deduite(evenement, nom, attendu):
    runs = _list_runs([_run(event=evenement, name=nom)])
    assert runs[0].triggered_by == attendu


def test_la_duree_est_comptee_entre_debut_et_derniere_mise_a_jour():
    assert _list_runs([_run()])[0].duration_s == 4 * 60


def test_le_bilan_est_annonce_disponible_quand_l_artefact_existe():
    """Ce drapeau ne se déduit **pas** de « terminé en succès » : une exécution
    rouge sans bilan est précisément le signal d'une panne d'infrastructure
    (D6), et le confondre avec un échec de scraping effacerait ce signal."""
    artefact = {"name": "bilan-b7c1f2e4", "expired": False,
                "workflow_run": {"id": 31270838117}}

    assert _list_runs([_run()], artefacts=[artefact])[0].report_available is True
    assert _list_runs([_run()], artefacts=[])[0].report_available is False


def test_un_artefact_expire_ne_compte_pas_comme_disponible():
    artefact = {"name": "bilan-b7c1f2e4", "expired": True,
                "workflow_run": {"id": 31270838117}}

    assert _list_runs([_run()], artefacts=[artefact])[0].report_available is False


def test_les_executions_sortent_de_la_plus_recente_a_la_plus_ancienne():
    """Le tri est refait ici : l'ordre de la plateforme n'est pas contractuel."""
    vieux = _run(id=1, run_started_at="2026-08-01T10:00:00Z")
    recent = _run(id=2, run_started_at="2026-08-08T10:00:00Z")

    assert [r.id for r in _list_runs([vieux, recent])] == [2, 1]


def test_la_borne_est_transmise_a_la_plateforme():
    vues: list[httpx.Request] = []

    _list_runs([_run()], vues=vues, limit=5)

    demande = next(v for v in vues if "/runs" in v.url.path)
    assert demande.url.params["per_page"] == "5"


def test_une_plateforme_injoignable_ne_rend_pas_une_liste_vide():
    """Une liste vide se lirait « aucun lancement ». L'information est
    seulement indisponible — et c'est autre chose."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("injoignable")

    with pytest.raises(batch_runs.BatchPlatformError):
        batch_runs.list_runs(_settings(), transport=httpx.MockTransport(handler))


# ── Bilan d'une exécution ────────────────────────────────────────────────────


BILAN = {"unique_supported": 117, "processed": 117, "errors": 3, "failures": []}


def _zip_du_bilan(charge=None, nom="bilan.json") -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr(nom, json.dumps(charge if charge is not None else BILAN))
    return tampon.getvalue()


def _handler_bilan(artefacts, zip_octets=None, statut_zip=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/zip"):
            if statut_zip != 200:
                return httpx.Response(statut_zip, json={"message": "expiré"})
            return httpx.Response(200, content=zip_octets)
        return httpx.Response(200, json={"artifacts": artefacts})

    return handler


def _artefact(**surcharges) -> dict:
    return {"id": 99, "name": "bilan-b7c1f2e4", "expired": False} | surcharges


def _fetch(handler, run_id=31270838117):
    return batch_runs.fetch_report(
        _settings(), run_id, transport=httpx.MockTransport(handler)
    )


def test_le_bilan_est_rendu_tel_quel():
    """La charge `--json` de la CLI est déjà un contrat stable (Principe IV) :
    la remodeler créerait une seconde définition à tenir alignée."""
    handler = _handler_bilan([_artefact()], _zip_du_bilan())

    assert _fetch(handler) == BILAN


def test_le_bilan_est_lu_en_memoire_quel_que_soit_le_nom_de_l_entree():
    handler = _handler_bilan([_artefact()], _zip_du_bilan(nom="backend/bilan.json"))

    assert _fetch(handler) == BILAN


def test_l_artefact_de_rapport_n_est_pas_confondu_avec_le_bilan():
    """Depuis que le rapport texte a son propre artefact, deux artefacts
    cohabitent sur une exécution. Seul le bilan est du JSON."""
    handler = _handler_bilan(
        [{"id": 12, "name": "rapport-b7c1f2e4", "expired": False}, _artefact()],
        _zip_du_bilan(),
    )

    assert _fetch(handler) == BILAN


def test_une_execution_sans_bilan_le_dit():
    with pytest.raises(batch_runs.BatchReportNotFoundError):
        _fetch(_handler_bilan([]))


def test_un_bilan_expire_se_distingue_d_un_bilan_absent():
    """404 et 410 ne disent pas la même chose à l'utilisateur : « pas encore »
    contre « plus jamais ». Les confondre lui ferait attendre pour rien."""
    with pytest.raises(batch_runs.BatchReportExpiredError):
        _fetch(_handler_bilan([_artefact(expired=True)]))

    with pytest.raises(batch_runs.BatchReportExpiredError):
        _fetch(_handler_bilan([_artefact()], statut_zip=410))


# ── Configuration et jeton ───────────────────────────────────────────────────


def test_sans_jeton_le_lancement_est_annonce_non_configure():
    """Un jeton absent est un état légitime — même politique que les réglages
    `AUTH_*` : le site public reste intact, le lancement se dit indisponible."""
    handler, vues = _capture()

    with pytest.raises(batch_runs.BatchNotConfiguredError):
        _dispatch(handler, settings=_settings(github_batch_token=""))

    assert not vues, "aucune requête ne doit partir sans jeton"


def test_sans_jeton_la_consultation_aussi():
    with pytest.raises(batch_runs.BatchNotConfiguredError):
        _list_runs([_run()], settings_=_settings(github_batch_token=""))


def test_un_jeton_refuse_par_la_plateforme_est_nomme():
    """Un jeton *fine-grained* expire — un an au plus. L'erreur doit le dire :
    c'est ce qui rend le diagnostic possible sans accès aux journaux."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    with pytest.raises(batch_runs.BatchTokenRejectedError):
        _dispatch(handler)


def test_les_deux_messages_de_jeton_sont_distincts():
    assert (
        batch_runs.BatchNotConfiguredError.message
        != batch_runs.BatchTokenRejectedError.message
    )


def test_un_refus_amont_quelconque_ne_passe_pas_pour_un_succes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"})

    with pytest.raises(batch_runs.BatchPlatformError):
        _dispatch(handler)
