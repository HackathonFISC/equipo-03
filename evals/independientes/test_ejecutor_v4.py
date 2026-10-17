"""El evaluador también debe detectar falsos verdes y proteger sus evidencias."""
import json

import httpx
import pytest

from evals.ejecutar import leer_junit, pendientes_integracion
from evals.independientes.caja_negra import ejecutar_guion, FalloComprobacion, puntero
from evals.metricas import resumir


def guion():
    return dict(id='sondeo_rechazo', pasos=[
        dict(nombre='antes', metodo='GET', ruta='/auditoria-ficticia',
             esperado=dict(http=200, json={'/version': 2}),
             capturar=dict(estado='/estado')),
        dict(nombre='rechazo', metodo='POST', ruta='/aprobacion-ficticia',
             cuerpo=dict(version=1),
             esperado=dict(http=409, json={'/codigo': 'version_obsoleta'})),
        dict(nombre='despues', metodo='GET', ruta='/auditoria-ficticia',
             esperado=dict(http=200, json={'/version': 2},
                           igual_a_captura={'/estado': 'estado'})),
    ])


def transporte(*, codigo=409, dominio='version_obsoleta', modificar=False):
    llamadas = []

    def responder(p):
        llamadas.append(p)
        if p.method == 'POST':
            return httpx.Response(codigo, json={'codigo': dominio})
        return httpx.Response(200, json=dict(version=2, estado={
            'aprobaciones': int(modificar and len(llamadas) == 3), 'avisos': 0}))
    return httpx.MockTransport(responder), llamadas


def test_caja_negra_comprueba_rechazo_y_estado_sin_importar_servicios():
    t, peticiones = transporte()
    r = ejecutar_guion('http://localhost:8000', guion(), transporte=t)
    assert len(r) == 3 and len(peticiones) == 3
    assert [x['http'] for x in r] == [200, 409, 200]


@pytest.mark.parametrize('codigo,dominio', [(404, 'version_obsoleta'), (405, 'version_obsoleta'),
    (401, 'sin_permiso'), (403, 'sin_permiso'), (409, 'plan_no_verificado'), (500, 'error')])
def test_http_inesperado_o_otro_error_no_demuestran_version_obsoleta(codigo, dominio):
    t, _ = transporte(codigo=codigo, dominio=dominio)
    with pytest.raises(FalloComprobacion):
        ejecutar_guion('http://localhost:8000', guion(), transporte=t)


def test_rechazo_http_con_efecto_secundario_falla():
    t, _ = transporte(modificar=True)
    with pytest.raises(FalloComprobacion, match='Cambió'):
        ejecutar_guion('http://localhost:8000', guion(), transporte=t)


def test_validar_guion_entero_antes_de_escribir():
    g = guion()
    g['pasos'][2]['esperado']['http'] = 404
    t, llamadas = transporte()
    with pytest.raises(FalloComprobacion):
        ejecutar_guion('http://localhost:8000', g, transporte=t)
    assert not llamadas


def test_no_filtra_credenciales_ni_respuesta_en_evidencia(monkeypatch):
    g = guion()
    g['pasos'][1]['cabeceras_entorno'] = {'Authorization': 'V4_TOKEN_FICTICIO'}
    monkeypatch.setenv('V4_TOKEN_FICTICIO', 'Bearer secreto-ficticio-123')
    t, llamadas = transporte()
    r = ejecutar_guion('http://localhost:8000', g, transporte=t)
    assert llamadas[1].headers['Authorization'] == 'Bearer secreto-ficticio-123'
    texto = json.dumps(r)
    assert 'secreto' not in texto and 'Authorization' not in texto
    assert 'version_obsoleta' not in texto and '/aprobacion' not in texto


def test_timeout_no_reintenta_y_no_expone_detalle():
    contador = []

    def fallo(p):
        contador.append(1)
        raise httpx.ReadTimeout('dato-privado-123', request=p)

    with pytest.raises(FalloComprobacion) as e:
        ejecutar_guion('http://localhost:8000', guion(), transporte=httpx.MockTransport(fallo))
    assert contador == [1] and 'dato-privado' not in str(e.value)


def test_no_sigue_redireccion_a_otro_servidor():
    llamadas = []

    def redirigir(p):
        llamadas.append(p)
        return httpx.Response(307, headers={'Location': 'https://otro.invalid'})

    with pytest.raises(FalloComprobacion):
        ejecutar_guion('http://localhost:8000', guion(), transporte=httpx.MockTransport(redirigir))
    assert len(llamadas) == 1


