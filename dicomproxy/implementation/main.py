from implementation import crud
from implementation import database
import sys, os, re, socket, zipfile, asyncio
from pathlib import Path
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# from implementation import crud, database
from implementation.config.logging_config import setup_logging, rotate_log_file
from implementation.config.settings import settings
from implementation.web import security, passwords
setup_logging()
BASE_PATH = Path(__file__).resolve().parent
LOGS_DIR = PROJECT_ROOT / "logs"
app = FastAPI(title="DICOM Proxy Service", version="1.0.8-stable")
app.mount("/static", StaticFiles(directory=BASE_PATH / "web/static"), name="static")
templates = Jinja2Templates(directory=BASE_PATH / "web/templates")
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token or (payload := security.decode_access_token(token)) is None:
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": "/admin"})
    return payload.get("sub")
@app.on_event("startup")
async def startup_event(): database.initialize_database()

# --- Endpoints ---
@app.get("/", tags=["Health Check"])
async def root(): return JSONResponse(content={"status": "ok"})
@app.get("/admin", response_class=HTMLResponse, tags=["Admin UI"])
async def admin_login_page(request: Request): return templates.TemplateResponse("login.html", {"request": request, "error": None})
@app.post("/admin/login", tags=["Admin UI"])
async def handle_admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.ADMIN_USER and passwords.verify_password(password, settings.ADMIN_PASSWORD_HASH):
        access_token = security.create_access_token(data={"sub": username})
        response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="lax")
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales incorrectas."})
@app.get("/admin/logout", tags=["Admin UI"])
async def handle_admin_logout():
    response = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response
@app.get("/admin/dashboard", response_class=HTMLResponse, tags=["Admin UI"])
async def admin_dashboard(request: Request, user: str = Depends(get_current_user)): return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})
@app.get("/admin/dashboard/config", response_class=HTMLResponse, tags=["Admin UI"])
async def admin_view_config(request: Request, user: str = Depends(get_current_user)):
    pacs_list = crud.get_all_pacs()
    proxy_config = crud.get_proxy_config()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80)); local_ip = s.getsockname()[0]
    except Exception: local_ip = "No se pudo determinar"
    return templates.TemplateResponse("config.html", {"request": request, "user": user, "pacs_list": pacs_list, "proxy_config": proxy_config, "local_ip": local_ip})
@app.get("/admin/pacs/new", response_class=HTMLResponse, tags=["Admin UI"])
async def admin_new_pacs_page(request: Request, user: str = Depends(get_current_user)):
    return templates.TemplateResponse("pacs_add.html", {"request": request, "user": user})
@app.post("/admin/pacs/add", tags=["Admin UI"])
async def admin_add_pacs(user: str = Depends(get_current_user), description: str = Form(...), aetitle: str = Form(...), ip_address: str = Form(...), port: int = Form(...)):
    crud.add_pacs_config(description, aetitle, ip_address, port)
    logger.info(f"Nuevo PACS añadido: {description} por '{user}'")
    return RedirectResponse(url="/admin/dashboard/config", status_code=status.HTTP_303_SEE_OTHER)

# --- ENDPOINT MODIFICADO ---
@app.post("/admin/logs/rotate", tags=["Admin UI"])
async def admin_rotate_logs(user: str = Depends(get_current_user)):
    success = rotate_log_file()
    message = "Nuevo archivo de log creado con éxito." if success else "Error al crear el nuevo log."
    query_params = urlencode({"toast": message, "toast_type": "success" if success else "error"})
    return RedirectResponse(url=f"/admin/dashboard/logs?{query_params}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/dashboard/logs", response_class=HTMLResponse, tags=["Admin UI"])
