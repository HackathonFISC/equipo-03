"""Pruebas de validar el lugar de un incidente, con RPC y sesión simuladas (sin red ni claves).

La RPC real es ra_validar_lugar_v1 (migración 0020, probada en supabase/tests/0020_validar_lugar_smoke.sql);
aquí se comprueba quién llama, qué se envía y cómo se traducen sus errores.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.main import app
from api.servicios.incidentes import _coordenadas

TOKEN = "aaa.bbb.ccc"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
USUARIO = uuid4()
INCIDENTE = uuid4()
CUERPO = {"version_incidente": 3, "evidencia": "Llamé a la junta comunal y confirmaron el punto."}
URL = f"/incidentes/{INCIDENTE}/validar-lugar"


class Respuesta:
    def __init__(self, data):
        self.data = data


class Consulta:
    def __init__(self, base, resultado):
        self.base, self.resultado = base, resultado

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        if self.base.error_rol:
            raise self.base.error_rol
        return Respuesta(self.resultado)


class BaseFalsa:
    def __init__(self):
        self.rol = {"rol": "coordinador", "activo": True}
        self.llamadas, self.respuesta, self.error, self.error_rol = [], None, None, None

    def table(self, nombre):
        assert nombre == "usuarios_operativos"
        return Consulta(self, [self.rol] if self.rol else [])

    def rpc(self, nombre, parametros):
        self.llamadas.append((nombre, parametros))
        base = self

        class Llamada:
            def execute(self):
                if base.error:
                    raise base.error
                return Respuesta(base.respuesta)

        return Llamada()


class VerificadorFalso:
    def usuario_id(self, token):
        return USUARIO


def error_rpc(mensaje, codigo="55000"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


@pytest.fixture
def db():
    return BaseFalsa()


@pytest.fixture
def cliente(db):
    app.dependency_overrides[obtener_db] = lambda: db
    app.dependency_overrides[obtener_verificador] = lambda: VerificadorFalso()
    yield TestClient(app)
    app.dependency_overrides.clear()


def validado():
    return {"incidente_id": str(INCIDENTE), "version": 4, "estado_validacion": "validada", "faltantes": ["Otro faltante"]}


def test_valida_con_el_usuario_del_token_y_pasa_la_evidencia(cliente, db):
    db.respuesta = validado()
    respuesta = cliente.post(URL, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == 200
    assert respuesta.json() == validado()
    assert db.llamadas == [
        (
            "ra_validar_lugar_v1",
            {
                "p_usuario_id": str(USUARIO),
                "p_incidente_id": str(INCIDENTE),
                "p_version": 3,
                "p_evidencia": "Llamé a la junta comunal y confirmaron el punto.",
            },
        )
    ]


def test_el_navegador_no_puede_elegir_quien_valida(cliente, db):
    respuesta = cliente.post(URL, headers=AUTH, json={**CUERPO, "usuario_id": str(uuid4())})
    assert respuesta.status_code == 422
    assert db.llamadas == []


@pytest.mark.parametrize("cuerpo", [
    {"version_incidente": 3, "evidencia": "corta"},
    {"version_incidente": 3, "evidencia": "   " + "x" * 5 + "   "},
    {"version_incidente": 3, "evidencia": "x" * 2001},
    {"version_incidente": 0, "evidencia": "Evidencia suficientemente larga"},
    {"version_incidente": "3", "evidencia": "Evidencia suficientemente larga"},
    {"evidencia": "Evidencia suficientemente larga"},
    {"version_incidente": 3},
])
def test_rechaza_cuerpos_invalidos_sin_llamar_a_la_base(cliente, db, cuerpo):
    assert cliente.post(URL, headers=AUTH, json=cuerpo).status_code == 422
    assert db.llamadas == []


def test_sin_sesion_no_valida(cliente, db):
    assert cliente.post(URL, json=CUERPO).status_code in (401, 403)
    assert db.llamadas == []


@pytest.mark.parametrize("rol", [None, {"rol": "observador", "activo": True}, {"rol": "coordinador", "activo": False}])
def test_solo_un_coordinador_activo_valida(cliente, db, rol):
    db.rol = rol
    respuesta = cliente.post(URL, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "sin_permiso"
    assert db.llamadas == []


@pytest.mark.parametrize("mensaje,codigo_sql,estado,codigo", [
    ("version_obsoleta: El incidente cambió", "40001", 409, "version_obsoleta"),
    ("lugar_ya_resuelto: El lugar ya está validada", "55000", 409, "version_obsoleta"),
    ("lugar_sin_punto: sin punto", "22023", None, "datos_insuficientes"),
    ("contrato_invalido: evidencia", "22023", None, "contrato_invalido"),
    ("sin_permiso: no", "42501", 403, "sin_permiso"),
])
def test_traduce_los_errores_de_la_rpc(cliente, db, mensaje, codigo_sql, estado, codigo):
    db.error = error_rpc(mensaje, codigo_sql)
    respuesta = cliente.post(URL, headers=AUTH, json=CUERPO)
    assert respuesta.json()["codigo"] == codigo
    if estado is not None:
        assert respuesta.status_code == estado


def test_otra_falla_de_la_base_es_proveedor_no_disponible(cliente, db):
    db.error = error_rpc("connection reset", "08006")
    respuesta = cliente.post(URL, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "proveedor_no_disponible"
    assert respuesta.json()["recuperable"] is True


def test_respuesta_de_la_rpc_con_forma_inesperada(cliente, db):
    db.respuesta = {"estado_validacion": "pendiente"}
    assert cliente.post(URL, headers=AUTH, json=CUERPO).status_code == 503


def test_acepta_la_respuesta_en_lista(cliente, db):
    db.respuesta = [validado()]
    assert cliente.post(URL, headers=AUTH, json=CUERPO).status_code == 200


# --- Coordenadas del catálogo que se muestran en el mapa ------------------------------------

BASE = {"punto_atencion_id": str(uuid4()), "nombre": "Escuela El Coco"}


def test_coordenadas_validas_del_catalogo_se_conservan():
    c = _coordenadas({**BASE, "latitud": 8.86672, "longitud": -79.81024, "precision_metros": 50, "fuente_ubicacion": "catalogo"})
    assert c == {"latitud": 8.86672, "longitud": -79.81024, "precision_metros": 50, "fuente_ubicacion": "catalogo"}


@pytest.mark.parametrize("extra", [{}, {"latitud": 8.9}, {"longitud": -79.8}, {"latitud": 99, "longitud": 0},
                                   {"latitud": "a", "longitud": 1}, {"latitud": None, "longitud": None},
                                   {"latitud": float("nan"), "longitud": 1}])
def test_coordenadas_invalidas_o_incompletas_no_se_inventan(extra):
    assert _coordenadas({**BASE, **extra}) == {}
