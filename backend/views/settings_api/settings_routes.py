"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-License-Identifier: AGPL-3.0-or-later

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
import json
import os
from datetime import datetime
from typing import Any

import requests as _requests
from fastapi import Depends, File, HTTPException, UploadFile
from sqlmodel import select

from backend.components.llm.llm_model import SummarizeModel, normalize_openai_base_url
from backend.components.models.audio_settings_model import AudioSettingsModel
from backend.components.models.categories import (
    Categories,
    CategoriesCreate,
    CategoriesListRead,
    CategoriesRead,
)
from backend.components.models.languages import (
    Languages,
    LanguagesCreate,
    LanguagesRead,
)
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.user_model import (
    PersonalGlossaryRead,
    PersonalGlossaryUpdate,
    User,
)
from backend.components.modules.env import env_or_file
from backend.components.services import audio_storage
from backend.components.services.asr_backends import DisabledBackend
from backend.components.services.asr_factory import (
    get_final_backend,
    get_live_backend,
    reset_asr_backends,
)
from backend.components.services.ldap import LdapService
from backend.components.services.session_store import (
    reconnect_session_store,
    session_store,
)
from backend.components.services.session_store_redis import RedisSessionStore
from backend.components.services.settings_service import get_settings_service
from backend.components.sql.sql_engine import SessionDep
from backend.views.auth_api.dependencies import get_current_user
from backend.views.settings_api import settings_bp


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Guard: only admins may write settings (except categories)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin role required",
        )
    return current_user


# Whisper Endpoints


@settings_bp.get("/whisper-settings/", response_model=WhisperSettingsModel)
async def get_whisper_settings(db: SessionDep):
    """Return the Whisper settings, creating defaults if missing."""
    settings = db.exec(select(WhisperSettingsModel)).first()
    if not settings:
        settings = WhisperSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.put("/whisper-settings/", response_model=WhisperSettingsModel)
