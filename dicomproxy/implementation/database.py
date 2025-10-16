import sqlite3
from pathlib import Path
from loguru import logger

DATABASE_FILE = Path(__file__).resolve().parent.parent / "dicomproxy.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    logger.info("Verificando inicialización de la base de datos...")
    conn = get_db_connection()
    cursor = conn.cursor()
    # Tabla de PACS remotos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pacs_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aetitle TEXT NOT NULL, ip_address TEXT NOT NULL,
        port INTEGER NOT NULL, description TEXT, is_active BOOLEAN NOT NULL CHECK (is_active IN (0, 1))
    );
    """)
    # NUEVA TABLA: para la configuración local del proxy
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proxy_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    # Insertar valores por defecto si no existen
    cursor.execute("INSERT OR IGNORE INTO proxy_config (key, value) VALUES ('proxy_aet', 'DICOMPROXY')")
    cursor.execute("INSERT OR IGNORE INTO proxy_config (key, value) VALUES ('proxy_port', '11112')")
    conn.commit()
    conn.close()
    logger.info("Base de datos lista.")
