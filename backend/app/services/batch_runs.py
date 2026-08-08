"""Lancement des batches sur la plateforme d'exécution (#47).

Les batches ne tournent pas dans ce service : l'offre gratuite ne porte qu'un
process, et il sert le site public. Ce module ne fait que *demander* leur
exécution à GitHub Actions, qui lance la CLI sur un runner.

Aucune fonction d'ici ne s'exécute longuement, aucune n'écrit en base.
"""
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import httpx

from app.core import http
from app.core.config import Settings
from app.core.exceptions import DomainError

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"

# La branche par défaut : un `workflow_dispatch` n'est déclenchable que là.
REF = "main"


def dispatch_batch(
    settings: Settings,
    *,
    mode: str,
    provider: str | None = None,
    older_than: int | None = None,
    limit: int | None = None,
    urls: list[str] | None = None,
    dry_run: bool = False,
    transport=None,
) -> str:
    """Demande une exécution et rend son `correlation_id`.

    **Pas de paramètre `target`.** La base visée vient du réglage
    `GITHUB_BATCH_TARGET` de l'instance : l'administration de la preview parle à
    la base de preview, celle de la production à la sienne. L'accepter d'un
    appelant rouvrirait exactement le chemin qu'on ferme.

    Le dispatch ne rend aucun identifiant d'exécution — la plateforme répond
    `204` sans corps. Le `correlation_id` produit ici est donc le seul lien
    entre la demande et l'exécution qu'elle crée ; il voyage dans le `run-name`.
    """
    _garde_configuration(settings)
    correlation_id = uuid4().hex[:8]
    corps = {
        "ref": REF,
        # Les huit entrées du contrat, toujours toutes présentes : une entrée
        # omise prend le défaut du workflow, qui n'est pas la valeur neutre
        # (`target` y vaut `preview`). Et l'API les veut en chaînes.
        "inputs": {
            "target": settings.github_batch_target,
            "mode": mode,
            "provider": provider or "",
            "older_than": "" if older_than is None else str(older_than),
            "limit": "" if limit is None else str(limit),
            "urls": "\n".join(urls or []),
            "dry_run": "true" if dry_run else "false",
            "correlation_id": correlation_id,
        },
    }

    url = (
        f"{API_ROOT}/repos/{settings.github_repository}"
        f"/actions/workflows/{settings.github_workflow_file}/dispatches"
    )
    with http.client(transport=transport) as client:
        _verifier(
            _appel(lambda: client.post(url, json=corps, headers=_headers(settings)))
        )

    return correlation_id


@dataclass(frozen=True)
class BatchRun:
    """Un lancement, vu de l'interface.

    Les valeurs d'énumération sont **en anglais** : une valeur sérialisée dans
    un contrat d'API est de la couche technique invisible (Principe I). « En
    cours » et « Échec » sont produits par les composants du front, jamais ici.
    """

    id: int
    label: str
    state: str
    outcome: str | None
    started_at: datetime
    duration_s: int | None
    triggered_by: str
    report_available: bool
    external_url: str


def list_runs(settings: Settings, *, limit: int = 20, transport=None) -> list[BatchRun]:
    """Les derniers lancements, du plus récent au plus ancien."""
    _garde_configuration(settings)
    with http.client(transport=transport) as client:
        runs = _get(
            client, settings,
            f"{API_ROOT}/repos/{settings.github_repository}"
            f"/actions/workflows/{settings.github_workflow_file}/runs",
            params={"per_page": limit},
        )["workflow_runs"]
        # **Un** appel pour toutes les exécutions, et non un par exécution :
        # l'artefact porte l'identifiant de l'exécution qui l'a produit.
        artefacts = _get(
            client, settings,
            f"{API_ROOT}/repos/{settings.github_repository}/actions/artifacts",
            params={"per_page": 100},
        )["artifacts"]

    avec_bilan = {
        a["workflow_run"]["id"]
        for a in artefacts
        if a["name"].startswith("bilan-") and not a["expired"]
    }
    # Le tri est refait ici : l'ordre de la plateforme n'est pas contractuel.
    return sorted(
        (_to_batch_run(run, avec_bilan) for run in runs),
        key=lambda r: r.started_at,
        reverse=True,
    )


def _to_batch_run(run: dict, avec_bilan: set[int]) -> BatchRun:
    debut = _horodatage(run["run_started_at"])
    termine = run["status"] == "completed"
    nom = run["name"].strip(" ·")
    return BatchRun(
        id=run["id"],
        # Le `correlation_id` reste dans le libellé : c'est par lui que
        # l'interface retrouve le lancement qu'elle vient de demander.
        label=nom,
        state=_STATES.get(run["status"], "pending"),
        outcome=_OUTCOMES.get(run["conclusion"], "failure") if termine else None,
        started_at=debut,
        duration_s=(
            int((_horodatage(run["updated_at"]) - debut).total_seconds())
            if termine else None
        ),
        # Sur le nom **brut** : c'est le `·` final resté sans rien derrière qui
        # dit « lancement manuel », et `nom` vient justement de l'avoir perdu.
        triggered_by=_origine(run),
        report_available=run["id"] in avec_bilan,
        external_url=run["html_url"],
    )


