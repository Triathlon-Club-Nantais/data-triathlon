"""Mot de passe partagé fermant l'accès public au site entier (#509).

Distinct du mot de passe bénévoles (#271) : secret propre, table propre,
cookie propre — même mécanisme (`services/shared_password`), même contrat
fail-closed. Contrairement à #271, ce cookie porte une expiration serveur
(`Settings.site_access_session_ttl_days`) : #509 la demande explicitement,
là où le cookie bénévoles est un cookie de session navigateur sans `max_age`.

Ne porte que ce qui est propre à cette feature : le nom du cookie, la
génération du secret et le remplacement du mot de passe. La signature HMAC et
le hachage scrypt s'appellent **directement** sur `shared_password` depuis les
routeurs et la garde — les délégations d'une ligne qui les renommaient ici ont
été supprimées en revue de #513, des deux côtés du jumelage.
"""
import secrets

from sqlalchemy.orm import Session

from app.models.site_access_config import SiteAccessConfig
from app.repositories import site_access_config_repository
from app.services import shared_password

SITE_SESSION_COOKIE = "tcn_site_session"

_GENERATED_PASSWORD_SIZE = 18


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)


def generate_password() -> str:
    """144 bits d'entropie (`secrets.token_urlsafe(18)`) — trop pour un
    humain à retenir, ce qui est le but d'une génération côté serveur."""
    return secrets.token_urlsafe(_GENERATED_PASSWORD_SIZE)


def replace_password(
    db: Session, *, password: str | None, admin_user_id: int
) -> tuple[SiteAccessConfig, str]:
    """Remplace le mot de passe — saisi ou généré. Rend `(config,
    mot_de_passe_en_clair)`. Hache le mot de passe, régénère
    `session_secret`, écrit les trois champs **ensemble** — jamais l'un sans
    les autres, sous peine de casser soit la vérification soit l'invalidation
    des sessions ouvertes.
    """
    mot_de_passe = password if password is not None else generate_password()
    password_hash, password_salt = shared_password.hash_password(mot_de_passe)
    config = site_access_config_repository.save_config(
        db,
        password_hash=password_hash,
        password_salt=password_salt,
        session_secret=new_session_secret(),
        updated_by_user_id=admin_user_id,
    )
    return config, mot_de_passe
