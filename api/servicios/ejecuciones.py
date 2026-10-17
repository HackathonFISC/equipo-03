"""Lectura del progreso de una ejecución y su traza (V2). Solo lectura."""
from uuid import UUID

from api.esquemas import EjecucionPanel, EventoPanel

COLUMNAS_EJECUCION = "ejecucion_id,reporte_id,estado,etapa,intentos,ultimo_error,creado_en,actualizado_en"
# Sin detalles, entrada_ids ni salida_ids: son internos de los agentes.
COLUMNAS_EVENTO = (
    "evento_id,agente,actor_tipo,decision,herramienta,resultado,duracion_ms,siguiente_estado,creado_en"
)


def obtener_ejecucion(db, ejecucion_id: UUID) -> EjecucionPanel | None:
    """Estado, etapa y eventos de la ejecución, del más antiguo al más reciente."""
    filas = (
        db.table("ejecuciones")
        .select(COLUMNAS_EJECUCION)
        .eq("ejecucion_id", str(ejecucion_id))
        .limit(1)
        .execute()
        .data
    )
    if not filas:
        return None
    fila = filas[0]
    eventos = (
        db.table("eventos")
        .select(COLUMNAS_EVENTO)
        .eq("ejecucion_id", str(ejecucion_id))
        .order("creado_en")
        .execute()
        .data
    )
    error = fila.get("ultimo_error")
    return EjecucionPanel(
        ejecucion_id=fila["ejecucion_id"],
        reporte_id=fila.get("reporte_id"),
        estado=fila["estado"],
        etapa=fila["etapa"],
        intentos=fila.get("intentos") or 0,
        # Solo el código: el mensaje del error no se expone al panel.
        error_codigo=error.get("codigo") if isinstance(error, dict) else None,
        creado_en=fila["creado_en"],
        actualizado_en=fila["actualizado_en"],
        eventos=[EventoPanel.model_validate(e) for e in eventos],
    )
