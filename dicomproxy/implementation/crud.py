from .database import get_db_connection
from sqlalchemy import text

def get_all_pacs():
    conn = get_db_connection()
    pacs_list = conn.execute('SELECT * FROM pacs_configs ORDER BY description').fetchall()
    conn.close()
    return pacs_list

def add_pacs_config(description: str, aetitle: str, ip_address: str, port: int):
    conn = get_db_connection()
    count = conn.execute("SELECT COUNT(id) FROM pacs_configs").fetchone()[0]
    is_active = 1 if count == 0 else 0
    conn.execute('INSERT INTO pacs_configs (description, aetitle, ip_address, port, is_active) VALUES (?, ?, ?, ?, ?)',
                 (description, aetitle, ip_address, port, is_active))
    conn.commit()
    conn.close()

# --- NUEVAS FUNCIONES ---
def get_proxy_config():
    """Obtiene la configuración local del proxy desde la BD."""
    conn = get_db_connection()
    config_rows = conn.execute('SELECT key, value FROM proxy_config').fetchall()
    conn.close()
    # Convierte la lista de filas en un diccionario
    return {row['key']: row['value'] for row in config_rows}

def update_proxy_config(proxy_aet: str, proxy_port: int):
    """Actualiza la configuración local del proxy."""
    conn = get_db_connection()
    conn.execute("UPDATE proxy_config SET value = ? WHERE key = 'proxy_aet'", (proxy_aet,))
    conn.execute("UPDATE proxy_config SET value = ? WHERE key = 'proxy_port'", (str(proxy_port),))
    conn.commit()
    conn.close()


def get_local_config(db):
    query = text("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    result = db.execute(query).fetchone()
    if result:
        return dict(result._mapping)
    else:
        return None

def update_local_config(db, aetitle: str, port: int, ip: str = None):
    if not ip:
        import socket
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except:
            ip = "127.0.0.1"
    query = text("UPDATE local_config SET aetitle=:aetitle, ip=:ip, port=:port WHERE id=1;")
    db.execute(query, {"aetitle": aetitle, "ip": ip, "port": port})
    db.commit()