async def admin_view_logs(request: Request, user: str = Depends(get_current_user), file: str = Query(None), level: str = Query("ALL"), search: str = Query(None)):
    try:
        if not os.path.exists(LOGS_DIR): os.makedirs(LOGS_DIR)
        log_files = sorted([f for f in os.listdir(LOGS_DIR) if f.endswith(('.log', '.zip', '.gz'))], reverse=True)
        actual_log_name = "DicomProxy_Actual.log"
        if file and file in log_files: selected_file = file
        elif actual_log_name in log_files: selected_file = actual_log_name
        elif log_files: selected_file = log_files[0]
        else: selected_file = None
        lines, final_logs = [], []
        if selected_file:
            filepath = LOGS_DIR / selected_file
            try:
                if selected_file.endswith('.zip'):
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        log_filename_in_zip = zf.namelist()[0]
                        with zf.open(log_filename_in_zip, 'r') as f: lines = [line.decode('utf-8', errors='ignore') for line in f.readlines()]
                else:
                    with open(filepath, "r", encoding="utf-8", errors='ignore') as f: lines = f.readlines()
            except Exception as e: logger.error(f"Could not read log file {filepath}: {e}")
        def parse_log(l):
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \| (\w+)\s+\| (.*)", l)
            return {"timestamp": m.group(1), "level": m.group(2).upper(), "message": m.group(3)} if m else None
        all_parsed_logs = [log for line in lines if (log := parse_log(line))]
        if search:
            filtered_logs = []
            for log in all_parsed_logs:
                if search.lower() in log['message'].lower():
                    log['message'] = re.sub(f'({re.escape(search)})', r'<mark>\1</mark>', log['message'], flags=re.IGNORECASE)
                    filtered_logs.append(log)
            final_logs = filtered_logs
        else: final_logs = all_parsed_logs
        if level and level != "ALL": final_logs = [log for log in final_logs if log['level'] == level.upper()]
        final_logs.reverse()
        return templates.TemplateResponse("logs.html", {"request": request, "user": user, "log_files": log_files, "selected_file": selected_file, "selected_level": level, "search_query": search or "", "logs": final_logs[-1000:]})
    except Exception as e:
        logger.exception(f"CRITICAL ERROR in admin_view_logs: {e}")
        return templates.TemplateResponse("logs.html", {"request": request, "user": user, "logs": [], "log_files": [], "error": "Error crítico."})

async def get_local_config():
    db = database.SessionLocal()
    config = crud.get_local_config(db)
    db.close()
    return config

async def update_local_config(
    aetitle: str = Form(...),
    port: int = Form(...)
):
    db = database.SessionLocal()
    crud.update_local_config(db, aetitle=aetitle, port=port)
    updated = crud.get_local_config(db)
    db.close()
    return {"success": True, "config": updated}

# ==============================
# CONFIGURACIÓN LOCAL (AE TITLE / IP / PUERTO)
# ==============================

import sqlite3
import socket
from fastapi.responses import JSONResponse
from fastapi import Form

DB_PATH = "/opt/dicomproxy/dicomproxy.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

async def get_local_config():
    """
    Devuelve la configuración local (AE Title, IP, Puerto)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    row = cur.fetchone()
    conn.close()

    if row:
        return dict(row)
    else:
        return {"error": "No se encontró configuración local"}

async def update_local_config(
    aetitle: str = Form(...),
    port: int = Form(...)
):
    """
    Actualiza la configuración local (AE Title, IP, Puerto)
    """
    # Obtener IP real (no loopback)
    try:
        ip_local = socket.gethostbyname(socket.gethostname())
        if ip_local.startswith("127."):
            import subprocess
            ip_local = subprocess.getoutput("hostname -I | awk '{print $1}'").strip()
    except Exception:
        ip_local = "127.0.0.1"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE local_config SET aetitle=?, ip=?, port=? WHERE id=1;", (aetitle, ip_local, port))
    conn.commit()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    row = cur.fetchone()
    conn.close()

    return {"success": True, "config": dict(row)}


# ==============================
# CONFIGURACIÓN LOCAL (AE TITLE / IP / PUERTO)
# ==============================

import sqlite3
import socket
from fastapi.responses import JSONResponse
from fastapi import Form

DB_PATH = "/opt/dicomproxy/dicomproxy.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/config/local", response_class=JSONResponse)
async def get_local_config():
    """
    Devuelve la configuración local (AE Title, IP, Puerto)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    row = cur.fetchone()
    conn.close()

    if row:
        return dict(row)
    else:
        return {"error": "No se encontró configuración local"}

@app.post("/config/local", response_class=JSONResponse)
async def update_local_config(
    aetitle: str = Form(...),
    port: int = Form(...)
):
    """
    Actualiza la configuración local (AE Title, IP, Puerto)
    """
    # Obtener IP real (no loopback)
    try:
        ip_local = socket.gethostbyname(socket.gethostname())
        if ip_local.startswith("127."):
            import subprocess
            ip_local = subprocess.getoutput("hostname -I | awk '{print $1}'").strip()
    except Exception:
        ip_local = "127.0.0.1"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE local_config SET aetitle=?, ip=?, port=? WHERE id=1;", (aetitle, ip_local, port))
    conn.commit()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    row = cur.fetchone()
    conn.close()

    return {"success": True, "config": dict(row)}


