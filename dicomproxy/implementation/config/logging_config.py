import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
from loguru import logger

file_handler_id = None
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
ACTIVE_LOG_FILE = LOGS_DIR / "DicomProxy_Actual.log"

def setup_logging():
    global file_handler_id
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="...") # Abreviado por simplicidad
    file_handler_id = logger.add(
        ACTIVE_LOG_FILE,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="50 MB",
        retention="30 days",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
    logger.info("✅ Sistema de logging configurado.")

def rotate_log_file():
    logger.info("Solicitud de rotación manual de log...")
    if file_handler_id is not None:
        logger.remove(file_handler_id)
    else:
        logger.warning("No se encontró un file_handler_id activo para detener.")

    if not ACTIVE_LOG_FILE.exists():
        logger.warning("No se encontró 'DicomProxy_Actual.log' para rotar. Se creará uno nuevo.")
        setup_logging()
        return True

    date_str = datetime.now().strftime("%Y%m%d")
    i = 1
    while True:
        archive_name = LOGS_DIR / f"DicomProxy_{date_str}_{i}.log"
        if not archive_name.exists():
            break
        i += 1
        
    try:
        shutil.move(ACTIVE_LOG_FILE, archive_name)
        logger.success(f"Log archivado como '{archive_name.name}'.")
    except Exception as e:
        logger.error(f"FALLO AL RENOMBRAR EL ARCHIVO DE LOG: {e}")
        setup_logging() # Reinicia el logging para no perder datos
        return False
    
    setup_logging()
    logger.info("Nuevo archivo 'DicomProxy_Actual.log' ha sido creado.")
    return True
