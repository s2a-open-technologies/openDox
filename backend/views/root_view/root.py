"""
  openDox - Medical transcription platform
  Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

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
