"""Version de l'application, exposée par `GET /api/v1/version` (#134).

Sert à comparer front vs back sur un utilisateur qui remonte un bug : le
front embed sa version au build, le back lit la sienne à froid. Un
mismatch (rollback partiel, redéploiement dissocié) devient visible.

Trois sources en cascade, la première non vide gagne :

1. `APP_VERSION` env var — **c'est le chemin réel en déploiement** (#162).
   `.github/workflows/deploy.yml` la pousse sur le service Render, via l'API,
   juste avant le deploy hook. Render déploie une *branche* et n'a donc aucune
   connaissance du tag ; le pipeline est le seul à le connaître, et c'est déjà
   lui qui alimente le front (`NEXT_PUBLIC_APP_VERSION`).
2. Fichier `VERSION` à la racine de `backend/` — repli pour un déploiement
   qui n'a pas de pipeline (conteneur auto-hébergé) et qui l'écrit lui-même,
   par exemple `git describe --tags --always > VERSION` au build. **Rien dans
   ce dépôt ne l'écrit** : ni le Dockerfile, ni Render, dont le `buildCommand`
   effectif est celui du dashboard et non celui de `render.yaml`. C'est cette
   croyance qui a fait répondre « dev » en production pendant #134.
3. Fallback `"dev"` — chemin local, tests, dev conteneur non taggé.

La lecture est **paresseuse et mise en cache** (`@lru_cache`) :
l'endpoint est peu appelé mais un chemin certain « aucun I/O par appel »
évite qu'un `open()` récurrent devienne une source de bruit en prod.
"""
from __future__ import annotations

from functools import lru_cache
from os import environ
from pathlib import Path

FALLBACK = "dev"

# Repli hors pipeline (cf. docstring) : aucun build de ce dépôt n'écrit ce
# fichier. En dev il est absent et on retombe sur `FALLBACK`.
_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


@lru_cache(maxsize=1)
def app_version() -> str:
    """Version courante, lue une seule fois par processus.

    L'invalidation du cache est laborieuse — mais dans un service web
    long-vivant, la version ne change pas entre deux redéploiements
    (chaque redéploiement lance un nouveau processus). Pas de rafraîchi.
    """
    env = (environ.get("APP_VERSION") or "").strip()
    if env:
        return env
    try:
        content = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return FALLBACK
    return content or FALLBACK
