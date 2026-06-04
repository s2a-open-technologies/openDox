from fastapi import APIRouter

root_bp = APIRouter(prefix="/")

from backend.views.record_api import root