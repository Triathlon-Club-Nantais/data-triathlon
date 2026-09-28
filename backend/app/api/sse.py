"""Mise en forme SSE des trois flux de progression (#1017)."""
import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass

from fastapi.responses import StreamingResponse

from app.services import sse_relay

# Padding initial de 2 KB : dépasse le seuil de buffering des navigateurs
# (Chrome / Firefox retiennent ~1-2 KB avant de laisser `Response.body.getReader()`
# rendre le premier chunk). Sans lui, un import Klikego fan-out (35 s de scraping)
# reste figé sur « Récupération des participants… » côté UI alors que le backend
# émet 8 events. Ligne SSE commençant par `:` = commentaire, ignoré par le parseur
# de `useImportStream`. Pas un no-op côté proto : le socket reçoit ces octets
# immédiatement, ce qui casse le tampon. `X-Accel-Buffering: no` ne suffit pas
# (c'est un hint pour nginx, pas pour le navigateur).
INITIAL_PADDING = b":" + b" " * 2048 + b"\n\n"

#: Traduction de `sse_relay.HEARTBEAT` : commentaire SSE, ignoré par le parseur
#: front comme le padding initial.
HEARTBEAT_LINE = b": heartbeat\n\n"

HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    # `Content-Encoding: identity` bloque la compression par tout
    # intermédiaire HTTP — le proxy Turbopack de Next.js dev l'a
    # rendue visible (avec `Accept-Encoding: gzip` d'un navigateur, il
    # bufferisait le stream dans son compresseur jusqu'à ~500 octets,
    # la barre par heat #156 apparaissait 4-5 s en retard), mais la
    # même compression peut réapparaître en prod (edge Vercel, CDN,
    # reverse-proxy) — d'où la garde côté application, pas côté env.
    # Coût mesuré : ~5 KB de plus par import (SSE non compressé),
    # négligeable devant le gain de latence perçue. `no-transform` du
    # Cache-Control est le second garde de RFC 7234.
    "Content-Encoding": "identity",
}


def json_default(value: object) -> object:
    """Filet de sérialisation des phases.

    `iter_import_event` peut émettre des dataclasses (ex. `Reassignment`,
    frozen, non sérialisable nativement) dans le champ `reassignments` de la
    phase `done`. `batch` consomme le même générateur et a besoin des objets
    Python — la conversion se fait donc ici, au point de sérialisation SSE,
    jamais dans le générateur.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def event_stream(events: Iterable[dict | object]) -> StreamingResponse:
    """`StreamingResponse` SSE d'un itérateur d'events et de battements."""

    def generate():
        yield INITIAL_PADDING
        for event in events:
            if event is sse_relay.HEARTBEAT:
                yield HEARTBEAT_LINE
                continue
            yield f"data: {json.dumps(event, default=json_default)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers=HEADERS)
