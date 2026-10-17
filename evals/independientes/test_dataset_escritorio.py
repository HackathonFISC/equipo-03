"""Oráculos independientes, inmutabilidad, evidencia y manifiesto del dataset PED."""
from copy import deepcopy
import json
import shutil
import socket

import pytest

from evals import escritorio
from scripts.generar_dataset_escritorio import generar


def test_ejecucion_sin_red_conserva_casos_y_pendientes(tmp_path, monkeypatch):
    def prohibido(*args, **kwargs):
        pytest.fail('El dataset local no debe abrir conexiones')
    monkeypatch.setattr(socket, 'socket', prohibido)
    carpeta = escritorio.DATASET
    previo = {p: escritorio.sha(p) for p in carpeta.rglob('*.json')}
    salida = tmp_path/'resultados'
    r = escritorio.ejecutar_dataset(carpeta, salida)
    assert r['resumen']['total'] == 30
    assert r['resumen']['aprobado'] == 18 and r['resumen']['pendiente'] == 12
    assert r['resumen']['fallido'] == r['resumen']['error'] == 0
    assert r['cierre_integrado'] is False
    assert {p: escritorio.sha(p) for p in previo} == previo
    assert len(list(salida.glob('PED-*.json'))) == 30
    for c in r['casos']:
        guardado = escritorio.leer(salida/c['evidencia'])
        assert guardado['id'] == c['id']
        if c['id'] not in escritorio.LOCALES:
            assert guardado['estado'] == 'pendiente'
            assert 'propuesta' not in guardado['obtenido']
    with pytest.raises(FileExistsError):
        escritorio.ejecutar_dataset(carpeta, salida)


def test_oraculo_incorrecto_falla_en_lugar_de_copiar_esperado():
    c = deepcopy(escritorio.leer(escritorio.DATASET/'casos/PED-01.json'))
    c['esperado']['demanda_litros'] = 999
    with pytest.raises(AssertionError, match='Litros de demanda'):
        escritorio.ejecutar_local(c)


def test_edicion_de_un_caso_exige_actualizar_manifiesto(tmp_path):
    copia = tmp_path/'dataset'
    shutil.copytree(escritorio.DATASET, copia)
    caso = copia/'casos/PED-01.json'
    d = escritorio.leer(caso)
    d['esperado']['demanda_litros'] = 999
    caso.write_text(json.dumps(d), encoding='utf-8')
    with pytest.raises(AssertionError, match='Caso modificado'):
        escritorio.validar_dataset(copia)


def test_generacion_es_reproducible_y_no_sobrescribe(tmp_path):
    nueva = tmp_path/'dataset'
    generar(nueva)
    for ruta in nueva.rglob('*.json'):
        assert escritorio.sha(ruta) == escritorio.sha(escritorio.DATASET/ruta.relative_to(nueva))
    with pytest.raises(FileExistsError):
        generar(nueva)


def test_checkout_crlf_no_produce_falso_error_de_integridad(tmp_path):
    copia = tmp_path/'crlf'
    shutil.copytree(escritorio.DATASET, copia)
    for ruta in copia.rglob('*.json'):
        ruta.write_bytes(ruta.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    _, casos = escritorio.validar_dataset(copia)
    assert len(casos) == 30


def test_obsoleto_es_rechazado_aun_con_etiquetas_iguales():
    caso = escritorio.leer(escritorio.DATASET/'casos/PED-24.json')
    r = escritorio.ejecutar_local(caso)
    assert r['verificacion']['valido'] is True
    assert r['verificacion_despues']['valido'] is False
    assert any(v['codigo'] == 'version' for v in r['verificacion_despues']['violaciones'])
    assert r['snapshot_cambiado']['datos_version'] == r['propuesta']['datos_version']
