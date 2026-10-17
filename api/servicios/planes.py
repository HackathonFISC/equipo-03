"""Planes guardados para el panel (V4). Solo lectura.

Lee planes, rutas y paradas de las tablas y completa el nombre del punto con el catálogo activo.
No calcula ni modifica nada: aprobar y rechazar están en servicios/aprobacion.py.
"""
import logging

from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import PlanPanel, RutaPanel, ParadaPanel
from api.servicios.incidentes import _puntos
from contratos.errores import CodigoError

logger = logging.getLogger("api.planes")

LIMITE = 20
COLUMNAS_PLAN = (
    "plan_id,version,ejecucion_id,estado,estado_solver,datos_version,politica_version,verificado,"
    "bloqueos_publicacion,no_atendidos,supuestos,aprobacion_id,origen,creado_en"
)
COLUMNAS_RUTA = "ruta_id,plan_id,version,vehiculo_id,salida_estimada,retorno_estimado"
COLUMNAS_PARADA = (
    "parada_id,ruta_id,plan_id,version,orden,punto_atencion_id,litros_asignados,"
    "llegada_estimada,inicio_descarga,fin_descarga,estado"
)


def _lista(datos) -> list[dict]:
    return datos if isinstance(datos, list) else []


def listar_planes(db, limite: int = LIMITE) -> list[PlanPanel]:
    """Las versiones de plan más recientes (todas las del mismo plan_id), la más nueva primero."""
    planes = _lista(
        db.table("planes").select(COLUMNAS_PLAN).order("creado_en", desc=True).limit(limite).execute().data
    )
    if not planes:
        return []
    ids = sorted({str(p["plan_id"]) for p in planes})
    rutas = _lista(db.table("rutas").select(COLUMNAS_RUTA).in_("plan_id", ids).execute().data)
    paradas = _lista(db.table("paradas").select(COLUMNAS_PARADA).in_("plan_id", ids).execute().data)
    puntos = _puntos(db) if paradas else {}

    paradas_por_ruta: dict[str, list[ParadaPanel]] = {}
    for fila in sorted(paradas, key=lambda f: f["orden"]):
        punto = puntos.get(str(fila["punto_atencion_id"]))
        paradas_por_ruta.setdefault(str(fila["ruta_id"]), []).append(
            ParadaPanel.model_validate({**fila, "punto": punto.model_dump() if punto else None})
        )
    rutas_por_plan: dict[tuple[str, int], list[RutaPanel]] = {}
    for fila in sorted(rutas, key=lambda f: str(f["salida_estimada"])):
        ruta = RutaPanel.model_validate({**fila, "paradas": paradas_por_ruta.get(str(fila["ruta_id"]), [])})
        rutas_por_plan.setdefault((str(fila["plan_id"]), int(fila["version"])), []).append(ruta)

    resultado = []
    for fila in planes:
        clave = (str(fila["plan_id"]), int(fila["version"]))
        try:
            resultado.append(PlanPanel.model_validate({**fila, "rutas": rutas_por_plan.get(clave, [])}))
        except ValidationError:
            # Solo el ID: el detalle podría incluir datos del plan.
            logger.error("Plan %s v%s no cumple el formato esperado", clave[0], clave[1])
            raise ErrorApi(
                CodigoError.PROVEEDOR_NO_DISPONIBLE,
                "Un plan guardado no tiene el formato esperado.",
                recuperable=False,
            ) from None
    return resultado
