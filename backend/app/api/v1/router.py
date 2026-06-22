"""Agrège tous les routers de la v1 de l'API derrière un seul APIRouter.

Monté sous `/api/v1` par `app.main`. Une future v2 vivra dans `app/api/v2/`.
"""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    athletes,
    courses,
    health,
    participations,
    scrape,
    stats,
)

api_router = APIRouter()

for module in (health, scrape, athletes, courses, participations, stats, admin):
    api_router.include_router(module.router)
