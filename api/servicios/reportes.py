"""Persistencia de reportes (V1). Sin transacciones: cada paso es idempotente.

Orden: remitente -> destino (chat de origen) -> reporte -> ejecución pendiente.
Si un paso falla a medias,
reintentar el mismo mensaje repara lo que falte sin crear duplicados.
Convención de identidad: supabase/IDENTIDAD_REPORTES.md.
"""
import logging
from uuid import UUID

from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import (
    EntradaPanel,
    InterpretadoPanel,
    NuevoReporteTelegram,
    RegistradoPanel,
    ReporteListado,
    SeguimientoPanel,
)
from contratos.errores import CodigoError
from contratos.modelos import EntradaReporte, ExtraccionReporteLLM, ReporteRegistrado

logger = logging.getLogger("api.reportes")

CANAL = "telegram"
ORIGEN = "sintetico"  # D003: todos los reportes de V1 se guardan como sintéticos.
UNICA_VIOLACION = "23505"

# reportes.destino_origen_id llega con la migración de aclaraciones de Emilia (V2).
# Mientras no esté aplicada en Supabase, el destino se registra pero no se enlaza al reporte.
# Pasar a True solo después de aplicar esa migración.
GUARDAR_DESTINO_ORIGEN = False


def _buscar(db, tabla: str, columnas: str, **filtros) -> dict | None:
    consulta = db.table(tabla).select(columnas)
    for columna, valor in filtros.items():
        consulta = consulta.eq(columna, valor)
    filas = consulta.limit(1).execute().data
    return filas[0] if filas else None


def _insertar_o_buscar(db, tabla: str, fila: dict, buscar) -> tuple[dict, bool]:
    """Inserta; si otro proceso ganó la carrera (23505), devuelve la fila existente."""
    try:
        return db.table(tabla).insert(fila).execute().data[0], True
    except APIError as error:
        if error.code != UNICA_VIOLACION:
            raise
        existente = buscar()
        if existente is None:
            raise
        return existente, False


def _remitente(db, identificador: str) -> str:
    def buscar():
        return _buscar(
            db, "remitentes", "remitente_ref",
            canal=CANAL, identificador_externo=identificador,
        )

    existente = buscar()
    if existente is not None:
        return existente["remitente_ref"]
    fila, _ = _insertar_o_buscar(
        db, "remitentes",
        {"canal": CANAL, "identificador_externo": identificador},
        buscar,
    )
    return fila["remitente_ref"]


def _destino(db, chat_id: int, usuario_telegram_id: int, remitente_ref: str) -> str:
    """Busca o crea el chat de origen. Nunca modifica un destino existente.

    En Telegram, un chat privado tiene el mismo ID que su usuario: solo entonces el
    destino se asocia al remitente. Un grupo queda sin remitente, porque varias
    personas pueden escribir en él (acuerdo con Emilia para V2). Un destino nuevo
    queda sin autorizar: la autorización es para los avisos de V4, no para aclaraciones.
    """
    identificador = str(chat_id)

    def buscar():
        return _buscar(
            db, "destinos", "destino_id",
            canal=CANAL, identificador_externo=identificador,
        )

    existente = buscar()
    if existente is not None:
        return existente["destino_id"]
    privado = chat_id == usuario_telegram_id
    fila, _ = _insertar_o_buscar(
        db, "destinos",
        {
            "canal": CANAL,
            "identificador_externo": identificador,
            "remitente_ref": remitente_ref if privado else None,
        },
        buscar,
    )
    return fila["destino_id"]


def _reporte(
    db, remitente_ref: str, destino_id: str, mensaje_externo_id: str, texto: str
) -> tuple[dict, bool]:
    columnas = "reporte_id,remitente_ref,creado_en,texto"

    def buscar():
        return _buscar(
            db, "reportes", columnas,
            canal=CANAL, mensaje_externo_id=mensaje_externo_id,
        )

    existente = buscar()
    if existente is not None:
        fila, nuevo = existente, False
    else:
        fila, nuevo = _insertar_o_buscar(
            db, "reportes",
            {
                "remitente_ref": remitente_ref,
                "canal": CANAL,
                "mensaje_externo_id": mensaje_externo_id,
                "modalidad": "texto",
                "texto": texto,
                "origen": ORIGEN,
                **({"destino_origen_id": destino_id} if GUARDAR_DESTINO_ORIGEN else {}),
            },
            buscar,
        )
    if str(fila["remitente_ref"]) != str(remitente_ref):
        # No se reasigna el reporte ni se devuelven datos de otra persona.
        raise ErrorApi(
            CodigoError.CONTRATO_INVALIDO,
            "Este mensaje ya está registrado con otro remitente.",
        )
    return fila, nuevo


