"""Validación humana del lugar de un incidente (migración 0021, RPC ra_validar_lugar_v1).

La decisión ocurre dentro de la RPC, en una transacción: coordinador activo, versión vigente, punto con
ubicación, evidencia escrita y un evento de auditoría. Aquí solo se traducen sus errores a los códigos
de dominio; el usuario siempre es el del token verificado. Esta operación no toca el texto de Telegram.
"""
import logging
from uuid import UUID

from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import ResultadoLugar, ValidarLugar
from api.servicios.aclaraciones import _una_fila
from contratos.errores import CodigoError

logger = logging.getLogger("api.lugar")

RPC_VALIDAR_LUGAR = "ra_validar_lugar_v1"

# Prefijo del mensaje de la RPC -> (código de dominio, mensaje para la persona, campos).
ERRORES_RPC: dict[str, tuple[CodigoError, str, list[str]]] = {
    "sin_permiso": (CodigoError.SIN_PERMISO, "Solo un coordinador activo puede validar un lugar.", []),
    "version_obsoleta": (
        CodigoError.VERSION_OBSOLETA,
        "El incidente cambió desde que lo revisó. Actualiza la página y revisa de nuevo.",
        [],
    ),
    "lugar_ya_resuelto": (
        CodigoError.VERSION_OBSOLETA,
        "El lugar de este incidente ya fue resuelto. Actualiza la página.",
        [],
    ),
    "lugar_sin_punto": (
        CodigoError.DATOS_INSUFICIENTES,
        "Este incidente no tiene un punto de atención con ubicación y reportes vinculados que se pueda validar.",
        ["incidente_id"],
    ),
    "contrato_invalido": (
        CodigoError.CONTRATO_INVALIDO,
        "La solicitud no es válida: revisa la evidencia (10 a 2000 caracteres) y que el incidente exista.",
        ["evidencia"],
    ),
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


def validar_lugar(db, usuario_id: UUID, incidente_id: UUID, datos: ValidarLugar) -> ResultadoLugar:
    try:
        fila = _una_fila(
            db.rpc(
                RPC_VALIDAR_LUGAR,
                {
                    "p_usuario_id": str(usuario_id),
                    "p_incidente_id": str(incidente_id),
                    "p_version": datos.version_incidente,
                    "p_evidencia": datos.evidencia,
                },
            ).execute().data
        )
    except APIError as error:
        traducido = traducir_error(error)
        if traducido is None:
            raise
        raise traducido from None
    try:
        if not isinstance(fila, dict):
            raise ValueError
        return ResultadoLugar.model_validate(fila)
    except (ValueError, TypeError, ValidationError):
        logger.error("La RPC %s devolvió una forma inesperada", RPC_VALIDAR_LUGAR)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La base de datos respondió con un formato inesperado.",
            recuperable=False,
        ) from None
