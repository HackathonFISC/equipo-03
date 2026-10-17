"""Límites y validación de clips; no abre archivos ni conexiones."""
import base64
import binascii

MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_AUDIO_SEGUNDOS = 120
MAX_AUDIO_BASE64 = 4 * ((MAX_AUDIO_BYTES + 2) // 3)
MIMES_AUDIO = {'audio/ogg', 'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/flac'}


def decodificar_audio(valor, mime):
    try:
        datos = base64.b64decode(valor, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('El audio no tiene una codificación válida.') from None
    if not datos or len(datos) > MAX_AUDIO_BYTES:
        raise ValueError('El audio debe ocupar como máximo 2 MB.')
    valido = (
        (mime == 'audio/ogg' and datos.startswith(b'OggS'))
        or (mime in {'audio/mpeg','audio/mp3'} and (datos.startswith(b'ID3') or (len(datos)>1 and datos[0]==255 and datos[1]&224==224)))
        or (mime == 'audio/wav' and datos.startswith(b'RIFF') and datos[8:12]==b'WAVE')
        or (mime == 'audio/flac' and datos.startswith(b'fLaC'))
    )
    if not valido:
        raise ValueError('El archivo debe ser OGG, MP3, WAV o FLAC válido.')
    return datos
