"""Accès partagé à la page de vérification des résultats bénévoles (#271).

Le mot de passe partagé est géré depuis le back-office et stocké **haché et
salé** (`hashlib.scrypt`, stdlib — research.md §D1 de
`specs/20260815-173645-admin-mdp-benevoles/`), jamais en clair. Le cookie de
session reste un HMAC signé sans état serveur, mais la clé n'est plus le mot
de passe lui-même : c'est `session_secret`, un secret distinct stocké aux
côtés du hachage et **régénéré à chaque remplacement** (research.md §D2) —
ce qui préserve la révocation collective des sessions ouvertes sans jamais
avoir besoin de relire le mot de passe en clair.

Ne porte que ce qui est propre à cette feature : le nom du cookie, le compte
système, la génération du secret et le remplacement du mot de passe. La
signature HMAC et le hachage scrypt s'appellent **directement** sur
`shared_password` depuis les routeurs et la garde — les délégations d'une ligne
qui les renommaient ici ont été supprimées en revue de #513, en même temps que
leurs jumelles de `site_access.py`.
"""
import secrets

from sqlalchemy.orm import Session

from app.models.benevole_access_config import BenevoleAccessConfig
from app.repositories import benevole_config_repository, user_repository
from app.services import shared_password

#: Nom du cookie de session bénévoles — distinct du cookie SSO (`tcn_session`,
#: `api/v1/auth.py`), sur un mécanisme entièrement séparé.
BENEVOLE_SESSION_COOKIE = "tcn_benevole_session"

#: Adresse synthétique du compte système « Bénévoles (accès partagé) »
#: (data-model.md §Addition) : n'appartient à personne, ne se connecte jamais
#: par OAuth. Sert uniquement de cible à `AdminActionLog.user_id` pour les
#: gestes déclenchés depuis cette page.
SYSTEM_USER_EMAIL = "benevoles@systeme.interne"

#: Taille du mot de passe généré (research.md §D5), en octets.
_GENERATED_PASSWORD_SIZE = 18


def system_user_id(db: Session) -> int:
    """L'id du compte système bénévoles, semé une fois par migration Alembic.

    Une seule requête nommée ici plutôt que dupliquée dans chaque route :
    l'id qu'attribue l'autoincrément diffère d'un environnement à l'autre
    (dev, preview, production n'ont pas la même table `users`), donc il ne
    peut pas être figé en constante Python — seule l'adresse ci-dessus,
    choisie par cette feature, est stable d'un environnement à l'autre.
    """
    comptes = user_repository.find_by_email(db, SYSTEM_USER_EMAIL)
    if not comptes:
        raise RuntimeError(
            f"Compte système bénévoles introuvable ({SYSTEM_USER_EMAIL}) — "
            "la migration de seed a-t-elle été appliquée ?"
        )
    return comptes[0].id


def new_session_secret() -> str:
    """Un secret de session neuf — jamais le même deux fois (research.md §D2)."""
    return secrets.token_urlsafe(32)


def generate_password() -> str:
    """Un mot de passe robuste, généré côté serveur (research.md §D5).

    144 bits d'entropie uniforme (`secrets.token_urlsafe(18)` → 24
    caractères) — trop pour un humain à retenir, ce qui est le but (Story 2
    vise un secret robuste, pas mémorisable).
    """
    return secrets.token_urlsafe(_GENERATED_PASSWORD_SIZE)


def replace_password(
    db: Session, *, password: str | None, admin_user_id: int
) -> tuple[BenevoleAccessConfig, str]:
    """Remplace le mot de passe bénévoles — saisi (`password` fourni) ou
    généré (`password` absent, Story 2). Rend `(config, mot_de_passe_en_clair)`.

    Orchestration de service, jamais un appel direct au repository depuis un
    routeur (AGENTS.md, « routers fins : délégation au service ») : hache le
    mot de passe, régénère `session_secret`, et écrit les trois champs
    **dans le même appel** à `save_config` — jamais l'un sans les autres
    (data-model.md, invariant d'atomicité, FR-006).
    """
    mot_de_passe = password if password is not None else generate_password()
    password_hash, password_salt = shared_password.hash_password(mot_de_passe)
    config = benevole_config_repository.save_config(
        db,
        password_hash=password_hash,
        password_salt=password_salt,
        session_secret=new_session_secret(),
        updated_by_user_id=admin_user_id,
    )
    return config, mot_de_passe
