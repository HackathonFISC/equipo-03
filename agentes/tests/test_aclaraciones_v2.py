import json
from pathlib import Path
from uuid import uuid4
from contratos.modelos import ReporteRegistrado, ExtraccionReporteLLM
from agentes.ingesta import interpretar_reporte
from contratos.modelos import RespuestaAclaracion
import pytest

RAIZ=Path(__file__).resolve().parents[2]


def test_reprocesar_conserva_original_y_evidencias_separadas():
    reporte=ReporteRegistrado.model_validate_json((RAIZ/'contratos/ejemplos/reporte_registrado.json').read_text())
    original=reporte.entrada.texto
    respuesta={'aclaracion_id':str(uuid4()),'respuesta_texto':'Son 48 horas y 120 personas en Escuela El Coco.'}
    class Extractor:
        def extraer(self,texto):
            assert original in texto and respuesta['respuesta_texto'] in texto
            return ExtraccionReporteLLM(resumen='Falta de agua',ubicacion_declarada='Escuela El Coco',
                campos=dict(horas_sin_agua=48.0,personas_afectadas=120,tipo_problema='sin_suministro'),
                evidencia_textual=[respuesta['respuesta_texto']],faltantes=[],requiere_aclaracion=False,fuera_de_alcance=False)
    resultado=interpretar_reporte(reporte,Extractor(),aclaraciones=[respuesta])
    assert reporte.entrada.texto==original
    assert len(resultado.reporte.evidencias)==2
    assert resultado.siguiente_etapa=='territorial'


def test_ubicacion_compartida_supera_faltante_geografico_pero_no_se_valida():
    reporte=ReporteRegistrado.model_validate_json((RAIZ/'contratos/ejemplos/reporte_registrado.json').read_text())
    respuesta={'aclaracion_id':str(uuid4()),'respuesta_ubicacion':dict(latitud=8.9,longitud=-79.7,fuente='compartida',precision_metros=None,representa_punto_atencion=None)}
    class Extractor:
        def extraer(self,texto):
            return ExtraccionReporteLLM(resumen='Reporte de agua',ubicacion_declarada=None,
                campos=dict(tipo_problema='sin_suministro'),evidencia_textual=[reporte.entrada.texto],
                faltantes=['ubicacion'],requiere_aclaracion=True,fuera_de_alcance=False)
    resultado=interpretar_reporte(reporte,Extractor(),aclaraciones=[respuesta])
    assert resultado.siguiente_etapa=='territorial'
    assert resultado.reporte.ubicacion_compartida.representa_punto_atencion is None


def test_contrato_admite_ubicacion_sola_y_rechaza_doble_contenido():
    contexto=dict(ejecucion_id=uuid4(),reporte_id=uuid4(),aclaracion_id=uuid4(),creado_en='2026-10-16T20:00:00-05:00',origen='sintetico')
    ubicacion=dict(latitud=8.9,longitud=-79.7,fuente='compartida')
    assert RespuestaAclaracion(**contexto,ubicacion_compartida=ubicacion).texto is None
    with pytest.raises(ValueError):
        RespuestaAclaracion(**contexto,texto='Texto',ubicacion_compartida=ubicacion)
    with pytest.raises(ValueError):
        RespuestaAclaracion(**contexto)
