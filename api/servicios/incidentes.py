"""Incidentes consolidados para el panel (V2). Solo lectura.

La base es la RPC ra_incidentes_snapshot_v2 de Emilia (incidentes con vínculos activos);
se completa con el nombre del punto (ra_catalogo_v2) y el conteo de vínculos activos.
"""
import logging

from pydantic import ValidationError

from api.esquemas import IncidentePanel, PuntoPanel
from contratos.modelos import EvaluacionNecesidades

logger = logging.getLogger("api.incidentes")

RPC_INCIDENTES = "ra_incidentes_snapshot_v2"
RPC_CATALOGO = "ra_catalogo_v2"
EVALUACION_INVALIDA = "La evaluación guardada no cumple el contrato; revisar antes de usarla."


def _lista(datos) -> list[dict]:
    # Una RPC que devuelve jsonb puede llegar como lista o, sin filas, como null.
    return datos if isinstance(datos, list) else []


def _puntos(db) -> dict[str, PuntoPanel]:
    catalogo = _lista(db.rpc(RPC_CATALOGO, {}).execute().data)
    return {
        str(p["punto_atencion_id"]): PuntoPanel(
            punto_atencion_id=p["punto_atencion_id"],
            nombre=p["nombre"],
            distrito=p.get("distrito"),
            corregimiento=p.get("corregimiento"),
        )
        for p in catalogo
    }


def _vinculados(db, ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    filas = (
        db.table("vinculos_reportes")
        .select("incidente_id")
        .is_("desvinculado_en", "null")
        .in_("incidente_id", ids)
        .execute()
        .data
    )
    conteo: dict[str, int] = {}
    for fila in filas:
        clave = str(fila["incidente_id"])
        conteo[clave] = conteo.get(clave, 0) + 1
    return conteo


def _evaluacion(fila: dict) -> tuple[EvaluacionNecesidades | None, list[str]]:
    pendientes = list(fila.get("pendientes_calculo") or [])
    guardada = fila.get("evaluacion_necesidad")
    if guardada is None:
        return None, pendientes
    try:
        return EvaluacionNecesidades.model_validate(guardada), pendientes
    except ValidationError:
        # Solo el ID: los detalles de validación podrían incluir datos del incidente.
        logger.warning("Evaluación inválida en el incidente %s", fila.get("incidente_id"))
        return None, [*pendientes, EVALUACION_INVALIDA]


def listar_incidentes(db) -> list[IncidentePanel]:
    """Incidentes con vínculos activos, del detectado más recientemente al más antiguo."""
    filas = _lista(db.rpc(RPC_INCIDENTES, {}).execute().data)
    if not filas:
        return []
    puntos = _puntos(db)
    vinculados = _vinculados(db, [str(f["incidente_id"]) for f in filas])
    incidentes = []
    for fila in filas:
        evaluacion, pendientes = _evaluacion(fila)
        punto_id = fila.get("punto_atencion_id")
        incidentes.append(
            IncidentePanel(
                incidente_id=fila["incidente_id"],
                ejecucion_id=fila["ejecucion_id"],
                version=fila["version"],
                origen=fila["origen"],
                sector_id=fila.get("sector_id"),
                punto_atencion_id=punto_id,
                punto=puntos.get(str(punto_id)) if punto_id else None,
                estado_validacion=fila["estado_validacion"],
                tipo_problema=fila.get("tipo_problema") or "desconocido",
                episodio_establecido=bool(fila.get("episodio_establecido")),
                periodo_inicio=fila["periodo_inicio"],
                periodo_fin=fila["periodo_fin"],
                primera_deteccion_en=fila["primera_deteccion_en"],
                confianza=fila.get("confianza"),
                conflictos=fila.get("conflictos") or [],
                faltantes=fila.get("faltantes") or [],
                requiere_revision_urgente=bool(fila.get("requiere_revision_urgente")),
                reportes_vinculados=vinculados.get(str(fila["incidente_id"]), 0),
                reportes_independientes=fila.get("reportes_independientes") or 0,
                evaluacion_necesidad=evaluacion,
                pendientes_calculo=pendientes,
            )
        )
    incidentes.sort(key=lambda i: i.primera_deteccion_en, reverse=True)
    return incidentes
