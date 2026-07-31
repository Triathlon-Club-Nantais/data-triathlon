"""Version de l'application, exposée par `GET /api/v1/version` (#134).

Sert à comparer front vs back sur un utilisateur qui remonte un bug : le
front embed sa version au build, le back lit la sienne à froid. Un
mismatch (rollback partiel, redéploiement dissocié) devient visible.

Trois sources en cascade, la première non vide gagne :

1. `APP_VERSION` env var — injectée par la plateforme de déploiement (Render
   la propage si elle est configurée dans `render.yaml`).
2. Fichier `VERSION` à la racine du dépôt — écrit par le `buildCommand`
   Render (`git describe --tags --always > VERSION`). C'est le repli qui
   fonctionne sans configuration de secret.
3. Fallback `"dev"` — chemin local, tests, dev conteneur non taggé.

La lecture est **paresseuse et mise en cache** (fonctionne `@lru_cache`) :
l'endpoint est peu appelé mais un chemin certain « aucun I/O par appel »
évite qu'un `open()` récurrent devienne une source de bruit en prod.
"""
from __future__ import annotations

from functools import lru_cache
from os import environ
from pathlib import Path

FALLBACK = "dev"

# Le fichier VERSION est écrit à la racine du dépôt par le buildCommand
# Render. En dev il est absent et on retombe sur `FALLBACK`.
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
