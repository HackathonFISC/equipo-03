"""Pruebas de las rutas por sector y destino (RPC de 0012 simuladas, sin red ni claves)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador, verificador_opcional
from api.dependencias import obtener_db, secreto_configurado
from api.main import app

TOKEN = "aaa.bbb.ccc"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
SECRETO = "secreto-de-prueba-0123456789"
BOT = {"X-Secreto-Bot": SECRETO}
USUARIO = uuid4()
SECTOR = uuid4()
PLAN = uuid4()
DESTINO = uuid4()
PUNTO = uuid4()
URL_ESTADO = f"/sectores/{SECTOR}/estado"
URL_SELECCION = f"/sectores/{SECTOR}/plan-vigente"
URL_DESTINO = f"/destinos/{DESTINO}/ensayo"


class Respuesta:
    def __init__(self, data):
        self.data = data


class Consulta:
    def __init__(self, base):
        self.base = base

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return Respuesta([self.base.rol] if self.base.rol else [])


class BaseFalsa:
    def __init__(self):
        self.rol = {"rol": "coordinador", "activo": True}
        self.llamadas, self.respuesta, self.error = [], None, None

    def table(self, nombre):
        assert nombre == "usuarios_operativos"
        return Consulta(self)

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
    def __init__(self):
        self.tokens = []

    def usuario_id(self, token):
        self.tokens.append(token)
        return USUARIO


def error_rpc(mensaje, codigo="55000"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


@pytest.fixture
def db():
    return BaseFalsa()


@pytest.fixture
def verificador():
    return VerificadorFalso()


@pytest.fixture
def cliente(db, verificador):
    app.dependency_overrides[obtener_db] = lambda: db
    app.dependency_overrides[obtener_verificador] = lambda: verificador
    app.dependency_overrides[verificador_opcional] = lambda: verificador
    app.dependency_overrides[secreto_configurado] = lambda: SECRETO
    yield TestClient(app)
    app.dependency_overrides.clear()


def estado_sin_plan(**extra):
    return {
        "esquema_version": "1.0",
        "consultado_en": "2026-10-17T10:00:00+00:00",
        "origen": "sintetico",
        "sector": {"sector_id": str(SECTOR), "nombre": "Sector V4", "distrito": "Arraijan", "corregimiento": None,
                   "origen": "sintetico", "estado_informacion": "sin_informacion"},
        "estado": "sin_plan_vigente",
        "plan_vigente": None,
        "puntos": [{"punto_atencion_id": str(PUNTO), "sector_id": str(SECTOR), "nombre": "Punto sin asignación",
                    "origen": "sintetico", "estado": "sin_asignacion", "parada_id": None, "litros_asignados": None,
                    "ventana_estimada": None, "motivo_sin_asignacion": "No hay plan vigente."}],
        **extra,
    }


# --- Estado del sector ----------------------------------------------------------------------


def test_estado_con_sesion_devuelve_el_contrato(cliente, db, verificador):
    db.respuesta = estado_sin_plan()
    respuesta = cliente.get(URL_ESTADO, headers=AUTH)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "sin_plan_vigente" and cuerpo["plan_vigente"] is None
    assert cuerpo["puntos"][0]["estado"] == "sin_asignacion"
    assert db.llamadas == [("ra_estado_sector_v4", {"p_sector_id": str(SECTOR)})]
    assert verificador.tokens == [TOKEN]


def test_estado_con_secreto_del_bot_no_verifica_sesion(cliente, db, verificador):
    db.respuesta = estado_sin_plan()
    assert cliente.get(URL_ESTADO, headers=BOT).status_code == 200
    assert verificador.tokens == []


def test_estado_acepta_respuesta_en_lista(cliente, db):
    db.respuesta = [estado_sin_plan()]
    assert cliente.get(URL_ESTADO, headers=AUTH).status_code == 200


@pytest.mark.parametrize("cabeceras", [{}, {"X-Secreto-Bot": "incorrecto-incorrecto"}, {"Authorization": "Basic x"}])
def test_estado_sin_credencial_valida_es_403_y_no_toca_la_base(cliente, db, cabeceras):
    respuesta = cliente.get(URL_ESTADO, headers=cabeceras)
    assert respuesta.status_code == 403 and respuesta.json()["codigo"] == "sin_permiso"
    assert db.llamadas == []


def test_estado_con_secreto_incorrecto_no_cae_a_la_sesion(cliente, db):
    respuesta = cliente.get(URL_ESTADO, headers={**AUTH, "X-Secreto-Bot": "incorrecto-incorrecto"})
    assert respuesta.status_code == 403 and db.llamadas == []


def test_estado_sin_verificador_configurado_y_sin_secreto_es_503(db):
    app.dependency_overrides[obtener_db] = lambda: db
    app.dependency_overrides[verificador_opcional] = lambda: None
    app.dependency_overrides[secreto_configurado] = lambda: SECRETO
    try:
        respuesta = TestClient(app).get(URL_ESTADO, headers=AUTH)
    finally:
        app.dependency_overrides.clear()
    assert respuesta.status_code == 503 and db.llamadas == []


def test_estado_de_sector_inexistente_es_422_y_no_un_sector_sin_plan(cliente, db):
    db.error = error_rpc("contrato_invalido: sector inexistente", "22023")
    respuesta = cliente.get(URL_ESTADO, headers=AUTH)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "contrato_invalido" and respuesta.json()["campos"] == ["sector_id"]


@pytest.mark.parametrize("data", [None, [], "texto", {"estado": "con_plan_vigente"}, estado_sin_plan(estado="con_plan_vigente")])
def test_estado_con_forma_inesperada_es_503(cliente, db, data):
    db.respuesta = data
    assert cliente.get(URL_ESTADO, headers=AUTH).status_code == 503


def test_estado_falla_de_base_es_503_y_no_sin_plan_vigente(cliente, db):
    db.error = error_rpc("deadlock detected", "40P01")
    respuesta = cliente.get(URL_ESTADO, headers=AUTH)
    assert respuesta.status_code == 503 and "deadlock" not in respuesta.text


def test_estado_con_id_que_no_es_uuid_es_422(cliente, db):
    assert cliente.get("/sectores/no-uuid/estado", headers=AUTH).status_code == 422
    assert db.llamadas == []


# --- Seleccionar plan -----------------------------------------------------------------------

CUERPO_SELECCION = {"plan_id": str(PLAN), "version": 2, "motivo": "Plan revisado para este sector"}


def test_seleccionar_usa_el_usuario_del_token(cliente, db):
    db.respuesta = {"sector_id": str(SECTOR), "plan_id": str(PLAN), "version": 2, "repetido": False}
    respuesta = cliente.post(URL_SELECCION, headers=AUTH, json=CUERPO_SELECCION)
    assert respuesta.status_code == 200 and respuesta.json()["repetido"] is False
    assert db.llamadas == [
        (
            "ra_seleccionar_plan_sector_v4",
            {"p_usuario_id": str(USUARIO), "p_sector_id": str(SECTOR), "p_plan_id": str(PLAN), "p_version": 2,
             "p_motivo": "Plan revisado para este sector"},
        )
    ]


def test_seleccionar_repetido_puede_venir_sin_plan(cliente, db):
    db.respuesta = {"sector_id": str(SECTOR), "repetido": True}
    cuerpo = cliente.post(URL_SELECCION, headers=AUTH, json=CUERPO_SELECCION).json()
    assert cuerpo["repetido"] is True and cuerpo["plan_id"] is None


@pytest.mark.parametrize(
    "mensaje, codigo, estado, esperado, fragmento",
    [
        ("sin_permiso: coordinador activo requerido", "42501", 403, "sin_permiso", "coordinador"),
        ("version_obsoleta: plan sin aprobación vigente o entradas cambiadas", "40001", 409, "version_obsoleta", "aprobación vigente"),
        ("contrato_invalido: sector ajeno al plan", "22023", 422, "contrato_invalido", "paradas en ese plan"),
        ("contrato_invalido: motivo requerido", "22023", 422, "contrato_invalido", ""),
    ],
)
def test_seleccionar_traduce_los_errores_de_la_rpc(cliente, db, mensaje, codigo, estado, esperado, fragmento):
    db.error = error_rpc(mensaje, codigo)
    respuesta = cliente.post(URL_SELECCION, headers=AUTH, json=CUERPO_SELECCION)
    assert respuesta.status_code == estado and respuesta.json()["codigo"] == esperado
    assert fragmento in respuesta.json()["mensaje"]
    assert mensaje not in respuesta.text


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {**CUERPO_SELECCION, "version": 0}, {**CUERPO_SELECCION, "motivo": ""}, {**CUERPO_SELECCION, "plan_id": "x"},
     {**CUERPO_SELECCION, "usuario_id": str(uuid4())}],
)
def test_seleccionar_cuerpo_invalido_es_422_sin_llamar_a_la_base(cliente, db, cuerpo):
    assert cliente.post(URL_SELECCION, headers=AUTH, json=cuerpo).status_code == 422
    assert db.llamadas == []


@pytest.mark.parametrize("rol", [None, {"rol": "consulta", "activo": True}, {"rol": "coordinador", "activo": False}])
def test_seleccionar_y_destino_exigen_coordinador_activo(cliente, db, rol):
    db.rol = rol
    assert cliente.post(URL_SELECCION, headers=AUTH, json=CUERPO_SELECCION).status_code == 403
    assert cliente.put(URL_DESTINO, headers=AUTH, json={"habilitado": True, "motivo": "m"}).status_code == 403
    assert db.llamadas == []


def test_seleccionar_y_destino_sin_sesion_son_403(cliente, db):
    assert cliente.post(URL_SELECCION, json=CUERPO_SELECCION).status_code == 403
    assert cliente.put(URL_DESTINO, json={"habilitado": True, "motivo": "m"}).status_code == 403
    assert cliente.post(URL_SELECCION, headers=BOT, json=CUERPO_SELECCION).status_code == 403
    assert db.llamadas == []


# --- Destino de ensayo ----------------------------------------------------------------------


def test_destino_de_ensayo_envia_usuario_del_token_y_habilitado(cliente, db):
    db.respuesta = {"destino_id": str(DESTINO), "habilitado": True}
    respuesta = cliente.put(URL_DESTINO, headers=AUTH, json={"habilitado": True, "motivo": "Solo chat autorizado de ensayo"})
    assert respuesta.status_code == 200 and respuesta.json() == {"destino_id": str(DESTINO), "habilitado": True}
    assert db.llamadas == [
        (
            "ra_configurar_destino_ensayo_v4",
            {"p_usuario_id": str(USUARIO), "p_destino_id": str(DESTINO), "p_habilitado": True,
             "p_motivo": "Solo chat autorizado de ensayo"},
        )
    ]


def test_destino_no_autorizado_es_403_con_mensaje_claro(cliente, db):
    db.error = error_rpc("sin_permiso: destino Telegram autorizado requerido", "42501")
    respuesta = cliente.put(URL_DESTINO, headers=AUTH, json={"habilitado": True, "motivo": "m"})
    assert respuesta.status_code == 403 and "destino de Telegram" in respuesta.json()["mensaje"]


@pytest.mark.parametrize("cuerpo", [{}, {"habilitado": True}, {"habilitado": "si", "motivo": "m"}, {"habilitado": True, "motivo": ""}])
def test_destino_cuerpo_invalido_es_422(cliente, db, cuerpo):
    assert cliente.put(URL_DESTINO, headers=AUTH, json=cuerpo).status_code == 422
    assert db.llamadas == []


def test_destino_falla_de_base_es_503(cliente, db):
    db.error = error_rpc("boom", "XX000")
    assert cliente.put(URL_DESTINO, headers=AUTH, json={"habilitado": False, "motivo": "m"}).status_code == 503
