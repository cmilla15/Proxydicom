import os
from dotenv import load_dotenv
# AHORA IMPORTAMOS DESDE EL MÓDULO SEGURO Y SIN DEPENDENCIAS 'passwords'
from implementation.web.passwords import get_password_hash

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

class DicomSettings:
    PROXY_AET: str = os.getenv("PROXY_AET", "PYNETDICOM")
    PACS_HOST: str = os.getenv("PACS_HOST", "127.0.0.1")
    PACS_PORT: int = int(os.getenv("PACS_PORT", "104"))
    PACS_AET: str = os.getenv("PACS_AET", "ANY_SCP")
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret_key")
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    _admin_password_plain: str = os.getenv("ADMIN_PASSWORD", "password")
    ADMIN_PASSWORD_HASH: str = get_password_hash(_admin_password_plain)

settings = DicomSettings()
