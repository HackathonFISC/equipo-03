from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from contratos.modelos import Ubicacion
from geografia.catalogo import PuntoCatalogo
from geografia.resolver import resolve_location
from geografia.consolidacion import periodo_reportado, mismo_episodio
from agentes.territorial import resolver_reporte


def punto(nombre='Escuela El Coco', alias=('Escuela del Coco',)):
    return PuntoCatalogo(uuid4(), uuid4(), nombre, alias, 'La Chorrera', 'El Coco', None, 'pendiente')


def test_alias_acentos_puntuacion_y_limites():
    p=punto('Centro de Atención', ('Centro de Atencion',))
    assert resolve_location(['En el CENTRO DE ATENCIÓN.'], [p]).punto == p
    assert resolve_location(['Centro de Atencionista'], [p]).estado == 'desconocida'


def test_zona_amplia_no_es_instalacion_aunque_se_cargue_alias_incorrecto():
    p=punto(alias=('El Coco', 'La Chorrera'))
    assert resolve_location(['En El Coco'], [p]).estado == 'desconocida'


def test_varios_nombres_piden_aclaracion_y_no_elige_el_primero():
    a,b=punto(),punto('Junta Comunal', ())
    assert resolve_location(['Escuela El Coco o Junta Comunal'], [a,b]).estado == 'ambigua'


def test_desconocido_no_equivale_a_fuera_de_area():
    assert resolve_location(['Barrio que no conocemos'], [punto()]).estado == 'desconocida'


def test_coordenadas_no_crean_punto_ni_se_asignan_por_cercania():
    u=Ubicacion(latitud=8.8,longitud=-79.8,fuente='compartida')
    assert resolve_location([], [punto()], u).estado == 'revision'
    assert resolve_location(['Escuela El Coco'], [punto()], u).estado == 'revision'


def test_identificar_no_valida_operacion():
    p=punto()
    assert resolve_location(['Escuela El Coco'], [p]).punto.estado_validacion == 'pendiente'


def test_solo_mismo_episodio_documentado():
    inicio,fin=periodo_reportado(datetime(2026,10,16,tzinfo=timezone.utc), 48)
    a=dict(punto_atencion_id='A',origen='sintetico',tipo_problema='sin_suministro',episodio_establecido=True,periodo_inicio=inicio,periodo_fin=fin)
    assert mismo_episodio(a,a)
    for cambio in [dict(punto_atencion_id='B'),dict(origen='real'),dict(tipo_problema='intermitencia'),dict(episodio_establecido=False),dict(periodo_inicio=fin,periodo_fin=fin.replace(year=2027))]:
        assert not mismo_episodio(a,{**a,**cambio})


def test_respuesta_precisa_resuelve_alternativas_del_original():
    a,b=punto(),punto('Junta Comunal', ())
    catalogo=[dict(punto_atencion_id=str(p.punto_atencion_id),sector_id=str(p.sector_id),nombre=p.nombre,
        alias=list(p.alias),distrito=p.distrito,corregimiento=p.corregimiento,estado_validacion='pendiente') for p in (a,b)]
    extraccion=dict(resumen='Falta agua',ubicacion_declarada='Escuela El Coco',
        campos=dict(horas_sin_agua=48.0,tipo_problema='sin_suministro'),evidencia_textual=['Falta agua'],
        faltantes=[],requiere_aclaracion=False,fuera_de_alcance=False)
    filas=dict(reporte=dict(texto='Falta agua en Escuela El Coco o Junta Comunal',creado_en='2026-10-16T20:00:00-05:00',interpretacion=extraccion),
        catalogo=catalogo,aclaraciones=[dict(respuesta_texto='Es en Junta Comunal')])
    assert resolver_reporte(filas)['punto_atencion_id']==str(b.punto_atencion_id)
