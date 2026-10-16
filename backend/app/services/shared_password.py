"""HMAC de cookie, hachage et génération de secrets — socle partagé par les deux
mots de passe communs du dépôt (`benevole_access`, #271 ; `site_access`,
#509). Les deux diffèrent par leur cookie, leur table et leur politique
d'expiration — jamais par ce calcul.

Les appelants (routeurs, `api/deps`, tests) s'adressent **directement** ici : les
deux modules de domaine ont porté un temps des délégations d'une ligne qui ne
faisaient que renommer ces fonctions, supprimées en revue de #513. Les décisions
d'origine restent tracées dans
`specs/20260815-173645-admin-mdp-benevoles/research.md` — §D1 pour scrypt plutôt
qu'un hachage rapide, §D2 pour la clé du cookie, qui est un `session_secret`
distinct et non le mot de passe lui-même.
"""
import hashlib
import hmac
import secrets
import time

_SALT_SIZE = 16

#: Taille du mot de passe généré (research.md §D5), en octets.
_GENERATED_PASSWORD_SIZE = 18


def new_session_secret() -> str:
    """Un secret de session neuf, jamais le même deux fois (research.md §D2)."""
    return secrets.token_urlsafe(32)


def generate_password() -> str:
    """Un mot de passe robuste, généré côté serveur (research.md §D5).

    144 bits d'entropie uniforme (`secrets.token_urlsafe(18)`, 24 caractères) :
    trop pour un humain à retenir, ce qui est le but d'une génération serveur.
    """
    return secrets.token_urlsafe(_GENERATED_PASSWORD_SIZE)


def sign_cookie(key: str) -> str:
    """`{horodatage}.{HMAC(key, horodatage)}` — sans état serveur à la vérification."""
    timestamp = str(int(time.time()))
    return f"{timestamp}.{_hmac(key, timestamp)}"


def verify_cookie(value: str | None, key: str, *, max_age_seconds: int | None = None) -> bool:
    """Vrai si `value` a été signée par `key`, et — si `max_age_seconds` est
    fourni — émise il y a moins de ce délai. Fail-closed sur toute forme
    inattendue : valeur/clé absente, horodatage non numérique, signature
    fausse rendent tous `False`, jamais une exception.
    """
    if not value or not key:
        return False
    timestamp, separator, signature = value.partition(".")
    if not separator or not timestamp or not signature:
        return False
    if not hmac.compare_digest(signature, _hmac(key, timestamp)):
        return False
    if max_age_seconds is None:
        return True
    try:
        issued_at = int(timestamp)
    except ValueError:
        return False
    return time.time() - issued_at <= max_age_seconds


def _hmac(key: str, message: str) -> str:
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str) -> tuple[str, str]:
    """`(password_hash, password_salt)`, hexadécimaux. `hashlib.scrypt`
    (memory-hard) plutôt qu'un SHA-256 salé : un mot de passe choisi par un
    humain a une entropie bien inférieure à un jeton généré. Sel de 16
    octets, régénéré à chaque appel.
    """
    salt = secrets.token_bytes(_SALT_SIZE)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return digest.hex(), salt.hex()


def verify_password(password: str, *, password_hash: str, password_salt: str) -> bool:
    """Comparaison en temps constant, même patron que `verify_cookie`."""
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=bytes.fromhex(password_salt), n=2**14, r=8, p=1
    )
    return hmac.compare_digest(digest.hex(), password_hash)
