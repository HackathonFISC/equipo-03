"""Pruebas de la verificación de sesión y del rol de coordinador (sin red ni claves reales)."""
import json
from uuid import uuid4

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import (
    UsuarioAutenticado,
    VerificadorSupabase,
    coordinador_actual,
    extraer_token,
    obtener_verificador,
)
from api.dependencias import obtener_db
from api.errores_http import ErrorApi, respuesta_error
from api.main import app
from contratos.errores import CodigoError

TOKEN = "aaa.bbb.ccc"
USUARIO = uuid4()
URL = "https://proyecto.supabase.co"


def verificador_con(manejador) -> VerificadorSupabase:
    return VerificadorSupabase(URL, "clave-publica", transporte=httpx.MockTransport(manejador))


def error_de(callable_):
    with pytest.raises(ErrorApi) as capturado:
        callable_()
    return capturado.value


# --- extraer_token -----------------------------------------------------------------------


def test_extrae_token_bearer():
    assert extraer_token(f"Bearer {TOKEN}") == TOKEN
    assert extraer_token(f"bearer {TOKEN}") == TOKEN


@pytest.mark.parametrize(
    "encabezado",
    [None, "", "Bearer", f"Basic {TOKEN}", f"Bearer {TOKEN} extra", "Bearer sin-puntos", "Bearer a.b.c d", "Bearer " + "a" * 5000 + ".b.c"],
)
def test_rechaza_encabezados_invalidos(encabezado):
    error = error_de(lambda: extraer_token(encabezado))
    assert error.codigo is CodigoError.SIN_PERMISO


# --- VerificadorSupabase -----------------------------------------------------------------


def test_verifica_token_y_envia_los_encabezados_correctos():
    vistos = []

    def manejador(peticion: httpx.Request):
        vistos.append(peticion)
        return httpx.Response(200, json={"id": str(USUARIO), "aud": "authenticated", "email": "a@b.c"})

    assert verificador_con(manejador).usuario_id(TOKEN) == USUARIO
    peticion = vistos[0]
    assert peticion.method == "GET"
    assert str(peticion.url) == f"{URL}/auth/v1/user"
    assert peticion.headers["authorization"] == f"Bearer {TOKEN}"
    assert peticion.headers["apikey"] == "clave-publica"


@pytest.mark.parametrize("estado", [400, 401, 403])
def test_token_rechazado_por_supabase_es_sin_permiso(estado):
    error = error_de(lambda: verificador_con(lambda p: httpx.Response(estado, json={})).usuario_id(TOKEN))
    assert error.codigo is CodigoError.SIN_PERMISO


@pytest.mark.parametrize("estado", [404, 429, 500, 502, 503])
def test_otros_estados_son_proveedor_no_disponible(estado):
    error = error_de(lambda: verificador_con(lambda p: httpx.Response(estado, json={})).usuario_id(TOKEN))
    assert error.codigo is CodigoError.PROVEEDOR_NO_DISPONIBLE
    assert error.recuperable


def test_fallo_de_red_es_proveedor_no_disponible_y_no_filtra_el_token():
    def manejador(peticion):
        raise httpx.ConnectError(f"no conecta con {peticion.headers['authorization']}")

    error = error_de(lambda: verificador_con(manejador).usuario_id(TOKEN))
    assert error.codigo is CodigoError.PROVEEDOR_NO_DISPONIBLE
    assert TOKEN not in str(error) and TOKEN not in error.mensaje


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(200, content=b"no es json"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"id": "no-es-uuid"}),
        httpx.Response(200, json=["lista"]),
        httpx.Response(200, json=None),
    ],
)
def test_respuesta_inesperada_es_proveedor_no_disponible(respuesta):
    error = error_de(lambda: verificador_con(lambda p: respuesta).usuario_id(TOKEN))
    assert error.codigo is CodigoError.PROVEEDOR_NO_DISPONIBLE


def test_sesion_anonima_se_rechaza():
    error = error_de(
        lambda: verificador_con(lambda p: httpx.Response(200, json={"id": str(USUARIO), "is_anonymous": True})).usuario_id(TOKEN)
    )
    assert error.codigo is CodigoError.SIN_PERMISO


def test_no_sigue_redirecciones():
    def manejador(peticion):
        return httpx.Response(302, headers={"location": "https://otro.sitio/robar"})

    error = error_de(lambda: verificador_con(manejador).usuario_id(TOKEN))
    assert error.codigo is CodigoError.PROVEEDOR_NO_DISPONIBLE


# --- Rol y rutas -------------------------------------------------------------------------


class Respuesta:
    def __init__(self, data):
        self.data = data


class ConsultaFalsa:
    def __init__(self, base):
        self.base = base

    def select(self, columnas):
        self.base.columnas = columnas
        return self

    def eq(self, columna, valor):
        self.base.filtros.append((columna, valor))
        return self

    def limit(self, n):
        return self

    def execute(self):
        if self.base.error:
            raise self.base.error
        return Respuesta(self.base.filas)


