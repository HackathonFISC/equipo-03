"""Pruebas V1 sin red: extracción, evidencias, transiciones y adaptador de cierre."""
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx

from agentes.gemini import ConfiguracionGemini, ErrorIngesta, ExtractorGemini
from agentes.ingesta import PersistenciaIngesta, interpretar_reporte, procesar_ejecucion, reconstruir_reporte
from contratos.errores import CodigoError
from contratos.modelos import ExtraccionReporteLLM, ReporteRegistrado, ReporteInterpretado


TEXTO = 'En P1 llevamos 48 horas sin agua. Hay 120 personas afectadas.'


def reporte():
    return ReporteRegistrado(
        ejecucion_id=uuid4(), creado_en='2026-10-16T18:00:00-05:00', origen='sintetico', reporte_id=uuid4(),
        entrada=dict(canal='telegram', mensaje_externo_id='-10001:7', remitente_ref=uuid4(), modalidad='texto', texto=TEXTO),
    )


def extraccion():
    return dict(resumen='Reporte de falta de agua.', ubicacion_declarada='P1',
                campos=dict(horas_sin_agua=48, personas_afectadas=120,
                            vulnerabilidad_declarada=None, institucion_declarada=None, tipo_problema='sin_suministro'),
                evidencia_textual=[TEXTO], faltantes=[], requiere_aclaracion=False, fuera_de_alcance=False)


def extractor(salida=None):
    objeto = Mock()
    objeto.extraer.return_value = ExtraccionReporteLLM.model_validate(salida or extraccion())
    return objeto


def filas():
    r = reporte().model_dump(mode='json')
    return dict(ejecucion=dict(ejecucion_id=r['ejecucion_id'], reporte_id=r['reporte_id'], origen=r['origen']),
                reporte=dict(esquema_version='1.0', reporte_id=r['reporte_id'], creado_en=r['creado_en'],
                             origen=r['origen'], **r['entrada']))


