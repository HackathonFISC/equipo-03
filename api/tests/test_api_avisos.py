"""Pruebas de las rutas de la bandeja de salida con RPC simuladas (sin red ni claves).

Las RPC reales son de la migración 0010; aquí solo se comprueba lo que hace la API con lo que devuelven.
"""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.dependencias import obtener_db, secreto_configurado
from api.main import app

SECRETO = "secreto-de-prueba-0123456789"
CABECERA = {"X-Secreto-Bot": SECRETO}
AVISO = str(uuid4())
FILA = {
    "aviso_id": AVISO,
    "chat_id": "-1001",
    "tipo": "distribucion",
    "version": 2,
    "punto_nombre": "Escuela El Coco",
    "litros_asignados": 2500,
    "ventana_inicio": "2026-10-17T13:10:00+00:00",
    "ventana_fin": "2026-10-17T13:20:00+00:00",
}


class Respuesta:
    def __init__(self, data):
        self.data = data


class Llamada:
    def __init__(self, ejecutar):
        self._ejecutar = ejecutar

    def execute(self):
        return Respuesta(self._ejecutar())


class BaseFalsa:
    def __init__(self):
        self.llamadas, self.respuestas, self.error = [], {}, None

    def rpc(self, nombre, parametros):
        self.llamadas.append((nombre, parametros))

        def ejecutar():
            if self.error:
                raise self.error
            return self.respuestas.get(nombre)

        return Llamada(ejecutar)


@pytest.fixture
def db():
    base = BaseFalsa()
    app.dependency_overrides[obtener_db] = lambda: base
    app.dependency_overrides[secreto_configurado] = lambda: SECRETO
    yield base
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(db):
    return TestClient(app)


# --- Reservar ---

def test_reservar_sin_pendientes_responde_204(cliente, db):
    r = cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 204
    assert db.llamadas == [("ra_reservar_aviso", {"p_trabajador_id": "bot:1"})]


@pytest.mark.parametrize("forma", [lambda f: f, lambda f: [f]], ids=["objeto", "lista"])
def test_reservar_devuelve_solo_lo_necesario_para_redactar(cliente, db, forma):
    db.respuestas["ra_reservar_aviso"] = forma(dict(FILA))
    r = cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["aviso_id"] == AVISO
    assert cuerpo["chat_id"] == -1001
    assert cuerpo["litros_asignados"] == 2500
    assert set(cuerpo) == {
        "aviso_id", "chat_id", "tipo", "version", "punto_nombre", "litros_asignados",
        "ventana_inicio", "ventana_fin",
    }


def test_reservar_no_pasa_campos_extra_de_la_base(cliente, db):
    db.respuestas["ra_reservar_aviso"] = {**FILA, "texto": "texto libre", "aprobacion_id": str(uuid4())}
    cuerpo = cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA).json()
    assert "texto" not in cuerpo and "aprobacion_id" not in cuerpo


@pytest.mark.parametrize(
    "cambio",
    [
        {"chat_id": "no-es-numero"},
        {"tipo": "otro"},
        {"litros_asignados": 0},
        {"litros_asignados": -5},
        {"version": 0},
        {"ventana_inicio": "2026-10-17T13:10:00"},  # sin zona horaria
    ],
    ids=["chat", "tipo", "litros_cero", "litros_negativo", "version", "sin_zona"],
)
def test_reserva_con_forma_inesperada_es_503_no_recuperable(cliente, db, cambio):
    db.respuestas["ra_reservar_aviso"] = {**FILA, **cambio}
    r = cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 503
    assert r.json()["recuperable"] is False


def test_reservar_sin_campo_obligatorio_es_503(cliente, db):
    fila = dict(FILA)
    del fila["punto_nombre"]
    db.respuestas["ra_reservar_aviso"] = fila
    assert cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA).status_code == 503


def test_reservar_con_la_base_caida_es_503_recuperable_sin_detalle(cliente, db):
    db.error = APIError({"message": "detalle interno secreto", "code": "XX000"})
    r = cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 503
    assert r.json()["recuperable"] is True
    assert "secreto" not in json.dumps(r.json())


# --- Registrar el envío ---

def test_registrar_envio_confirmado_llama_a_la_rpc(cliente, db):
    r = cliente.post(
        f"/avisos/{AVISO}/envio",
        json={"trabajador_id": "bot:1", "estado": "enviado", "proveedor_mensaje_id": "101"},
        headers=CABECERA,
    )
    assert r.status_code == 204
    assert db.llamadas == [("ra_registrar_envio_aviso", {
        "p_aviso_id": AVISO, "p_trabajador_id": "bot:1", "p_estado": "enviado",
        "p_proveedor_mensaje_id": "101", "p_error": None,
    })]


def test_registrar_envio_incierto_lleva_error_y_no_id(cliente, db):
    r = cliente.post(
        f"/avisos/{AVISO}/envio",
        json={"trabajador_id": "bot:1", "estado": "incierto", "error": "Telegram: TimedOut"},
        headers=CABECERA,
    )
    assert r.status_code == 204
    assert db.llamadas[0][1]["p_error"] == "Telegram: TimedOut"
    assert db.llamadas[0][1]["p_proveedor_mensaje_id"] is None


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"trabajador_id": "bot:1", "estado": "enviado"},
        {"trabajador_id": "bot:1", "estado": "enviado", "proveedor_mensaje_id": "1", "error": "x"},
        {"trabajador_id": "bot:1", "estado": "fallido"},
        {"trabajador_id": "bot:1", "estado": "fallido", "error": "x", "proveedor_mensaje_id": "1"},
        {"trabajador_id": "bot:1", "estado": "cancelado", "error": "x"},
        {"estado": "enviado", "proveedor_mensaje_id": "1"},
    ],
    ids=["enviado_sin_id", "enviado_con_error", "fallido_sin_error", "fallido_con_id", "estado_ajeno", "sin_trabajador"],
)
def test_registrar_envio_incoherente_es_422_y_no_toca_la_base(cliente, db, cuerpo):
    r = cliente.post(f"/avisos/{AVISO}/envio", json=cuerpo, headers=CABECERA)
    assert r.status_code == 422
    assert db.llamadas == []


def test_registrar_envio_con_reserva_ajena_no_es_exito(cliente, db):
    db.error = APIError({"message": "Reserva ajena o inexistente", "code": "55000"})
    r = cliente.post(
        f"/avisos/{AVISO}/envio",
        json={"trabajador_id": "otro", "estado": "enviado", "proveedor_mensaje_id": "1"},
        headers=CABECERA,
    )
    assert r.status_code == 503


def test_aviso_id_que_no_es_uuid_es_422(cliente, db):
    r = cliente.post("/avisos/no-uuid/envio", json={"trabajador_id": "b", "estado": "incierto", "error": "x"},
                     headers=CABECERA)
    assert r.status_code == 422


# --- Secreto del bot ---

@pytest.mark.parametrize("cabecera", [{}, {"X-Secreto-Bot": "incorrecto-0123456789"}], ids=["sin", "incorrecto"])
def test_sin_el_secreto_no_hay_acceso(cliente, db, cabecera):
    r = cliente.post("/avisos/reservar", json={"trabajador_id": "bot:1"}, headers=cabecera)
    assert r.status_code == 403
    assert db.llamadas == []
