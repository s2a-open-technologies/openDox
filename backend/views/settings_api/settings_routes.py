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
import os
import shutil

import requests as _requests
from fastapi import File, HTTPException, UploadFile
from sqlmodel import select

from backend.components.models.categories import (
    Categories,
    CategoriesCreate,
    CategoriesRead,
)
from backend.components.models.languages import (
    Languages,
    LanguagesCreate,
    LanguagesRead,
)
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.services.asr_backends import DisabledBackend
from backend.components.services.asr_factory import (
    get_final_backend,
    get_live_backend,
    reset_asr_backends,
)
from backend.components.services.ldap import LdapService
from backend.components.services.session_store import session_store
from backend.components.services.session_store_redis import RedisSessionStore
from backend.components.services.settings_service import get_settings_service
from backend.components.sql.sql_engine import SessionDep
from backend.views.settings_api import settings_bp

# Whisper Endpoints


@settings_bp.get("/whisper-settings/", response_model=WhisperSettingsModel)
async def get_whisper_settings(db: SessionDep):
    settings = db.exec(select(WhisperSettingsModel)).first()
    if not settings:
        settings = WhisperSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.put("/whisper-settings/", response_model=WhisperSettingsModel)
async def update_whisper_settings(settings_in: WhisperSettingsModel, db: SessionDep):
    settings = db.exec(select(WhisperSettingsModel)).first()
    if not settings:
        settings = WhisperSettingsModel()

    settings.live_backend = settings_in.live_backend
    settings.live_api_endpoint = settings_in.live_api_endpoint
    settings.live_api_key = settings_in.live_api_key
    settings.live_api_model = settings_in.live_api_model

    settings.final_backend = settings_in.final_backend
    settings.final_api_endpoint = settings_in.final_api_endpoint
    settings.final_api_key = settings_in.final_api_key
    settings.final_api_model = settings_in.final_api_model

    settings.language = settings_in.language
    settings.chunk_length_s = settings_in.chunk_length_s
    settings.overlap_s = settings_in.overlap_s

    # Anti-hallucination / faster-whisper tuning
    settings.temperature = settings_in.temperature
    settings.vad_filter = settings_in.vad_filter
    settings.vad_min_silence_ms = settings_in.vad_min_silence_ms
    settings.condition_on_previous_text = settings_in.condition_on_previous_text
    settings.no_speech_threshold = settings_in.no_speech_threshold
    settings.compression_ratio_threshold = settings_in.compression_ratio_threshold
    settings.log_prob_threshold = settings_in.log_prob_threshold
    settings.hallucination_silence_threshold = (
        settings_in.hallucination_silence_threshold
    )
    settings.live_beam_size = settings_in.live_beam_size
    settings.final_beam_size = settings_in.final_beam_size

    db.add(settings)
    db.commit()
    db.refresh(settings)

    get_settings_service().invalidate_cache()
    reset_asr_backends()

    return settings


# LLM Endpoints


@settings_bp.get("/llm-settings/", response_model=LlmSettingsModel)
async def get_llm_settings(db: SessionDep):
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings:
        settings = LlmSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.put("/llm-settings/", response_model=LlmSettingsModel)
async def update_llm_settings(settings_in: LlmSettingsModel, db: SessionDep):
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings:
        settings = LlmSettingsModel()

    settings.llm_api_endpoint = settings_in.llm_api_endpoint
    settings.llm_api_key = settings_in.llm_api_key
    settings.llm_model = settings_in.llm_model
    settings.llm_temperature = settings_in.llm_temperature
    settings.llm_max_tokens = settings_in.llm_max_tokens
    settings.correction_model = settings_in.correction_model or None

    settings.sanitizer_enabled = settings_in.sanitizer_enabled
    settings.sanitizer_endpoint = settings_in.sanitizer_endpoint or None
    settings.sanitizer_api_key = settings_in.sanitizer_api_key or None

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


@settings_bp.get("/llm-test/")
async def test_llm_connection(db: SessionDep):
    """Ping the configured LLM endpoint and return available models."""
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings or not settings.llm_api_endpoint:
        raise HTTPException(status_code=400, detail="Kein LLM-Endpoint konfiguriert")

    base = settings.llm_api_endpoint.rstrip("/")
    # Strip trailing /v1 so we can reconstruct the models URL cleanly
    if base.endswith("/v1"):
        base = base[:-3]
    models_url = f"{base}/v1/models"

    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    def _fetch():
        return _requests.get(models_url, headers=headers, timeout=5)

    try:
        response = await asyncio.to_thread(_fetch)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("id", m) for m in data.get("data", [])]
            return {"ok": True, "models": models, "url": models_url}
        return {"ok": False, "error": f"HTTP {response.status_code}", "url": models_url}
    except _requests.exceptions.ConnectionError:
        return {"ok": False, "error": "Verbindung abgelehnt – Endpoint nicht erreichbar", "url": models_url}
    except _requests.exceptions.Timeout:
        return {"ok": False, "error": "Timeout (5s)", "url": models_url}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": models_url}


# Services Health Endpoint


