from fastapi import APIRouter

root_bp = APIRouter(prefix="/")

from app.views.record_api import root