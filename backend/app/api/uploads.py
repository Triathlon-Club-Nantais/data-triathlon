"""Lecture bornée d'un fichier téléversé, commune aux écrans d'import (#47, #1202)."""
from fastapi import UploadFile

from app.core.exceptions import DomainError

#: Deux méga-octets : largement au-dessus de tout export du club, largement en
#: dessous de ce qui met un process web à genoux.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class FileTooLargeError(DomainError):
    status_code = 413
    message = "Fichier trop volumineux : la limite est de 2 Mo."


async def read_bounded_upload(file: UploadFile) -> bytes:
    """Lit le corps **par morceaux**, en comptant au fur et à mesure.

    Jamais d'après `Content-Length` : c'est un en-tête écrit par le client, et
    un client qui ment sur la taille est exactement celui dont on se garde.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise FileTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)
