from fastapi import APIRouter

dashboard_bp = APIRouter()

from app.views.dashboard import routes