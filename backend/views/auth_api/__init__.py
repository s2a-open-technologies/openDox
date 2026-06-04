from fastapi import APIRouter

auth_bp = APIRouter(prefix="/api/v1/auth", tags=["auth"])

from backend.views.auth_api import auth_routes