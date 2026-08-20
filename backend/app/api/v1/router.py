"""Agrège tous les routers de la v1 de l'API derrière un seul APIRouter.

Monté sous `/api/v1` par `app.main`. Une future v2 vivra dans `app/api/v2/`.
"""
from fastapi import APIRouter, Depends

from app.api.deps import require_site_access
from app.api.v1 import (
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_benevole_access,
    admin_course_duplicates,
    admin_course_merge,
    admin_course_rescrape,
    admin_course_sources,
    admin_data,
    admin_feedback,
    admin_groups,
    admin_roles,
    admin_sessions,
    admin_site_access,
    athletes,
    auth,
    benevoles,
    courses,
    feedback,
    health,
    participations,
    scrape,
    site_access,
    stats,
)

api_router = APIRouter()

# La garde `require_site_access` (#509) ferme tout, à l'inclusion — jamais sur
# le router lui-même (`module.router.dependencies` reste `[]`, cf.
# `test_aucune_dependance_globale_sur_les_routers_existants`). Cinq
# exceptions nommées (design § Garde backend) : `health` (infra), `site_access`
# (pose le cookie, ne peut pas exiger sa propre présence), `benevoles` (#271 —
# population potentiellement non-adhérente), et `auth`/`admin_site_access` —
# ajoutés après un verrou de démarrage détecté en revue : gater `auth`
# interdisait toute connexion SSO sans cookie site, et gater
# `admin_site_access` exigeait ce même cookie pour le poser — sur une
# installation neuve, sans configuration, aucune des deux routes n'était
# jamais atteignable, y compris par un administrateur, sans échappatoire en
# base ni en CLI. Les deux restent protégées par ce qui les protégeait déjà :
# `admin_site_access` par `require_permission(P.SITE_ACCESS_MANAGE)` (RBAC),
# `auth` par ses propres contrôles (liste d'autorisation, #170) — le même
# patron que `admin_benevole_access`, jamais doublement gardé par
# `require_benevole_access`.
_EXEMPTES_DE_LA_GARDE_SITE = (health, site_access, auth, admin_site_access, benevoles)

for module in _EXEMPTES_DE_LA_GARDE_SITE:
    api_router.include_router(module.router)

for module in (
    scrape,
    athletes,
    courses,
    participations,
    stats,
    feedback,
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_benevole_access,
    admin_course_duplicates,
    admin_course_merge,
    admin_course_rescrape,
    admin_course_sources,
    admin_data,
    admin_feedback,
    admin_roles,
    admin_groups,
    admin_sessions,
):
    api_router.include_router(module.router, dependencies=[Depends(require_site_access)])
