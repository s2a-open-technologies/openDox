from fastapi import APIRouter

auth_bp = APIRouter(prefix="/api/v1/auth", tags=["auth"])

from app.views.auth_api import auth_routes