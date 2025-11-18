from fastapi import APIRouter

record_bp = APIRouter(prefix="/api/v1/record", tags=["record"])

from app.views.record_api import record