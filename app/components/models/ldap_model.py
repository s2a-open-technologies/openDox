from typing import Optional
from sqlmodel import Field, SQLModel

class LdapSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    server_host: str
    server_port: int
    use_ssl: bool = False
    base_dn: str
    user_dn: str
    bind_user_dn: Optional[str] = None
    bind_user_password: Optional[str] = None
    cert_filename: Optional[str] = None
