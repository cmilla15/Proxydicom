import asyncio
from pynetdicom import AE, evt, AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES
from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
from loguru import logger
import pydicom

async def handle_store(event, queue: asyncio.Queue):
    """
    Este es el manejador de eventos que se activa cuando el PACS nos envía una imagen (C-STORE).
    """
    try:
        # El dataset DICOM (la imagen) viene en el evento
        dataset = event.dataset
        dataset.file_meta = event.file_meta

        logger.success("¡Instancia DICOM recibida por el C-STORE SCP!")
        
        # Guardamos el dataset en un objeto BytesIO en memoria
        with pydicom.filebase.DicomBytesIO() as buffer:
            dataset.save_as(buffer, write_like_original=False)
            dicom_bytes = buffer.getvalue()
        
        # Ponemos los bytes de la instancia en la cola para que la petición web los recoja
        await queue.put(dicom_bytes)
        
        logger.info("Instancia puesta en la cola para ser enviada al cliente web.")
        
        # Devolvemos un estado de éxito al PACS
        return 0x0000
    except Exception as e:
        logger.error(f"Error en el manejador C-STORE: {e}")
        await queue.put(None) # Señal de error
        return 0xA700 # Out of resources

async def start_scp_server(queue: asyncio.Queue, port: int, aet: str):
    """
    Inicia un servidor SCP temporal en un puerto específico y con un AET dado.
    """
    ae = AE(ae_title=aet)
    
    # Añadir todos los contextos de almacenamiento para aceptar cualquier tipo de imagen
    ae.supported_contexts = AllStoragePresentationContexts
    
    # Definimos el manejador para el evento EVT_C_STORE
    handlers = [(evt.EVT_C_STORE, handle_store, [queue])]

    logger.info(f"Iniciando servidor C-STORE SCP temporal en el puerto {port} con AET {aet}")
    
    # Iniciar el servidor con un timeout de 15 segundos
    # Si no recibe nada en 15s, se apagará para no quedar colgado.
    try:
        server = await asyncio.wait_for(
            ae.start_server(('', port), block=False, evt_handlers=handlers),
            timeout=2.0 # Timeout para el arranque del servidor
        )
        
        # Esperar a que la cola reciba algo o se cumpla el timeout principal
        await asyncio.wait_for(queue.get(), timeout=15.0)
        # Una vez que la cola tiene un item, ya no necesitamos la tarea get(), así que la "des-obtenemos"
        queue.task_done()
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout esperando la instancia DICOM en el puerto {port}. El PACS no envió la imagen a tiempo.")
        await queue.put(None) # Poner un None en la cola para señalar el timeout
    except Exception as e:
        logger.error(f"Error inesperado en el servidor SCP: {e}")
        if not queue.full():
            await queue.put(None)
    finally:
        if 'server' in locals() and server.is_running:
            logger.info(f"Apagando servidor SCP del puerto {port}.")
            server.shutdown()

