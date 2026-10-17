"""Audio de Telegram: protegido con el secreto del bot; ninguna clave en el bot."""
import httpx
from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError
from api.dependencias import obtener_db, verificar_secreto_bot
from api.errores_http import ErrorApi
from api.esquemas import AudioTelegram, AudioTranscrito
from api.servicios.audio import transcribir
from agentes.transcripcion import TranscriptorGemini
from contratos.errores import CodigoError

router = APIRouter(prefix='/audio',tags=['audio'],dependencies=[Depends(verificar_secreto_bot)])


def obtener_transcriptor():
    # Carga diferida: un mensaje guardado no requiere otra llamada al proveedor.
    return TranscriptorGemini.cargar


@router.post('/transcribir',response_model=AudioTranscrito)
def transcribir_audio(datos: AudioTelegram, db=Depends(obtener_db), crear_transcriptor=Depends(obtener_transcriptor)):
    try:
        return transcribir(db,datos,crear_transcriptor)
    except (APIError,httpx.HTTPError):
        raise ErrorApi(CodigoError.PROVEEDOR_NO_DISPONIBLE,'No se pudo preparar la transcripción. Intenta más tarde o escribe el mensaje.',recuperable=True) from None
