"""Regresiones de evidencia, cantidades y fallos de proveedor; sin red."""
from unittest.mock import Mock
from uuid import UUID
import httpx
import pytest
from agentes import gemini
from agentes.gemini import ConfiguracionGemini, ErrorIngesta, ExtractorGemini
from agentes.ingesta import interpretar_reporte, procesar_ejecucion
from agentes.tests.test_ingesta import reporte, extraccion, extractor, filas


def interpretar(texto, horas, personas):
    r=reporte(); r.entrada.texto=texto
    x=extraccion(); x['evidencia_textual']=[texto]
    x['campos'].update(horas_sin_agua=horas, personas_afectadas=personas)
    return interpretar_reporte(r,extractor(x))


@pytest.mark.parametrize('expresion,horas',[('48 hrs',48),('48 hs',48),('48 h',48),
    ('2 días',48),('1 semana',168),('2 semanas',336),('medio día',12),('0,5 días',12)])
def test_unidades_de_duracion_comprobables(expresion,horas):
    r=interpretar(f'En P1 llevamos {expresion} sin agua. Hay 120 personas.',horas,120)
    assert r.reporte.interpretacion.campos.horas_sin_agua==horas
    assert r.siguiente_etapa=='territorial'


@pytest.mark.parametrize('texto,horas,personas,campo',[
 ('En P1 hay 120 personas y 48 horas sin agua.',120,120,'horas_sin_agua'),
 ('En P1 hay 120 personas y 48 horas sin agua.',48,48,'personas_afectadas'),
 ('En P1 somos 20 familias y llevamos 48 horas sin agua.',48,20,'personas_afectadas'),
 ('En P1 llevamos 48 horas sin agua y hay 1.5 personas.',48,5,'personas_afectadas'),
 ('En P1 llevamos -48 horas sin agua. Hay 120 personas.',48,120,'horas_sin_agua'),
 ('En P1 llevamos 24 horasExtra sin agua. Hay 120 personas.',24,120,'horas_sin_agua'),
 ('En P1 llevamos 1 semana sin agua. Hay 120 familias.',168,600,'personas_afectadas'),
 ('En P1 llevamos cuarenta horas sin agua. Hay 120 personas.',40,120,'horas_sin_agua'),
])
def test_cifra_no_respaldada_queda_null_y_pide_aclaracion(texto,horas,personas,campo):
    r=interpretar(texto,horas,personas)
    assert getattr(r.reporte.interpretacion.campos,campo) is None
    assert campo in r.reporte.interpretacion.faltantes
    assert r.evento.siguiente_estado=='espera_aclaracion'


def test_evidencia_y_declaraciones_recuperan_fragmento_original():
    r=reporte(); r.entrada.texto='En P1 falta agua. La INSTITUCIÓN  Ñandú tiene adultos mayores. Son 48 horas y 120 personas.'
    x=extraccion(); x.update(evidencia_textual=['la institucion ñandu tiene adultos mayores.'])
    x['campos'].update(institucion_declarada='institucion ñandu',vulnerabilidad_declarada='ADULTOS MAYORES')
    resultado=interpretar_reporte(r,extractor(x)).reporte.interpretacion
    assert resultado.evidencia_textual==['La INSTITUCIÓN  Ñandú tiene adultos mayores.']
    assert resultado.campos.institucion_declarada=='INSTITUCIÓN  Ñandú'
    assert resultado.campos.vulnerabilidad_declarada=='adultos mayores'


def test_normalizacion_no_admite_parafrasis_ni_union_entre_fuentes():
    r=reporte(); x=extraccion(); x['evidencia_textual']=['48 horas sin agua. Respuesta de aclaración: somos']
    with pytest.raises(ErrorIngesta):
        interpretar_reporte(r,extractor(x),aclaraciones=[dict(aclaracion_id='x',respuesta_texto='somos 120 personas')])


@pytest.mark.parametrize('contador,esperado',[(0,'espera_validacion'),(1,'espera_validacion'),(2,'espera_revision')])
def test_error_recuperable_tiene_presupuesto_persistido(contador,esperado):
    f=filas(); f['ejecucion']['reintentos_ingesta']=contador
    p=Mock(); p.tomar.return_value=f
    ex=Mock(); ex.extraer.side_effect=ErrorIngesta('proveedor_no_disponible','Error de conexión controlado.',True)
    procesar_ejecucion(UUID(f['ejecucion']['ejecucion_id']),p,ex)
    assert p.finalizar.call_args.kwargs['evento'].siguiente_estado==esperado
    ex.extraer.assert_called_once(); p.finalizar.assert_called_once()


