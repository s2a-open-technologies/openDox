from fastapi import APIRouter

settings_bp = APIRouter(prefix="/api/v1/settings", tags=["settings"])

from backend.views.settings_api import settings_routes
