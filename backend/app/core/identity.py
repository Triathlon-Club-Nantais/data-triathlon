"""Clé et empreinte d'une opposition (#334). Module pur.

La clé confond ce que les chronométreurs publient en variantes pour une même
personne : casse, accents, tirets, espaces, et l'inversion nom/prénom (mots
triés). Elle ignore la date de naissance, que les imports n'ont jamais.

L'empreinte est un SHA-256 de la clé : un pseudonyme, pas une anonymisation (un
nom connu se retrouve par essai). Elle évite seulement de stocker le nom en clair.
"""
import hashlib
import re

from app.core.text import deaccent

_SEPARATORS = re.compile(r"[^a-z0-9]+")


def opposition_key(nom: str, prenom: str) -> str:
    words = _SEPARATORS.split(deaccent(f"{nom} {prenom}").lower())
    return " ".join(sorted(word for word in words if word))


def identity_hash(nom: str, prenom: str) -> str:
    return hashlib.sha256(opposition_key(nom, prenom).encode()).hexdigest()
