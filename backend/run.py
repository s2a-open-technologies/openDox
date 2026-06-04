# Standard library
import os
from typing import Annotated
from logging import getLogger

# Third party
from fastapi import FastAPI, Depends
from sqlmodel import Session
from dotenv import load_dotenv
from sqlmodel import select, insert

# Load environment variables befor importing the modules
load_dotenv(override=True)

# Custom import
from backend.components.modules.logger import get_logger, initialize_logging
from backend.components.security.hashing import get_password_hash
from backend.views.record_api import record_bp
from backend.views.auth_api import auth_bp
from backend.views.settings_api import settings_bp
from config import Config
from backend.components.sql.sql_engine import get_session_factory

from backend.components.sql.sql_engine import create_db_and_tables
from backend.components.models.record_model import Record
from backend.components.models.user_model import User
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.sql.sql_engine import SessionDep


def seed_startup(logger):
    """Generates necessary data for the application at startup. """
    session_factory = get_session_factory()
    
    # initialize db
    db: Session = session_factory()
    
    # Checks whether Admin user exists
    admin_user_query = select(User).where(User.name == "admin")
    is_admin_user = db.exec(admin_user_query).first()
    
    try:
        if not is_admin_user:
            logger.info("Admin user does not exist. Creating Admin User...")
            # Create Admin User
            admin_user = User(
                name="admin",
                is_active=True,
                is_superuser=True,
                hashed_password=get_password_hash("admin")
            )
            
            db.add(admin_user)
            db.commit()
            logger.info("Admin User created")
        else:
            logger.info("Admin User already exists")

    except Exception as e:
        db.rollback()
        logger.error("Error creating Admin User: %s", e) 
        
    finally:
        db.close()
        

def create_app():
    
    # Initialize logging
    initialize_logging()
    logger = get_logger()
    
    # Initialize DB
    create_db_and_tables()
    
    # Initialize app
    app = FastAPI()
    logger.info("App successfully startet")
    
    # Seed startup
    seed_startup(logger)
    
    # Register record
    app.include_router(record_bp)
    
    # Register auth
    app.include_router(auth_bp)

    # Register settings
    app.include_router(settings_bp)

    return app