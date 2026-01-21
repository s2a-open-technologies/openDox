from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.views.settings_api import settings_bp
from app.components.sql.sql_engine import SessionDep
from app.components.models.settings_model import WhisperSettingsModel
from app.components.models.ldap_model import LdapSettingsModel
from app.components.services.ldap import LdapService
from sqlmodel import select
import shutil
import os

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
    
    settings.model_size = settings_in.model_size
    settings.device = settings_in.device
    settings.compute_type = settings_in.compute_type
    
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings

# LDAP Endpoints

@settings_bp.get("/ldap-settings/", response_model=LdapSettingsModel)
async def get_ldap_settings(db: SessionDep):
    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        # Return empty/default
        return LdapSettingsModel(server_host="", server_port=389, base_dn="", user_dn="")
    return settings

@settings_bp.put("/ldap-settings/", response_model=LdapSettingsModel)
async def update_ldap_settings(settings_in: LdapSettingsModel, db: SessionDep):
    settings = db.exec(select(LdapSettingsModel)).first()
    if not settings:
        settings = LdapSettingsModel(**settings_in.dict(exclude={"id"}))
        db.add(settings)
    else:
        # Update existing
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