# ==============================
# CONFIGURACIÓN LOCAL (AE TITLE / IP / PUERTO) — CON LOGGING DETALLADO
# ==============================

import sqlite3
import socket
import logging
from fastapi.responses import JSONResponse
from fastapi import Form

# Logger del módulo (usa configuración global)
logger = logging.getLogger(__name__)

DB_PATH = "/opt/dicomproxy/dicomproxy.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/config/local", response_class=JSONResponse)
async def get_local_config():
    """
    Devuelve la configuración local (AE Title, IP, Puerto)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    row = cur.fetchone()
    conn.close()

    if row:
        return dict(row)
    else:
        return {"error": "No se encontró configuración local"}

@app.post("/config/local", response_class=JSONResponse)
async def update_local_config(
    aetitle: str = Form(...),
    port: int = Form(...)
):
    """
    Actualiza la configuración local (AE Title, IP, Puerto)
    y registra el evento en los logs.
    """
    try:
        # Obtener IP real
        ip_local = socket.gethostbyname(socket.gethostname())
        if ip_local.startswith("127."):
            import subprocess
            ip_local = subprocess.getoutput("hostname -I | awk '{print $1}'").strip()
    except Exception:
        ip_local = "127.0.0.1"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE local_config SET aetitle=?, ip=?, port=? WHERE id=1;", (aetitle, ip_local, port))
    conn.commit()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1;")
    row = cur.fetchone()
    conn.close()

    # Registrar log detallado
    logger.info(f"Configuración local actualizada — AE Title: {aetitle}, Puerto: {port}, IP: {ip_local}")

    return {
        "success": True,
        "config": dict(row),
        "message": f"Configuración local actualizada — AE Title: {aetitle}, Puerto: {port}, IP: {ip_local}"
    }


# ======================================================
# CONFIGURACIÓN LOCAL DICOM + GESTIÓN DE PACS (FUNCIONAL)
# ======================================================

import sqlite3
import logging
from fastapi import Form
from fastapi.responses import JSONResponse, RedirectResponse

DB_PATH = "/opt/dicomproxy/dicomproxy.db"
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN LOCAL DICOM --- #
@app.get("/config/local", response_class=JSONResponse)
async def get_local_config():
    """Devuelve la configuración local del servidor DICOM"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, aetitle, ip, port FROM local_config LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "aetitle": row[1], "ip": row[2], "port": row[3]}
    return {"error": "No se encontró configuración local"}

@app.post("/config/local", response_class=JSONResponse)
async def update_local_config(aetitle: str = Form(...), ip: str = Form(...), port: int = Form(...)):
    """Actualiza la configuración local del servidor DICOM"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM local_config LIMIT 1")
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE local_config SET aetitle=?, ip=?, port=? WHERE id=?", (aetitle, ip, port, row[0]))
        logger.info(f"🔧 Configuración local actualizada — AE Title: {aetitle}, IP: {ip}, Puerto: {port}")
    else:
        cur.execute("INSERT INTO local_config (aetitle, ip, port) VALUES (?, ?, ?)", (aetitle, ip, port))
        logger.info(f"🆕 Configuración local creada — AE Title: {aetitle}, IP: {ip}, Puerto: {port}")

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Configuración local actualizada — AE Title: {aetitle}, IP: {ip}, Puerto: {port}",
        "config": {"aetitle": aetitle, "ip": ip, "port": port}
    }


# --- LISTAR CONFIGURACIÓN Y PACS --- #
@app.get("/admin/dashboard/config", response_class=HTMLResponse)
async def admin_view_config(request: Request, user: str = Depends(get_current_user)):
    """Vista de configuración completa"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, descripcion, aetitle, ip, port, activo FROM pacs_configs")
    pacs_list = cur.fetchall()
    conn.close()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT aetitle, ip, port FROM local_config LIMIT 1")
    row = cur.fetchone()
    conn.close()

    local_data = {
        "aetitle": row[0] if row else "DICOMWEBPROXY",
        "ip": row[1] if row else "127.0.0.1",
        "port": row[2] if row else 104
    }

    return templates.TemplateResponse(
        "config.html",
        {"request": request, "user": user, "pacs_list": pacs_list, "local_config": local_data}
    )


