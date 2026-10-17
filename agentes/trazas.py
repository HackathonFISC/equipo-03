"""Composición de trazas sin credenciales, prompts ni contenido ciudadano."""
from datetime import datetime, timezone
from uuid import UUID, uuid5

from contratos.estados import Agente, EstadoEjecucion
from contratos.modelos import EventoTraza, ReporteRegistrado


def traza_ingesta(reporte: ReporteRegistrado, *, intento_ref: str,
                 siguiente_estado: EstadoEjecucion, duracion_ms: int,
                 decision: str, resultado: str) -> EventoTraza:
    return EventoTraza(
        evento_id=uuid5(reporte.ejecucion_id, f'ingesta:{intento_ref}'),
        ejecucion_id=reporte.ejecucion_id, creado_en=datetime.now(timezone.utc), origen=reporte.origen,
        agente=Agente.INGESTA, decision=decision, herramienta='gemini.generateContent',
        entrada_ids=[reporte.reporte_id], salida_ids=[reporte.reporte_id],
        resultado=resultado, duracion_ms=max(0, duracion_ms), siguiente_estado=siguiente_estado,
    )
