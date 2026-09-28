"""Relais d'un travail de fond vers un flux SSE (#1017).

Les trois flux (import public, re-scrape et bascule de source admin) lancent leur
travail dans un thread daemon, indépendant de la consommation du flux : une
déconnexion du client ne l'interrompt pas (FR-011). Ce module est leur seul
mécanisme, pour qu'une correction de transport ne soit plus à refaire trois fois
(#705 puis #731).
"""
import queue
import threading
from collections.abc import Callable, Iterator

#: Sentinelle de battement, distincte de tout event métier : la route la traduit en
#: ligne de commentaire SSE (`app/api/sse.py`).
HEARTBEAT = object()

#: Une phase sans event métier (fan-out Klikego lent, persistance d'un gros lot)
#: peut rester muette assez longtemps pour qu'un proxy d'infra (Vercel, Render)
#: coupe la connexion avant `done` (#705, #731).
HEARTBEAT_INTERVAL_SECONDS = 15.0

#: Pas d'attente de la file : compromis entre la réactivité à la coupure du
#: client (le générateur ne se clôt qu'entre deux attentes) et le coût CPU.
_POLL_SECONDS = 0.5

Emit = Callable[[dict], None]


def relay(work: Callable[[Emit], dict | None]) -> Iterator[dict | object]:
    """Lance `work(emit)` dans un thread daemon et relaie ce qu'il émet.

    `work` rend éventuellement l'event final (`done` ou `error`) : il part **après**
    le retour de `work`, donc après ses `finally`, comme la libération d'un verrou.
    `HEARTBEAT` est rendu après `HEARTBEAT_INTERVAL_SECONDS` sans event.
    """
    events: queue.Queue[dict | object] = queue.Queue()
    fin = object()

    def run() -> None:
        try:
            final = work(events.put)
            if final is not None:
                events.put(final)
        finally:
            events.put(fin)

    threading.Thread(target=run, daemon=True).start()

    silence = 0.0
    while True:
        attente = min(_POLL_SECONDS, HEARTBEAT_INTERVAL_SECONDS)
        try:
            item = events.get(timeout=attente)
        except queue.Empty:
            silence += attente
            if silence >= HEARTBEAT_INTERVAL_SECONDS:
                silence = 0.0
                yield HEARTBEAT
            continue
        silence = 0.0
        if item is fin:
            return
        yield item
