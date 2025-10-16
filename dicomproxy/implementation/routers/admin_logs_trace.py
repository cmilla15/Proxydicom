import logging
from fastapi import APIRouter, Request, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

logger = logging.getLogger("dicomproxy.ui.trace")

router = APIRouter(prefix="/admin/dashboard/logs", tags=["Admin-Logs-Trace"])

class TraceEvent(BaseModel):
    event: str = Field(..., description="Tipo de evento: change|click|submit|navigate|other")
    field: Optional[str] = Field(None, description="Nombre del control (log_file|level|q|apply|go_current|...)")
    value: Optional[str] = Field(None, description="Valor asociado al evento (si aplica)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos opcionales")

@router.post("/trace")
async def trace_ui_event(
    payload: TraceEvent,
    request: Request,
    x_requested_with: Optional[str] = Header(default=None)
):
    """
    Recibe eventos de interacción desde la interfaz web y los escribe en el log del backend.
    """
    client = request.client.host if request.client else "-"
    referer = request.headers.get("referer", "-")
    agent = request.headers.get("user-agent", "-")
    xrw = x_requested_with or "-"

    logger.info(
        "UI TRACE | ip=%s | event=%s | field=%s | value=%s | referer=%s | agent=%s | xrw=%s | ctx=%s",
        client, payload.event, payload.field, payload.value or "-", referer, agent, xrw, payload.context or {}
    )
    return {"ok": True}
