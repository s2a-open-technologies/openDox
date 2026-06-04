from fastapi import APIRouter

record_bp = APIRouter(prefix="/api/v1/records", tags=["records"])

from backend.views.record_api import record