"""Agrège tous les routers de la v1 de l'API derrière un seul APIRouter.

Monté sous `/api/v1` par `app.main`. Une future v2 vivra dans `app/api/v2/`.
"""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_data,
    admin_groups,
    admin_roles,
    admin_sessions,
    athletes,
    auth,
    courses,
    health,
    participations,
    scrape,
    stats,
)

api_router = APIRouter()

# **Aucun `dependencies=`** ici ni sur aucun router (FR-018) : la protection se
# pose route par route. Montée sur `admin`, une garde supprimerait le
# signalement anonyme du site public sans que rien ne la nomme.
for module in (
    health,
    scrape,
    athletes,
    courses,
    participations,
    stats,
    admin,
    admin_allowed_emails,
    admin_batches,
    admin_data,
    admin_roles,
    admin_groups,
    admin_sessions,
    auth,
):
    api_router.include_router(module.router)
