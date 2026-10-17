"""Políticas activas para el formulario de revisión (tablas simuladas, sin red ni claves)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.main import app

AUTH = {"Authorization": "Bearer aaa.bbb.ccc"}
POLITICA = {
    "politica_version": "oeste-prioridad-apoyo-pa-1", "fundamento": "Apoyo a puntos sin agua",
    "peso_duracion": 0.4, "peso_vulnerabilidad": 0.4, "peso_poblacion": 0.2,
    "tope_horas": 72.0, "tope_personas": 500, "origen": "sintetico",
}


class Consulta:
    def __init__(self, base):
        self.base, self.filtros = base, []

    def select(self, columnas):
        self.base.columnas = columnas
        return self

    def eq(self, columna, valor):
        self.filtros.append((columna, valor))
        return self

    def order(self, *_, **__):
        return self

    def execute(self):
        if self.base.error:
            raise self.base.error
        self.base.filtros = self.filtros
        return type("R", (), {"data": self.base.filas})()


class Base:
    def __init__(self):
        self.filas, self.error, self.filtros, self.columnas = [POLITICA], None, [], ""

    def table(self, nombre):
        assert nombre == "politicas_prioridad"
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


def test_lista_solo_las_activas(base):
    r = TestClient(app).get("/politicas", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == [POLITICA]
    assert ("estado", "activa") in base.filtros
    assert "creado_por" not in base.columnas


def test_sin_sesion_responde_403(base):
    assert TestClient(app).get("/politicas").status_code == 403


def test_fallo_de_la_base_responde_503(base):
    base.error = APIError({"message": "x", "code": "XX000", "hint": None, "details": None})

    assert TestClient(app).get("/politicas", headers=AUTH).status_code == 503
