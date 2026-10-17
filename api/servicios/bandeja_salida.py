"""Bandeja de salida de avisos (V4): llamadas a las RPC de la migración 0011.

La API no crea avisos (los crea Comunicación) ni cambia su estado por su cuenta: las RPC reservan el
siguiente aviso vigente y registran el resultado en una sola transacción. Un aviso que dejó de ser
vigente (plan invalidado, suscripción inactiva, litros distintos) lo cancela la RPC antes de entregarlo.
"""
import logging

from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import AvisoPorEnviar, ResultadoEnvio
from api.servicios.aclaraciones import _una_fila
from contratos.errores import CodigoError

logger = logging.getLogger("api.avisos")

RPC_RESERVAR = "ra_reservar_aviso"
RPC_REGISTRAR_ENVIO = "ra_registrar_envio_aviso"


def _respuesta_incompatible(rpc: str) -> ErrorApi:
    logger.error("La RPC %s devolvió una forma inesperada", rpc)
    return ErrorApi(
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
        "La base de datos respondió con un formato inesperado.",
        recuperable=False,
    )


def reservar(db, trabajador_id: str) -> AvisoPorEnviar | None:
    fila = _una_fila(db.rpc(RPC_RESERVAR, {"p_trabajador_id": trabajador_id}).execute().data)
    if fila is None:
        return None
    if fila is False:
        raise _respuesta_incompatible(RPC_RESERVAR)
    try:
        return AvisoPorEnviar.model_validate({**fila, "chat_id": int(fila["chat_id"])})
    except (KeyError, ValueError, TypeError, ValidationError):
        raise _respuesta_incompatible(RPC_RESERVAR) from None


def registrar_envio(db, aviso_id, datos: ResultadoEnvio) -> None:
    db.rpc(
        RPC_REGISTRAR_ENVIO,
        {
            "p_aviso_id": str(aviso_id),
            "p_trabajador_id": datos.trabajador_id,
            "p_estado": datos.estado,
            "p_proveedor_mensaje_id": datos.proveedor_mensaje_id,
            "p_error": datos.error,
        },
    ).execute()
