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

# Standard library
import os
from typing import Annotated
from logging import getLogger

# Third party
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
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
from backend.components.sql.db_config import SQLALCHEMY_URI

from backend.components.models.user_model import User
from backend.components.sql.sql_engine import SessionDep


def seed_startup(logger):
    """Generates necessary data for the application at startup. 
    
    This runs AFTER Alembic migrations, so most seed data (admin, defaults)
    is already present. It only handles idempotent verification and 
    any additional runtime setup.
    """
    session_factory = get_session_factory()
    db: Session = session_factory()
    
    try:
        # Verify admin user exists (should be seeded by alembic migration)
        admin_user_query = select(User).where(User.name == "admin")
        is_admin_user = db.exec(admin_user_query).first()
        
        if not is_admin_user:
            logger.warning("Admin user not found! Creating fallback...")
            admin_user = User(
                name="admin",
                is_active=True,
                is_superuser=True,
                hashed_password=get_password_hash("admin")
            )
            db.add(admin_user)
            db.commit()
            logger.info("Fallback Admin User created")
        else:
            logger.info("Admin User exists")

    except Exception as e:
        db.rollback()
        logger.error("Error during seed startup: %s", e) 
        
    finally:
        db.close()
        

def _run_alembic_migrations(logger):
    """Run pending Alembic migrations on startup."""
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.command import upgrade
        
        # Load alembic.ini from project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg = AlembicConfig(os.path.join(project_root, "alembic.ini"))
        # Override sqlalchemy.url to match current env
        alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_URI)
        
        # Run migrations to head
        upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
        
    except Exception as e:
        logger.error("Alembic migration failed: %s", e)
        # Don't crash the app - tables might already exist or be managed manually


def create_app():
    
    # Initialize logging
    initialize_logging()
    logger = get_logger()
    
    # Run Alembic migrations (replaces create_db_and_tables)
    logger.info("Running Alembic migrations...")
    _run_alembic_migrations(logger)
    
    # Read root path from environment (e.g. /app for sub-path deployment)
    root_path = os.getenv("ROOT_PATH", "")
    if root_path:
        logger.info(f"Serving under root path: {root_path}")
    
    # Initialize app
    app = FastAPI()
    logger.info("App successfully started")
    
    # Configure CORS to allow frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production restrict this to your frontend URL
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware for Permissions-Policy header (allows microphone access)
    @app.middleware("http")
    async def add_permissions_policy(request: Request, call_next):
        response = await call_next(request)
        # Allow microphone in cross-origin contexts
        response.headers["Permissions-Policy"] = "microphone=(self), camera=(self)"
        return response

    # Health check endpoint for Docker / load balancers
    health_prefix = f"{root_path}/api/endpoint" if root_path else "/api/endpoint"
    @app.get(health_prefix)
    async def health_check():
        return {"status": "ok"}
    
    # Register routers with optional root prefix - MUST be registered BEFORE static files
    router_prefix = root_path or ""
    app.include_router(record_bp, prefix=router_prefix)
    app.include_router(auth_bp, prefix=router_prefix)
    app.include_router(settings_bp, prefix=router_prefix)
    
    # Seed startup (idempotent verification)
    seed_startup(logger)
    
    # Mount static files (built React frontend) on root path
    # This allows relative asset references like "./assets/..." to work correctly
    # MUST be mounted AFTER API routes so that API routes take precedence
    from fastapi.staticfiles import StaticFiles
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    if not os.path.isdir(static_dir):
        # Fallback: if running from project root
        static_dir = "static"
    if not os.path.isdir(static_dir):
        logger.warning("Static directory '%s' does not exist. Creating empty directory.", static_dir)
        os.makedirs(static_dir, exist_ok=True)
    # Mount on root so relative paths in index.html resolve correctly
    # html=True serves index.html for 404s (SPA catch-all)
    static_prefix = f"{root_path}/" if root_path else "/"
    app.mount(static_prefix, StaticFiles(directory=static_dir, html=True), name="static")

    # SPA Catch-All: Handle 404s by serving index.html for client-side routing
    # This must be registered as exception handler, not as a route
    from fastapi.exceptions import HTTPException as FastAPIHTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Only handle 404s that are NOT API routes
        if exc.status_code == 404:
            path = request.url.path
            # Skip API routes - return original 404
            api_prefix = f"{root_path}/api/" if root_path else "/api/"
            if path.startswith(api_prefix):
                raise exc
            # Serve index.html for SPA routing
            index_path = os.path.join(static_dir, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
        # Re-raise other exceptions
        raise exc

    return app