def _ejecucion(db, reporte_id: str) -> str:
    clave = f"ingesta:{reporte_id}"

    def buscar():
        return _buscar(db, "ejecuciones", "ejecucion_id", clave_idempotencia=clave)

    existente = buscar()
    if existente is not None:
        return existente["ejecucion_id"]
    fila, _ = _insertar_o_buscar(
        db, "ejecuciones",
        {"reporte_id": reporte_id, "origen": ORIGEN, "clave_idempotencia": clave},
        buscar,
    )
    return fila["ejecucion_id"]


def registrar_reporte_telegram(db, datos: NuevoReporteTelegram) -> tuple[ReporteRegistrado, bool]:
    """Guarda el reporte y su ejecución pendiente. Devuelve (registro, es_nuevo)."""
    mensaje_externo_id = f"{datos.chat_id}:{datos.message_id}"
    remitente_ref = _remitente(db, str(datos.usuario_telegram_id))
    destino_id = _destino(db, datos.chat_id, datos.usuario_telegram_id, remitente_ref)
    fila, nuevo = _reporte(db, remitente_ref, destino_id, mensaje_externo_id, datos.texto)
    ejecucion_id = _ejecucion(db, fila["reporte_id"])
    registrado = ReporteRegistrado(
        ejecucion_id=ejecucion_id,
        creado_en=fila["creado_en"],
        origen=ORIGEN,
        reporte_id=fila["reporte_id"],
        entrada=EntradaReporte(
            canal=CANAL,
            mensaje_externo_id=mensaje_externo_id,
            remitente_ref=UUID(str(remitente_ref)),
            modalidad="texto",
            texto=datos.texto,
        ),
    )
    return registrado, nuevo


def _leer_interpretacion(valor) -> ExtraccionReporteLLM | None:
    """Acepta ExtraccionReporteLLM o un ReporteInterpretado que la contenga."""
    if not isinstance(valor, dict):
        return None
    try:
        return ExtraccionReporteLLM.model_validate(valor.get("interpretacion", valor))
    except ValidationError:
        logger.warning("Una interpretación guardada no cumple el contrato; se muestra sin interpretar.")
        return None


def listar_reportes(db, limite: int) -> list[ReporteListado]:
    """Reportes más recientes primero, sin identificadores del remitente."""
    filas = (
        db.table("reportes")
        .select("reporte_id,canal,modalidad,texto,interpretacion,origen,creado_en,ejecuciones(ejecucion_id,estado,etapa)")
        .order("creado_en", desc=True)
        .limit(limite)
        .execute()
        .data
    )
    resultado = []
    for fila in filas:
        ejecuciones = fila.get("ejecuciones") or []
        ejecucion = ejecuciones[0] if ejecuciones else None
        interpretacion = _leer_interpretacion(fila.get("interpretacion"))
        resultado.append(
            ReporteListado(
                registrado=RegistradoPanel(
                    reporte_id=fila["reporte_id"],
                    ejecucion_id=ejecucion["ejecucion_id"] if ejecucion else None,
                    creado_en=fila["creado_en"],
                    origen=fila["origen"],
                    entrada=EntradaPanel(
                        canal=fila["canal"], modalidad=fila["modalidad"], texto=fila["texto"]
                    ),
                ),
                interpretado=InterpretadoPanel(interpretacion=interpretacion)
                if interpretacion
                else None,
                seguimiento=SeguimientoPanel(estado=ejecucion["estado"], etapa=ejecucion["etapa"])
                if ejecucion
                else None,
            )
        )
    return resultado
