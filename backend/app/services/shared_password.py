"""HMAC de cookie et hachage de mot de passe — socle partagé par les deux
mots de passe communs du dépôt (`benevole_access`, #271 ; `site_access`,
#509). Les deux diffèrent par leur cookie, leur table et leur politique
d'expiration — jamais par ce calcul.
"""
import hashlib
import hmac
import secrets
import time

_SALT_SIZE = 16


def sign_cookie(key: str) -> str:
    """`{horodatage}.{HMAC(key, horodatage)}` — sans état serveur à la vérification."""
    horodatage = str(int(time.time()))
    return f"{horodatage}.{_hmac(key, horodatage)}"


def verify_cookie(value: str | None, key: str, *, max_age_seconds: int | None = None) -> bool:
    """Vrai si `value` a été signée par `key`, et — si `max_age_seconds` est
    fourni — émise il y a moins de ce délai. Fail-closed sur toute forme
    inattendue : valeur/clé absente, horodatage non numérique, signature
    fausse rendent tous `False`, jamais une exception.
    """
    if not value or not key:
        return False
    horodatage, separateur, signature = value.partition(".")
    if not separateur or not horodatage or not signature:
        return False
    if not hmac.compare_digest(signature, _hmac(key, horodatage)):
        return False
    if max_age_seconds is None:
        return True
    try:
        emis = int(horodatage)
    except ValueError:
        return False
    return time.time() - emis <= max_age_seconds


def _hmac(key: str, message: str) -> str:
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str) -> tuple[str, str]:
    """`(password_hash, password_salt)`, hexadécimaux. `hashlib.scrypt`
    (memory-hard) plutôt qu'un SHA-256 salé : un mot de passe choisi par un
    humain a une entropie bien inférieure à un jeton généré. Sel de 16
    octets, régénéré à chaque appel.
    """
    salt = secrets.token_bytes(_SALT_SIZE)
    empreinte = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return empreinte.hex(), salt.hex()


def verify_password(password: str, *, password_hash: str, password_salt: str) -> bool:
    """Comparaison en temps constant, même patron que `verify_cookie`."""
    empreinte = hashlib.scrypt(
        password.encode("utf-8"), salt=bytes.fromhex(password_salt), n=2**14, r=8, p=1
    )
    return hmac.compare_digest(empreinte.hex(), password_hash)
