"""Solo transcribe; la persistencia posterior reutiliza reportes/aclaraciones idempotentes."""
from api.errores_http import ErrorApi
from api.esquemas import AudioTranscrito
from api.servicios.reportes import _buscar
from api.servicios.aclaraciones import _remitente_existente
from agentes.gemini import ErrorIngesta
from contratos.errores import CodigoError


def transcribir(db, datos, crear_transcriptor):
    externo = f'{datos.chat_id}:{datos.message_id}'
    existente = _buscar(db,'reportes','texto,remitente_ref,fuente_texto',canal='telegram',mensaje_externo_id=externo)
    referencia = 'remitente_ref'
    fuente = 'fuente_texto'
    texto = 'texto'
    if existente is None:
        existente = _buscar(db,'aclaraciones','respuesta_texto,respuesta_remitente_ref,respuesta_fuente_texto',respuesta_externo_id=externo)
        referencia, fuente, texto = 'respuesta_remitente_ref','respuesta_fuente_texto','respuesta_texto'
    if existente is not None:
        remitente = _remitente_existente(db,datos.usuario_telegram_id)
        if remitente is None or str(existente.get(referencia)) != str(remitente):
            raise ErrorApi(CodigoError.SIN_PERMISO,'El mensaje pertenece a otra persona.')
        if existente.get(fuente) != 'transcripcion_audio' or not existente.get(texto):
            raise ErrorApi(CodigoError.CONTRATO_INVALIDO,'El mensaje ya fue recibido con otro formato.')
        return AudioTranscrito(texto=existente[texto])
    try:
        transcripcion = crear_transcriptor().transcribir(datos.audio_base64,datos.mime_type)
    except ErrorIngesta as error:
        raise ErrorApi(error.codigo,str(error),recuperable=error.recuperable) from None
    return AudioTranscrito(texto=transcripcion)
