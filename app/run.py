# Standard library
import os
from typing import Annotated

# Third party
from fastapi import FastAPI, Depends
from sqlmodel import Session
from dotenv import load_dotenv

# Custom import
from app.components.modules.logger import get_logger, initialize_logging
from app.views.record_api import record_bp
from app.views.auth_api import auth_bp
from config import Config

from app.components.sql.sql_engine import create_db_and_tables
from app.components.models.record_model import Record
from app.components.models.user_model import User

def create_app():
    
    # Initialize Environment
    load_dotenv()
    
    # Initialize logging
    initialize_logging()
    logger = get_logger()
    
    # Initialize DB
    create_db_and_tables()
    
    # Initialize app
    app = FastAPI()
    logger.info("App successfully startet")
    
    # Register record
    app.include_router(record_bp)
    
    # Register auth
    app.include_router(auth_bp)

    return app