def test_configuracion_erronea_se_deja_en_revision():
    f=filas(); p=Mock(); p.tomar.return_value=f
    ex=Mock(); ex.extraer.side_effect=gemini.ErrorConfiguracionGemini('Configuración de prueba inválida.')
    procesar_ejecucion(UUID(f['ejecucion']['ejecucion_id']),p,ex)
    assert p.finalizar.call_args.kwargs['evento'].siguiente_estado=='espera_revision'
    assert p.finalizar.call_args.kwargs['error'].recuperable


@pytest.mark.parametrize('status',[401,403,404])
def test_modelo_o_clave_rechazados_son_error_de_configuracion(status):
    ex=ExtractorGemini(ConfiguracionGemini('clave_ficticia'),transporte=httpx.MockTransport(
        lambda req: httpx.Response(status,json={'error':{'message':'PRIVADO'}})))
    with pytest.raises(gemini.ErrorConfiguracionGemini) as e:
        ex.extraer('Mensaje sintético')
    assert 'PRIVADO' not in str(e.value)


def test_preflight_modelo_no_envia_reportes():
    peticiones=[]
    def handler(req):
        peticiones.append(req)
        return httpx.Response(200,json={'name':'models/gemini-3.8-flash','supportedGenerationMethods':['generateContent']})
    ExtractorGemini(ConfiguracionGemini('clave_ficticia'),transporte=httpx.MockTransport(handler)).verificar_modelo()
    assert len(peticiones)==1 and peticiones[0].method=='GET' and not peticiones[0].content


def test_preflight_rechaza_modelo_sin_generatecontent():
    ex=ExtractorGemini(ConfiguracionGemini('clave_ficticia'),transporte=httpx.MockTransport(
        lambda req:httpx.Response(200,json={'supportedGenerationMethods':['embedContent']})))
    with pytest.raises(gemini.ErrorConfiguracionGemini): ex.verificar_modelo()


def test_falta_clave_es_configuracion_sin_reservar_reportes(monkeypatch,capsys):
    from orquestador import trabajador
    monkeypatch.setattr(gemini,'dotenv_values',lambda *a,**k:{})
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setattr('sys.argv',['trabajador','--una-vuelta'])
    db=Mock(); monkeypatch.setattr(trabajador,'get_supabase',db)
    assert trabajador.main()==1
    db.assert_not_called()
    assert 'GEMINI_API_KEY' in capsys.readouterr().out


def test_preflight_transitorio_reintenta_sin_tocar_cola_y_se_cachea(monkeypatch):
    from orquestador import trabajador
    monkeypatch.setattr('sys.argv',['trabajador','--una-vuelta'])
    monkeypatch.setattr(trabajador.ConfiguracionGemini,'cargar',lambda: ConfiguracionGemini('clave_ficticia'))
    ex=Mock(); ex.verificar_modelo.side_effect=[ErrorIngesta('proveedor_no_disponible','Transitorio.',True), None]
    monkeypatch.setattr(trabajador,'ExtractorGemini',lambda cfg:ex)
    db=Mock(); monkeypatch.setattr(trabajador,'get_supabase',lambda:db)
    seleccion=Mock(return_value=[]); monkeypatch.setattr(trabajador,'una_vuelta',seleccion)
    def bucle(vuelta,**kwargs):
        with pytest.raises(ErrorIngesta): vuelta()
        seleccion.assert_not_called(); assert not db.mock_calls
        assert vuelta()==[] and vuelta()==[]
        return 0
    monkeypatch.setattr(trabajador,'ejecutar_bucle',bucle)
    assert trabajador.main()==0
    assert ex.verificar_modelo.call_count==2 and seleccion.call_count==2


def test_configuracion_invalida_no_entra_en_backoff():
    from orquestador.trabajador import ejecutar_bucle
    vuelta=Mock(side_effect=gemini.ErrorConfiguracionGemini('Modelo de prueba inválido.'))
    esperar=Mock()
    assert ejecutar_bucle(vuelta,detener=lambda:False,esperar=esperar)==1
    vuelta.assert_called_once(); esperar.assert_not_called()
