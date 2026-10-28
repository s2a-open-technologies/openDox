"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
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
import re
from datetime import datetime, timezone
from typing import Any

import requests as _requests
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select

from backend.components.llm.llm_model import SummarizeModel, normalize_openai_base_url
from backend.components.models.audio_settings_model import AudioSettingsModel
from backend.components.models.categories import (
    Categories,
    CategoriesCreate,
    CategoriesListRead,
    CategoriesRead,
)
from backend.components.models.client_settings_model import (
    ClientConfig,
    ClientSettingsModel,
)
from backend.components.models.dictionary import (
    CategoryDictionaryLink,
    Dictionary,
    DictionaryCreate,
    DictionaryListRead,
    DictionaryRead,
    DictionaryUpdate,
)
from backend.components.models.languages import (
    Languages,
    LanguagesCreate,
    LanguagesRead,
)
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.oidc_model import OidcSettingsModel
from backend.components.models.session_settings_model import (
    SessionConfig,
    SessionSettingsModel,
)
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.user_model import (
    UI_LANGUAGES,
    RetentionRead,
    RetentionUpdate,
    UiLanguageRead,
    UiLanguageUpdate,
    User,
)
from backend.components.modules.api_errors import api_error
from backend.components.modules.env import env_or_file
from backend.components.modules.public_url import request_base_url
from backend.components.services import audio_storage, dictionary_service
from backend.components.services.asr_backends import DisabledBackend
from backend.components.services.asr_factory import (
    get_final_backend,
    get_live_backend,
    reset_asr_backends,
)
from backend.components.services.audit_service import audit, changed_fields, snapshot
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
        raise api_error(403, "admin_required", "Admin role required")
    return current_user


def _optional_user(request: Request, db: SessionDep) -> User | None:
    """Resolve the bearer-token user if there is a valid one, else None.

    For endpoints that must stay reachable without login (e.g. the desktop
    client reads ``live_backend`` before anyone signs in) but may expose more
    to privileged users. An invalid or expired token counts as anonymous.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db
        )
    except HTTPException:
        return None


def _require_secret_reader(current_user: User = Depends(get_current_user)) -> User:
    """Guard for settings GETs that carry secrets: admin, or demo viewer (redacted)."""
    if current_user.role not in ("admin", "demo_viewer"):
        raise api_error(403, "admin_required", "Admin role required")
    return current_user


def _audit_settings(
    db: SessionDep,
    request: Request,
    admin: User,
    key: str,
    before: dict[str, Any],
    row,
) -> None:
    """Audit a settings save by the names of the changed fields (no values).

    A save that changes nothing is not logged.
    """
    fields = changed_fields(before, snapshot(row))
    if fields:
        audit(
            db,
            f"settings.{key}.update",
            request=request,
            actor=admin,
            target_type="settings",
            target_id=key,
            details={"fields": fields},
        )


def _redact_secrets(settings, user: User | None, fields: tuple[str, ...]):
    """Return ``settings`` with ``fields`` blanked unless ``user`` is an admin.

    Works on a detached copy — the stored row is never modified.
    """
    if user is not None and user.role == "admin":
        return settings
    blank = {
        field: ("" if isinstance(getattr(settings, field), str) else None)
        for field in fields
    }
    return settings.model_copy(update=blank)


# Whisper Endpoints


@settings_bp.get("/whisper-settings/", response_model=WhisperSettingsModel)
async def get_whisper_settings(
    db: SessionDep, user: User | None = Depends(_optional_user)
):
    """Return the Whisper settings, creating defaults if missing.

    Readable without login (the recorder UIs need ``live_backend`` before
    sign-in), but the API keys are only included for admins.
    """
    settings = db.exec(select(WhisperSettingsModel)).first()
    if not settings:
        settings = WhisperSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return _redact_secrets(settings, user, ("live_api_key", "final_api_key"))


@settings_bp.put("/whisper-settings/", response_model=WhisperSettingsModel)
async def update_whisper_settings(
    settings_in: WhisperSettingsModel,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Update the Whisper settings and reset cached ASR backends."""
    settings = db.exec(select(WhisperSettingsModel)).first()
    before = snapshot(settings)
    if not settings:
        settings = WhisperSettingsModel()

    settings.live_backend = settings_in.live_backend
    settings.live_api_endpoint = settings_in.live_api_endpoint
    settings.live_api_key = settings_in.live_api_key

    settings.final_backend = settings_in.final_backend
    settings.final_api_endpoint = settings_in.final_api_endpoint
    settings.final_api_key = settings_in.final_api_key
    settings.final_api_model = settings_in.final_api_model

    settings.language = settings_in.language

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
    settings.final_beam_size = settings_in.final_beam_size

    settings.term_correction_enabled = settings_in.term_correction_enabled
    settings.term_correction_threshold = settings_in.term_correction_threshold

    _audit_settings(db, request, admin, "whisper", before, settings)
    db.add(settings)
    db.commit()
    db.refresh(settings)

    get_settings_service().invalidate_cache()
    reset_asr_backends()

    return settings


# LLM Endpoints


