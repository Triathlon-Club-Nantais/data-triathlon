"""Accès partagé à la page de vérification des résultats bénévoles (#271).

Aucune nouvelle table : un cookie de session signé par HMAC-SHA256 **avec le
mot de passe partagé lui-même comme clé** (research.md §D1). La vérification
recalcule ce HMAC avec le mot de passe courant — changer le mot de passe
invalide donc tous les cookies existants, seul mécanisme de révocation
retenu (collective, pas individuelle : il n'y a pas d'identité à révoquer).
"""
import hashlib
import hmac
import time

from sqlalchemy.orm import Session

from app.repositories import user_repository

#: Nom du cookie de session bénévoles — distinct du cookie SSO (`tcn_session`,
#: `api/v1/auth.py`), sur un mécanisme entièrement séparé.
BENEVOLE_SESSION_COOKIE = "tcn_benevole_session"

#: Adresse synthétique du compte système « Bénévoles (accès partagé) »
#: (data-model.md §Addition) : n'appartient à personne, ne se connecte jamais
#: par OAuth. Sert uniquement de cible à `AdminActionLog.user_id` pour les
#: gestes déclenchés depuis cette page.
SYSTEM_USER_EMAIL = "benevoles@systeme.interne"


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


def sign_session(password: str) -> str:
    """Fabrique la valeur du cookie : `{horodatage}.{HMAC(password, horodatage)}`."""
    horodatage = str(int(time.time()))
    signature = _hmac(password, horodatage)
    return f"{horodatage}.{signature}"


def verify_session(value: str | None, password: str) -> bool:
    """Vrai si `value` a bien été signée par `password`.

    Fail-closed : mot de passe vide (non configuré), valeur absente, ou
    valeur mal formée rendent tous `False`, jamais une exception.
    """
    if not value or not password:
        return False
    horodatage, separateur, signature = value.partition(".")
    if not separateur or not horodatage or not signature:
        return False
    attendue = _hmac(password, horodatage)
    return hmac.compare_digest(signature, attendue)


def _hmac(password: str, message: str) -> str:
    return hmac.new(password.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
