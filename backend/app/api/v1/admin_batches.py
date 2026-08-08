"""Router du lancement et du suivi des batches (#47).

**Chaque route porte sa garde individuellement**, jamais le préfixe : `admin.py`
monte sous le même `/admin/` le signalement anonyme du site public, qu'une garde
de router supprimerait sans que rien ne la nomme.

Couche mince. Aucune de ces routes ne s'exécute longuement — la plus lente
télécharge un artefact de quelques kilo-octets — et aucune n'écrit en base : le
service web ne porte jamais le batch (FR-013).
"""
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import require_permission
from app.core.config import get_settings
from app.core.exceptions import DomainError
from app.core.permissions import P
from app.models.user import User
from app.schemas.batch_run import (
    BatchLaunched,
    BatchRunRead,
    ColumnPreview,
    RescrapeLaunch,
    SheetColumns,
)
from app.services import batch_runs, sheet_source

router = APIRouter(tags=["admin"])

#: Deux méga-octets — largement au-dessus de tout export du club, largement en
#: dessous de ce qui met un process web à genoux.
TAILLE_MAX = 2 * 1024 * 1024
#: Bornes du lot, en épreuves après dédoublonnage. Au-delà, refus explicite : un
#: lot tronqué se termine en vert, et les épreuves manquantes ne se voient
#: nulle part.
URLS_MAX = 500
#: Trois valeurs suffisent à reconnaître une colonne ; tronquées, elles ne
#: rejouent pas le fichier dans la réponse.
ECHANTILLONS = 3
LONGUEUR_ECHANTILLON = 80


class FileTooLargeError(DomainError):
    status_code = 413
    message = "Fichier trop volumineux : la limite est de 2 Mo."


class ColumnOutOfRangeError(DomainError):
    status_code = 422
    message = "Colonne inconnue : ce fichier n'en compte pas autant."


class NoUsableLinkError(DomainError):
    status_code = 422
    message = (
        "Cette colonne ne porte aucun lien exploitable. Vérifiez qu'elle "
        "contient bien des adresses commençant par « http »."
    )


class TooManyUrlsError(DomainError):
    status_code = 422
    message = (
        f"Plus de {URLS_MAX} épreuves après dédoublonnage. Découpez le fichier : "
        "un lot tronqué se terminerait en vert sans dire ce qu'il a laissé."
    )


async def _lire_borne(fichier: UploadFile) -> bytes:
    """Lit le corps **par morceaux**, en comptant au fur et à mesure.

    Jamais d'après `Content-Length` (D9) : c'est un en-tête écrit par le client,
    et un client qui ment sur la taille est exactement celui dont on se garde.
    Le compte réel, lui, ne se falsifie pas.
    """
    morceaux: list[bytes] = []
    total = 0
    while morceau := await fichier.read(64 * 1024):
        total += len(morceau)
        if total > TAILLE_MAX:
            raise FileTooLargeError
        morceaux.append(morceau)
    return b"".join(morceaux)


# `exclude_none` : `epreuves` et `ignored_by_host` n'ont de sens qu'au
# lancement depuis un fichier. Les rendre à `null` sur une reprise filtrée
# ajouterait au contrat deux champs qui ne veulent rien dire là.
@router.post(
    "/admin/batches",
    status_code=202,
    response_model=BatchLaunched,
    response_model_exclude_none=True,
)
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


@router.post("/admin/sheets/columns", response_model=SheetColumns)
async def read_sheet_columns(
    file: UploadFile = File(...),
    _: User = Depends(require_permission(P.BATCH_RUN)),
):
    """Les colonnes d'un fichier téléversé, avec ce que chacune porte.

    `batch:run` et non `batch:read` : ce n'est pas une consultation, c'est la
    première moitié d'un lancement.

    **Le fichier n'est pas conservé.** Il est lu en mémoire et oublié ; le
    navigateur le garde pour le second appel (FR-011). C'est ce qui évite un
    stockage temporaire côté serveur, et la question de sa purge.
    """
    contenu = await _lire_borne(file)
    entetes, lignes = sheet_source.read_table(contenu, file.filename or "")

    colonnes = [
        ColumnPreview(
            index=index,
            header=entete,
            link_count=sheet_source.links_in_column(lignes, index).count,
            samples=[
                ligne[index][:LONGUEUR_ECHANTILLON]
                for ligne in lignes
                if index < len(ligne) and ligne[index]
            ][:ECHANTILLONS],
        )
        for index, entete in enumerate(entetes)
    ]
    # La plus fournie, et `None` si aucune n'en porte : présélectionner au
    # hasard ferait lancer sur la mauvaise colonne (D8).
    fournie = max(colonnes, key=lambda c: c.link_count, default=None)
    return SheetColumns(
        row_count=len(lignes),
        suggested_index=fournie.index if fournie and fournie.link_count else None,
        columns=colonnes,
    )


@router.post(
    "/admin/batches/from-file",
    status_code=202,
    response_model=BatchLaunched,
    response_model_exclude_none=True,
)
async def launch_batch_from_file(
    file: UploadFile = File(...),
    url_column: int = Form(...),
    dry_run: bool = Form(False),
    _: User = Depends(require_permission(P.BATCH_RUN)),
):
    """Lance depuis la colonne de liens désignée par l'utilisateur.

    Le refus est toujours **explicite** : colonne inconnue, colonne sans lien,
    lot trop grand. Aucune troncature silencieuse — un lot tronqué se termine en
    vert, et ce qu'il a laissé de côté ne se voit nulle part.
    """
    settings = get_settings()
    batch_runs.ensure_idle(settings)

    contenu = await _lire_borne(file)
    entetes, lignes = sheet_source.read_table(contenu, file.filename or "")
    if not 0 <= url_column < len(entetes):
        raise ColumnOutOfRangeError

    colonne = sheet_source.links_in_column(lignes, url_column)
    if not colonne.supported:
        raise NoUsableLinkError
    if len(colonne.supported) > URLS_MAX:
        raise TooManyUrlsError

    correlation_id = batch_runs.dispatch_batch(
        settings, mode="urls", urls=colonne.supported, dry_run=dry_run
    )
    return BatchLaunched(
        correlation_id=correlation_id,
        epreuves=len(colonne.supported),
        # Annoncés avant même le bilan : ils ne partiront jamais, et les taire
        # ferait chercher des épreuves manquantes dans le rapport.
        ignored_by_host=colonne.ignored_by_host,
    )


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
