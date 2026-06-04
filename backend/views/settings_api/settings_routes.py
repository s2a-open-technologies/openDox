from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from backend.views.settings_api import settings_bp
from backend.components.sql.sql_engine import SessionDep
from backend.components.models.settings_model import WhisperSettingsModel
from backend.components.models.ldap_model import LdapSettingsModel
from backend.components.services.ldap import LdapService
from backend.components.services.settings_service import get_settings_service
from backend.components.services.asr_factory import reset_asr_backends
from backend.components.models.categories import Categories, CategoriesCreate, CategoriesRead
from backend.components.models.languages import Languages, LanguagesCreate, LanguagesRead
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
    
    # Update API-relevant fields
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
    
    db.add(settings)
    db.commit()
    db.refresh(settings)
    
    # Invalidate settings cache so services pick up changes
    get_settings_service().invalidate_cache()
    
    # Reset ASR backends to pick up new settings
    reset_asr_backends()
    
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