# Tout ce qui n'est ni terminé ni en cours est en attente : un statut ajouté
# demain en amont ne doit pas faire tomber l'écran.
_STATES = {"completed": "completed", "in_progress": "running"}
# `timed_out`, `startup_failure`, `action_required` disent trois causes et un
# seul sens : ça n'a pas abouti. Le pourquoi est dans le bilan.
_OUTCOMES = {"success": "success", "cancelled": "cancelled"}


def _origine(run: dict) -> str:
    """`ui`, `schedule` ou `manual`.

    Un lancement venu de l'interface porte un `correlation_id` ; un lancement
    fait à la main depuis l'onglet Actions n'en porte pas. C'est le seul
    discriminant disponible — la plateforme ne dit pas *qui* a cliqué.
    """
    if run["event"] == "schedule":
        return "schedule"
    return "ui" if run["name"].rsplit("·", 1)[-1].strip() else "manual"


def _horodatage(valeur: str) -> datetime:
    return datetime.fromisoformat(valeur)


def fetch_report(settings: Settings, run_id: int, *, transport=None) -> dict:
    """Le bilan d'une exécution — la charge `--json` de la CLI, **telle quelle**.

    Elle est déjà un contrat stable (Principe IV) : la remodeler créerait une
    seconde définition à tenir alignée.
    """
    _garde_configuration(settings)
    with http.client(transport=transport) as client:
        artefacts = _get(
            client, settings,
            f"{API_ROOT}/repos/{settings.github_repository}"
            f"/actions/runs/{run_id}/artifacts",
            params={"per_page": 100},
        )["artifacts"]
        # Deux artefacts cohabitent depuis que le rapport texte a le sien ; seul
        # celui du bilan est du JSON.
        bilans = [a for a in artefacts if a["name"].startswith("bilan-")]
        if not bilans:
            raise BatchReportNotFoundError
        if bilans[0]["expired"]:
            raise BatchReportExpiredError

        reponse = _appel(
            lambda: client.get(
                f"{API_ROOT}/repos/{settings.github_repository}"
                f"/actions/artifacts/{bilans[0]['id']}/zip",
                headers=_headers(settings),
            )
        )
        if reponse.status_code == 410:
            raise BatchReportExpiredError
        _verifier(reponse)
        octets = reponse.content

    # Aucune écriture disque : le zip ne pèse que quelques kilo-octets.
    with zipfile.ZipFile(io.BytesIO(octets)) as archive:
        return json.loads(archive.read(archive.namelist()[0]))


def _get(client, settings: Settings, url: str, *, params: dict) -> dict:
    reponse = _appel(lambda: client.get(url, params=params, headers=_headers(settings)))
    _verifier(reponse)
    return reponse.json()


def _appel(action):
    """Traduit une plateforme injoignable en erreur nommée.

    Jamais une liste vide en repli : elle se lirait « aucun lancement » alors
    que l'information est seulement indisponible.
    """
    try:
        return action()
    except httpx.HTTPError as erreur:
        raise BatchPlatformError(
            f"La plateforme d'exécution est injoignable ({erreur.__class__.__name__})."
        ) from erreur


def _verifier(reponse) -> None:
    """Sépare le jeton refusé du reste — c'est ce qui rend le diagnostic
    possible sans accès aux journaux de la plateforme."""
    if reponse.status_code in (401, 403):
        raise BatchTokenRejectedError
    if reponse.status_code >= 400:
        raise BatchPlatformError(
            f"La plateforme d'exécution a refusé la demande (HTTP {reponse.status_code})."
        )


def _garde_configuration(settings: Settings) -> None:
    if not settings.github_batch_token:
        raise BatchNotConfiguredError


class BatchPlatformError(DomainError):
    """503 et non 500 : rien n'est cassé ici, c'est l'amont qui ne répond pas."""

    status_code = 503
    message = "La plateforme d'exécution des batches est injoignable."


class BatchNotConfiguredError(DomainError):
    """503, comme `AuthUnavailableError` : une absence de configuration n'est
    pas une panne. Une installation sans jeton est un état légitime."""

    status_code = 503
    message = "Le lancement de batches n'est pas configuré sur ce site."


class BatchTokenRejectedError(DomainError):
    status_code = 503
    message = (
        "Le jeton d'accès à la plateforme d'exécution a été refusé : "
        "il est expiré ou révoqué."
    )


class BatchReportNotFoundError(DomainError):
    status_code = 404
    message = (
        "Ce lancement n'a pas de bilan : il n'est pas terminé, ou il a échoué "
        "avant que la commande ne s'exécute."
    )


class BatchReportExpiredError(DomainError):
    """410 et non 404 : « plus jamais », et non « pas encore ». Les confondre
    ferait attendre l'utilisateur pour rien."""

    status_code = 410
    message = "Le bilan de ce lancement a expiré ; l'exécution reste consultable."


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.github_batch_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
