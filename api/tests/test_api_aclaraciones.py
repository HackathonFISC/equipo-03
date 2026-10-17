"""Pruebas de las rutas de aclaración con RPC simuladas (sin red ni claves).

Las RPC reales son de Emilia; aquí solo se comprueba lo que hace la API con lo que devuelven.
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
REMITENTE = str(uuid4())
ACLARACION = str(uuid4())


class Respuesta:
    def __init__(self, data):
        self.data = data


class Llamada:
    def __init__(self, ejecutar):
        self._ejecutar = ejecutar

    def execute(self):
        return Respuesta(self._ejecutar())


class Tabla:
    """Solo lo que usa la API para buscar remitentes."""

    def __init__(self, filas):
        self.filas, self.filtros = filas, {}

    def select(self, _columnas):
        return self

    def eq(self, columna, valor):
        self.filtros[columna] = valor
        return self

    def limit(self, _n):
        return self

    def execute(self):
        return Respuesta([f for f in self.filas if all(f.get(c) == v for c, v in self.filtros.items())])


class BaseFalsa:
    def __init__(self):
        self.remitentes = [{"canal": "telegram", "identificador_externo": "111", "remitente_ref": REMITENTE}]
        self.llamadas = []
        self.respuestas = {}
        self.error = None

    def table(self, nombre):
        assert nombre == "remitentes"
        return Tabla(self.remitentes)

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


RESPUESTA = {
    "usuario_telegram_id": 111,
    "chat_id": -1001,
    "pregunta_mensaje_id": 55,
    "message_id": 56,
    "texto": "Somos unas 80 personas.",
}


# --- Reservar ---

def test_reservar_sin_pendientes_responde_204(cliente, db):
    r = cliente.post("/aclaraciones/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 204
    assert db.llamadas == [("ra_reservar_aclaracion", {"p_trabajador_id": "bot:1"})]


@pytest.mark.parametrize("forma", [lambda f: f, lambda f: [f]], ids=["objeto", "lista"])
def test_reservar_devuelve_la_aclaracion(cliente, db, forma):
    db.respuestas["ra_reservar_aclaracion"] = forma({
        "aclaracion_id": ACLARACION, "pregunta": "¿Cuántas personas son?",
        "chat_id": "-1001", "mensaje_externo_id": "-1001:7",
    })
    r = cliente.post("/aclaraciones/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 200
    assert r.json() == {
        "aclaracion_id": ACLARACION, "pregunta": "¿Cuántas personas son?",
        "chat_id": -1001, "mensaje_original_id": 7,
    }


def test_reservar_con_mensaje_original_ilegible_lo_deja_vacio(cliente, db):
    db.respuestas["ra_reservar_aclaracion"] = {
        "aclaracion_id": ACLARACION, "pregunta": "¿Dónde?", "chat_id": "-1001",
        "mensaje_externo_id": "formato-raro",
    }
    r = cliente.post("/aclaraciones/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.json()["mensaje_original_id"] is None


def test_reservar_con_forma_inesperada_responde_503(cliente, db):
    db.respuestas["ra_reservar_aclaracion"] = [{"a": 1}, {"b": 2}]
    r = cliente.post("/aclaraciones/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 503 and r.json()["recuperable"] is False


# --- Registrar envío ---

def test_registrar_envio_confirmado(cliente, db):
    r = cliente.post(
        f"/aclaraciones/{ACLARACION}/envio",
        json={"trabajador_id": "bot:1", "estado": "enviado", "proveedor_mensaje_id": "55"},
        headers=CABECERA,
    )
    assert r.status_code == 204
    assert db.llamadas == [("ra_registrar_envio_aclaracion", {
        "p_aclaracion_id": ACLARACION, "p_trabajador_id": "bot:1", "p_estado": "enviado",
        "p_proveedor_mensaje_id": "55", "p_error": None,
    })]


@pytest.mark.parametrize("cuerpo", [
    {"estado": "enviado"},
    {"estado": "enviado", "proveedor_mensaje_id": "55", "error": "x"},
    {"estado": "fallido"},
    {"estado": "incierto", "proveedor_mensaje_id": "55", "error": "x"},
    {"estado": "reenviado", "error": "x"},
])
def test_registrar_envio_incoherente_responde_422(cliente, db, cuerpo):
    r = cliente.post(f"/aclaraciones/{ACLARACION}/envio",
                     json={"trabajador_id": "bot:1", **cuerpo}, headers=CABECERA)
    assert r.status_code == 422 and db.llamadas == []


# --- Respuestas ---

@pytest.mark.parametrize("resultado", [
    "aceptada", "repetida", "ya_respondida", "autor_distinto", "no_encontrada", "vencida",
])
def test_respuesta_devuelve_el_resultado_de_la_rpc(cliente, db, resultado):
    ejecucion = str(uuid4())
    db.respuestas["ra_aceptar_respuesta_aclaracion"] = {"resultado": resultado, "ejecucion_id": ejecucion}
    r = cliente.post("/aclaraciones/respuestas", json=RESPUESTA, headers=CABECERA)
    assert r.status_code == 200
    assert r.json() == {"resultado": resultado, "ejecucion_id": ejecucion}


def test_respuesta_envia_a_la_rpc_los_datos_acordados(cliente, db):
    db.respuestas["ra_aceptar_respuesta_aclaracion"] = {"resultado": "aceptada"}
    cliente.post("/aclaraciones/respuestas", json=RESPUESTA, headers=CABECERA)
    assert db.llamadas == [("ra_aceptar_respuesta_aclaracion", {
        "p_chat_id": "-1001", "p_pregunta_mensaje_id": "55",
        "p_respuesta_externo_id": "-1001:56", "p_remitente_ref": REMITENTE,
        "p_texto": "Somos unas 80 personas.", "p_ubicacion": None,
    })]


def test_respuesta_con_ubicacion_usa_el_contrato_ubicacion(cliente, db):
    db.respuestas["ra_aceptar_respuesta_aclaracion"] = {"resultado": "aceptada"}
    cuerpo = {**RESPUESTA, "texto": None,
              "ubicacion": {"latitud": 8.9, "longitud": -79.7, "precision_metros": 12.5}}
    cliente.post("/aclaraciones/respuestas", json=cuerpo, headers=CABECERA)
    _, parametros = db.llamadas[0]
    assert parametros["p_texto"] is None
    assert parametros["p_ubicacion"] == {
        "latitud": 8.9, "longitud": -79.7, "fuente": "compartida",
        "precision_metros": 12.5, "representa_punto_atencion": None,
    }


def test_respuesta_de_quien_nunca_reporto_no_llama_a_la_rpc(cliente, db):
    r = cliente.post("/aclaraciones/respuestas", json={**RESPUESTA, "usuario_telegram_id": 999},
                     headers=CABECERA)
    assert r.json()["resultado"] == "autor_distinto"
    assert db.llamadas == []
    assert len(db.remitentes) == 1  # no se crea remitente


@pytest.mark.parametrize("cambios", [
    {"texto": None},
    {"ubicacion": {"latitud": 8.9, "longitud": -79.7}},
    {"texto": "a" * 4001},
    {"pregunta_mensaje_id": 0},
    {"texto": None, "ubicacion": {"latitud": 91, "longitud": 0}},
])
def test_respuesta_invalida_responde_422_sin_eco(cliente, db, cambios):
    r = cliente.post("/aclaraciones/respuestas", json={**RESPUESTA, **cambios}, headers=CABECERA)
    assert r.status_code == 422
    assert "aaaa" not in json.dumps(r.json()) and "80 personas" not in json.dumps(r.json())
    assert db.llamadas == []


def test_resultado_desconocido_de_la_rpc_responde_503(cliente, db):
    db.respuestas["ra_aceptar_respuesta_aclaracion"] = {"resultado": "quizas"}
    r = cliente.post("/aclaraciones/respuestas", json=RESPUESTA, headers=CABECERA)
    assert r.status_code == 503


# --- Comunes ---

@pytest.mark.parametrize("ruta, cuerpo", [
    ("/aclaraciones/reservar", {"trabajador_id": "bot:1"}),
    (f"/aclaraciones/{ACLARACION}/envio", {"trabajador_id": "bot:1", "estado": "fallido", "error": "x"}),
    ("/aclaraciones/respuestas", RESPUESTA),
])
def test_todas_las_rutas_exigen_el_secreto(cliente, db, ruta, cuerpo):
    assert cliente.post(ruta, json=cuerpo).status_code == 403
    assert db.llamadas == []


def test_error_de_la_base_responde_503(cliente, db):
    db.error = APIError({"message": "caída", "code": "XX000"})
    r = cliente.post("/aclaraciones/reservar", json={"trabajador_id": "bot:1"}, headers=CABECERA)
    assert r.status_code == 503 and r.json()["recuperable"] is True
