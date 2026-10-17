"""Pruebas de aprobar y rechazar planes con RPC y sesión simuladas (sin red ni claves).

Las RPC reales son de la migración 0003; aquí se comprueba quién llama, qué se envía y cómo se traducen sus errores.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.main import app

TOKEN = "aaa.bbb.ccc"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
USUARIO = uuid4()
PLAN = uuid4()
BLOQUEO = "Política sintética: el cálculo no acredita autorización operativa ni calidad del agua."
CUERPO = {"datos_version": "d1", "politica_version": "p1", "motivo": "Revisado con el equipo", "bloqueos_reconocidos": [BLOQUEO]}
URL_APROBAR = f"/planes/{PLAN}/versiones/1/aprobar"
URL_RECHAZAR = f"/planes/{PLAN}/versiones/1/rechazar"


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


def aprobado(repetido=False):
    return {"plan_id": str(PLAN), "version": 1, "aprobacion_id": str(uuid4()), "estado": "aprobado",
            "ejecucion_id": str(uuid4()), "repetido": repetido}


def rechazado(repetido=False):
    return {"plan_id": str(PLAN), "version": 1, "estado": "rechazado", "repetido": repetido}


# --- Aprobar ------------------------------------------------------------------------------


def test_aprobar_usa_el_usuario_del_token_y_pasa_lo_revisado(cliente, db):
    db.respuesta = aprobado()
    respuesta = cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aprobado" and respuesta.json()["repetido"] is False
    assert db.llamadas == [
        (
            "ra_aprobar_plan",
            {
                "p_usuario_id": str(USUARIO),
                "p_plan_id": str(PLAN),
                "p_version": 1,
                "p_datos_version": "d1",
                "p_politica_version": "p1",
                "p_motivo": "Revisado con el equipo",
                "p_bloqueos_reconocidos": [BLOQUEO],
            },
        )
    ]


def test_el_navegador_no_puede_elegir_quien_aprueba(cliente, db):
    db.respuesta = aprobado()
    respuesta = cliente.post(URL_APROBAR, headers=AUTH, json={**CUERPO, "usuario_id": str(uuid4())})
    assert respuesta.status_code == 422
    assert db.llamadas == []


def test_aprobar_repetido_devuelve_el_acuse(cliente, db):
    db.respuesta = aprobado(repetido=True)
    assert cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO).json()["repetido"] is True


def test_aprobar_acepta_respuesta_en_lista(cliente, db):
    db.respuesta = [aprobado()]
    assert cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO).status_code == 200


@pytest.mark.parametrize(
    "mensaje, codigo, estado, esperado",
    [
        ("sin_permiso: solo un coordinador activo puede aprobar planes", "42501", 403, "sin_permiso"),
        ("version_obsoleta: las entradas cambiaron desde el cálculo del plan", "40001", 409, "version_obsoleta"),
        ("politica_no_activa: la política del plan no está activa", "55000", 409, "politica_no_activa"),
        ("plan_no_verificado: el plan no tiene una verificación independiente válida", "55000", 409, "plan_no_verificado"),
        ("cobertura_critica_pendiente: hay puntos críticos sin atender", "55000", 409, "cobertura_critica_pendiente"),
        ("plan_ya_resuelto: el plan está en estado invalidado", "55000", 409, "version_obsoleta"),
        ("bloqueos_sin_reconocer: falta reconocer: algo", "22023", 422, "contrato_invalido"),
        ("contrato_invalido: el plan no existe", "22023", 422, "contrato_invalido"),
    ],
)
def test_errores_de_la_rpc_se_traducen_a_codigos_de_dominio(cliente, db, mensaje, codigo, estado, esperado):
    db.error = error_rpc(mensaje, codigo)
    respuesta = cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == estado
    assert respuesta.json()["codigo"] == esperado
    # Nunca se devuelve el texto interno de la base: solo el mensaje preparado para la persona.
    assert mensaje not in respuesta.text


def test_bloqueos_sin_reconocer_indica_el_campo(cliente, db):
    db.error = error_rpc("bloqueos_sin_reconocer: falta reconocer: x", "22023")
    assert cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO).json()["campos"] == ["bloqueos_reconocidos"]


def test_sqlstate_conocido_sin_prefijo_tambien_se_traduce(cliente, db):
    db.error = error_rpc("permission denied", "42501")
    respuesta = cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == 403


def test_falla_desconocida_de_la_base_es_503_recuperable(cliente, db):
    db.error = error_rpc("deadlock detected", "40P01")
    respuesta = cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO)
    assert respuesta.status_code == 503
    assert respuesta.json()["recuperable"] is True
    assert "deadlock" not in respuesta.text


@pytest.mark.parametrize("data", [None, [], "texto", {"estado": "aprobado"}, {**rechazado(), "estado": "otro"}])
def test_respuesta_inesperada_de_la_rpc_es_503(cliente, db, data):
    db.respuesta = data
    assert cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO).status_code == 503


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {**CUERPO, "motivo": ""},
        {**CUERPO, "motivo": "   "},
        {**CUERPO, "motivo": "x" * 4001},
        {**CUERPO, "datos_version": ""},
        {**CUERPO, "bloqueos_reconocidos": "no es lista"},
        {**CUERPO, "bloqueos_reconocidos": [""]},
        {**CUERPO, "bloqueos_reconocidos": ["x"] * 21},
        {k: v for k, v in CUERPO.items() if k != "bloqueos_reconocidos"},
    ],
)
def test_cuerpo_invalido_es_422_sin_llamar_a_la_base(cliente, db, cuerpo):
    assert cliente.post(URL_APROBAR, headers=AUTH, json=cuerpo).status_code == 422
    assert db.llamadas == []


@pytest.mark.parametrize("ruta", ["/planes/no-uuid/versiones/1/aprobar", f"/planes/{PLAN}/versiones/0/aprobar", f"/planes/{PLAN}/versiones/-1/aprobar", f"/planes/{PLAN}/versiones/x/aprobar"])
def test_ruta_invalida_es_422(cliente, db, ruta):
    assert cliente.post(ruta, headers=AUTH, json=CUERPO).status_code == 422
    assert db.llamadas == []


# --- Permisos -----------------------------------------------------------------------------


@pytest.mark.parametrize("url, cuerpo", [(URL_APROBAR, CUERPO), (URL_RECHAZAR, {"motivo": "no"})])
def test_sin_sesion_es_403_y_no_toca_la_base(cliente, db, url, cuerpo):
    respuesta = cliente.post(url, json=cuerpo)
    assert respuesta.status_code == 403 and respuesta.json()["codigo"] == "sin_permiso"
    assert db.llamadas == []


@pytest.mark.parametrize("rol", [None, {"rol": "consulta", "activo": True}, {"rol": "coordinador", "activo": False}])
@pytest.mark.parametrize("url, cuerpo", [(URL_APROBAR, CUERPO), (URL_RECHAZAR, {"motivo": "no"})])
def test_quien_no_es_coordinador_activo_no_llega_a_la_rpc(cliente, db, rol, url, cuerpo):
    db.rol = rol
    respuesta = cliente.post(url, headers=AUTH, json=cuerpo)
    assert respuesta.status_code == 403
    assert db.llamadas == []


def test_falla_al_leer_el_rol_es_503(cliente, db):
    db.error_rol = error_rpc("boom", "XX000")
    assert cliente.post(URL_APROBAR, headers=AUTH, json=CUERPO).status_code == 503
    assert db.llamadas == []


# --- Rechazar -----------------------------------------------------------------------------


def test_rechazar_envia_usuario_del_token_y_motivo(cliente, db):
    db.respuesta = rechazado()
    respuesta = cliente.post(URL_RECHAZAR, headers=AUTH, json={"motivo": "Datos no confiables"})
    assert respuesta.status_code == 200 and respuesta.json()["estado"] == "rechazado"
    assert db.llamadas == [
        ("ra_rechazar_plan", {"p_usuario_id": str(USUARIO), "p_plan_id": str(PLAN), "p_version": 1, "p_motivo": "Datos no confiables"})
    ]


@pytest.mark.parametrize("cuerpo", [{}, {"motivo": ""}, {"motivo": "ok", "usuario_id": str(uuid4())}])
def test_rechazar_exige_motivo_y_no_acepta_extras(cliente, db, cuerpo):
    assert cliente.post(URL_RECHAZAR, headers=AUTH, json=cuerpo).status_code == 422
    assert db.llamadas == []


def test_rechazar_plan_ya_resuelto_es_409(cliente, db):
    db.error = error_rpc("plan_ya_resuelto: el plan está en estado aprobado")
    assert cliente.post(URL_RECHAZAR, headers=AUTH, json={"motivo": "no"}).status_code == 409


# --- Listar -------------------------------------------------------------------------------


class ConsultaLectura:
    def __init__(self, base, tabla):
        self.base, self.tabla = base, tabla

    def select(self, columnas):
        self.base.selects.append((self.tabla, columnas))
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_):
        return self

    def in_(self, columna, valores):
        self.base.filtros.append((self.tabla, columna, valores))
        return self

    def execute(self):
        if self.base.error_lectura:
            raise self.base.error_lectura
        return Respuesta(self.base.tablas.get(self.tabla, []))


class BaseLectura(BaseFalsa):
    def __init__(self):
        super().__init__()
        self.tablas, self.selects, self.filtros, self.error_lectura = {}, [], [], None
        self.catalogo = []

    def table(self, nombre):
        if nombre == "usuarios_operativos":
            return super().table(nombre)
        return ConsultaLectura(self, nombre)

    def rpc(self, nombre, parametros):
        if nombre == "ra_catalogo_v2":
            datos = self.catalogo
            return type("L", (), {"execute": lambda s: Respuesta(datos)})()
        return super().rpc(nombre, parametros)


@pytest.fixture
def lectura():
    return BaseLectura()


@pytest.fixture
def cliente_lectura(lectura):
    app.dependency_overrides[obtener_db] = lambda: lectura
    app.dependency_overrides[obtener_verificador] = lambda: VerificadorFalso()
    yield TestClient(app)
    app.dependency_overrides.clear()


RUTA = str(uuid4())
PUNTO = str(uuid4())


def plan_fila(**extra):
    return {
        "plan_id": str(PLAN), "version": 1, "ejecucion_id": str(uuid4()), "estado": "pendiente_revision",
        "estado_solver": "factible", "datos_version": "d1", "politica_version": "p1", "verificado": True,
        "bloqueos_publicacion": [BLOQUEO], "no_atendidos": [], "supuestos": ["supuesto"], "aprobacion_id": None,
        "origen": "sintetico", "creado_en": "2026-10-17T08:00:00+00:00", **extra,
    }


def test_listar_sin_sesion_es_403(cliente_lectura):
    assert cliente_lectura.get("/planes").status_code == 403


def test_listar_sin_planes_devuelve_lista_vacia(cliente_lectura, lectura):
    respuesta = cliente_lectura.get("/planes", headers=AUTH)
    assert respuesta.status_code == 200 and respuesta.json() == []
    assert [s[0] for s in lectura.selects] == ["planes"]


def test_listar_arma_rutas_y_paradas_con_nombre_de_punto(cliente_lectura, lectura):
    lectura.tablas = {
        "planes": [plan_fila()],
        "rutas": [{"ruta_id": RUTA, "plan_id": str(PLAN), "version": 1, "vehiculo_id": str(uuid4()),
                   "salida_estimada": "2026-10-17T12:00:00+00:00", "retorno_estimado": "2026-10-17T16:00:00+00:00"}],
        "paradas": [
            {"parada_id": str(uuid4()), "ruta_id": RUTA, "plan_id": str(PLAN), "version": 1, "orden": 2,
             "punto_atencion_id": str(uuid4()), "litros_asignados": 1000, "llegada_estimada": "2026-10-17T14:00:00+00:00",
             "inicio_descarga": "2026-10-17T14:05:00+00:00", "fin_descarga": "2026-10-17T14:20:00+00:00", "estado": "programada"},
            {"parada_id": str(uuid4()), "ruta_id": RUTA, "plan_id": str(PLAN), "version": 1, "orden": 1,
             "punto_atencion_id": PUNTO, "litros_asignados": 2500, "llegada_estimada": "2026-10-17T13:00:00+00:00",
             "inicio_descarga": "2026-10-17T13:05:00+00:00", "fin_descarga": "2026-10-17T13:20:00+00:00", "estado": "programada"},
        ],
    }
    lectura.catalogo = [{"punto_atencion_id": PUNTO, "nombre": "Escuela El Coco", "distrito": "Arraiján", "corregimiento": None}]
    plan = cliente_lectura.get("/planes", headers=AUTH).json()[0]
    assert plan["datos_version"] == "d1" and plan["politica_version"] == "p1" and plan["bloqueos_publicacion"] == [BLOQUEO]
    paradas = plan["rutas"][0]["paradas"]
    assert [p["orden"] for p in paradas] == [1, 2]
    assert paradas[0]["punto"]["nombre"] == "Escuela El Coco" and paradas[1]["punto"] is None


def test_listar_no_expone_nada_fuera_de_las_columnas_del_plan(cliente_lectura, lectura):
    lectura.tablas = {"planes": [plan_fila(solicitud_snapshot={"secreto": 1}, creado_por=str(uuid4()))]}
    plan = cliente_lectura.get("/planes", headers=AUTH).json()[0]
    assert "solicitud_snapshot" not in plan and "creado_por" not in plan
    assert "solicitud_snapshot" in lectura.selects[0][1]  # Backend: coordenadas congeladas para navegación; no se exponen.


def test_listar_plan_con_formato_roto_es_503(cliente_lectura, lectura):
    lectura.tablas = {"planes": [plan_fila(estado="raro")]}
    assert cliente_lectura.get("/planes", headers=AUTH).status_code == 503


def test_listar_falla_de_base_es_503(cliente_lectura, lectura):
    lectura.error_lectura = error_rpc("boom", "XX000")
    assert cliente_lectura.get("/planes", headers=AUTH).status_code == 503


def test_navegacion_usa_coordenadas_del_snapshot(cliente_lectura,lectura):
    from urllib.parse import parse_qs,urlsplit
    original={'latitud':8.9,'longitud':-79.7,'fuente':'escenario'}
    destino={'latitud':8.91,'longitud':-79.71,'fuente':'escenario'}
    lectura.tablas={'planes':[plan_fila(solicitud_snapshot={'deposito':{'ubicacion':original},
        'puntos':[{'punto_atencion_id':PUNTO,'ubicacion':destino}]})],
        'rutas':[{'ruta_id':RUTA,'plan_id':str(PLAN),'version':1,'vehiculo_id':str(uuid4()),
            'salida_estimada':'2026-10-17T12:00:00+00:00','retorno_estimado':'2026-10-17T16:00:00+00:00'}],
        'paradas':[{'parada_id':str(uuid4()),'ruta_id':RUTA,'plan_id':str(PLAN),'version':1,'orden':1,
            'punto_atencion_id':PUNTO,'litros_asignados':1000,'llegada_estimada':'2026-10-17T13:00:00+00:00',
            'inicio_descarga':'2026-10-17T13:00:00+00:00','fin_descarga':'2026-10-17T13:30:00+00:00','estado':'programada'}]}
    lectura.catalogo=[{'punto_atencion_id':PUNTO,'nombre':'Nombre cambiado','latitud':9.99,'longitud':-80.0}]
    ruta=cliente_lectura.get('/planes',headers=AUTH).json()[0]['rutas'][0]
    parametros=parse_qs(urlsplit(ruta['navegacion_url']).query)
    assert parametros['waypoints']==['8.91,-79.71']
    assert parametros['destination']==['8.9,-79.7'] and len(ruta['tramos_navegacion'])==2
