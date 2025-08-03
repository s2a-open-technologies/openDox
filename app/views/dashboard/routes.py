# Standard library

# Third party
from fastapi import Request
from fastapi.templating import Jinja2Templates


# Custom imports
from app.views.dashboard import dashboard_bp

# Defining templatefolder
templates = Jinja2Templates(directory='app/templates')

@dashboard_bp.get("/")    
async def get(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
    
    