@pytest.mark.parametrize('base', ['http://usuario:clave@localhost', 'https://api.invalid?token=clave',
    'http://api.invalid', 'file:///tmp/archivo'])
def test_no_envia_a_base_insegura_o_con_credenciales(base):
    t, llamadas = transporte()
    with pytest.raises(FalloComprobacion):
        ejecutar_guion(base, guion(), transporte=t)
    assert not llamadas


def test_puntero_campo_ausente_no_se_confunde_con_null():
    assert puntero({'a/b': {'~x': [None]}}, '/a~1b/~0x/0') is None
    with pytest.raises(FalloComprobacion):
        puntero({}, '/desconocido')


def test_metricas_no_convierten_pendiente_en_aprobado():
    m = resumir([{'estado': 'aprobado'}, {'estado': 'pendiente'}, {'estado': 'fallido'}])
    assert m['total'] == 3 and m['ejecutados'] == 2
    assert m['tasa_exito_ejecutados'] == .5
    assert m['proporcion_aprobada_total'] == 1/3
    assert resumir([])['tasa_exito_ejecutados'] is None


def test_estados_desconocidos_se_rechazan():
    with pytest.raises(ValueError):
        resumir([{'estado': 'parece_bien'}])


def test_casos_integracion_siguen_pendientes_sin_evidencia_real():
    r = pendientes_integracion()
    assert {x['id'] for x in r} == {'18', '20', '21'}
    assert resumir(r)['pendiente'] == 3 and not resumir(r)['aprobado']


def test_junit_cuenta_errores_saltos_y_fallos(tmp_path):
    p = tmp_path/'resultado.xml'
    p.write_text('<testsuites><testsuite tests="8" failures="1" errors="2" skipped="3"/></testsuites>')
    assert leer_junit(p) == dict(tests=8, failures=1, errors=2, skipped=3)


def test_cli_guarda_pendientes_y_devuelve_incompleto(tmp_path, monkeypatch):
    import evals.ejecutar as ejecutor
    salida = tmp_path/'evidencia'
    monkeypatch.setattr('sys.argv', ['evals.ejecutar', '--salida', str(salida)])
    monkeypatch.setattr(ejecutor, 'ejecutar_regresion', lambda p: {'estado': 'aprobado'})
    monkeypatch.setattr(ejecutor, 'huellas_codigo', lambda: {})
    assert ejecutor.main() == 2
    reporte = json.loads((salida/'informe.json').read_text(encoding='utf-8'))
    assert reporte['cierre_v4'] is False
    assert reporte['metricas_integracion']['pendiente'] == 3
    # Un segundo lanzamiento no sobrescribe ni vuelve a ejecutar pruebas.
    with pytest.raises(FileExistsError):
        ejecutor.main()


def test_cli_no_oculta_regresion_fallida(tmp_path, monkeypatch):
    import evals.ejecutar as ejecutor
    monkeypatch.setattr('sys.argv', ['evals.ejecutar', '--salida', str(tmp_path/'evidencia')])
    monkeypatch.setattr(ejecutor, 'ejecutar_regresion', lambda p: {'estado': 'fallido'})
    monkeypatch.setattr(ejecutor, 'huellas_codigo', lambda: {})
    assert ejecutor.main() == 1


@pytest.mark.parametrize('local,segundo_invalido', [('fallido', False), ('aprobado', True)])
def test_cli_no_inicia_http_con_prerrequisitos_incompletos(tmp_path, monkeypatch, local, segundo_invalido):
    import evals.ejecutar as ejecutor
    perfil = tmp_path/'perfil.json'
    datos = dict(base_url='http://localhost:8000', guiones=[guion()])
    if segundo_invalido:
        datos['guiones'].append(dict(id='incompleto', pasos=[]))
    perfil.write_text(json.dumps(datos), encoding='utf-8')
    salida = tmp_path/'evidencia'
    monkeypatch.setattr('sys.argv', ['evals.ejecutar', '--salida', str(salida), '--perfil-http', str(perfil)])
    monkeypatch.setattr(ejecutor, 'ejecutar_regresion', lambda p: {'estado': local})
    monkeypatch.setattr(ejecutor, 'huellas_codigo', lambda: {})
    def prohibido(*a, **k):
        pytest.fail('No iniciar peticiones con prerrequisitos incompletos')
    monkeypatch.setattr('evals.independientes.caja_negra.ejecutar_guion', prohibido)
    assert ejecutor.main() == 1
    reporte = json.loads((salida/'informe.json').read_text(encoding='utf-8'))
    assert reporte['metricas_sondeos']['error'] == 1
