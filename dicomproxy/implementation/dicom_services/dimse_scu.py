from pynetdicom import AE, evt
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind
from pydicom.dataset import Dataset
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ahora importamos 'crud' para acceder a la base de datos
from implementation import crud
from implementation.config.settings import settings # Todavía lo usamos para el PROXY_AET

def perform_c_find(pacs_config: dict, query_params: dict):
    """
    Realiza una única operación C-FIND a un PACS específico.
    Esta función está diseñada para ser ejecutada en un hilo separado.
    """
    aet = pacs_config['aetitle']
    ip = pacs_config['ip_address']
    port = pacs_config['port']
    description = pacs_config['description']
    
    logger.info(f"Iniciando C-FIND en '{description}' ({aet}@{ip}:{port})")

    ae = AE(ae_title=settings.PROXY_AET)
    ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

    ds = Dataset()
    ds.QueryRetrieveLevel = "STUDY"
    if "PatientID" in query_params:
        ds.PatientID = query_params.get("PatientID")
    
    ds.PatientName = ""
    ds.StudyInstanceUID = ""
    ds.StudyDate = ""
    ds.StudyDescription = ""
    ds.ModalitiesInStudy = ""

    results = []
    assoc = ae.associate(ip, port, ae_title=aet)

    if assoc.is_established:
        logger.success(f"Asociación exitosa con '{description}'")
        responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind, query_model='S')
        for status, identifier in responses:
            if status and status.Status in (0xFF00, 0xFF01) and identifier:
                results.append(identifier)
        assoc.release()
    else:
        logger.error(f"Fallo al establecer asociación con '{description}'")

    logger.info(f"Búsqueda en '{description}' finalizada. Se encontraron {len(results)} resultados.")
    return results

def find_studies(query_params: dict):
    """
    Realiza una búsqueda C-FIND federada en todos los PACS activos en paralelo.
    """
    logger.info("Iniciando búsqueda C-FIND federada...")
    
    # 1. Obtener todos los PACS de la base de datos y filtrar los activos
    all_pacs = crud.get_all_pacs()
    active_pacs = [pacs for pacs in all_pacs if pacs['is_active']]

    if not active_pacs:
        logger.warning("No hay ningún PACS configurado como 'Activo'. No se realizará la búsqueda.")
        return []

    all_results = []
    # 2. Usar un ThreadPoolExecutor para lanzar las búsquedas en paralelo
    with ThreadPoolExecutor(max_workers=len(active_pacs)) as executor:
        # Creamos un futuro para cada búsqueda en un PACS activo
        future_to_pacs = {executor.submit(perform_c_find, pacs, query_params): pacs for pacs in active_pacs}
        
        # 3. Recopilar los resultados a medida que se completan
        for future in as_completed(future_to_pacs):
            pacs_description = future_to_pacs[future]['description']
            try:
                pacs_results = future.result()
                if pacs_results:
                    all_results.extend(pacs_results)
            except Exception as exc:
                logger.error(f"La búsqueda en '{pacs_description}' generó una excepción: {exc}")

    logger.success(f"Búsqueda federada completada. Total de resultados combinados: {len(all_results)}")
    return all_results

# La función move_instances no cambia, ya que se dirige a un PACS específico
# (Asumiremos que la imagen a mover ya fue encontrada y sabemos en qué PACS está,
# aunque esto es una simplificación que podríamos refinar más adelante).

def move_instances(study_uid, series_uid, instance_uid, move_destination_aet):
    # ... (código existente de C-MOVE)
    pass
