"""Fotos de Telegram: protegido con el secreto del bot; ninguna clave en el bot."""
import httpx
from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError
from api.dependencias import obtener_db, verificar_secreto_bot
from api.errores_http import ErrorApi
from api.esquemas import ImagenTelegram, ImagenInterpretada
from api.servicios.imagen import analizar
from agentes.imagen import LectorImagenGemini
from contratos.errores import CodigoError

router = APIRouter(prefix='/imagenes',tags=['imagenes'],dependencies=[Depends(verificar_secreto_bot)])


def obtener_lector():
    # Carga diferida: un mensaje guardado no requiere otra llamada al proveedor.
    return LectorImagenGemini.cargar


@router.post('/analizar',response_model=ImagenInterpretada)
def analizar_imagen(datos: ImagenTelegram, db=Depends(obtener_db), crear_lector=Depends(obtener_lector)):
    try:
        return analizar(db,datos,crear_lector)
    except (APIError,httpx.HTTPError):
        raise ErrorApi(CodigoError.PROVEEDOR_NO_DISPONIBLE,'No se pudo analizar la foto. Intenta más tarde o escribe el mensaje.',recuperable=True) from None
