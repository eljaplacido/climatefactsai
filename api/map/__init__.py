"""
Map API package — country statistics, layer data, queries, and comparison endpoints.

Monolith split (2026-06-17 audit): 2530-line api/map_routes.py → modular package
with routes separated by concern and shared models/cache/services extracted.
"""
from fastapi import APIRouter

from .routes_main import router as main_router
from .routes_query import router as query_router
from .routes_country import router as country_router
from .routes_layers import router as layers_router
from .routes_compare import router as compare_router

router = APIRouter(prefix="/api/map", tags=["Map"])
router.include_router(main_router)
router.include_router(query_router)
router.include_router(country_router)
router.include_router(layers_router)
router.include_router(compare_router)
