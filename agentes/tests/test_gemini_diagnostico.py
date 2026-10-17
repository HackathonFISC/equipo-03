"""Diagnósticos específicos sin red ni contenido privado en trazas."""
import json
from unittest.mock import Mock
from uuid import UUID
import httpx
import pytest
from agentes.gemini import (ConfiguracionGemini, ErrorIngesta, ExtractorGemini,
    configuracion_extraccion, validar_respuesta_extraccion)
from agentes.tests.test_ingesta import extraccion, filas
from agentes.ingesta import procesar_ejecucion


def respuesta(texto):
    return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':texto}]}}]})


@pytest.mark.parametrize('modelo,thinking',[
 ('gemini-3.8-flash',{'thinkingLevel':'low'}),('gemini-3-flash-preview',{'thinkingLevel':'low'}),
 ('gemini-4-argon',{'thinkingLevel':'low'}),('gemini-2.5-flash',{'thinkingBudget':0}),
 ('gemini-2.5-flash-lite',{'thinkingBudget':0}),('gemini-2.5-pro',None),('modelo-personalizado',None)])
def test_configuracion_por_familia(modelo,thinking):
    c=configuracion_extraccion(modelo)
    assert c['maxOutputTokens']==4096 and c.get('thinkingConfig')==thinking
    assert c['responseJsonSchema']['title']=='ExtraccionReporteLLM'


@pytest.mark.parametrize('body,motivo',[
 ({},'gemini_sin_candidato'),({'candidates':[]},'gemini_sin_candidato'),
 ({'candidates':[None]},'gemini_sin_candidato'),
 ({'candidates':[{'finishReason':'MAX_TOKENS'}]},'gemini_max_tokens'),
 ({'candidates':[{'finishReason':'SAFETY'}]},'gemini_generacion_interrumpida'),
 ({'candidates':[{'finishReason':'SECRETO_DE_PROVEEDOR'}]},'gemini_generacion_interrumpida'),
 ({'candidates':[{'finishReason':'STOP'}]},'gemini_sin_contenido'),
 ({'candidates':[{'finishReason':'STOP','content':{'parts':[None]}}]},'gemini_estructura_invalida'),
 ({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':123}]}}]},'gemini_estructura_invalida'),
 ({'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'SECRETO_DE_PROVEEDOR'}]}}]},'gemini_sin_contenido')])
def test_fallos_especificos_sin_filtrar(body,motivo):
    with pytest.raises(ErrorIngesta) as exc:validar_respuesta_extraccion(httpx.Response(200,json=body))
    assert motivo in str(exc.value) and 'SECRETO_DE_PROVEEDOR' not in str(exc.value)


def test_json_http_y_json_del_modelo_distintos():
    with pytest.raises(ErrorIngesta,match='gemini_respuesta_no_json'):
        validar_respuesta_extraccion(httpx.Response(200,text='SECRETO_DE_PROVEEDOR'))
    with pytest.raises(ErrorIngesta,match='gemini_json_invalido'):
        validar_respuesta_extraccion(respuesta('{"resumen":"SECRETO_DE_PROVEEDOR'))


def test_campos_sin_valores_privados():
    x=extraccion();x.pop('ubicacion_declarada');x['SECRETO_DE_PROVEEDOR']='texto privado'
    with pytest.raises(ErrorIngesta,match='gemini_campos_invalidos') as exc:
        validar_respuesta_extraccion(respuesta(json.dumps(x)))
    assert exc.value.campos==['ubicacion_declarada']
    assert 'SECRETO' not in str(exc.value) and 'texto privado' not in str(exc.value)


def test_pensamientos_excluidos():
    r=httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[
        {'thought':True,'text':'SECRETO_DE_PROVEEDOR'}, {'text':json.dumps(extraccion())}]}}]})
    assert validar_respuesta_extraccion(r).campos.horas_sin_agua==48


def test_salida_cortada_no_se_reintenta():
    llamadas=[]
    def handler(request):
        llamadas.append(json.loads(request.content))
        return httpx.Response(200,json={'candidates':[{'finishReason':'MAX_TOKENS'}]})
    with pytest.raises(ErrorIngesta,match='gemini_max_tokens'):
        ExtractorGemini(ConfiguracionGemini('sintetica'),transporte=httpx.MockTransport(handler)).extraer('Prueba')
    assert len(llamadas)==1 and llamadas[0]['generationConfig']['thinkingConfig']=={'thinkingLevel':'low'}


def test_diagnostico_en_error_y_traza():
    f=filas();p=Mock();p.tomar.return_value=f;ex=Mock()
    ex.extraer.side_effect=ErrorIngesta('contrato_invalido','JSON incompatible [gemini_campos_invalidos].',campos=['campos'])
    procesar_ejecucion(UUID(f['ejecucion']['ejecucion_id']),p,ex)
    salida=p.finalizar.call_args.kwargs
    assert salida['error'].campos==['campos'] and 'gemini_campos_invalidos' in salida['evento'].resultado