class TestIngesta(unittest.TestCase):
    def test_texto_valido_conserva_contexto_y_produce_traza(self):
        r = reporte(); ex = extractor(); resultado = interpretar_reporte(r, ex)
        self.assertEqual(resultado.reporte.reporte_id, r.reporte_id)
        self.assertEqual(resultado.reporte.ejecucion_id, r.ejecucion_id)
        self.assertEqual(resultado.reporte.origen, r.origen)
        self.assertEqual(resultado.reporte.interpretacion.campos.personas_afectadas, 120)
        self.assertEqual(resultado.siguiente_etapa, 'territorial')
        self.assertEqual(resultado.evento.siguiente_estado, 'pendiente')
        self.assertEqual(resultado.evento.agente, 'ingesta')
        ex.extraer.assert_called_once_with(TEXTO)
        self.assertEqual(ReporteInterpretado.model_validate_json(resultado.reporte.model_dump_json()), resultado.reporte)

    def test_evidencia_la_compone_backend_y_referencia_original(self):
        r = reporte(); a = interpretar_reporte(r, extractor()); b = interpretar_reporte(r, extractor())
        self.assertEqual(a.reporte.evidencias[0].evidencia_id, b.reporte.evidencias[0].evidencia_id)
        self.assertIn(str(r.reporte_id), a.reporte.evidencias[0].referencia)
        self.assertEqual(a.reporte.evidencias[0].campos_respaldados, ['entrada.texto'])

    def test_datos_desconocidos_no_se_convierten_en_cero(self):
        r = reporte(); r.entrada.texto = 'Falta agua en P1.'
        x = extraccion(); x['campos']['horas_sin_agua'] = x['campos']['personas_afectadas'] = None
        x.update(evidencia_textual=[r.entrada.texto], faltantes=['duracion', 'poblacion'], requiere_aclaracion=True)
        resultado = interpretar_reporte(r, extractor(x))
        self.assertIsNone(resultado.reporte.interpretacion.campos.horas_sin_agua)
        self.assertEqual(resultado.evento.siguiente_estado, 'espera_aclaracion')
        self.assertEqual(resultado.siguiente_etapa, 'ingesta')

    def test_fuera_de_alcance_no_pasa_a_territorial(self):
        r = reporte(); r.entrada.texto = 'Hola, recomiéndame una película.'
        x = extraccion(); x.update(ubicacion_declarada=None, fuera_de_alcance=True, evidencia_textual=[])
        x['campos'].update(horas_sin_agua=None, personas_afectadas=None, tipo_problema='otro')
        resultado = interpretar_reporte(r, extractor(x))
        self.assertEqual(resultado.evento.siguiente_estado, 'completada')
        self.assertEqual(resultado.siguiente_etapa, 'terminada')

    def test_rechaza_citas_inventadas(self):
        x = extraccion(); x['evidencia_textual'] = ['Hay un hospital.']
        with self.assertRaises(ErrorIngesta): interpretar_reporte(reporte(), extractor(x))

    def test_rechaza_ubicacion_institucion_o_vulnerabilidad_inventadas(self):
        for campo in ['ubicacion_declarada','institucion_declarada','vulnerabilidad_declarada']:
            x = extraccion()
            if campo == 'ubicacion_declarada': x[campo] = 'Lugar inventado'
            else: x['campos'][campo] = 'Dato inventado'
            with self.subTest(campo=campo), self.assertRaises(ErrorIngesta):
                interpretar_reporte(reporte(), extractor(x))

    def test_cantidad_inventada_o_intercambiada_pide_aclaracion(self):
        for campo, valor in [('horas_sin_agua',999),('horas_sin_agua',120),('personas_afectadas',48)]:
            x = extraccion(); x['campos'][campo] = valor
            with self.subTest(campo=campo):
                resultado=interpretar_reporte(reporte(), extractor(x))
                self.assertIsNone(getattr(resultado.reporte.interpretacion.campos,campo))
                self.assertEqual(resultado.evento.siguiente_estado,'espera_aclaracion')

    def test_dias_numericos_se_convierten_a_horas(self):
        r = reporte(); r.entrada.texto = TEXTO.replace('48 horas','2 días')
        x = extraccion(); x['evidencia_textual'] = [r.entrada.texto]
        self.assertEqual(interpretar_reporte(r, extractor(x)).reporte.interpretacion.campos.horas_sin_agua,48)

    def test_rechaza_agua_sin_evidencia(self):
        x = extraccion(); x['evidencia_textual'] = []
        with self.assertRaises(ErrorIngesta): interpretar_reporte(reporte(), extractor(x))

    def test_rechaza_fuera_de_alcance_con_aclaracion(self):
        x = extraccion(); x.update(fuera_de_alcance=True, requiere_aclaracion=True, faltantes=['dato'])
        with self.assertRaises(ErrorIngesta): interpretar_reporte(reporte(), extractor(x))

    def test_modalidad_no_soportada_no_llama_gemini(self):
        r = reporte().model_dump(mode='json'); r['entrada'].update(modalidad='foto', adjunto_id=str(uuid4()))
        ex = extractor()
        with self.assertRaises(ErrorIngesta): interpretar_reporte(ReporteRegistrado.model_validate(r), ex)
        ex.extraer.assert_not_called()

    def test_no_se_persiste_una_salida_sin_validar(self):
        ex = Mock(); ex.extraer.return_value = {'aprobado': True}
        with self.assertRaises(ErrorIngesta): interpretar_reporte(reporte(), ex)

    def test_traza_id_estable_por_intento_y_sin_contenido_ciudadano(self):
        r = reporte(); a = interpretar_reporte(r, extractor(), intento_ref='a')
        b = interpretar_reporte(r, extractor(), intento_ref='a'); c = interpretar_reporte(r, extractor(), intento_ref='b')
        self.assertEqual(a.evento.evento_id,b.evento.evento_id)
        self.assertNotEqual(a.evento.evento_id,c.evento.evento_id)
        self.assertNotIn(TEXTO,a.evento.model_dump_json())

    def test_reconstruccion_de_filas_usa_contexto_real(self):
        f = filas(); r = reconstruir_reporte(f)
        self.assertEqual(str(r.ejecucion_id),f['ejecucion']['ejecucion_id'])
        f['ejecucion']['reporte_id'] = str(uuid4())
        with self.assertRaises(ErrorIngesta): reconstruir_reporte(f)

    def test_ejecucion_no_tomada_no_llama_modelo(self):
        p = Mock(); p.tomar.return_value = None; ex = extractor()
        self.assertEqual(procesar_ejecucion(uuid4(),p,ex)['estado'],'no_tomada')
        ex.extraer.assert_not_called(); p.finalizar.assert_not_called()

    def test_cierre_recibe_resultado_y_traza_en_una_operacion(self):
        f = filas(); p = Mock(); p.tomar.return_value = f; p.finalizar.return_value = {'estado':'pendiente','etapa':'territorial'}
        self.assertEqual(procesar_ejecucion(UUID(f['ejecucion']['ejecucion_id']),p,extractor())['etapa'],'territorial')
        p.finalizar.assert_called_once()
        kw = p.finalizar.call_args.kwargs
        self.assertIsInstance(kw['resultado'],ReporteInterpretado)
        self.assertEqual(kw['evento'].ejecucion_id,kw['resultado'].ejecucion_id)

    def test_error_proveedor_persiste_error_tipado_y_traza(self):
        f = filas(); p = Mock(); p.tomar.return_value = f
        ex = Mock(); ex.extraer.side_effect = ErrorIngesta(CodigoError.PROVEEDOR_NO_DISPONIBLE,'Proveedor no disponible.',True)
        procesar_ejecucion(UUID(f['ejecucion']['ejecucion_id']),p,ex)
        kw = p.finalizar.call_args.kwargs
        self.assertEqual(kw['error'].codigo,'proveedor_no_disponible')
        self.assertTrue(kw['error'].recuperable)
        self.assertEqual(kw['evento'].siguiente_estado,'espera_validacion')

    def test_fallo_de_cierre_no_dispara_otro_cierre_ni_otra_llamada(self):
        f = filas(); p = Mock(); p.tomar.return_value = f; p.finalizar.side_effect = RuntimeError('respuesta perdida')
        ex = extractor()
        with self.assertRaises(RuntimeError): procesar_ejecucion(UUID(f['ejecucion']['ejecucion_id']),p,ex)
        p.finalizar.assert_called_once(); ex.extraer.assert_called_once()

    def test_adaptador_usa_rpc_sin_updates_separados(self):
        db = Mock(); db.rpc.return_value.execute.return_value = SimpleNamespace(data=None)
        PersistenciaIngesta(db).tomar(uuid4(),'ingesta:prueba')
        self.assertEqual(db.rpc.call_args.args[0],'ra_tomar_ingesta')
        db.table.assert_not_called()

    def test_finalizar_serializa_contratos_y_parametros_de_la_rpc(self):
        r=reporte(); resultado=interpretar_reporte(r,extractor())
        db=Mock(); db.rpc.return_value.execute.return_value=SimpleNamespace(data={'estado':'pendiente'})
        PersistenciaIngesta(db).finalizar(ejecucion_id=r.ejecucion_id, trabajador_id='ingesta:test',
            snapshot={'texto':TEXTO}, resultado=resultado.reporte, evento=resultado.evento)
        nombre, parametros=db.rpc.call_args.args
        self.assertEqual(nombre,'ra_finalizar_ingesta')
        self.assertEqual(parametros['p_resultado']['interpretacion'],extraccion())
        self.assertIsNone(parametros['p_error'])
        self.assertEqual(parametros['p_evento']['agente'],'ingesta')
        db.table.assert_not_called()