class BaseFalsa:
    def __init__(self):
        self.filas, self.error, self.filtros, self.columnas = [], None, [], None

    def table(self, nombre):
        assert nombre == "usuarios_operativos"
        return ConsultaFalsa(self)


class VerificadorFalso:
    def __init__(self, usuario=USUARIO, error=None):
        self.usuario, self.error, self.tokens = usuario, error, []

    def usuario_id(self, token):
        self.tokens.append(token)
        if self.error:
            raise self.error
        return self.usuario


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
    yield TestClient(app)
    app.dependency_overrides.clear()


AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_sesion_sin_token_es_403(cliente):
    respuesta = cliente.get("/sesion")
    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "sin_permiso"


def test_sesion_con_token_rechazado_es_403(cliente, verificador):
    verificador.error = ErrorApi(CodigoError.SIN_PERMISO, "La sesión no es válida o venció.")
    respuesta = cliente.get("/sesion", headers=AUTH)
    assert respuesta.status_code == 403


def test_sesion_con_proveedor_caido_es_503(cliente, verificador):
    verificador.error = ErrorApi(CodigoError.PROVEEDOR_NO_DISPONIBLE, "No se pudo verificar.", recuperable=True)
    assert cliente.get("/sesion", headers=AUTH).status_code == 503


@pytest.mark.parametrize(
    "fila, rol, activo, es_coordinador",
    [
        (None, None, False, False),
        ({"rol": "coordinador", "activo": True}, "coordinador", True, True),
        ({"rol": "coordinador", "activo": False}, "coordinador", False, False),
        ({"rol": "consulta", "activo": True}, "consulta", True, False),
        ({"rol": "conductor", "activo": True}, "conductor", True, False),
    ],
)
def test_sesion_informa_rol(cliente, db, fila, rol, activo, es_coordinador):
    db.filas = [fila] if fila else []
    respuesta = cliente.get("/sesion", headers=AUTH)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo == {"usuario_id": str(USUARIO), "rol": rol, "activo": activo, "es_coordinador": es_coordinador}


def test_el_usuario_sale_del_token_y_no_de_lo_que_envia_el_navegador(cliente, db, verificador):
    otro = uuid4()
    db.filas = [{"rol": "coordinador", "activo": True}]
    respuesta = cliente.get(f"/sesion?usuario_id={otro}", headers={**AUTH, "X-Usuario-Id": str(otro)})
    assert respuesta.json()["usuario_id"] == str(USUARIO)
    assert ("usuario_id", str(USUARIO)) in db.filtros and ("usuario_id", str(otro)) not in db.filtros
    assert verificador.tokens == [TOKEN]


def test_fallo_de_base_al_leer_el_rol_es_503(cliente, db):
    db.error = APIError({"message": "boom", "code": "XX000", "hint": None, "details": None})
    assert cliente.get("/sesion", headers=AUTH).status_code == 503


# --- coordinador_actual ------------------------------------------------------------------


@pytest.fixture
def app_coordinador(db, verificador):
    mini = FastAPI()
    mini.add_exception_handler(ErrorApi, lambda peticion, error: respuesta_error(error))

    @mini.post("/solo-coordinador")
    def ruta(usuario: UsuarioAutenticado = Depends(coordinador_actual)):
        return {"usuario_id": str(usuario.usuario_id)}

    mini.dependency_overrides[obtener_db] = lambda: db
    mini.dependency_overrides[obtener_verificador] = lambda: verificador
    return TestClient(mini)


def test_coordinador_activo_pasa_y_su_identidad_es_la_del_token(app_coordinador, db):
    db.filas = [{"rol": "coordinador", "activo": True}]
    respuesta = app_coordinador.post("/solo-coordinador", headers=AUTH, json={"usuario_id": str(uuid4())})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario_id": str(USUARIO)}


@pytest.mark.parametrize(
    "filas",
    [[], [{"rol": "consulta", "activo": True}], [{"rol": "coordinador", "activo": False}], [{"rol": "coordinador"}]],
)
def test_quien_no_es_coordinador_activo_recibe_403(app_coordinador, db, filas):
    db.filas = filas
    respuesta = app_coordinador.post("/solo-coordinador", headers=AUTH)
    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "sin_permiso"


def test_sin_token_no_se_consulta_la_base(app_coordinador, db):
    respuesta = app_coordinador.post("/solo-coordinador")
    assert respuesta.status_code == 403
    assert db.filtros == []


def test_sin_configuracion_el_verificador_real_responde_503(monkeypatch):
    from api import auth

    auth._clave_publica.cache_clear()
    auth.obtener_verificador.cache_clear()
    monkeypatch.setattr(auth, "_clave_publica", lambda: "")
    mini = FastAPI()
    mini.add_exception_handler(ErrorApi, lambda peticion, error: respuesta_error(error))

    @mini.get("/x")
    def ruta(usuario: UsuarioAutenticado = Depends(auth.usuario_autenticado)):
        return {}

    try:
        respuesta = TestClient(mini).get("/x", headers=AUTH)
    finally:
        auth.obtener_verificador.cache_clear()
    assert respuesta.status_code == 503
    assert json.loads(respuesta.text)["codigo"] == "proveedor_no_disponible"