async def update_whisper_settings(
    settings_in: WhisperSettingsModel,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Update the Whisper settings and reset cached ASR backends."""
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
    settings.left_context_s = settings_in.left_context_s

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

    settings.term_correction_enabled = settings_in.term_correction_enabled
    settings.term_correction_threshold = settings_in.term_correction_threshold

    db.add(settings)
    db.commit()
    db.refresh(settings)

    get_settings_service().invalidate_cache()
    reset_asr_backends()

    return settings


# LLM Endpoints


@settings_bp.get("/llm-settings/", response_model=LlmSettingsModel)
async def get_llm_settings(db: SessionDep):
    """Return the LLM settings, creating defaults if missing."""
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings:
        settings = LlmSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.put("/llm-settings/", response_model=LlmSettingsModel)
async def update_llm_settings(
    settings_in: LlmSettingsModel,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Update the LLM settings and invalidate the settings cache."""
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings:
        settings = LlmSettingsModel()

    settings.llm_api_endpoint = settings_in.llm_api_endpoint
    settings.llm_api_key = settings_in.llm_api_key
    settings.llm_model = settings_in.llm_model
    settings.llm_temperature = settings_in.llm_temperature
    settings.llm_max_tokens = settings_in.llm_max_tokens
    settings.llm_top_p = settings_in.llm_top_p
    settings.llm_frequency_penalty = settings_in.llm_frequency_penalty
    settings.llm_enable_thinking = settings_in.llm_enable_thinking
    settings.correction_model = settings_in.correction_model or None

    settings.sanitizer_enabled = settings_in.sanitizer_enabled
    settings.sanitizer_endpoint = settings_in.sanitizer_endpoint or None
    settings.sanitizer_api_key = settings_in.sanitizer_api_key or None

    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


LLM_TEST_TIMEOUT_SECONDS = 15


@settings_bp.get("/llm-test/")
async def test_llm_connection(
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Send a real chat-completion probe to the configured LLM endpoint.

    A /v1/models reachability check alone is not representative of what a
    real summary call does: SummarizeModel/ChatOpenAI builds requests by
    appending "/chat/completions" directly to the configured base_url, with
    no normalization of its own. A URL that looks reachable via /models
    (e.g. a bare "https://ollama.com" without "/v1") can still silently
    land on the provider's website — HTML instead of JSON — for real chat
    calls. This probe goes through SummarizeModel itself, so a green result
    here is a true predictor of whether summary generation will work.
    """
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings or not settings.llm_api_endpoint:
        raise HTTPException(status_code=400, detail="Kein LLM-Endpoint konfiguriert")
    llm_api_endpoint: str = settings.llm_api_endpoint

    def _probe_chat() -> str:
        model = SummarizeModel(
            model_name=settings.llm_model,
            base_url=llm_api_endpoint,
            api_key=settings.llm_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            top_p=settings.llm_top_p,
            frequency_penalty=settings.llm_frequency_penalty,
            enable_thinking=settings.llm_enable_thinking,
            timeout=LLM_TEST_TIMEOUT_SECONDS,
        )
        return model.generate_response(
            "hi bist du da?", custom_system_prompt="Antworte in einem kurzen Satz."
        )

    def _fetch_models() -> list:
        models_url = f"{normalize_openai_base_url(llm_api_endpoint)}/models"
        headers = {}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        try:
            response = _requests.get(
                models_url, headers=headers, timeout=LLM_TEST_TIMEOUT_SECONDS
            )
            if response.status_code == 200:
                return [m.get("id", m) for m in response.json().get("data", [])]
        except _requests.exceptions.RequestException:
            pass
        return []

    try:
        reply = await asyncio.to_thread(_probe_chat)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    models = await asyncio.to_thread(_fetch_models)
    return {"ok": True, "reply": reply, "models": models}


@settings_bp.get("/asr-test/")
async def test_asr_connection(
    backend: str,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Probe the configured ASR backend for reachability.

    Args:
        backend: "live" or "final".
        db: Database session.
        _: Admin user check.

    Returns:
        {"ok": true/false, "error": str?, "model": str?}
    """
    if backend not in ("live", "final"):
        raise HTTPException(status_code=400, detail='backend must be "live" or "final"')

    asr_backend = get_live_backend() if backend == "live" else get_final_backend()

    if isinstance(asr_backend, DisabledBackend):
        return {"ok": False, "error": "Backend ist deaktiviert oder nicht konfiguriert"}

    ok = await asyncio.to_thread(asr_backend.health_check)
    if ok:
        model = getattr(asr_backend, "model", None)
        result = {"ok": True}
        if model:
            result["model"] = model
        return result
    return {"ok": False, "error": "Endpoint nicht erreichbar"}


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
            return {"name": "Datenbank", "status": "online"}
        except Exception:
            return {"name": "Datenbank", "status": "offline"}

    async def check_redis():
        # REDIS_URL configured but the active store is in-memory → the app
        # process started while Redis was still down (depends_on only orders
        # initial compose creation, not single-container restarts). Try a
        # live reconnect before reporting "offline" — the health check is
        # the natural trigger since it runs every 10s from the admin UI.
        active_store = session_store.get()
        if env_or_file("REDIS_URL") and not isinstance(active_store, RedisSessionStore):
            reconnected = await asyncio.to_thread(reconnect_session_store)
            active_store = session_store.get()
            if not reconnected:
                return {"name": "Cache", "status": "offline"}
        if not isinstance(active_store, RedisSessionStore):
            return {"name": "Cache", "status": "disabled"}
        try:
            await asyncio.to_thread(active_store.ping)
            return {"name": "Cache", "status": "online"}
        except Exception:
            return {"name": "Cache", "status": "offline"}

    async def check_whisper():
        backend = get_final_backend()
        if isinstance(backend, DisabledBackend):
            return {"name": "Transkription", "status": "disabled"}
        ok = await asyncio.to_thread(backend.health_check)
        return {"name": "Transkription", "status": "online" if ok else "offline"}

    async def check_parakeet():
        backend = get_live_backend()
        if isinstance(backend, DisabledBackend):
            return {"name": "Live", "status": "disabled"}
        ok = await asyncio.to_thread(backend.health_check)
        return {"name": "Live", "status": "online" if ok else "offline"}

    async def check_entityguard():
        sanitizer_configured = (
            llm_settings
            and llm_settings.sanitizer_enabled
            and llm_settings.sanitizer_endpoint
        )
        if not sanitizer_configured:
            return {"name": "PII", "status": "disabled"}
        try:
            await asyncio.to_thread(
                _requests.post,
                llm_settings.sanitizer_endpoint.rstrip("/"),
                json={},
                timeout=5,
            )
            return {"name": "PII", "status": "online"}
        except (_requests.exceptions.ConnectionError, _requests.exceptions.Timeout):
            return {"name": "PII", "status": "offline"}

    async def check_s3():
        if not audio_storage.is_configured():
            return {"name": "Objekt-Speicher (S3)", "status": "disabled"}
        try:
            await asyncio.to_thread(audio_storage.head_bucket)
            return {"name": "Objekt-Speicher (S3)", "status": "online"}
        except Exception:
            return {"name": "Objekt-Speicher (S3)", "status": "offline"}

    async def check_encryption():
        from backend.components.models.encryption_key_state import EncryptionKeyState
        from backend.components.security import field_encryption, key_rotation

        current_key = field_encryption.get_current_key()
        if current_key is None:
            return {"name": "Verschlüsselung", "status": "disabled"}
        state = db.exec(select(EncryptionKeyState)).first()
        if state and state.key_fingerprint == key_rotation.fingerprint_key(current_key):
            return {"name": "Verschlüsselung", "status": "online"}
        return {"name": "Verschlüsselung", "status": "offline"}

    services = await asyncio.gather(
        check_postgres(),
        check_redis(),
        check_whisper(),
        check_parakeet(),
        check_entityguard(),
        check_s3(),
        check_encryption(),
    )
    return {"services": [{"name": "Backend", "status": "online"}, *services]}


# LDAP Endpoints
@settings_bp.get("/ldap-settings/", response_model=LdapSettingsModel)
async def get_ldap_settings(db: SessionDep):
    """Return the LDAP settings or an empty default object if missing."""
    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        return LdapSettingsModel(
            server_host="", server_port=389, base_dn="", user_dn=""
        )
    return settings


@settings_bp.put("/ldap-settings/", response_model=LdapSettingsModel)
async def update_ldap_settings(
    settings_in: LdapSettingsModel,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Create or update the LDAP settings (admin only)."""
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
async def test_ldap_connection(
    settings_in: LdapSettingsModel,
    _: User = Depends(_require_admin),
):
    """Test connectivity to the configured LDAP server (admin only)."""
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
async def upload_ldap_cert(
    db: SessionDep,
    file: UploadFile = File(...),
    _: User = Depends(_require_admin),
):
    """Store an uploaded LDAP CA certificate directly in the settings row.

    The certificate content (PEM text) is persisted in the database and
    passed to ``ldap3.Tls`` as ``ca_certs_data`` at connect time — no file is
    ever written to disk, so the upload's filename cannot be used to write
    outside a managed directory.
    """
    raw = await file.read()
    try:
        cert_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, detail="Zertifikat muss eine PEM-Textdatei sein"
        )
    if not cert_text.strip():
        raise HTTPException(status_code=400, detail="Zertifikatsdatei ist leer")

    display_name = os.path.basename(file.filename or "certificate.pem")

    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        settings = LdapSettingsModel(
            server_host="", server_port=389, base_dn="", user_dn=""
        )
    settings.cert_data = cert_text
    settings.cert_filename = display_name
    db.add(settings)
    db.commit()

    return {"filename": display_name}


# Categories Endpoints
#
# Categories with user_id=None are global, admin/moderator-managed
# categories visible to everyone. Categories with a user_id are personal
# categories, owned by that single user and invisible to everyone else
# (admins can see/edit any category for support purposes). Personal
# categories may never carry a custom LLM backend override - that stays a
# moderator/admin-only capability, enforced server-side below regardless
# of what a client sends.
_LLM_OVERRIDE_DEFAULTS = {
    "llm_override_enabled": False,
    "llm_model": None,
    "llm_api_endpoint": None,
    "llm_api_key": None,
    "llm_temperature": None,
    "llm_max_tokens": None,
    "llm_top_p": None,
    "llm_frequency_penalty": None,
    "llm_enable_thinking": None,
}


@settings_bp.post("/categories/", response_model=CategoriesRead)
async def create_category(
    category: CategoriesCreate,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Create a global or personal category for the current user."""
    data = category.model_dump()
    if current_user.role in ("admin", "moderator", "demo_viewer"):
        data["user_id"] = None
    else:
        data["user_id"] = current_user.id
        data.update(_LLM_OVERRIDE_DEFAULTS)
    db_category = Categories(**data)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@settings_bp.get("/categories/", response_model=list[CategoriesListRead])
async def read_categories(
    db: SessionDep,
    current_user: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = 100,
):
    """List categories visible to the current user with pagination."""
    query = select(Categories)
    if current_user.role != "admin":
        query = query.where(
            (Categories.user_id.is_(None)) | (Categories.user_id == current_user.id)
        )
    categories = db.exec(query.offset(offset).limit(limit)).all()
    return categories


@settings_bp.get("/categories/{category_id}", response_model=CategoriesListRead)
async def read_category(
    category_id: int,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Return a single category if the current user may see it."""
    category = db.get(Categories, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if (
        current_user.role != "admin"
        and category.user_id is not None
        and category.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@settings_bp.put("/categories/{category_id}", response_model=CategoriesRead)
async def update_category(
    category_id: int,
    category: CategoriesCreate,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Update a category with ownership and LLM-override checks."""
    db_category = db.get(Categories, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    is_owner = (
        db_category.user_id is not None and db_category.user_id == current_user.id
    )
    if db_category.user_id is None:
        if current_user.role not in ("admin", "moderator", "demo_viewer"):
            raise HTTPException(
                status_code=403, detail="Moderator or admin role required"
            )
    elif not is_owner and current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this category"
        )

    category_data = category.model_dump(exclude_unset=True)
    is_privileged_editor = current_user.role in ("admin", "moderator", "demo_viewer")
    if not is_privileged_editor or db_category.user_id is not None:
        category_data.update(_LLM_OVERRIDE_DEFAULTS)
    if not category_data.get("llm_api_key"):
        # GET responses never include the raw key, so an edit form that
        # didn't touch it would otherwise wipe the stored key on every save.
        category_data.pop("llm_api_key", None)

    db_category.sqlmodel_update(category_data)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


@settings_bp.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Delete a category with ownership checks."""
    category = db.get(Categories, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    is_owner = category.user_id is not None and category.user_id == current_user.id
    if category.user_id is None:
        if current_user.role not in ("admin", "moderator", "demo_viewer"):
            raise HTTPException(
                status_code=403, detail="Moderator or admin role required"
            )
    elif not is_owner and current_user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this category"
        )

    db.delete(category)
    db.commit()
    return {"ok": True}


# Personal Dictionary Endpoint
#
# Each user's own free-text correction glossary, private to them — never
# exposed via any admin-facing endpoint or schema, unlike personal
# categories (which admins can see for support purposes, see above).
# Merged with the selected recording's category glossary at term-correction
# time (background_transcription_service.py), regardless of which category
# was picked.


@settings_bp.get("/my-dictionary/", response_model=PersonalGlossaryRead)
async def get_my_dictionary(current_user: User = Depends(get_current_user)):
    """Return the current user's personal glossary."""
    return PersonalGlossaryRead(personal_glossary=current_user.personal_glossary)


@settings_bp.put("/my-dictionary/", response_model=PersonalGlossaryRead)
async def update_my_dictionary(
    payload: PersonalGlossaryUpdate,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Update the current user's personal glossary."""
    current_user.personal_glossary = payload.personal_glossary
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return PersonalGlossaryRead(personal_glossary=current_user.personal_glossary)


# Languages Endpoints
@settings_bp.post("/languages/", response_model=LanguagesRead)
async def create_language(
    language: LanguagesCreate,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Create a new language (admin only)."""
    db_language = Languages.model_validate(language)
    db.add(db_language)
    db.commit()
    db.refresh(db_language)
    return db_language


@settings_bp.get("/languages/", response_model=list[LanguagesRead])
async def read_languages(db: SessionDep, offset: int = 0, limit: int = 100):
    """List languages with pagination."""
    languages = db.exec(select(Languages).offset(offset).limit(limit)).all()
    return languages


@settings_bp.get("/languages/{language_id}", response_model=LanguagesRead)
async def read_language(language_id: int, db: SessionDep):
    """Return a single language by ID."""
    language = db.get(Languages, language_id)
    if not language:
        raise HTTPException(status_code=404, detail="Language not found")
    return language


@settings_bp.put("/languages/{language_id}", response_model=LanguagesRead)
async def update_language(
    language_id: int,
    language: LanguagesCreate,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Update a language by ID (admin only)."""
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
async def delete_language(
    language_id: int,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Delete a language by ID (admin only)."""
    language = db.get(Languages, language_id)
    if not language:
        raise HTTPException(status_code=404, detail="Language not found")
    db.delete(language)
    db.commit()
    return {"ok": True}


# Backup / Restore Endpoints


def _serialize_model(model) -> dict[str, Any]:
    """Serialize a single SQLModel instance to a dict, excluding the PK."""
    data = model.model_dump()
    data.pop("id", None)
    return data


def _export_all_settings(db: SessionDep) -> dict[str, Any]:
    """Collect all settings tables into a serializable dict.

    Args:
        db: Active database session.

    Returns:
        Dict with a "version" timestamp and a "settings" mapping, where each
        key is a table name and the value is either a single dict (singleton
        settings) or a list of dicts (list tables).
    """
    whisper = db.exec(select(WhisperSettingsModel)).first()
    llm = db.exec(select(LlmSettingsModel)).first()
    ldap = db.exec(select(LdapSettingsModel)).first()
    audio = db.exec(select(AudioSettingsModel)).first()
    categories = db.exec(select(Categories)).all()
    languages = db.exec(select(Languages)).all()

    return {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "settings": {
            "whisper": _serialize_model(whisper) if whisper else None,
            "llm": _serialize_model(llm) if llm else None,
            "ldap": _serialize_model(ldap) if ldap else None,
            "audio": _serialize_model(audio) if audio else None,
            "categories": [_serialize_model(c) for c in categories],
            "languages": [_serialize_model(lang) for lang in languages],
        },
    }


def _import_all_settings(db: SessionDep, data: dict[str, Any]) -> None:
    """Restore settings from a backup dict into the database.

    Overwrites singleton rows in place (matching by first row) and replaces
    all list-table rows (categories, languages) wholesale.

    Args:
        db: Active database session.
        data: Backup dict as produced by ``_export_all_settings``.

    Raises:
        HTTPException: 400 if the backup structure is invalid.
    """
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise HTTPException(status_code=400, detail="Ungültiges Backup-Format")

    # --- Singleton settings (upsert first row) ---
    for model_cls, key in [
        (WhisperSettingsModel, "whisper"),
        (LlmSettingsModel, "llm"),
        (LdapSettingsModel, "ldap"),
        (AudioSettingsModel, "audio"),
    ]:
        row_data = settings.get(key)
        if not row_data or not isinstance(row_data, dict):
            continue
        existing = db.exec(select(model_cls)).first()
        if existing:
            for field, value in row_data.items():
                setattr(existing, field, value)
            db.add(existing)
        else:
            db.add(model_cls(**row_data))

    # --- List tables (replace wholesale) ---
    for model_cls, key in [
        (Categories, "categories"),
        (Languages, "languages"),
    ]:
        rows_data = settings.get(key)
        if not isinstance(rows_data, list):
            continue
        for row in db.exec(select(model_cls)).all():
            db.delete(row)
        for row_data in rows_data:
            if not isinstance(row_data, dict):
                continue
            if model_cls is Categories and "glossary" not in row_data:
                # Backups made before the glossary/whisper_prompt split only
                # have whisper_prompt — backfill so term correction doesn't
                # silently stop working after restoring an older backup
                # (mirrors the migration's own backfill).
                row_data = {**row_data, "glossary": row_data.get("whisper_prompt")}
            db.add(model_cls(**row_data))

    db.commit()
    get_settings_service().invalidate_cache()
    reset_asr_backends()


@settings_bp.get("/backup/")
async def export_backup(
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Export all settings tables as a downloadable JSON file.

    Returns:
        JSON response with Content-Disposition attachment header. The
        filename includes the export timestamp.
    """
    from fastapi import Response

    data = _export_all_settings(db)
    filename = f"opendox-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    content = json.dumps(data, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@settings_bp.post("/backup/restore/")
async def import_backup(
    db: SessionDep,
    file: UploadFile = File(...),
    _: User = Depends(_require_admin),
):
    """Restore settings from an uploaded JSON backup file.

    Args:
        db: Active database session.
        file: Uploaded JSON file produced by the export endpoint.

    Returns:
        Dict with an "ok" flag and a summary of restored tables.
    """
    raw = await file.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Kein gültiges JSON: {exc}")
    _import_all_settings(db, data)
    return {"ok": True, "restored": list(data.get("settings", {}).keys())}


# OIDC Endpoints


@settings_bp.get("/oidc-settings/", response_model=OidcSettingsModel)
async def get_oidc_settings(db: SessionDep):
    """Return the current OIDC settings, creating a default row if none exists."""
    settings = db.exec(select(OidcSettingsModel)).first()
    if not settings:
        settings = OidcSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.put("/oidc-settings/", response_model=OidcSettingsModel)
async def update_oidc_settings(
    settings_in: OidcSettingsModel,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Upsert OIDC settings from the admin UI."""
    settings = db.exec(select(OidcSettingsModel)).first()
    if not settings:
        settings = OidcSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        settings_data = settings_in.dict(exclude_unset=True, exclude={"id"})
        for key, value in settings_data.items():
            setattr(settings, key, value)
        db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


@settings_bp.get("/audio-settings/", response_model=AudioSettingsModel)
async def get_audio_settings(db: SessionDep):
    """Return current audio download settings, creating a default row if none."""
    settings = db.exec(select(AudioSettingsModel)).first()
    if not settings:
        settings = AudioSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


_ALLOWED_AUDIO_FORMATS = {"mp3", "wav", "flac", "ogg"}
_ALLOWED_AUDIO_BITRATES = {
    "32k",
    "48k",
    "64k",
    "96k",
    "128k",
    "160k",
    "192k",
    "256k",
    "320k",
}


@settings_bp.put("/audio-settings/", response_model=AudioSettingsModel)
async def update_audio_settings(
    settings_in: AudioSettingsModel,
    db: SessionDep,
    _: User = Depends(_require_admin),
):
    """Upsert audio download settings from the admin UI."""
    if (
        settings_in.audio_format is not None
        and settings_in.audio_format not in _ALLOWED_AUDIO_FORMATS
    ):
        raise HTTPException(
            status_code=422,
            detail=f"audio_format muss einer von {sorted(_ALLOWED_AUDIO_FORMATS)} sein",
        )
    if (
        settings_in.audio_bitrate is not None
        and settings_in.audio_bitrate not in _ALLOWED_AUDIO_BITRATES
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"audio_bitrate muss einer von {sorted(_ALLOWED_AUDIO_BITRATES)} sein"
            ),
        )
    if settings_in.auto_archive_days is not None and not (
        1 <= settings_in.auto_archive_days <= 3650
    ):
        raise HTTPException(
            status_code=422,
            detail="auto_archive_days muss zwischen 1 und 3650 liegen",
        )

    settings = db.exec(select(AudioSettingsModel)).first()
    if not settings:
        settings = AudioSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        settings_data = settings_in.dict(exclude_unset=True, exclude={"id"})
        for key, value in settings_data.items():
            setattr(settings, key, value)
        db.add(settings)
    db.commit()
    db.refresh(settings)
    get_settings_service().invalidate_cache()
    return settings