@settings_bp.get("/services-health/")
async def get_services_health(db: SessionDep):
    """Check reachability of every service in the deployment stack.

    Runs one lightweight check per service concurrently. No Docker access
    is involved — each check probes the service over the network the same
    way the app itself would (DB connection, Redis PING, HTTP calls).

    Returns:
        Dict with a "services" list of {name, status} entries, where status
        is "online", "offline", or "disabled" (service not configured/enabled).
    """
    llm_settings = db.exec(select(LlmSettingsModel)).first()

    async def check_postgres():
        try:
            db.exec(select(1))
            return {"name": "Postgres", "status": "online"}
        except Exception:
            return {"name": "Postgres", "status": "offline"}

    async def check_redis():
        if not isinstance(session_store, RedisSessionStore):
            return {"name": "Redis", "status": "disabled"}
        try:
            await asyncio.to_thread(session_store.ping)
            return {"name": "Redis", "status": "online"}
        except Exception:
            return {"name": "Redis", "status": "offline"}

    async def check_whisper():
        backend = get_final_backend()
        if isinstance(backend, DisabledBackend):
            return {"name": "Whisper", "status": "disabled"}
        ok = await asyncio.to_thread(backend.health_check)
        return {"name": "Whisper", "status": "online" if ok else "offline"}

    async def check_parakeet():
        backend = get_live_backend()
        if isinstance(backend, DisabledBackend):
            return {"name": "Parakeet", "status": "disabled"}
        ok = await asyncio.to_thread(backend.health_check)
        return {"name": "Parakeet", "status": "online" if ok else "offline"}

    async def check_entityguard():
        sanitizer_configured = (
            llm_settings
            and llm_settings.sanitizer_enabled
            and llm_settings.sanitizer_endpoint
        )
        if not sanitizer_configured:
            return {"name": "EntityGuard", "status": "disabled"}
        try:
            await asyncio.to_thread(
                _requests.post,
                llm_settings.sanitizer_endpoint.rstrip("/"),
                json={},
                timeout=5,
            )
            return {"name": "EntityGuard", "status": "online"}
        except (_requests.exceptions.ConnectionError, _requests.exceptions.Timeout):
            return {"name": "EntityGuard", "status": "offline"}

    services = await asyncio.gather(
        check_postgres(),
        check_redis(),
        check_whisper(),
        check_parakeet(),
        check_entityguard(),
    )
    return {"services": [{"name": "App", "status": "online"}, *services]}


# LDAP Endpoints
@settings_bp.get("/ldap-settings/", response_model=LdapSettingsModel)
async def get_ldap_settings(db: SessionDep):
    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        return LdapSettingsModel(
            server_host="", server_port=389, base_dn="", user_dn=""
        )
    return settings


@settings_bp.put("/ldap-settings/", response_model=LdapSettingsModel)
async def update_ldap_settings(settings_in: LdapSettingsModel, db: SessionDep):
    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        settings = LdapSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        settings_data = settings_in.dict(exclude_unset=True, exclude={"id"})
        for key, value in settings_data.items():
            setattr(settings, key, value)
        db.add(settings)

    db.commit()
    db.refresh(settings)
    return settings


@settings_bp.post("/ldap-settings/test")
async def test_ldap_connection(settings_in: LdapSettingsModel):
    service = LdapService(settings_in)
    try:
        conn = service.connect()
        if conn.bind():
            conn.unbind()
            return {"success": True, "message": "Connection successful"}
        else:
            return {"success": False, "message": "Bind failed"}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {str(e)}"}


@settings_bp.post("/ldap-settings/upload-cert/")
async def upload_ldap_cert(file: UploadFile = File(...)):
    certs_dir = "certs"
    os.makedirs(certs_dir, exist_ok=True)
    file_path = os.path.join(certs_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": file.filename}


# Categories Endpoints
@settings_bp.post("/categories/", response_model=CategoriesRead)
async def create_category(category: CategoriesCreate, db: SessionDep):
    db_category = Categories.model_validate(category)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@settings_bp.get("/categories/", response_model=list[CategoriesRead])
async def read_categories(db: SessionDep, offset: int = 0, limit: int = 100):
    categories = db.exec(select(Categories).offset(offset).limit(limit)).all()
    return categories


@settings_bp.get("/categories/{category_id}", response_model=CategoriesRead)
async def read_category(category_id: int, db: SessionDep):
    category = db.get(Categories, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@settings_bp.put("/categories/{category_id}", response_model=CategoriesRead)
async def update_category(category_id: int, category: CategoriesCreate, db: SessionDep):
    db_category = db.get(Categories, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")
    category_data = category.model_dump(exclude_unset=True)
    db_category.sqlmodel_update(category_data)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@settings_bp.delete("/categories/{category_id}")
async def delete_category(category_id: int, db: SessionDep):
    category = db.get(Categories, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(category)
    db.commit()
    return {"ok": True}


# Languages Endpoints
@settings_bp.post("/languages/", response_model=LanguagesRead)
async def create_language(language: LanguagesCreate, db: SessionDep):
    db_language = Languages.model_validate(language)
    db.add(db_language)
    db.commit()
    db.refresh(db_language)
    return db_language


@settings_bp.get("/languages/", response_model=list[LanguagesRead])
async def read_languages(db: SessionDep, offset: int = 0, limit: int = 100):
    languages = db.exec(select(Languages).offset(offset).limit(limit)).all()
    return languages


@settings_bp.get("/languages/{language_id}", response_model=LanguagesRead)
async def read_language(language_id: int, db: SessionDep):
    language = db.get(Languages, language_id)
    if not language:
        raise HTTPException(status_code=404, detail="Language not found")
    return language


@settings_bp.put("/languages/{language_id}", response_model=LanguagesRead)
async def update_language(language_id: int, language: LanguagesCreate, db: SessionDep):
    db_language = db.get(Languages, language_id)
    if not db_language:
        raise HTTPException(status_code=404, detail="Language not found")
    language_data = language.model_dump(exclude_unset=True)
    db_language.sqlmodel_update(language_data)
    db.add(db_language)
    db.commit()
    db.refresh(db_language)
    return db_language


@settings_bp.delete("/languages/{language_id}")
async def delete_language(language_id: int, db: SessionDep):
    language = db.get(Languages, language_id)
    if not language:
        raise HTTPException(status_code=404, detail="Language not found")
    db.delete(language)
    db.commit()
    return {"ok": True}
