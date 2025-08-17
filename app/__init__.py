

# Standard library
import os

# Third party
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Custom import
from app.components.modules.logger import get_logger, initialize_logging
from app.views.api import api_bp
from app.views.dashboard import dashboard_bp
from config import Config


templates = Jinja2Templates(directory='app/templates')

def create_app():
    
    # Initialize logging
    initialize_logging()
    logger = get_logger()
    
    # Initialize app
    app = FastAPI()
    app.mount('/static', StaticFiles(directory='app/static'), name='static')
    logger.info("App successfully startet")
    
    # Register blueprints
    app.include_router(api_bp, prefix="/api/v1")
    app.include_router(dashboard_bp, prefix="/dashboard")    
  
    return app