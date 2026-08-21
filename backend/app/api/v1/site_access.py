"""Session du mot de passe partagé du site (#509).

Couche mince : `require_site_access` (`api/deps.py`) garde la vérification,
elle-même **auto-appliquée** ici sur `GET /site-access/session` — c'est le
point que le frontend interroge pour savoir s'il doit rediriger vers
`/acces`. `POST`/`DELETE` restent non gardées : la première pose le cookie,
la seconde n'a aucun effet de bord sensible.

**`POST` porte `site_access_rate_limit`** (revue finale, § Plafond de débit
du design) : depuis #509, cette route est la seule porte publique non
authentifiée du site — à la différence de `POST /benevoles/session`, qui ne
sert qu'une poignée de bénévoles — et elle déclenche `hashlib.scrypt`
(~16 Mo, 50-100 ms CPU) à chaque tentative, un levier de déni de service et de
force brute sans ce plafond. **Son propre seau**, plus large, depuis la revue
de #513 : partagé avec `POST /admin/pending-providers` et
`POST /participations`, le plafond couplait la porte d'entrée du site à la
saisie manuelle de résultats — un membre qui saisissait sa saison ne pouvait
plus ouvrir de session (`api/deps.SITE_ACCESS_RATE_LIMIT_MAX_PER_WINDOW`).
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import NotAuthenticatedError, require_site_access, site_access_rate_limit
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories import site_access_config_repository
from app.schemas.site_access import SiteAccessLogin
from app.services import shared_password, site_access

router = APIRouter(tags=["site-access"])


@router.post("/site-access/session", status_code=204, dependencies=[Depends(site_access_rate_limit)])
def open_session(
    body: SiteAccessLogin,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    config = site_access_config_repository.get_config(db)
    if config is None or not shared_password.verify_password(
        body.password, password_hash=config.password_hash, password_salt=config.password_salt
    ):
        raise NotAuthenticatedError("Mot de passe incorrect.")

    response.set_cookie(
        key=site_access.SITE_SESSION_COOKIE,
        value=shared_password.sign_cookie(config.session_secret),
        max_age=settings.site_access_session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.delete("/site-access/session", status_code=204)
def close_session(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(
        key=site_access.SITE_SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/site-access/session", dependencies=[Depends(require_site_access)])
def check_session():
    """Le frontend l'appelle via `serverFetchAuthed` : 200 si la session est
    valide, 401 sinon (levé par `require_site_access` avant d'atteindre ce corps)."""
    return {"ok": True}
