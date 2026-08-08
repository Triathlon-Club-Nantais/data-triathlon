"""Router du lancement et du suivi des batches (#47).

**Chaque route porte sa garde individuellement**, jamais le préfixe : `admin.py`
monte sous le même `/admin/` le signalement anonyme du site public, qu'une garde
de router supprimerait sans que rien ne la nomme.

Couche mince. Aucune de ces routes ne s'exécute longuement — la plus lente
télécharge un artefact de quelques kilo-octets — et aucune n'écrit en base : le
service web ne porte jamais le batch (FR-013).
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_permission
from app.core.config import get_settings
from app.core.permissions import P
from app.models.user import User
from app.schemas.batch_run import BatchLaunched, BatchRunRead, RescrapeLaunch
from app.services import batch_runs

router = APIRouter(tags=["admin"])


@router.post("/admin/batches", status_code=202, response_model=BatchLaunched)
def launch_batch(
    demande: RescrapeLaunch,
    _: User = Depends(require_permission(P.BATCH_RUN)),
):
    """Lance une reprise filtrée.

    **La base visée n'est pas dans le corps** : elle vient du réglage
    `GITHUB_BATCH_TARGET` de l'instance. `RescrapeLaunch` refuse d'ailleurs tout
    champ inconnu, donc un `target` glissé là ressort en 422 plutôt que d'être
    ignoré sans bruit.
    """
    settings = get_settings()
    batch_runs.ensure_idle(settings)
    correlation_id = batch_runs.dispatch_batch(
        settings,
        mode=demande.mode,
        provider=demande.provider,
        older_than=demande.older_than,
        limit=demande.limit,
        dry_run=demande.dry_run,
    )
    return BatchLaunched(correlation_id=correlation_id)


@router.get("/admin/batches", response_model=list[BatchRunRead])
def list_batches(
    limit: int = 20,
    _: User = Depends(require_permission(P.BATCH_READ)),
):
    """Les derniers lancements, le plus récent d'abord.

    Une plateforme injoignable ressort en 503, jamais en liste vide — qui se
    lirait « aucun lancement » alors que l'information est indisponible.
    """
    return batch_runs.list_runs(get_settings(), limit=min(limit, 50))


@router.get("/admin/batches/{run_id}/report")
def get_batch_report(
    run_id: int,
    _: User = Depends(require_permission(P.BATCH_READ)),
) -> dict:
    """Le bilan, **tel quel**.

    Pas de `response_model` : la charge `--json` de la CLI est déjà un contrat
    stable (Principe IV), et la remodeler ici créerait une seconde définition à
    tenir alignée.
    """
    return batch_runs.fetch_report(get_settings(), run_id)
