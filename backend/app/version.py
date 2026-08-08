"""Version de l'application, exposée par `GET /api/v1/version` (#134).

Sert à comparer front vs back sur un utilisateur qui remonte un bug : le
front embed sa version au build, le back lit la sienne à froid. Un
mismatch (rollback partiel, redéploiement dissocié) devient visible.

`APP_VERSION` est **le chemin réel en déploiement** (#162) :
`.github/workflows/deploy.yml` la pousse sur le service Render, via l'API,
juste avant le deploy hook. Render déploie une *branche* et n'a donc aucune
connaissance du tag ; le pipeline est le seul à le connaître, et c'est déjà
lui qui alimente le front (`NEXT_PUBLIC_APP_VERSION`). À défaut : `"dev"`
(chemin local, tests, dev conteneur non taggé).
"""
from __future__ import annotations

from os import environ

FALLBACK = "dev"


def app_version() -> str:
    """Version courante, lue dans l'environnement à chaque appel."""
    return (environ.get("APP_VERSION") or "").strip() or FALLBACK
