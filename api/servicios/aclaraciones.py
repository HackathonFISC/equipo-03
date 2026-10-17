"""Llamadas a las RPC de aclaraciones de Emilia (V2, acuerdo D004).

FIRMAS PROVISIONALES: los nombres y parámetros de las RPC son la propuesta enviada a
Emilia. Si cambian en su migración, se ajustan aquí y en ningún otro archivo.
La API no cambia estados de ejecución: eso lo hacen las RPC en una sola transacción.
"""
import logging
from typing import get_args

from api.errores_http import ErrorApi
from api.esquemas import (
    AclaracionPorEnviar,
    ResultadoAclaracion,
    ResultadoEnvio,
    RespuestaDelBot,
    ResultadoRespuesta,
)
from contratos.errores import CodigoError
from contratos.modelos import Ubicacion

logger = logging.getLogger("api.aclaraciones")

CANAL = "telegram"
RPC_RESERVAR = "ra_reservar_aclaracion"
RPC_REGISTRAR_ENVIO = "ra_registrar_envio_aclaracion"
RPC_ACEPTAR_RESPUESTA = "ra_aceptar_respuesta_aclaracion"
RESULTADOS = set(get_args(ResultadoAclaracion))


def _respuesta_incompatible(rpc: str) -> ErrorApi:
    logger.error("La RPC %s devolvió una forma inesperada", rpc)
    return ErrorApi(
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
        "La base de datos respondió con un formato inesperado.",
        recuperable=False,
    )


def _una_fila(datos):
    """PostgREST puede devolver un objeto, una lista con uno, una lista vacía o null."""
    if datos is None or datos == []:
        return None
    if isinstance(datos, list):
        return datos[0] if len(datos) == 1 and isinstance(datos[0], dict) else False
    return datos if isinstance(datos, dict) else False


def _mensaje_original(mensaje_externo_id) -> int | None:
    """De "<chat_id>:<message_id>" saca el message_id; None si el formato no cuadra."""
    try:
        _, mensaje = str(mensaje_externo_id).rsplit(":", 1)
        valor = int(mensaje)
        return valor if valor > 0 else None
    except (ValueError, TypeError):
        return None


def reservar(db, trabajador_id: str) -> AclaracionPorEnviar | None:
    fila = _una_fila(db.rpc(RPC_RESERVAR, {"p_trabajador_id": trabajador_id}).execute().data)
    if fila is None:
        return None
    if fila is False:
        raise _respuesta_incompatible(RPC_RESERVAR)
    try:
        return AclaracionPorEnviar(
            aclaracion_id=fila["aclaracion_id"],
            pregunta=fila["pregunta"],
            campos_solicitados=fila.get("campos_solicitados", []),
            chat_id=int(fila["chat_id"]),
            mensaje_original_id=_mensaje_original(fila.get("mensaje_externo_id")),
        )
    except (KeyError, ValueError, TypeError):
        raise _respuesta_incompatible(RPC_RESERVAR) from None


def registrar_envio(db, aclaracion_id, datos: ResultadoEnvio) -> None:
    db.rpc(
        RPC_REGISTRAR_ENVIO,
        {
            "p_aclaracion_id": str(aclaracion_id),
            "p_trabajador_id": datos.trabajador_id,
            "p_estado": datos.estado,
            "p_proveedor_mensaje_id": datos.proveedor_mensaje_id,
            "p_error": datos.error,
        },
    ).execute()


def _remitente_existente(db, usuario_telegram_id: int) -> str | None:
    """Solo busca: una respuesta nunca crea remitentes."""
    filas = (
        db.table("remitentes")
        .select("remitente_ref")
        .eq("canal", CANAL)
        .eq("identificador_externo", str(usuario_telegram_id))
        .limit(1)
        .execute()
        .data
    )
    return filas[0]["remitente_ref"] if filas else None


def aceptar_respuesta(db, datos: RespuestaDelBot) -> ResultadoRespuesta:
    remitente_ref = _remitente_existente(db, datos.usuario_telegram_id)
    if remitente_ref is None:
        # Quien nunca reportó no puede ser el autor del reporte original.
        return ResultadoRespuesta(resultado="autor_distinto")
    ubicacion = None
    if datos.ubicacion is not None:
        ubicacion = Ubicacion(
            latitud=datos.ubicacion.latitud,
            longitud=datos.ubicacion.longitud,
            fuente="compartida",
            precision_metros=datos.ubicacion.precision_metros,
            representa_punto_atencion=None,  # Nunca valida un punto de entrega.
        ).model_dump(mode="json")
    fila = _una_fila(
        db.rpc(
            "ra_aceptar_respuesta_audio" if datos.fuente_texto == "transcripcion_audio" else RPC_ACEPTAR_RESPUESTA,
            {
                "p_chat_id": str(datos.chat_id),
                "p_pregunta_mensaje_id": str(datos.pregunta_mensaje_id),
                "p_respuesta_externo_id": f"{datos.chat_id}:{datos.message_id}",
                "p_remitente_ref": str(remitente_ref),
                "p_texto": datos.texto,
                "p_ubicacion": ubicacion,
            },
        ).execute().data
    )
    if not fila or fila.get("resultado") not in RESULTADOS:
        raise _respuesta_incompatible(RPC_ACEPTAR_RESPUESTA)
    return ResultadoRespuesta(resultado=fila["resultado"], ejecucion_id=fila.get("ejecucion_id"))
