import base64
import json
from unittest.mock import Mock
import httpx
import pytest
from agentes.gemini import ConfiguracionGemini, ErrorIngesta
from agentes.transcripcion import TranscriptorGemini
from contratos.modelos import ReporteRegistrado
from agentes.ingesta import interpretar_reporte, reconstruir_reporte
from api.esquemas import AudioTelegram
from comun.audio import MAX_AUDIO_BYTES, decodificar_audio
from pathlib import Path

AUDIO=base64.b64encode(b'OggS'+b'\x00'*28+b'OpusHead').decode()
TEXTO='En Escuela El Coco llevamos 48 horas sin agua. Somos 120 personas.'


def proveedor(salida=None, finish='STOP', status=200, error=None):
    llamadas=[]
    def responder(p):
        llamadas.append(p)
        if error: raise error
        return httpx.Response(status,json={'candidates':[{'finishReason':finish,'content':{'parts':[
            {'thought':True,'text':'razonamiento no público'},
            {'text':json.dumps(salida if salida is not None else {'texto':TEXTO,'audio_claro':True})}]}}]})
    return TranscriptorGemini(ConfiguracionGemini('clave-simulada'),transporte=httpx.MockTransport(responder)),llamadas


def test_audio_inline_sin_clave_en_url_y_sin_pensamientos(caplog):
    p,llamadas=proveedor()
    assert p.transcribir(AUDIO,'audio/ogg')==TEXTO
    llamada=llamadas[0];body=json.loads(llamada.content)
    assert llamada.headers['x-goog-api-key']=='clave-simulada'
    assert 'clave-simulada' not in str(llamada.url)
    assert body['contents'][0]['parts'][0]['inlineData']=={'mimeType':'audio/ogg','data':AUDIO}
    assert 'transcribe' in body['systemInstruction']['parts'][0]['text'].lower()
    assert AUDIO not in caplog.text and TEXTO not in caplog.text


@pytest.mark.parametrize('salida,finish',[
    ({'texto':None,'audio_claro':False},'STOP'),({'texto':'','audio_claro':True},'STOP'),
    ({'texto':TEXTO,'audio_claro':True},'MAX_TOKENS'),({'texto':TEXTO,'audio_claro':'false'},'STOP'),
    ({'texto':'x'*4001,'audio_claro':True},'STOP'),({'texto':TEXTO,'audio_claro':True},'SAFETY')])
def test_audio_incierto_no_se_convierte_en_reporte(salida,finish):
    p,_=proveedor(salida,finish)
    with pytest.raises(ErrorIngesta): p.transcribir(AUDIO,'audio/ogg')


@pytest.mark.parametrize('codigo',[403,429,500])
def test_fallo_seguro_sin_reintentar(codigo):
    p,llamadas=proveedor(status=codigo)
    with pytest.raises(ErrorIngesta) as e: p.transcribir(AUDIO,'audio/ogg')
    assert 'clave-simulada' not in str(e.value) and len(llamadas)==1


def test_timeout_no_reintenta():
    p,llamadas=proveedor(error=httpx.ReadTimeout('simulado'))
    with pytest.raises(ErrorIngesta): p.transcribir(AUDIO,'audio/ogg')
    assert len(llamadas)==1


@pytest.mark.parametrize('contenido,mime',[(b'OggSdata','audio/ogg'),(b'ID3data','audio/mpeg'),
    (b'RIFF0000WAVEdata','audio/wav'),(b'fLaCdata','audio/flac')])
def test_formatos_admitidos(contenido,mime):
    assert decodificar_audio(base64.b64encode(contenido).decode(),mime)==contenido


def test_audio_grande_o_disfrazado_rechazado():
    for dato,mime in [(b'OggS'+b'a'*MAX_AUDIO_BYTES,'audio/ogg'),(b'no audio','audio/ogg')]:
        with pytest.raises(ValueError): decodificar_audio(base64.b64encode(dato).decode(),mime)
    with pytest.raises(ValueError): decodificar_audio('no base64','audio/ogg')


def test_evidencia_indica_transcripcion_no_audio_original():
    raiz=Path(__file__).resolve().parents[2]
    base=ReporteRegistrado.model_validate_json((raiz/'contratos/ejemplos/reporte_registrado.json').read_text())
    entrada=base.entrada.model_copy(update={'texto':TEXTO,'fuente_texto':'transcripcion_audio'})
    reporte=base.model_copy(update={'entrada':entrada})
    from contratos.modelos import ExtraccionReporteLLM
    extractor=Mock();extractor.extraer.return_value=ExtraccionReporteLLM(resumen='Falta agua',ubicacion_declarada='Escuela El Coco',
        campos={'horas_sin_agua':48.0,'personas_afectadas':120,'tipo_problema':'sin_suministro'},
        evidencia_textual=[TEXTO],faltantes=[],requiere_aclaracion=False,fuera_de_alcance=False)
    salida=interpretar_reporte(reporte,extractor)
    assert salida.siguiente_etapa=='territorial'
    assert salida.reporte.evidencias[0].tipo=='audio'
    assert 'no contra el audio original' in salida.reporte.evidencias[0].descripcion
    assert salida.reporte.interpretacion.campos.personas_afectadas==120


def test_aclaracion_audio_tiene_procedencia_separada():
    raiz=Path(__file__).resolve().parents[2]
    base=ReporteRegistrado.model_validate_json((raiz/'contratos/ejemplos/reporte_registrado.json').read_text())
    from contratos.modelos import ExtraccionReporteLLM
    from uuid import uuid4
    extractor=Mock();extractor.extraer.return_value=ExtraccionReporteLLM(resumen='Sin agua',ubicacion_declarada=None,
        campos={'tipo_problema':'sin_suministro'},evidencia_textual=[base.entrada.texto],
        faltantes=['ubicacion'],requiere_aclaracion=True,fuera_de_alcance=False)
    salida=interpretar_reporte(base,extractor,aclaraciones=[{'aclaracion_id':str(uuid4()),'respuesta_texto':TEXTO,'respuesta_fuente_texto':'transcripcion_audio'}])
    assert salida.reporte.evidencias[1].tipo=='audio'
