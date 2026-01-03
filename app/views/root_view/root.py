from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles

root_router = APIRouter()

# Mountet den statischen Ordner unter dem Pfad "/static"
app.mount("/static", StaticFiles(directory="static"), name="static")

# Beispiel-Route für deine API
@root_router.get("/api/endpoint")
async def api_endpoint():
    return {"message": "API Endpoint"}

app.include_router(router, prefix="/api")