@settings_bp.get("/llm-settings/", response_model=LlmSettingsModel)
async def get_llm_settings(
    db: SessionDep, user: User = Depends(_require_secret_reader)
):
    """Return the LLM settings (admin; API keys blanked for demo viewers)."""
    settings = db.exec(select(LlmSettingsModel)).first()
    if not settings:
        settings = LlmSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return _redact_secrets(settings, user, ("llm_api_key", "sanitizer_api_key"))


@settings_bp.put("/llm-settings/", response_model=LlmSettingsModel)
async def update_llm_settings(
    settings_in: LlmSettingsModel,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Update the LLM settings and invalidate the settings cache."""
    settings = db.exec(select(LlmSettingsModel)).first()
    before = snapshot(settings)
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

    _audit_settings(db, request, admin, "llm", before, settings)
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
        raise api_error(400, "llm_endpoint_missing", "Kein LLM-Endpoint konfiguriert")
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
        return {
            "ok": False,
            "code": "asr_backend_disabled",
            "error": "Backend ist deaktiviert oder nicht konfiguriert",
        }

    ok = await asyncio.to_thread(asr_backend.health_check)
    if ok:
        model = getattr(asr_backend, "model", None)
        result = {"ok": True}
        if model:
            result["model"] = model
        return result
    return {
        "ok": False,
        "code": "asr_endpoint_unreachable",
        "error": "Endpoint nicht erreichbar",
    }


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
async def get_ldap_settings(
    db: SessionDep, user: User = Depends(_require_secret_reader)
):
    """Return the LDAP settings (admin; bind password blanked for demo viewers)."""
    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        return LdapSettingsModel(
            server_host="", server_port=389, base_dn="", user_dn=""
        )
    return _redact_secrets(settings, user, ("bind_user_password",))


@settings_bp.put("/ldap-settings/", response_model=LdapSettingsModel)
async def update_ldap_settings(
    settings_in: LdapSettingsModel,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Create or update the LDAP settings (admin only)."""
    settings = db.exec(select(LdapSettingsModel)).first()
    before = snapshot(settings)
    if not settings:
        settings = LdapSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        settings_data = settings_in.dict(exclude_unset=True, exclude={"id"})
        for key, value in settings_data.items():
            setattr(settings, key, value)
        db.add(settings)
    _audit_settings(db, request, admin, "ldap", before, settings)

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
    request: Request,
    db: SessionDep,
    file: UploadFile = File(...),
    admin: User = Depends(_require_admin),
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
        raise api_error(
            400, "certificate_not_pem", "Zertifikat muss eine PEM-Textdatei sein"
        )
    if not cert_text.strip():
        raise api_error(400, "certificate_empty", "Zertifikatsdatei ist leer")

    display_name = os.path.basename(file.filename or "certificate.pem")

    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        settings = LdapSettingsModel(
            server_host="", server_port=389, base_dn="", user_dn=""
        )
    settings.cert_data = cert_text
    settings.cert_filename = display_name
    audit(
        db,
        "settings.ldap.certificate_upload",
        request=request,
        actor=admin,
        target_type="settings",
        target_id="ldap",
        details={"filename": display_name},
    )
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


_PRIVILEGED_CATEGORY_ROLES = ("admin", "moderator", "demo_viewer")


def _validate_dictionary_ids(
    db: SessionDep, dictionary_ids: list[int], category_user_id: int | None
) -> None:
    """Check that dictionaries may be attached to a category of this scope.

    A global category takes global dictionaries only; a personal category
    takes global ones plus those owned by the category's owner.

    Raises:
        HTTPException: 404 for an unknown id, 400 for a scope mismatch.
    """
    for dictionary_id in dictionary_ids:
        dictionary = db.get(Dictionary, dictionary_id)
        if dictionary is None:
            raise api_error(404, "dictionary_not_found", "Dictionary not found")
        if dictionary.user_id is not None and (
            category_user_id is None or dictionary.user_id != category_user_id
        ):
            raise api_error(
                400,
                "dictionary_scope_mismatch",
                "A global category can only use global dictionaries",
            )


def _category_out(db: SessionDep, category: Categories, schema: type) -> Any:
    """Build a category response including its attached dictionary ids."""
    ids = dictionary_service.dictionary_ids_by_category(db, [category.id])
    return schema(**category.model_dump(), dictionary_ids=ids[category.id])


@settings_bp.post("/categories/", response_model=CategoriesRead)
async def create_category(
    category: CategoriesCreate,
    request: Request,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Create a global or personal category for the current user.

    Privileged roles create global categories unless they ask for
    ``scope="personal"`` (profile view); everyone else always gets a personal one.
    """
    data = category.model_dump()
    dictionary_ids = data.pop("dictionary_ids") or []
    scope = data.pop("scope")
    if current_user.role in _PRIVILEGED_CATEGORY_ROLES and scope != "personal":
        data["user_id"] = None
    else:
        data["user_id"] = current_user.id
        data.update(_LLM_OVERRIDE_DEFAULTS)
    _validate_dictionary_ids(db, dictionary_ids, data["user_id"])
    db_category = Categories(**data)
    db.add(db_category)
    db.flush()
    dictionary_service.set_category_dictionaries(db, db_category.id, dictionary_ids)
    if db_category.user_id is None:
        audit(
            db,
            "category.create",
            request=request,
            actor=current_user,
            target_type="category",
            target_id=db_category.id,
            details={"name": db_category.name},
        )
    db.commit()
    db.refresh(db_category)
    return _category_out(db, db_category, CategoriesRead)


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
    ids = dictionary_service.dictionary_ids_by_category(db, [c.id for c in categories])
    return [
        CategoriesListRead(**c.model_dump(), dictionary_ids=ids[c.id])
        for c in categories
    ]


@settings_bp.get("/categories/{category_id}", response_model=CategoriesListRead)
async def read_category(
    category_id: int,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Return a single category if the current user may see it."""
    category = db.get(Categories, category_id)
    if not category:
        raise api_error(404, "category_not_found", "Category not found")
    if (
        current_user.role != "admin"
        and category.user_id is not None
        and category.user_id != current_user.id
    ):
        raise api_error(404, "category_not_found", "Category not found")
    return _category_out(db, category, CategoriesListRead)


@settings_bp.put("/categories/{category_id}", response_model=CategoriesRead)
async def update_category(
    category_id: int,
    category: CategoriesCreate,
    request: Request,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Update a category with ownership and LLM-override checks."""
    db_category = db.get(Categories, category_id)
    if not db_category:
        raise api_error(404, "category_not_found", "Category not found")

    is_owner = (
        db_category.user_id is not None and db_category.user_id == current_user.id
    )
    if db_category.user_id is None:
        if current_user.role not in _PRIVILEGED_CATEGORY_ROLES:
            raise api_error(
                403, "moderator_required", "Moderator or admin role required"
            )
    elif not is_owner and current_user.role != "admin":
        raise api_error(
            403, "category_edit_forbidden", "Not authorized to edit this category"
        )

    category_data = category.model_dump(exclude_unset=True)
    # The scope is fixed at creation time.
    category_data.pop("scope", None)
    # Omitted = leave the attached dictionaries as they are.
    dictionary_ids = category_data.pop("dictionary_ids", None)
    is_privileged_editor = current_user.role in _PRIVILEGED_CATEGORY_ROLES
    if not is_privileged_editor or db_category.user_id is not None:
        category_data.update(_LLM_OVERRIDE_DEFAULTS)
    if not category_data.get("llm_api_key"):
        # GET responses never include the raw key, so an edit form that
        # didn't touch it would otherwise wipe the stored key on every save.
        category_data.pop("llm_api_key", None)

    before = snapshot(db_category)
    old_dictionary_ids = dictionary_service.dictionary_ids_by_category(
        db, [db_category.id]
    )[db_category.id]
    if dictionary_ids is not None:
        _validate_dictionary_ids(db, dictionary_ids, db_category.user_id)
        dictionary_service.set_category_dictionaries(db, db_category.id, dictionary_ids)
    db_category.sqlmodel_update(category_data)
    if db_category.user_id is None:
        fields = changed_fields(before, snapshot(db_category))
        if dictionary_ids is not None and sorted(dictionary_ids) != sorted(
            old_dictionary_ids
        ):
            fields.append("dictionary_ids")
        if fields:
            audit(
                db,
                "category.update",
                request=request,
                actor=current_user,
                target_type="category",
                target_id=db_category.id,
                details={"name": db_category.name, "fields": fields},
            )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return _category_out(db, db_category, CategoriesRead)


def _delete_links(db: SessionDep, column, value: int) -> None:
    """Delete category/dictionary links explicitly.

    The FKs cascade on PostgreSQL, but SQLite (tests) does not enforce them.
    """
    for link in db.exec(select(CategoryDictionaryLink).where(column == value)).all():
        db.delete(link)


@settings_bp.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    request: Request,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Delete a category with ownership checks."""
    category = db.get(Categories, category_id)
    if not category:
        raise api_error(404, "category_not_found", "Category not found")

    is_owner = category.user_id is not None and category.user_id == current_user.id
    if category.user_id is None:
        if current_user.role not in _PRIVILEGED_CATEGORY_ROLES:
            raise api_error(
                403, "moderator_required", "Moderator or admin role required"
            )
    elif not is_owner and current_user.role != "admin":
        raise api_error(
            403, "category_delete_forbidden", "Not authorized to delete this category"
        )

    _delete_links(db, CategoryDictionaryLink.category_id, category_id)
    if category.user_id is None:
        audit(
            db,
            "category.delete",
            request=request,
            actor=current_user,
            target_type="category",
            target_id=category_id,
            details={"name": category.name},
        )
    db.delete(category)
    db.commit()
    return {"ok": True}


# Dictionary Endpoints
#
# Term lists for the phonetic term correction. user_id=None = global, managed
# by admins/moderators (same roles as global categories); otherwise personal
# and visible to its owner ONLY — unlike personal categories, admins never see
# another user's dictionaries (users realistically enter names there). A
# global dictionary takes effect through the categories it is attached to; a
# personal one always applies to its owner's recordings, whatever the category.


def _get_visible_dictionary(
    db: SessionDep, dictionary_id: int, current_user: User
) -> Dictionary:
    """Return a dictionary the caller may see, else 404."""
    dictionary = db.get(Dictionary, dictionary_id)
    if dictionary is None or (
        dictionary.user_id is not None and dictionary.user_id != current_user.id
    ):
        raise api_error(404, "dictionary_not_found", "Dictionary not found")
    return dictionary


def _get_editable_dictionary(
    db: SessionDep, dictionary_id: int, current_user: User
) -> Dictionary:
    """Return a dictionary the caller may change, else 404/403."""
    dictionary = _get_visible_dictionary(db, dictionary_id, current_user)
    if (
        dictionary.user_id is None
        and current_user.role not in _PRIVILEGED_CATEGORY_ROLES
    ):
        raise api_error(403, "moderator_required", "Moderator or admin role required")
    return dictionary


def _dictionary_out(db: SessionDep, dictionary: Dictionary, with_terms: bool) -> Any:
    """Build a dictionary response with the ids of the categories using it."""
    category_ids = dictionary_service.category_ids_by_dictionary(db, [dictionary.id])
    fields = dict(
        id=dictionary.id,
        name=dictionary.name,
        user_id=dictionary.user_id,
        term_count=dictionary.term_count,
        updated_at=dictionary.updated_at,
        category_ids=category_ids[dictionary.id],
    )
    if with_terms:
        return DictionaryRead(
            **fields, terms=dictionary_service.parse_terms(dictionary.terms)
        )
    return DictionaryListRead(**fields)


def _audit_dictionary(
    db: SessionDep,
    request: Request,
    user: User,
    action: str,
    dictionary: Dictionary,
    **details: Any,
) -> None:
    """Audit a change to a global dictionary; personal ones are never logged."""
    if dictionary.user_id is not None:
        return
    audit(
        db,
        f"dictionary.{action}",
        request=request,
        actor=user,
        target_type="dictionary",
        target_id=dictionary.id,
        details={"name": dictionary.name, **details},
    )


def _normalized_terms(terms: list[str]) -> list[str]:
    """Normalize typed terms, mapping input errors to API errors."""
    try:
        return dictionary_service.normalize_terms(terms)
    except dictionary_service.DictionaryInputError as e:
        raise api_error(400, e.code, e.message, **e.params) from e


@settings_bp.get("/dictionaries/", response_model=list[DictionaryListRead])
async def list_dictionaries(
    db: SessionDep, current_user: User = Depends(get_current_user)
):
    """List the global dictionaries plus the caller's own, without terms."""
    dictionaries = db.exec(
        select(Dictionary)
        .where((Dictionary.user_id.is_(None)) | (Dictionary.user_id == current_user.id))
        .order_by(Dictionary.name)
    ).all()
    category_ids = dictionary_service.category_ids_by_dictionary(
        db, [d.id for d in dictionaries]
    )
    return [
        DictionaryListRead(
            id=d.id,
            name=d.name,
            user_id=d.user_id,
            term_count=d.term_count,
            updated_at=d.updated_at,
            category_ids=category_ids[d.id],
        )
        for d in dictionaries
    ]


@settings_bp.get("/dictionaries/{dictionary_id}", response_model=DictionaryRead)
async def read_dictionary(
    dictionary_id: int,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Return one dictionary including its terms."""
    dictionary = _get_visible_dictionary(db, dictionary_id, current_user)
    return _dictionary_out(db, dictionary, with_terms=True)


@settings_bp.post("/dictionaries/", response_model=DictionaryRead)
async def create_dictionary(
    payload: DictionaryCreate,
    request: Request,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Create a global (moderator/admin) or personal dictionary."""
    if (
        payload.scope == "global"
        and current_user.role not in _PRIVILEGED_CATEGORY_ROLES
    ):
        raise api_error(403, "moderator_required", "Moderator or admin role required")
    name = payload.name.strip()
    if not name:
        raise api_error(400, "dictionary_name_required", "Name is required")
    dictionary = Dictionary(
        name=name, user_id=None if payload.scope == "global" else current_user.id
    )
    dictionary_service.set_terms(dictionary, _normalized_terms(payload.terms or []))
    db.add(dictionary)
    db.flush()
    _audit_dictionary(
        db, request, current_user, "create", dictionary, terms=dictionary.term_count
    )
    db.commit()
    db.refresh(dictionary)
    return _dictionary_out(db, dictionary, with_terms=True)


@settings_bp.put("/dictionaries/{dictionary_id}", response_model=DictionaryRead)
async def update_dictionary(
    dictionary_id: int,
    payload: DictionaryUpdate,
    request: Request,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Rename a dictionary and/or replace its terms."""
    dictionary = _get_editable_dictionary(db, dictionary_id, current_user)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise api_error(400, "dictionary_name_required", "Name is required")
        dictionary.name = name
    if payload.terms is not None:
        dictionary_service.set_terms(dictionary, _normalized_terms(payload.terms))
    dictionary.updated_at = datetime.now(timezone.utc)
    _audit_dictionary(
        db, request, current_user, "update", dictionary, terms=dictionary.term_count
    )
    db.add(dictionary)
    db.commit()
    db.refresh(dictionary)
    return _dictionary_out(db, dictionary, with_terms=True)


@settings_bp.post(
    "/dictionaries/{dictionary_id}/upload", response_model=DictionaryListRead
)
async def upload_dictionary_terms(
    dictionary_id: int,
    request: Request,
    db: SessionDep,
    file: UploadFile = File(...),
    mode: str = Form("replace"),
    current_user: User = Depends(get_current_user),
):
    """Replace or extend a dictionary's terms from a .txt/.csv file.

    See ``dictionary_service`` for the accepted file format.
    """
    dictionary = _get_editable_dictionary(db, dictionary_id, current_user)
    if mode not in ("replace", "append"):
        raise api_error(400, "dictionary_upload_invalid", "Invalid upload mode")
    data = await file.read(dictionary_service.MAX_UPLOAD_BYTES + 1)
    try:
        uploaded = dictionary_service.parse_upload(file.filename or "", data)
        if mode == "append":
            uploaded = dictionary_service.normalize_terms(
                dictionary_service.parse_terms(dictionary.terms) + uploaded
            )
    except dictionary_service.DictionaryInputError as e:
        raise api_error(400, e.code, e.message, **e.params) from e
    dictionary_service.set_terms(dictionary, uploaded)
    dictionary.updated_at = datetime.now(timezone.utc)
    _audit_dictionary(
        db,
        request,
        current_user,
        "upload",
        dictionary,
        mode=mode,
        terms=dictionary.term_count,
    )
    db.add(dictionary)
    db.commit()
    db.refresh(dictionary)
    return _dictionary_out(db, dictionary, with_terms=False)


@settings_bp.delete("/dictionaries/{dictionary_id}")
async def delete_dictionary(
    dictionary_id: int,
    request: Request,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Delete a dictionary; it is detached from all categories."""
    dictionary = _get_editable_dictionary(db, dictionary_id, current_user)
    _delete_links(db, CategoryDictionaryLink.dictionary_id, dictionary_id)
    _audit_dictionary(db, request, current_user, "delete", dictionary)
    db.delete(dictionary)
    db.commit()
    return {"ok": True}


# UI language Endpoint — the caller's own preferred interface language only.


@settings_bp.get("/my-language/", response_model=UiLanguageRead)
async def get_my_language(current_user: User = Depends(get_current_user)):
    """Return the current user's UI language."""
    return UiLanguageRead(ui_language=current_user.ui_language)


@settings_bp.put("/my-language/", response_model=UiLanguageRead)
async def update_my_language(
    payload: UiLanguageUpdate,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Update the current user's UI language."""
    if payload.ui_language not in UI_LANGUAGES:
        raise HTTPException(status_code=422, detail="Unsupported UI language")
    current_user.ui_language = payload.ui_language
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UiLanguageRead(ui_language=current_user.ui_language)


# Retention Endpoint — the caller's own automatic deletion period only.


def _retention_out(db: SessionDep, user: User) -> RetentionRead:
    audio = db.exec(select(AudioSettingsModel)).first() or AudioSettingsModel()
    return RetentionRead(
        personal_days=user.auto_delete_days,
        global_enabled=audio.auto_delete_enabled,
        global_days=audio.auto_delete_days,
    )


@settings_bp.get("/my-retention/", response_model=RetentionRead)
async def get_my_retention(
    db: SessionDep, current_user: User = Depends(get_current_user)
):
    """Return the caller's retention and the global limit it must stay within."""
    return _retention_out(db, current_user)


@settings_bp.put("/my-retention/", response_model=RetentionRead)
async def update_my_retention(
    payload: RetentionUpdate,
    db: SessionDep,
    current_user: User = Depends(get_current_user),
):
    """Set (or with ``null`` clear) the caller's own, shorter retention."""
    current = _retention_out(db, current_user)
    if (
        payload.personal_days is not None
        and current.global_enabled
        and payload.personal_days > current.global_days
    ):
        raise api_error(
            400,
            "retention_exceeds_global",
            f"Höchstens {current.global_days} Tage erlaubt",
            max=current.global_days,
        )
    current_user.auto_delete_days = payload.personal_days
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _retention_out(db, current_user)


# Languages Endpoints
@settings_bp.post("/languages/", response_model=LanguagesRead)
async def create_language(
    language: LanguagesCreate,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Create a new language (admin only)."""
    db_language = Languages.model_validate(language)
    db.add(db_language)
    db.flush()
    audit(
        db,
        "language.create",
        request=request,
        actor=admin,
        target_type="language",
        target_id=db_language.id,
    )
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
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Update a language by ID (admin only)."""
    db_language = db.get(Languages, language_id)
    if not db_language:
        raise HTTPException(status_code=404, detail="Language not found")
    language_data = language.model_dump(exclude_unset=True)
    before = snapshot(db_language)
    db_language.sqlmodel_update(language_data)
    audit(
        db,
        "language.update",
        request=request,
        actor=admin,
        target_type="language",
        target_id=language_id,
        details={"fields": changed_fields(before, snapshot(db_language))},
    )
    db.add(db_language)
    db.commit()
    db.refresh(db_language)
    return db_language


@settings_bp.delete("/languages/{language_id}")
async def delete_language(
    language_id: int,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Delete a language by ID (admin only)."""
    language = db.get(Languages, language_id)
    if not language:
        raise HTTPException(status_code=404, detail="Language not found")
    audit(
        db,
        "language.delete",
        request=request,
        actor=admin,
        target_type="language",
        target_id=language_id,
    )
    db.delete(language)
    db.commit()
    return {"ok": True}


# Backup / Restore Endpoints

# Global settings rows in the backup, as (model, backup key).
_BACKUP_SINGLETONS: tuple[tuple[type, str], ...] = (
    (WhisperSettingsModel, "whisper"),
    (LlmSettingsModel, "llm"),
    (LdapSettingsModel, "ldap"),
    (OidcSettingsModel, "oidc"),
    (AudioSettingsModel, "audio"),
    (SessionSettingsModel, "session"),
    (ClientSettingsModel, "client"),
)

# Credentials never leave the server in a backup file, and a restore never
# writes them (an old backup would otherwise put back a rotated key). The
# admin enters them once on a new server.
_BACKUP_SECRET_FIELDS: dict[str, tuple[str, ...]] = {
    "whisper": ("live_api_key", "final_api_key"),
    "llm": ("llm_api_key", "sanitizer_api_key"),
    "ldap": ("bind_user_password", "cert_data", "cert_filename"),
    "oidc": ("client_secret",),
    "categories": ("llm_api_key",),
}


def _without_secrets(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``data`` without the credential fields of backup section ``key``."""
    secrets = _BACKUP_SECRET_FIELDS.get(key, ())
    return {k: v for k, v in data.items() if k not in secrets}


def _serialize_model(model, key: str) -> dict[str, Any]:
    """Serialize a settings row for the backup, without PK and credentials."""
    data = model.model_dump()
    data.pop("id", None)
    return _without_secrets(data, key)


def _export_all_settings(db: SessionDep) -> dict[str, Any]:
    """Collect all settings tables into a serializable dict.

    Args:
        db: Active database session.

    Returns:
        Dict with a "version" timestamp and a "settings" mapping, where each
        key is a table name and the value is either a single dict (singleton
        settings) or a list of dicts (list tables).
    """
    singletons = {}
    for model_cls, key in _BACKUP_SINGLETONS:
        row = db.exec(select(model_cls)).first()
        singletons[key] = _serialize_model(row, key) if row else None
    categories = db.exec(select(Categories)).all()
    languages = db.exec(select(Languages)).all()
    # Personal dictionaries stay out, like the User table; categories carry
    # their global dictionaries by name (ids change on restore) and their
    # personal ones by id (those rows survive a restore untouched).
    global_dictionaries = db.exec(
        select(Dictionary).where(Dictionary.user_id.is_(None))
    ).all()
    global_names = {d.id: d.name for d in global_dictionaries}
    links = dictionary_service.dictionary_ids_by_category(
        db, [c.id for c in categories]
    )

    def _category_entry(category: Categories) -> dict[str, Any]:
        ids = links[category.id]
        return {
            **_serialize_model(category, "categories"),
            "global_dictionaries": [global_names[i] for i in ids if i in global_names],
            "personal_dictionary_ids": [i for i in ids if i not in global_names],
        }

    return {
        "version": "1.1",
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "settings": {
            **singletons,
            "categories": [_category_entry(c) for c in categories],
            "languages": [_serialize_model(lang, "languages") for lang in languages],
            "dictionaries": [
                {
                    "name": d.name,
                    "terms": dictionary_service.parse_terms(d.terms),
                }
                for d in global_dictionaries
            ],
        },
    }


def _known_fields(model_cls: type, row_data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the model no longer has (fields removed since the backup)."""
    return {k: v for k, v in row_data.items() if k in model_cls.model_fields}


def _split_legacy_glossary(text: str | None) -> list[str]:
    """Split a pre-dictionary free-text glossary (comma/semicolon/newline)."""
    if not text:
        return []
    return [t for t in re.split(r"[,;\n]+", text) if len(t.strip()) >= 3]


def _import_all_settings(db: SessionDep, data: dict[str, Any]) -> None:
    """Restore settings from a backup dict into the database.

    Overwrites singleton rows in place (matching by first row) and replaces
    all list-table rows (global dictionaries, categories, languages) wholesale;
    personal dictionaries are kept and re-attached to their categories.

    Args:
        db: Active database session.
        data: Backup dict as produced by ``_export_all_settings``.

    Raises:
        HTTPException: 400 if the backup structure is invalid.
    """
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise api_error(400, "backup_invalid_format", "Ungültiges Backup-Format")

    # --- Singleton settings (upsert first row, stored credentials kept) ---
    for model_cls, key in _BACKUP_SINGLETONS:
        row_data = settings.get(key)
        if not row_data or not isinstance(row_data, dict):
            continue
        row_data = _without_secrets(_known_fields(model_cls, row_data), key)
        if model_cls is WhisperSettingsModel and row_data.get("live_backend") == "api":
            # Near-live Whisper was removed; older backups still select it.
            row_data["live_backend"] = "disabled"
        existing = db.exec(select(model_cls)).first()
        if existing:
            for field, value in row_data.items():
                setattr(existing, field, value)
            db.add(existing)
        else:
            db.add(model_cls(**row_data))

    # --- Global dictionaries (replace wholesale; personal ones are kept) ---
    dictionaries_data = settings.get("dictionaries")
    global_by_name: dict[str, int] = {}
    if isinstance(dictionaries_data, list):
        for old in db.exec(
            select(Dictionary).where(Dictionary.user_id.is_(None))
        ).all():
            _delete_links(db, CategoryDictionaryLink.dictionary_id, old.id)
            db.delete(old)
        db.flush()
        for entry in dictionaries_data:
            if not isinstance(entry, dict) or not entry.get("name"):
                continue
            dictionary = Dictionary(name=entry["name"])
            dictionary_service.set_terms(
                dictionary,
                _normalized_terms([str(t) for t in entry.get("terms") or []]),
            )
            db.add(dictionary)
            db.flush()
            global_by_name[dictionary.name] = dictionary.id
    else:
        global_by_name = {
            d.name: d.id
            for d in db.exec(
                select(Dictionary).where(Dictionary.user_id.is_(None))
            ).all()
        }

    # --- Categories (replace wholesale, re-attach dictionaries) ---
    categories_data = settings.get("categories")
    if isinstance(categories_data, list):
        # The backup carries no per-category LLM key; keep the stored one of
        # the category with the same name and owner.
        kept_keys: dict[tuple[str, int | None], str] = {}
        for row in db.exec(select(Categories)).all():
            if row.llm_api_key:
                kept_keys[(row.name, row.user_id)] = row.llm_api_key
            _delete_links(db, CategoryDictionaryLink.category_id, row.id)
            db.delete(row)
        db.flush()
        for row_data in categories_data:
            if not isinstance(row_data, dict):
                continue
            category = Categories(
                **_without_secrets(_known_fields(Categories, row_data), "categories")
            )
            category.llm_api_key = kept_keys.get((category.name, category.user_id))
            db.add(category)
            db.flush()
            dictionary_ids = [
                global_by_name[name]
                for name in row_data.get("global_dictionaries") or []
                if name in global_by_name
            ]
            for dictionary_id in row_data.get("personal_dictionary_ids") or []:
                personal = db.get(Dictionary, dictionary_id)
                if personal is not None and personal.user_id == category.user_id:
                    dictionary_ids.append(dictionary_id)
            # Backups from before dictionaries carry the old free-text
            # glossary (or, older still, only whisper_prompt, which doubled
            # as the glossary): turn it into a dictionary of the category's
            # scope so term correction keeps working after the restore.
            if "global_dictionaries" not in row_data:
                legacy = row_data.get("glossary", row_data.get("whisper_prompt"))
                terms = _normalized_terms(_split_legacy_glossary(legacy))
                if terms:
                    dictionary = Dictionary(
                        name=category.name, user_id=category.user_id
                    )
                    dictionary_service.set_terms(dictionary, terms)
                    db.add(dictionary)
                    db.flush()
                    dictionary_ids.append(dictionary.id)
            dictionary_service.set_category_dictionaries(
                db, category.id, dictionary_ids
            )

    # --- Languages (replace wholesale) ---
    languages_data = settings.get("languages")
    if isinstance(languages_data, list):
        for row in db.exec(select(Languages)).all():
            db.delete(row)
        for row_data in languages_data:
            if isinstance(row_data, dict):
                db.add(Languages(**_known_fields(Languages, row_data)))

    db.commit()
    get_settings_service().invalidate_cache()
    reset_asr_backends()


@settings_bp.get("/backup/")
async def export_backup(
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Export all settings tables as a downloadable JSON file.

    Returns:
        JSON response with Content-Disposition attachment header. The
        filename includes the export timestamp.
    """
    from fastapi import Response

    data = _export_all_settings(db)
    audit(db, "backup.export", request=request, actor=admin, commit=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"opendox-backup-{stamp}.json"
    content = json.dumps(data, indent=2, ensure_ascii=False)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@settings_bp.post("/backup/restore/")
async def import_backup(
    request: Request,
    db: SessionDep,
    file: UploadFile = File(...),
    admin: User = Depends(_require_admin),
):
    """Restore settings from an uploaded JSON backup file.

    Args:
        request: Current request (audit log).
        db: Active database session.
        file: Uploaded JSON file produced by the export endpoint.
        admin: The admin restoring the backup.

    Returns:
        Dict with an "ok" flag and a summary of restored tables.
    """
    raw = await file.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise api_error(
            400, "backup_invalid_json", f"Kein gültiges JSON: {exc}", error=str(exc)
        )
    _import_all_settings(db, data)
    restored = list(data.get("settings", {}).keys())
    audit(
        db,
        "backup.restore",
        request=request,
        actor=admin,
        details={"sections": restored},
        commit=True,
    )
    return {"ok": True, "restored": restored}


# OIDC Endpoints


@settings_bp.get("/oidc-settings/", response_model=OidcSettingsModel)
async def get_oidc_settings(
    db: SessionDep, user: User = Depends(_require_secret_reader)
):
    """Return the OIDC settings (admin; client secret blanked for demo viewers)."""
    settings = db.exec(select(OidcSettingsModel)).first()
    if not settings:
        settings = OidcSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return _redact_secrets(settings, user, ("client_secret",))


@settings_bp.put("/oidc-settings/", response_model=OidcSettingsModel)
async def update_oidc_settings(
    settings_in: OidcSettingsModel,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Upsert OIDC settings from the admin UI."""
    settings = db.exec(select(OidcSettingsModel)).first()
    before = snapshot(settings)
    if not settings:
        settings = OidcSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        settings_data = settings_in.dict(exclude_unset=True, exclude={"id"})
        for key, value in settings_data.items():
            setattr(settings, key, value)
        db.add(settings)
    _audit_settings(db, request, admin, "oidc", before, settings)
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
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Upsert audio download settings from the admin UI."""
    if (
        settings_in.audio_format is not None
        and settings_in.audio_format not in _ALLOWED_AUDIO_FORMATS
    ):
        raise api_error(
            422,
            "audio_format_invalid",
            f"audio_format muss einer von {sorted(_ALLOWED_AUDIO_FORMATS)} sein",
            allowed=", ".join(sorted(_ALLOWED_AUDIO_FORMATS)),
        )
    if (
        settings_in.audio_bitrate is not None
        and settings_in.audio_bitrate not in _ALLOWED_AUDIO_BITRATES
    ):
        raise api_error(
            422,
            "audio_bitrate_invalid",
            f"audio_bitrate muss einer von {sorted(_ALLOWED_AUDIO_BITRATES)} sein",
            allowed=", ".join(sorted(_ALLOWED_AUDIO_BITRATES)),
        )
    if settings_in.auto_archive_days is not None and not (
        1 <= settings_in.auto_archive_days <= 3650
    ):
        raise api_error(
            422,
            "auto_archive_days_invalid",
            "auto_archive_days muss zwischen 1 und 3650 liegen",
        )
    if settings_in.auto_delete_days is not None and not (
        1 <= settings_in.auto_delete_days <= 3650
    ):
        raise api_error(
            422,
            "auto_delete_days_invalid",
            "auto_delete_days muss zwischen 1 und 3650 liegen",
        )

    settings = db.exec(select(AudioSettingsModel)).first()
    before = snapshot(settings)
    if not settings:
        settings = AudioSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        settings_data = settings_in.dict(exclude_unset=True, exclude={"id"})
        for key, value in settings_data.items():
            setattr(settings, key, value)
        db.add(settings)
    _audit_settings(db, request, admin, "audio", before, settings)
    db.commit()
    db.refresh(settings)
    get_settings_service().invalidate_cache()
    return settings


# Desktop client (openDox client: policy + installer distribution)

# The installers are built and signed outside the server and published as
# GitHub release assets under fixed names — ``releases/latest/download/<name>``
# then always resolves to the newest client, without a server update.
_DEFAULT_CLIENT_DOWNLOAD_BASE_URL = (
    "https://github.com/s2a-open-technologies/openDox-client/releases/latest/download"
)
_CLIENT_DOWNLOAD_FILES = {
    "windows_msi": "opendox-client-installer.msi",
    "windows_exe": "opendox-client-amd64-installer.exe",
    "macos_zip": "opendox-client-macos.zip",
}


def _get_or_create_client_settings(db) -> ClientSettingsModel:
    settings = db.exec(select(ClientSettingsModel)).first()
    if not settings:
        settings = ClientSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.get("/client-config/", response_model=ClientConfig)
async def get_client_config(db: SessionDep):
    """Return the desktop-client policy.

    Deliberately unauthenticated: the client fetches it at startup, before
    anyone has logged in. The content (program names, numbers) is not secret.
    """
    return ClientConfig.from_row(_get_or_create_client_settings(db))


@settings_bp.put("/client-config/", response_model=ClientConfig)
async def update_client_config(
    config_in: ClientConfig,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Save the desktop-client policy from the admin UI."""
    settings = _get_or_create_client_settings(db)
    before = snapshot(settings)
    config_in.apply_to(settings)
    _audit_settings(db, request, admin, "client", before, settings)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return ClientConfig.from_row(settings)


def _get_or_create_session_settings(db) -> SessionSettingsModel:
    settings = db.exec(select(SessionSettingsModel)).first()
    if not settings:
        settings = SessionSettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@settings_bp.get("/session-config/", response_model=SessionConfig)
async def get_session_config(
    db: SessionDep,
    _: User = Depends(get_current_user),
):
    """Return the web UI session policy (idle timeout) for any logged-in user."""
    settings = _get_or_create_session_settings(db)
    return SessionConfig(idle_timeout_minutes=settings.idle_timeout_minutes)


@settings_bp.put("/session-config/", response_model=SessionConfig)
async def update_session_config(
    config_in: SessionConfig,
    request: Request,
    db: SessionDep,
    admin: User = Depends(_require_admin),
):
    """Save the web UI session policy from the admin UI."""
    settings = _get_or_create_session_settings(db)
    before = snapshot(settings)
    settings.idle_timeout_minutes = config_in.idle_timeout_minutes
    _audit_settings(db, request, admin, "session", before, settings)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return SessionConfig(idle_timeout_minutes=settings.idle_timeout_minutes)


@settings_bp.get("/client-distribution/")
async def get_client_distribution(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Everything the admin UI needs to hand out the desktop client.

    ``server_url`` goes into the one-line ``settings.json`` the admin deploys
    next to the installer (``CLIENT_SERVER_URL`` overrides the URL derived
    from the request, e.g. when clients reach the server under another name).
    """
    if current_user.role not in ("admin", "demo_viewer"):
        raise api_error(403, "admin_required", "Admin role required")
    server_url = env_or_file("CLIENT_SERVER_URL", "") or request_base_url(request)
    download_base_url = (
        env_or_file("CLIENT_DOWNLOAD_BASE_URL", "") or _DEFAULT_CLIENT_DOWNLOAD_BASE_URL
    )
    return {
        "server_url": server_url.strip().rstrip("/"),
        "download_base_url": download_base_url.strip().rstrip("/"),
        "files": _CLIENT_DOWNLOAD_FILES,
    }
