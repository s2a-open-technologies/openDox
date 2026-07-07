"""openDox - Medical transcription platform
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

import asyncio
import contextlib
import os
import re
import tomllib

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.components.modules.env import env_or_file
from backend.components.modules.logger import get_logger, initialize_logging
from backend.components.sql.db_config import SQLALCHEMY_URI
from backend.views.auth_api import auth_bp, oidc_bp
from backend.views.record_api import record_bp
from backend.views.settings_api import settings_bp


class SPAStaticFiles(StaticFiles):
    """StaticFiles that falls back to index.html for unknown paths.

    Serves real files (assets) directly, but returns the SPA shell for any
    path without a matching file (e.g. /login, /dashboard) so client-side
    routing works on reload and deep links.
    """

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def _run_alembic_migrations(logger):
    try:
        from alembic.command import upgrade
        from alembic.config import Config as AlembicConfig

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_cfg = AlembicConfig(os.path.join(project_root, "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_URI)
        upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully")
    except Exception as e:
        logger.error("Alembic migration failed: %s", e)


def _read_app_version(project_root: str) -> str:
    """Read the app version from pyproject.toml's [project] table."""
    try:
        with open(os.path.join(project_root, "pyproject.toml"), "rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "unknown"


def _inject_root_path(static_dir: str, root_path: str) -> None:
    """Write window.__ROOT_PATH__ into index.html on disk at startup.

    StaticFiles with html=True serves the file directly — injection must be
    on disk so every response (root, deep links, reloads) gets the value.
    """
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.isfile(index_path):
        return
    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()
    script = f"<script>window.__ROOT_PATH__='{root_path}';</script>"
    html = re.sub(r"<script>window\.__ROOT_PATH__='.*?';</script>", "", html)
    html = (
        html.replace("</head>", f"{script}</head>", 1)
        if "</head>" in html
        else script + html
    )
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)


def _cleanup_orphaned_chunk_files(logger) -> None:
    """Remove session_*.pcm / session_*.wav files left over from a previous crash.

    Runs once at startup, before the server accepts connections. At that point
    no sessions exist yet (Redis is either fresh or in-memory is empty), so any
    leftover file in the chunks directory is by definition orphaned.
    """
    chunks_dir = "chunks"
    if not os.path.isdir(chunks_dir):
        return
    removed = 0
    for name in os.listdir(chunks_dir):
        if name.startswith("session_") and (
            name.endswith(".pcm") or name.endswith(".wav")
        ):
            try:
                os.remove(os.path.join(chunks_dir, name))
                removed += 1
            except OSError:
                pass
    if removed:
        logger.info("Startup cleanup: removed %d orphaned chunk file(s)", removed)


async def _stale_session_cleanup_loop(logger) -> None:
    """Periodically remove recording sessions inactive for >30 minutes.

    Covers the case where a user closes the browser without pressing "Stop" —
    the session stays in the store with its PCM file on disk. ``cleanup_stale_sessions``
    deletes the session and the file. The loop runs every 10 minutes; the task
    is cancelled automatically when the lifespan context exits.
    """
    from backend.components.services.session_store import session_store

    while True:
        await asyncio.sleep(600)
        try:
            count = await asyncio.to_thread(session_store.cleanup_stale_sessions, 30)
            if count:
                logger.info("Cleaned up %d stale recording session(s)", count)
        except Exception as exc:
            logger.warning("Stale-session cleanup failed: %s", exc)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup cleanup + background tasks, graceful shutdown.

    On startup: remove orphaned chunk files from a previous crash, then start
    the stale-session cleanup loop. On shutdown: cancel the loop so the event
    loop can stop cleanly.
    """
    logger = get_logger()
    _cleanup_orphaned_chunk_files(logger)
    cleanup_task = asyncio.create_task(_stale_session_cleanup_loop(logger))
    logger.info("Stale-session cleanup loop started (interval=600s, max_age=30min)")
    try:
        yield
    finally:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task
        logger.info("Stale-session cleanup loop stopped")


def create_app():
    initialize_logging()
    logger = get_logger()

    logger.info("Running Alembic migrations...")
    _run_alembic_migrations(logger)

    root_path = env_or_file("ROOT_PATH", "") or ""
    if root_path:
        logger.info(f"Serving under root path: {root_path}")

    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
    if not os.path.isdir(static_dir):
        logger.warning("Static directory '%s' does not exist.", static_dir)
        os.makedirs(static_dir, exist_ok=True)

    # Bake ROOT_PATH into index.html so StaticFiles (html=True) serves it correctly
    _inject_root_path(static_dir, root_path)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app_version = _read_app_version(project_root)

    # NOTE: do NOT pass root_path= here. Routes are prefixed manually below;
    # setting FastAPI(root_path=...) makes Starlette strip the prefix before
    # matching, which would double-count it and 404 everything.
    app = FastAPI(title="openDox", version=app_version, lifespan=lifespan)
    logger.info("App successfully started")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_permissions_policy(request: Request, call_next):
        response = await call_next(request)
        response.headers["Permissions-Policy"] = "microphone=(self), camera=(self)"
        return response

    health_prefix = f"{root_path}/api/endpoint" if root_path else "/api/endpoint"

    @app.get(health_prefix)
    async def health_check():
        return {"status": "ok"}

    version_path = f"{root_path}/api/version" if root_path else "/api/version"

    @app.get(version_path)
    async def get_version():
        return {"version": app_version}

    router_prefix = root_path or ""
    app.include_router(record_bp, prefix=router_prefix)
    app.include_router(auth_bp, prefix=router_prefix)
    app.include_router(oidc_bp, prefix=router_prefix)
    app.include_router(settings_bp, prefix=router_prefix)

    # /opendox → /opendox/ so the browser resolves relative asset paths correctly
    if root_path:

        @app.get(root_path, include_in_schema=False)
        async def redirect_to_root():
            return RedirectResponse(url=f"{root_path}/", status_code=301)

    static_prefix = f"{root_path}/" if root_path else "/"
    app.mount(
        static_prefix,
        SPAStaticFiles(directory=static_dir, html=True),
        name="static",
    )

    return app
