import base64
import json
from unittest.mock import Mock
import httpx
import pytest
from agentes.gemini import ConfiguracionGemini, ErrorIngesta
from agentes.imagen import LectorImagenGemini
from contratos.modelos import ReporteRegistrado
from agentes.ingesta import interpretar_reporte
from pathlib import Path

IMAGEN=base64.b64encode(b'\xff\xd8\xffimagen').decode()
TEXTO='En Escuela El Coco llevamos 48 horas sin agua. Somos 120 personas.'


def proveedor(salida=None, finish='STOP', status=200, error=None):
    llamadas=[]
    def responder(p):
        llamadas.append(p)
        if error: raise error
        return httpx.Response(status,json={'candidates':[{'finishReason':finish,'content':{'parts':[
            {'thought':True,'text':'razonamiento no público'},
            {'text':json.dumps(salida if salida is not None else {'texto':TEXTO,'imagen_clara':True})}]}}]})
    return LectorImagenGemini(ConfiguracionGemini('clave-simulada'),transporte=httpx.MockTransport(responder)),llamadas


def test_imagen_inline_sin_clave_en_url_y_sin_pensamientos(caplog):
    p,llamadas=proveedor()
    assert p.analizar(IMAGEN,'image/jpeg')==TEXTO
    llamada=llamadas[0];body=json.loads(llamada.content)
    assert llamada.headers['x-goog-api-key']=='clave-simulada'
    assert 'clave-simulada' not in str(llamada.url)
    assert body['contents'][0]['parts'][0]['inlineData']=={'mimeType':'image/jpeg','data':IMAGEN}
    assert 'no infieras' in body['systemInstruction']['parts'][0]['text'].lower()
    assert IMAGEN not in caplog.text and TEXTO not in caplog.text


@pytest.mark.parametrize('salida,finish',[
    ({'texto':None,'imagen_clara':False},'STOP'),({'texto':'','imagen_clara':True},'STOP'),
    ({'texto':TEXTO,'imagen_clara':True},'MAX_TOKENS'),({'texto':TEXTO,'imagen_clara':'false'},'STOP'),
    ({'texto':'x'*2501,'imagen_clara':True},'STOP'),({'texto':TEXTO,'imagen_clara':True},'SAFETY')])
def test_imagen_incierto_no_se_convierte_en_reporte(salida,finish):
    p,_=proveedor(salida,finish)
    with pytest.raises(ErrorIngesta): p.analizar(IMAGEN,'image/jpeg')


@pytest.mark.parametrize('codigo',[403,429,500])
def test_fallo_seguro_sin_reintentar(codigo):
    p,llamadas=proveedor(status=codigo)
    with pytest.raises(ErrorIngesta) as e: p.analizar(IMAGEN,'image/jpeg')
    assert 'clave-simulada' not in str(e.value) and len(llamadas)==1


def test_timeout_no_reintenta():
    p,llamadas=proveedor(error=httpx.ReadTimeout('simulado'))
    with pytest.raises(ErrorIngesta): p.analizar(IMAGEN,'image/jpeg')
    assert len(llamadas)==1




def test_ingesta_conserva_evidencia_de_foto_y_faltantes():
    from contratos.modelos import ExtraccionReporteLLM
    base=ReporteRegistrado.model_validate_json((Path(__file__).resolve().parents[2]/'contratos/ejemplos/reporte_registrado.json').read_text())
    texto='Descripción automática: tubería con agua visible.'
    base=base.model_copy(update={'entrada':base.entrada.model_copy(update={
        'texto':texto,'fuente_texto':'descripcion_imagen'})})
    extractor=Mock()
    extractor.extraer.return_value=ExtraccionReporteLLM(resumen='Posible fuga',ubicacion_declarada=None,
        campos={'tipo_problema':'otro'},evidencia_textual=[texto],faltantes=['ubicacion'],
        requiere_aclaracion=True,fuera_de_alcance=False)
    salida=interpretar_reporte(base,extractor)
    assert salida.reporte.evidencias[0].tipo=='foto'
    assert 'no se conserva la foto original' in salida.reporte.evidencias[0].descripcion
    assert salida.reporte.interpretacion.campos.personas_afectadas is None
    assert salida.reporte.interpretacion.campos.horas_sin_agua is None
    assert salida.reporte.interpretacion.requiere_aclaracion
