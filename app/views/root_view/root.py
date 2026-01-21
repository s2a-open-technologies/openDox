from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles

app = FastAPI()
root_router = APIRouter()

# Mountet den statischen Ordner unter dem Pfad "/static"
app.mount("/static", StaticFiles(directory="static"), name="static")

# Beispiel-Route für deine API
@root_router.get("/api/endpoint")
async def api_endpoint():
    return {"message": "API Endpoint"}

@root_router.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(root_router)
