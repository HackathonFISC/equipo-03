"""Validación acotada de fotos; no conserva archivos."""
import base64
import binascii

MAX_IMAGEN_BYTES = 5 * 1024 * 1024
MAX_IMAGEN_BASE64 = 4 * ((MAX_IMAGEN_BYTES + 2) // 3)


def decodificar_imagen(valor, mime):
    try:
        datos = base64.b64decode(valor, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('La foto no tiene una codificación válida.') from None
    if not datos or len(datos) > MAX_IMAGEN_BYTES:
        raise ValueError('La foto debe ocupar como máximo 5 MB.')
    if not ((mime == 'image/jpeg' and datos.startswith(b'\xff\xd8\xff')) or
            (mime == 'image/png' and datos.startswith(b'\x89PNG\r\n\x1a\n'))):
        raise ValueError('Envía una foto JPEG o PNG válida.')
    return datos
