"""Registro general de eventos (tablas simuladas, sin red ni claves)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.main import app

AUTH = {"Authorization": "Bearer aaa.bbb.ccc"}
EJECUCION = "7c1b7d0e-4f0a-4c53-9c64-1a2b3c4d5e6f"


def evento(**cambios):
    base = {
        "evento_id": str(uuid4()), "ejecucion_id": EJECUCION, "agente": "ingesta", "actor_tipo": "agente",
        "decision": "Interpretó el mensaje", "herramienta": "gemini.generateContent",
        "resultado": "Reporte interpretado", "duracion_ms": 840, "siguiente_estado": "pendiente",
        "origen": "real", "creado_en": "2026-10-17T13:00:00+00:00",
    }
    return {**base, **cambios}


class Consulta:
    def __init__(self, base):
        self.base = base

    def select(self, columnas):
        self.base.columnas = columnas
        return self

    def eq(self, columna, valor):
        self.base.filtros.append((columna, valor))
        return self

    def order(self, columna, desc=False):
        self.base.orden = (columna, desc)
        return self

    def limit(self, n):
        self.base.limite = n
        return self

    def execute(self):
        if self.base.error:
            raise self.base.error
        return type("R", (), {"data": self.base.filas})()


class Base:
    def __init__(self):
        self.filas, self.error = [evento()], None
        self.filtros, self.columnas, self.orden, self.limite = [], "", None, None

    def table(self, nombre):
        assert nombre == "eventos"
        return Consulta(self)


class Verificador:
    def usuario_id(self, _token):
        return uuid4()


@pytest.fixture
def base():
    b = Base()
    app.dependency_overrides[obtener_db] = lambda: b
    app.dependency_overrides[obtener_verificador] = lambda: Verificador()
    yield b
    app.dependency_overrides.clear()


def test_lista_los_mas_recientes_primero_con_limite_por_defecto(base):
    r = TestClient(app).get("/eventos", headers=AUTH)

    assert r.status_code == 200
    assert r.json()[0]["decision"] == "Interpretó el mensaje"
    assert base.orden == ("creado_en", True)
    assert base.limite == 100
    assert base.filtros == []


def test_no_pide_datos_internos(base):
    TestClient(app).get("/eventos", headers=AUTH)

    for interno in ("detalles", "entrada_ids", "salida_ids", "usuario_id"):
        assert interno not in base.columnas


def test_aplica_los_filtros(base):
    r = TestClient(app).get(
        "/eventos", params={"agente": "territorial", "actor_tipo": "agente", "ejecucion_id": EJECUCION, "limite": 25},
        headers=AUTH,
    )

    assert r.status_code == 200
    assert ("agente", "territorial") in base.filtros
    assert ("actor_tipo", "agente") in base.filtros
    assert ("ejecucion_id", EJECUCION) in base.filtros
    assert base.limite == 25


def test_evento_de_una_persona_no_necesita_agente(base):
    base.filas = [evento(agente=None, actor_tipo="coordinador", herramienta=None, siguiente_estado=None)]

    r = TestClient(app).get("/eventos", headers=AUTH)

    assert r.status_code == 200
    assert r.json()[0]["agente"] is None
    assert r.json()[0]["actor_tipo"] == "coordinador"


@pytest.mark.parametrize("params", [{"agente": "otro"}, {"actor_tipo": "robot"}, {"limite": 0}, {"limite": 201}, {"ejecucion_id": "x"}])
def test_filtros_invalidos_responden_422(base, params):
    assert TestClient(app).get("/eventos", params=params, headers=AUTH).status_code == 422


def test_sin_sesion_responde_403(base):
    assert TestClient(app).get("/eventos").status_code == 403


def test_fallo_de_la_base_responde_503(base):
    base.error = APIError({"message": "x", "code": "XX000", "hint": None, "details": None})

    assert TestClient(app).get("/eventos", headers=AUTH).status_code == 503


def test_evento_guardado_con_formato_roto_responde_503(base):
    base.filas = [evento(duracion_ms="mucho")]

    assert TestClient(app).get("/eventos", headers=AUTH).status_code == 503
