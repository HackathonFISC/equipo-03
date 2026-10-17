"""Aprobación y rechazo de planes (V4): llamadas a las RPC de la migración 0003.

Toda la decisión ocurre dentro de la RPC, en una transacción: permisos, versión vigente, entradas
sin cambios, verificación y bloqueos reconocidos. Aquí solo se traducen sus errores a los códigos
de dominio de D003; el usuario siempre es el del token verificado.
"""
import logging
from uuid import UUID

from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import AprobarPlan, RechazarPlan, ResultadoPlan
from api.servicios.aclaraciones import _una_fila
from contratos.errores import CodigoError

logger = logging.getLogger("api.aprobacion")

RPC_APROBAR = "ra_aprobar_plan"
RPC_RECHAZAR = "ra_rechazar_plan"

# Prefijo del mensaje de la RPC -> (código de dominio, mensaje para la persona, campos).
ERRORES_RPC: dict[str, tuple[CodigoError, str, list[str]]] = {
    "sin_permiso": (CodigoError.SIN_PERMISO, "Solo un coordinador activo puede hacer esto.", []),
    "version_obsoleta": (
        CodigoError.VERSION_OBSOLETA,
        "El plan cambió desde que lo revisó. Recarga el plan y revísalo de nuevo.",
        [],
    ),
    "politica_no_activa": (CodigoError.POLITICA_NO_ACTIVA, "La política de este plan ya no está activa.", []),
    "plan_no_verificado": (
        CodigoError.PLAN_NO_VERIFICADO,
        "El plan no tiene una verificación válida o tiene bloqueos que una aprobación no puede levantar.",
        [],
    ),
    "cobertura_critica_pendiente": (
        CodigoError.COBERTURA_CRITICA_PENDIENTE,
        "Hay puntos críticos sin atender; el plan no se puede aprobar.",
        [],
    ),
    "plan_ya_resuelto": (
        CodigoError.VERSION_OBSOLETA,
        "Este plan ya fue resuelto (aprobado, rechazado o invalidado). Recarga la lista.",
        [],
    ),
    "bloqueos_sin_reconocer": (
        CodigoError.CONTRATO_INVALIDO,
        "Falta reconocer uno o más bloqueos del plan antes de aprobarlo.",
        ["bloqueos_reconocidos"],
    ),
    "contrato_invalido": (CodigoError.CONTRATO_INVALIDO, "La solicitud no corresponde a un plan existente.", ["cuerpo"]),
}
POR_SQLSTATE = {"42501": "sin_permiso", "40001": "version_obsoleta"}


def traducir_error(error: APIError) -> ErrorApi | None:
    """Error de dominio si la RPC rechazó con un código conocido; None si es otra falla de la base."""
    mensaje = str(getattr(error, "message", "") or "")
    prefijo = mensaje.split(":", 1)[0].strip() if ":" in mensaje else ""
    clave = prefijo if prefijo in ERRORES_RPC else POR_SQLSTATE.get(str(getattr(error, "code", "")))
    if clave is None:
        return None
    codigo, texto, campos = ERRORES_RPC[clave]
    return ErrorApi(codigo, texto, campos=list(campos))


def _llamar(db, rpc: str, parametros: dict) -> ResultadoPlan:
    try:
        fila = _una_fila(db.rpc(rpc, parametros).execute().data)
    except APIError as error:
        traducido = traducir_error(error)
        if traducido is None:
            raise
        raise traducido from None
    try:
        if not isinstance(fila, dict):
            raise ValueError
        return ResultadoPlan.model_validate(fila)
    except (ValueError, TypeError, ValidationError):
        logger.error("La RPC %s devolvió una forma inesperada", rpc)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La base de datos respondió con un formato inesperado.",
            recuperable=False,
        ) from None


def aprobar(db, usuario_id: UUID, plan_id: UUID, version: int, datos: AprobarPlan) -> ResultadoPlan:
    return _llamar(
        db,
        RPC_APROBAR,
        {
            "p_usuario_id": str(usuario_id),
            "p_plan_id": str(plan_id),
            "p_version": version,
            "p_datos_version": datos.datos_version,
            "p_politica_version": datos.politica_version,
            "p_motivo": datos.motivo,
            "p_bloqueos_reconocidos": datos.bloqueos_reconocidos,
        },
    )


def rechazar(db, usuario_id: UUID, plan_id: UUID, version: int, datos: RechazarPlan) -> ResultadoPlan:
    return _llamar(
        db,
        RPC_RECHAZAR,
        {"p_usuario_id": str(usuario_id), "p_plan_id": str(plan_id), "p_version": version, "p_motivo": datos.motivo},
    )
