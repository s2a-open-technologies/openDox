# Standard library
import os
from typing import Annotated
from logging import getLogger

# Third party
from fastapi import FastAPI, Depends
from sqlmodel import Session
from dotenv import load_dotenv
from sqlmodel import select, insert

# Custom import
from app.components.modules.logger import get_logger, initialize_logging
from app.components.security.hashing import get_password_hash
from app.views.record_api import record_bp
from app.views.auth_api import auth_bp
from config import Config
from app.components.sql.sql_engine import get_session_factory

from app.components.sql.sql_engine import create_db_and_tables
from app.components.models.record_model import Record
from app.components.models.user_model import User
from app.components.sql.sql_engine import SessionDep


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
    
    # Seed startup
    seed_startup(logger)
    
    # Register record
    app.include_router(record_bp)
    
    # Register auth
    app.include_router(auth_bp)

    return app