class TestGemini(unittest.TestCase):
    def ejecutar(self, handler):
        return ExtractorGemini(ConfiguracionGemini('clave_sintetica'),transporte=httpx.MockTransport(handler)).extraer(TEXTO)

    def test_salida_estructurada_y_credencial_en_cabecera(self):
        def handler(request):
            self.assertEqual(request.headers['x-goog-api-key'],'clave_sintetica')
            self.assertNotIn('clave_sintetica',str(request.url))
            body = json.loads(request.content)
            self.assertEqual(body['contents'][0]['parts'][0]['text'],TEXTO)
            self.assertEqual(body['generationConfig']['responseJsonSchema']['title'],'ExtraccionReporteLLM')
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(extraccion())}]}}]})
        self.assertEqual(self.ejecutar(handler).campos.horas_sin_agua,48)

    def test_errores_no_exponen_respuesta_proveedor(self):
        for codigo in [400,401,403,404,429,500,503]:
            with self.subTest(codigo=codigo), self.assertRaises(ErrorIngesta) as error:
                self.ejecutar(lambda r:httpx.Response(codigo,json={'error':{'message':'clave_sintetica'}}))
            self.assertNotIn('clave_sintetica',str(error.exception))

    def test_timeout_no_expone_detalle(self):
        def handler(request): raise httpx.ReadTimeout('clave_sintetica',request=request)
        with self.assertRaises(ErrorIngesta) as error: self.ejecutar(handler)
        self.assertTrue(error.exception.recuperable)
        self.assertNotIn('clave_sintetica',str(error.exception))

    def test_candidatos_ausentes_truncados_o_no_json(self):
        for body in [{}, {'candidates':[]}, {'candidates':[{'finishReason':'MAX_TOKENS'}]},
                     {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'no-json'}]}}]}]:
            with self.subTest(body=body), self.assertRaises(ErrorIngesta):
                self.ejecutar(lambda r:httpx.Response(200,json=body))

    def test_salida_no_admite_ids_coordenadas_o_aprobaciones(self):
        for campo,valor in [('reporte_id',str(uuid4())),('aprobado',True),('latitud',8.9)]:
            x=extraccion(); x[campo]=valor
            with self.subTest(campo=campo), self.assertRaises(ErrorIngesta):
                self.ejecutar(lambda r:httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(x)}]}}]}))

    def test_configuracion_no_muestra_clave(self):
        self.assertNotIn('clave_sintetica',repr(ConfiguracionGemini('clave_sintetica')))


if __name__ == '__main__':
    unittest.main()
