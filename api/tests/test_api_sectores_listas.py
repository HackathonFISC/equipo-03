"""Listas de sectores y destinos para el panel (tablas simuladas, sin red ni claves)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.main import app

AUTH = {"Authorization": "Bearer aaa.bbb.ccc"}
USUARIO = uuid4()
D1, D2 = uuid4(), uuid4()


class Respuesta:
    def __init__(self, data):
        self.data = data


class Consulta:
    def __init__(self, base, tabla):
        self.base, self.tabla, self.filtros = base, tabla, []

    def select(self, columnas):
        self.base.columnas.append((self.tabla, columnas))
        return self

    def eq(self, columna, valor):
        self.filtros.append((columna, valor))
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        self.base.filtros[self.tabla] = self.filtros
        error = self.base.errores.get(self.tabla)
        if error:
            raise error
        if self.tabla == "usuarios_operativos":
            return Respuesta([self.base.rol] if self.base.rol else [])
        return Respuesta(self.base.tablas.get(self.tabla, []))


class BaseFalsa:
    def __init__(self):
        self.rol = {"rol": "coordinador", "activo": True}
        self.tablas, self.errores, self.columnas, self.filtros = {}, {}, [], {}

    def table(self, nombre):
        return Consulta(self, nombre)


class Verificador:
    def usuario_id(self, _token):
        return USUARIO


def api_error(codigo, mensaje="fallo"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


@pytest.fixture
def db():
    return BaseFalsa()


@pytest.fixture
def cliente(db):
    app.dependency_overrides[obtener_db] = lambda: db
    app.dependency_overrides[obtener_verificador] = lambda: Verificador()
    yield TestClient(app)
    app.dependency_overrides.clear()


def sector(**extra):
    return {"sector_id": str(uuid4()), "nombre": "Puerto Caimito", "distrito": "La Chorrera",
            "corregimiento": None, "origen": "sintetico", **extra}


def test_sectores_con_sesion_devuelve_el_catalogo(cliente, db):
    db.tablas["sectores"] = [sector(), sector(nombre="Otro", origen="real")]
    respuesta = cliente.get("/sectores", headers=AUTH)
    assert respuesta.status_code == 200
    assert [s["nombre"] for s in respuesta.json()] == ["Puerto Caimito", "Otro"]
    assert respuesta.json()[1]["origen"] == "real"


def test_sectores_no_pide_columnas_de_fuente_ni_de_personas(cliente, db):
    cliente.get("/sectores", headers=AUTH)
    columnas = dict(db.columnas)["sectores"]
    assert "fuente" not in columnas and "creado_por" not in columnas and "motivo" not in columnas


def test_sectores_sin_sesion_es_403(cliente, db):
    assert cliente.get("/sectores").status_code == 403


def test_sectores_vacio_es_lista_vacia(cliente, db):
    assert cliente.get("/sectores", headers=AUTH).json() == []


def test_sectores_con_fila_invalida_es_503(cliente, db):
    db.tablas["sectores"] = [sector(origen="inventado")]
    assert cliente.get("/sectores", headers=AUTH).status_code == 503


def test_sectores_falla_de_base_es_503(cliente, db):
    db.errores["sectores"] = api_error("XX000", "secreto interno")
    respuesta = cliente.get("/sectores", headers=AUTH)
    assert respuesta.status_code == 503 and "secreto interno" not in respuesta.text


def test_destinos_oculta_el_identificador_completo(cliente, db):
    db.tablas["destinos"] = [{"destino_id": str(D1), "identificador_externo": "7854737387", "autorizado": True}]
    db.tablas["destinos_ensayo_v4"] = [{"destino_id": str(D1), "habilitado": True}]
    respuesta = cliente.get("/destinos", headers=AUTH)
    assert respuesta.status_code == 200
    destino = respuesta.json()[0]
    assert destino == {"destino_id": str(D1), "referencia": "terminado en 7387", "autorizado": True, "habilitado_ensayo": True}
    assert "7854737387" not in respuesta.text
    assert db.filtros["destinos"] == [("canal", "telegram")]


def test_destino_sin_fila_de_ensayo_figura_como_no_habilitado(cliente, db):
    db.tablas["destinos"] = [{"destino_id": str(D2), "identificador_externo": "-1001234", "autorizado": False}]
    db.tablas["destinos_ensayo_v4"] = []
    destino = cliente.get("/destinos", headers=AUTH).json()[0]
    assert destino["autorizado"] is False and destino["habilitado_ensayo"] is False


@pytest.mark.parametrize("codigo", ["PGRST205", "42P01"])
def test_sin_migracion_0012_el_estado_de_ensayo_es_desconocido(cliente, db, codigo):
    db.tablas["destinos"] = [{"destino_id": str(D1), "identificador_externo": "7854737387", "autorizado": True}]
    db.errores["destinos_ensayo_v4"] = api_error(codigo)
    respuesta = cliente.get("/destinos", headers=AUTH)
    assert respuesta.status_code == 200 and respuesta.json()[0]["habilitado_ensayo"] is None


def test_otro_fallo_de_la_tabla_de_ensayo_no_se_oculta(cliente, db):
    db.tablas["destinos"] = [{"destino_id": str(D1), "identificador_externo": "7854737387", "autorizado": True}]
    db.errores["destinos_ensayo_v4"] = api_error("XX000")
    assert cliente.get("/destinos", headers=AUTH).status_code == 503


def test_destinos_exige_coordinador_activo(cliente, db):
    db.tablas["destinos"] = [{"destino_id": str(D1), "identificador_externo": "7854737387", "autorizado": True}]
    for rol in (None, {"rol": "consulta", "activo": True}, {"rol": "coordinador", "activo": False}):
        db.rol = rol
        assert cliente.get("/destinos", headers=AUTH).status_code == 403
    assert cliente.get("/destinos").status_code == 403


def test_destino_con_identificador_corto_no_se_filtra(cliente, db):
    db.tablas["destinos"] = [{"destino_id": str(D1), "identificador_externo": "123", "autorizado": True}]
    db.tablas["destinos_ensayo_v4"] = []
    respuesta = cliente.get("/destinos", headers=AUTH)
    assert respuesta.json()[0]["referencia"] == "identificador corto" and "123" not in respuesta.text


def test_destinos_vacio_no_consulta_la_tabla_de_ensayo(cliente, db):
    db.errores["destinos_ensayo_v4"] = api_error("XX000")
    assert cliente.get("/destinos", headers=AUTH).json() == []
