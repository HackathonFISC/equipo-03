"""Proceso simulado; nunca arranca agentes reales ni utiliza credenciales."""
import subprocess
import sys
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import pytest

from api.main import app
from orquestador import servicio
from orquestador.trabajador import una_vuelta


class Proceso:
    def __init__(self):
        self.returncode = None
        self.terminado = False
        self.esperas = []

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.esperas.append(timeout)
        self.returncode = 0
        return 0

    def terminate(self):
        self.terminado = True
        self.returncode = -1

    def kill(self):
        self.returncode = -2


@pytest.fixture
def proceso(monkeypatch):
    p = Proceso()
    iniciar = Mock(return_value=p)
    monkeypatch.setattr(servicio.subprocess, 'Popen', iniciar)
    return p, iniciar


def test_automatico_por_defecto_y_desactivacion_explicita(monkeypatch):
    monkeypatch.setattr(servicio, 'dotenv_values', lambda *a, **k: {})
    monkeypatch.delenv('TRABAJADOR_AUTOMATICO')
    assert servicio.automatico()
    monkeypatch.setenv('TRABAJADOR_AUTOMATICO', 'false')
    assert not servicio.automatico()
    monkeypatch.setenv('TRABAJADOR_AUTOMATICO', 'incorrecto')
    with pytest.raises(ValueError):
        servicio.automatico()


def test_inicia_mismo_interprete_y_cierra_con_senal(tmp_path, proceso):
    p, iniciar = proceso
    s = servicio.ServicioAgentes(tmp_path)
    try:
        s.iniciar()
        s.iniciar()
        iniciar.assert_called_once()
        argumentos = iniciar.call_args.args[0]
        assert argumentos[:4] == [sys.executable, '-u', '-m', 'orquestador.trabajador']
        assert '--archivo-parada' in argumentos
        assert iniciar.call_args.kwargs['cwd'] == str(tmp_path)
        assert s.consultar() == 'iniciado'
        señal = s.parada
        def esperar(timeout):
            assert señal.exists()
            p.returncode = 0
        p.wait = esperar
    finally:
        s.cerrar()
    assert s.estado == 'detenido' and not p.terminado


def test_dos_instancias_no_lanzan_dos_hijos_y_reinicio_libera_bloqueo(tmp_path, proceso):
    _, iniciar = proceso
    a, b = servicio.ServicioAgentes(tmp_path), servicio.ServicioAgentes(tmp_path)
    try:
        a.iniciar()
        b.iniciar()
        assert b.estado == 'otra_instancia'
        assert iniciar.call_count == 1
        a.cerrar()
        iniciar.return_value = Proceso()
        b.iniciar()
        assert iniciar.call_count == 2 and b.estado == 'iniciado'
    finally:
        a.cerrar()
        b.cerrar()


def test_fallo_de_arranque_libera_bloqueo(tmp_path, proceso):
    _, iniciar = proceso
    iniciar.side_effect = OSError('fallo ficticio')
    s = servicio.ServicioAgentes(tmp_path)
    with pytest.raises(OSError):
        s.iniciar()
    assert s.bloqueo is None and s.temporal is None
    iniciar.side_effect = None
    try:
        s.iniciar()
        assert s.consultar() == 'iniciado'
    finally:
        s.cerrar()


def test_salida_con_error_visible_sin_reinicio_ciego(tmp_path, proceso):
    p, iniciar = proceso
    s = servicio.ServicioAgentes(tmp_path)
    try:
        s.iniciar()
        p.returncode = 1
        assert s.consultar() == 'fallido'
        assert iniciar.call_count == 1
    finally:
        s.cerrar()


def test_cierre_forzado_solo_despues_del_plazo(tmp_path, proceso):
    p, _ = proceso
    s = servicio.ServicioAgentes(tmp_path)
    s.iniciar()
    def esperar(timeout):
        if not p.terminado:
            raise subprocess.TimeoutExpired('trabajador-ficticio', timeout)
        return p.returncode
    p.wait = esperar
    s.cerrar()
    assert p.terminado and s.bloqueo is None


def test_api_arranca_y_cierra_trabajador_con_su_ciclo_de_vida(tmp_path, monkeypatch, proceso):
    p, iniciar = proceso
    clase = servicio.ServicioAgentes
    monkeypatch.setattr(servicio, 'ServicioAgentes', lambda: clase(tmp_path))
    monkeypatch.setenv('TRABAJADOR_AUTOMATICO', 'true')
    with TestClient(app) as cliente:
        assert cliente.get('/salud').json() == {'estado': 'ok'}
        assert cliente.get('/salud/agentes').json() == {'estado': 'iniciado'}
        iniciar.assert_called_once()
    assert p.returncode == 0


def test_api_en_pruebas_no_arranca_procesos_reales(proceso):
    _, iniciar = proceso
    with TestClient(app) as cliente:
        assert cliente.get('/salud/agentes').json() == {'estado': 'desactivado'}
    iniciar.assert_not_called()


def test_senal_de_parada_antes_de_reservar_no_toca_bd():
    db = Mock()
    assert una_vuelta(db, None, detener=lambda: True) == []
    assert not db.mock_calls


def test_senal_entre_ejecuciones_no_toma_mas_trabajo():
    db = Mock()
    db.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        dict(ejecucion_id='primera', etapa='ingesta'), dict(ejecucion_id='segunda', etapa='ingesta')]
    señal = iter([False, False, True])
    with patch('orquestador.trabajador.avanzar', return_value={'estado': 'ok'}) as avanzar:
        r = una_vuelta(db, None, detener=lambda: next(señal))
    assert r == [{'estado': 'ok'}]
    avanzar.assert_called_once()
