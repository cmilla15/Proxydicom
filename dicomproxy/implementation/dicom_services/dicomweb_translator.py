from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag
from loguru import logger

def _format_value(elem):
    """Formatea el valor del elemento DICOM para JSON."""
    if elem.VR == 'PN':
        # Los nombres de persona tienen una estructura especial
        return [{"Alphabetic": str(name)} for name in elem.value] if isinstance(elem.value, list) else [{"Alphabetic": str(elem.value)}]
    elif isinstance(elem.value, list):
        return elem.value
    elif elem.value is None:
        return []
    else:
        # pydicom a veces devuelve tipos no serializables (ej. DS)
        return [str(elem.value)]

def _dataset_to_dicomweb_dict(ds: Dataset) -> dict:
    """Convierte un único dataset de pydicom a un diccionario con formato DICOMweb."""
    dicomweb_dict = {}
    for elem in ds:
        tag_str = f"{elem.tag.group:04X}{elem.tag.element:04X}"
        
        if elem.VR == 'SQ':
            # Para secuencias, se procesa cada item recursivamente
            value = [_dataset_to_dicomweb_dict(item) for item in elem.value]
        else:
            value = _format_value(elem)

        dicomweb_dict[tag_str] = {
            "vr": elem.VR,
            "Value": value
        }
    return dicomweb_dict

def pydicom_to_dicomweb_json(datasets: list[Dataset]) -> list[dict]:
    """
    Convierte una lista de datasets de pydicom a una lista de diccionarios
    conformes con el estándar DICOMweb QIDO-RS.
    """
    if not datasets:
        return []
    
    logger.info(f"Traduciendo {len(datasets)} datasets al formato DICOMweb JSON.")
    try:
        return [_dataset_to_dicomweb_dict(ds) for ds in datasets]
    except Exception as e:
        logger.error(f"Error durante la traducción a DICOMweb JSON: {e}")
        return []

