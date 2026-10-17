import json
import shutil

import pytest

from calculo.prioridad import score_needs
from contratos.errores import CodigoError, ExcepcionContrato
from contratos.solicitudes import SolicitudPriorizarNecesidades
from scripts.verificar_escenario_v3 import CARPETA, verificar


def test_catalogo_escenario_y_demanda_pendiente_sin_mutar_archivos():
    antes = {p.name: p.read_bytes() for p in CARPETA.glob('*.json')}
    r = verificar()
    assert (r['puntos'], r['vehiculos'], r['nodos_matriz']) == (6, 2, 7)
    assert r['demanda_ensayo_litros'] == 18000 and r['necesidades_pendientes'] == 6
    assert r['politica_estado'] == 'propuesta_demo' and not r['autorizacion_operativa']
    assert all(set(n['faltantes']) == {'demanda.confirmacion', 'capacidad_recepcion_litros'}
               for n in r['validaciones_demanda'])
    assert antes == {p.name: p.read_bytes() for p in CARPETA.glob('*.json')}


@pytest.mark.parametrize('archivo,ruta,valor', [
    ('solicitud_rutas.json', ('puntos', 0, 'ubicacion', 'latitud'), 0.0),
    ('solicitud_rutas.json', ('puntos', 0, 'ubicacion', 'representa_punto_atencion'), True),
    ('solicitud_rutas.json', ('puntos', 0, 'origen'), 'sintetico'),
    ('solicitud_rutas.json', ('vehiculos', 0, 'capacidad_litros'), 12000.0),
    ('solicitud_rutas.json', ('necesidades', 0, 'demanda_litros'), 1000.0),
    ('solicitudes_validacion.json', (0, 'capacidad_recepcion_litros'), 5000.0),
    ('solicitudes_validacion.json', (0, 'incidente_id'), '00000000-0000-0000-0000-000000000001'),
    ('supuestos.json', ('sha256_catalogo_lf',), 'fuente-modificada'),
])
def test_detecta_cambios_de_procedencia_confirmacion_y_coherencia(tmp_path, archivo, ruta, valor):
    carpeta = tmp_path / 'escenario'
    shutil.copytree(CARPETA, carpeta)
    p = carpeta / archivo
    datos = json.loads(p.read_text(encoding='utf-8'))
    cursor = datos
    for clave in ruta[:-1]:
        cursor = cursor[clave]
    cursor[ruta[-1]] = valor
    p.write_text(json.dumps(datos), encoding='utf-8')
    with pytest.raises(ValueError):
        verificar(carpeta)


def test_politica_propuesta_no_habilita_ranking():
    s = json.loads((CARPETA / 'solicitud_rutas.json').read_text(encoding='utf-8'))
    entrada = SolicitudPriorizarNecesidades.model_validate({k: s[k] for k in (
        'esquema_version', 'ejecucion_id', 'creado_en', 'origen', 'datos_version', 'politica', 'necesidades')})
    with pytest.raises(ExcepcionContrato) as error:
        score_needs(entrada)
    assert error.value.detalle.codigo == CodigoError.POLITICA_NO_ACTIVA