# --- NUEVO PACS --- #
@app.get("/admin/pacs/new", response_class=HTMLResponse)
async def admin_new_pacs_page(request: Request, user: str = Depends(get_current_user)):
    """Página para añadir un nuevo PACS"""
    return templates.TemplateResponse("pacs_add.html", {"request": request, "user": user})

@app.post("/admin/pacs/add")
async def admin_add_pacs(
    user: str = Depends(get_current_user),
    description: str = Form(...),
    aetitle: str = Form(...),
    ip_address: str = Form(...),
    port: int = Form(...)
):
    """Agrega un nuevo PACS a la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO pacs_configs (descripcion, aetitle, ip, port, activo) VALUES (?, ?, ?, ?, 0)",
        (description, aetitle, ip_address, port)
    )
    conn.commit()
    conn.close()

    logger.info(f"🩻 Nuevo PACS añadido — Descripción: {description}, AE Title: {aetitle}, IP: {ip_address}, Puerto: {port}, Usuario: {user}")

    return RedirectResponse(url="/admin/dashboard/config", status_code=303)


# --- GESTIÓN DE PACS: Activar/Desactivar y Eliminar --- #
from fastapi.responses import JSONResponse

@app.post("/admin/pacs/toggle", response_class=JSONResponse)
async def toggle_pacs_status(request: Request, user: str = Depends(get_current_user)):
    """Activa o desactiva un PACS (AJAX)"""
    import logging
    data = await request.json()
    pacs_id = data.get("id")
    log = logging.getLogger("dicomproxy")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT is_active FROM pacs_configs WHERE id=?", (pacs_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "msg": "PACS no encontrado"}

    new_status = 0 if row[0] == 1 else 1
    cur.execute("UPDATE pacs_configs SET is_active=? WHERE id=?", (new_status, pacs_id))
    conn.commit()
    conn.close()

    log.info(f"🔁 Estado del PACS ID {pacs_id} cambiado a {'Activo' if new_status else 'Inactivo'} por '{user}'")
    return {"success": True, "msg": f"PACS {'activado' if new_status else 'desactivado'} correctamente"}

@app.post("/admin/pacs/delete", response_class=JSONResponse)
async def delete_pacs(request: Request, user: str = Depends(get_current_user)):
    """Elimina un PACS (AJAX)"""
    import logging
    data = await request.json()
    pacs_id = data.get("id")
    log = logging.getLogger("dicomproxy")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM pacs_configs WHERE id=?", (pacs_id,))
    conn.commit()
    conn.close()

    log.info(f"🗑️ PACS eliminado (ID {pacs_id}) por '{user}'")
    return {"success": True, "msg": "PACS eliminado correctamente"}

# ======================================================
# ENDPOINT: /admin/logs/add  → utilizado por config.html
# ======================================================
from fastapi.responses import JSONResponse
import logging

# ======================================================
# ENDPOINT DEFINITIVO: /admin/logs/add
# ======================================================
from fastapi.responses import JSONResponse
import logging
from implementation.config.logging_config import setup_logging

# ======================================================
# ENDPOINT FINAL: /admin/logs/add  (sin reinicializar logger)
# ======================================================
from fastapi.responses import JSONResponse
import logging

@app.post("/admin/logs/add", response_class=JSONResponse)
async def add_admin_log(request: Request, user: str = Depends(get_current_user)):
    """
    Registra una acción del panel de administración (config/logs)
    directamente en el archivo de log activo.
    """
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        if not message:
            return {"success": False, "msg": "Mensaje vacío"}

        # Usar el logger global configurado al iniciar el sistema
        log = logging.getLogger("dicomproxy")
        if not log.handlers:
            # Seguridad: si no existen handlers, evita duplicar setup
            from implementation.config.logging_config import setup_logging
            setup_logging()

        log.info(f"🧩 [WEB ACTION] {message} — Usuario: {user}")
        return {"success": True, "msg": "Log registrado correctamente"}

    except Exception as e:
        logging.getLogger("dicomproxy").error(f"Error al registrar log desde interfaz: {e}")
        return {"success": False, "msg": f"Error al registrar log: {e}"}
