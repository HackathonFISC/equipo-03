"""Fallos transitorios simulados; sin conexiones ni credenciales."""
import json
from unittest.mock import Mock, patch

from orquestador import trabajador
from orquestador.servicio import ServicioAgentes


class Reloj:
    def __init__(self):
        self.t = 0
    def ahora(self):
        return self.t
    def esperar(self, segundos):
        self.t += segundos


def test_error_transitorio_de_mantenimiento_recupera_siguiente_vuelta(tmp_path):
    reloj = Reloj()
    vuelta = Mock(side_effect=[RuntimeError('SECRETO'), []])
    salud = tmp_path/'salud.json'
    assert trabajador.ejecutar_bucle(vuelta, detener=lambda: vuelta.call_count == 2,
        esperar=reloj.esperar, monotono=reloj.ahora, archivo_salud=salud) == 0
    assert vuelta.call_count == 2 and reloj.t == 5
    assert json.loads(salud.read_text())['ultima_vuelta_exitosa']


def test_backoff_tiene_tope_y_sale_no_cero_tras_limite(caplog):
    reloj = Reloj()
    vuelta = Mock(side_effect=RuntimeError('SECRETO'))
    assert trabajador.ejecutar_bucle(vuelta, detener=lambda: False, intervalo=20,
        max_fallos=5, esperar=reloj.esperar, monotono=reloj.ahora) == 1
    assert vuelta.call_count == 5
    assert abs(reloj.t - (20+40+60+60)) < .001
    assert 'SECRETO' not in caplog.text


def test_exito_reinicia_contador_de_fallos():
    reloj = Reloj()
    vuelta = Mock(side_effect=[RuntimeError(), [], RuntimeError(), []])
    assert trabajador.ejecutar_bucle(vuelta, detener=lambda: vuelta.call_count == 4,
        max_fallos=2, esperar=reloj.esperar, monotono=reloj.ahora) == 0
    assert reloj.t == 15


def test_una_sola_vuelta_fallida_no_reintenta():
    vuelta = Mock(side_effect=RuntimeError())
    assert trabajador.ejecutar_bucle(vuelta, detener=lambda: False, una_sola=True) == 1
    assert vuelta.call_count == 1


def test_error_etapa_marca_solo_reserva_del_mismo_trabajador(caplog):
    db = Mock()
    db.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data = [dict(ejecucion_id='a', etapa='ingesta')]
    with patch('orquestador.trabajador.avanzar', side_effect=RuntimeError('SECRETO')) as avanzar:
        assert trabajador.una_vuelta(db, None) == [dict(estado='requiere_revision', ejecucion_id='a')]
    propietario = avanzar.call_args.kwargs['trabajador_id']
    db.rpc.assert_any_call('ra_marcar_error_trabajador', dict(p_ejecucion_id='a', p_trabajador_id=propietario))
    assert 'SECRETO' not in caplog.text


def test_salud_es_desconocida_hasta_vuelta_confirmada(tmp_path):
    s = ServicioAgentes(tmp_path)
    assert s.ultima_vuelta_exitosa() is None
    s.archivo_salud = tmp_path/'salud.json'
    s.archivo_salud.write_text('incompleto')
    assert s.ultima_vuelta_exitosa() is None
    s.archivo_salud.write_text(json.dumps({'ultima_vuelta_exitosa': '2026-10-17T12:00:00+00:00'}))
    assert s.ultima_vuelta_exitosa() == '2026-10-17T12:00:00+00:00'
