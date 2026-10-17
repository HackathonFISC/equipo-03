"""Pruebas de POST/GET /reportes con una base de datos simulada (sin red ni claves)."""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

import api.servicios.reportes as servicio_reportes
from api.auth import obtener_verificador
from api.dependencias import obtener_db, secreto_configurado
from api.main import app
from contratos.modelos import ReporteRegistrado

SECRETO = "secreto-de-prueba-0123456789"
CABECERA = {"X-Secreto-Bot": SECRETO}
AUTH = {"Authorization": "Bearer aaa.bbb.ccc"}


class VerificadorFalso:
    def usuario_id(self, token):
        return uuid4()

CUERPO = {
    "usuario_telegram_id": 111,
    "chat_id": -1001,
    "message_id": 7,
    "texto": "Llevamos tres días sin agua en P1; somos unas 120 personas.",
}
UNICAS = {
    "remitentes": ("canal", "identificador_externo"),
    "reportes": ("canal", "mensaje_externo_id"),
    "ejecuciones": ("clave_idempotencia",),
    "destinos": ("canal", "identificador_externo"),
}
# Valores por defecto que pone la base en 0001_esquema.sql.
DEFECTOS = {
    "ejecuciones": {
        "estado": "pendiente",
        "etapa": "ingesta",
        "intentos": 0,
        "ultimo_error": None,
        "actualizado_en": "2026-10-16T18:00:00-05:00",
    },
}
COLUMNA_ID = {
    "remitentes": "remitente_ref",
    "reportes": "reporte_id",
    "ejecuciones": "ejecucion_id",
    "eventos": "evento_id",
    "destinos": "destino_id",
}


class Respuesta:
    def __init__(self, data):
        self.data = data


class Consulta:
    def __init__(self, db, tabla):
        self.db, self.tabla = db, tabla
        self.filtros, self.fila, self.limite, self.descendente = {}, None, None, False

    def select(self, columnas):
        self.columnas = columnas
        return self

    def eq(self, columna, valor):
        self.filtros[columna] = valor
        return self

    def order(self, columna, desc=False):
        self.descendente = desc
        return self

    def limit(self, n):
        self.limite = n
        return self

    def insert(self, fila):
        self.fila = fila
        return self

    def execute(self):
        if self.db.error_proximo:
            error, self.db.error_proximo = self.db.error_proximo, None
            raise error
        filas = self.db.tablas[self.tabla]
        if self.fila is not None:
            if self.db.duplicado_proximo == self.tabla:
                self.db.duplicado_proximo = None
                self.db.tablas[self.tabla].append(self.db.fila_oculta)
                raise APIError({"message": "duplicado", "code": "23505"})
            for columnas in [UNICAS.get(self.tabla, ())]:
                if columnas and any(
                    all(f.get(c) == self.fila.get(c) for c in columnas) for f in filas
                ):
                    raise APIError({"message": "duplicado", "code": "23505"})
            nueva = {
                **DEFECTOS.get(self.tabla, {}),
                **self.fila,
                COLUMNA_ID[self.tabla]: str(uuid4()),
                "creado_en": f"2026-10-16T18:{len(filas):02d}:00-05:00",
            }
            filas.append(nueva)
            return Respuesta([dict(nueva)])
        resultado = [
            dict(f) for f in filas if all(f.get(c) == v for c, v in self.filtros.items())
        ]
        if self.tabla == "reportes" and "ejecuciones(" in self.columnas:
            for f in resultado:
                f["ejecuciones"] = [
                    {k: e[k] for k in ("ejecucion_id", "estado", "etapa")}
                    for e in self.db.tablas["ejecuciones"]
                    if e["reporte_id"] == f["reporte_id"]
                ]
        resultado.sort(key=lambda f: f.get("creado_en", ""), reverse=self.descendente)
        return Respuesta(resultado[: self.limite])


class BaseFalsa:
    def __init__(self):
        self.tablas = {"remitentes": [], "reportes": [], "ejecuciones": [], "eventos": [], "destinos": []}
        self.error_proximo = None
        self.duplicado_proximo = None
        self.fila_oculta = None

    def table(self, nombre):
        return Consulta(self, nombre)


@pytest.fixture
def db():
    base = BaseFalsa()
    app.dependency_overrides[obtener_db] = lambda: base
    app.dependency_overrides[secreto_configurado] = lambda: SECRETO
    app.dependency_overrides[obtener_verificador] = lambda: VerificadorFalso()
    yield base
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(db):
    return TestClient(app, headers=AUTH)


def cuerpo(**cambios):
    return {**CUERPO, **cambios}


def test_crea_reporte_nuevo(cliente, db):
    r = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert r.status_code == 201
    registrado = ReporteRegistrado.model_validate(r.json())
    assert registrado.origen.value == "sintetico"
    assert registrado.entrada.mensaje_externo_id == "-1001:7"
    assert registrado.entrada.canal == "telegram"
    assert registrado.entrada.texto == CUERPO["texto"]
    assert len(db.tablas["remitentes"]) == 1
    assert db.tablas["remitentes"][0]["identificador_externo"] == "111"
    assert len(db.tablas["reportes"]) == 1
    assert db.tablas["reportes"][0]["origen"] == "sintetico"
    assert db.tablas["ejecuciones"][0]["clave_idempotencia"] == f"ingesta:{registrado.reporte_id}"
    assert str(registrado.ejecucion_id) == db.tablas["ejecuciones"][0]["ejecucion_id"]


def test_mensaje_repetido_devuelve_el_mismo_reporte(cliente, db):
    primero = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    segundo = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert primero.status_code == 201 and segundo.status_code == 200
    assert primero.json()["reporte_id"] == segundo.json()["reporte_id"]
    assert primero.json()["ejecucion_id"] == segundo.json()["ejecucion_id"]
    assert [len(db.tablas[t]) for t in ("remitentes", "reportes", "ejecuciones")] == [1, 1, 1]


def test_mismo_remitente_en_dos_mensajes_se_reutiliza(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    cliente.post("/reportes", json=cuerpo(message_id=8), headers=CABECERA)
    assert [len(db.tablas[t]) for t in ("remitentes", "reportes", "ejecuciones")] == [1, 2, 2]


def test_mismo_mensaje_de_otro_remitente_se_rechaza(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    r = cliente.post("/reportes", json=cuerpo(usuario_telegram_id=222), headers=CABECERA)
    assert r.status_code == 422
    assert r.json()["codigo"] == "contrato_invalido"
    assert len(db.tablas["reportes"]) == 1


def test_carrera_en_el_reporte_devuelve_el_existente(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    remitente = db.tablas["remitentes"][0]["remitente_ref"]
    existente = {
        "reporte_id": str(uuid4()), "remitente_ref": remitente, "canal": "telegram",
        "mensaje_externo_id": "-1001:9", "texto": "x", "creado_en": "2026-10-16T18:30:00-05:00",
    }
    db.duplicado_proximo, db.fila_oculta = "reportes", existente
    # La primera búsqueda no ve la fila; el insert falla con 23505 y se recupera.
    original = db.tablas["reportes"]
    visible = list(original)
    db.tablas["reportes"] = visible
    r = cliente.post("/reportes", json=cuerpo(message_id=9), headers=CABECERA)
    assert r.status_code == 200
    assert r.json()["reporte_id"] == existente["reporte_id"]


def test_reintento_repara_la_ejecucion_que_faltaba(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    db.tablas["ejecuciones"].clear()  # simula un fallo entre reporte y ejecución
    r = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert r.status_code == 200
    assert len(db.tablas["ejecuciones"]) == 1
    assert len(db.tablas["reportes"]) == 1


@pytest.mark.parametrize("cabeceras", [{}, {"X-Secreto-Bot": "incorrecto-incorrecto-1"}])
def test_sin_secreto_correcto_responde_403(cliente, db, cabeceras):
    r = cliente.post("/reportes", json=CUERPO, headers=cabeceras)
    assert r.status_code == 403 and r.json()["codigo"] == "sin_permiso"
    assert db.tablas["reportes"] == []


def test_secreto_no_configurado_cierra_la_ruta(cliente, db):
    app.dependency_overrides[secreto_configurado] = lambda: ""
    r = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert r.status_code == 503 and r.json()["codigo"] == "proveedor_no_disponible"
    app.dependency_overrides[secreto_configurado] = lambda: "corto"
    assert cliente.post("/reportes", json=CUERPO, headers={"X-Secreto-Bot": "corto"}).status_code == 503


def test_secreto_incorrecto_se_rechaza_antes_de_validar_el_cuerpo(cliente):
    r = cliente.post("/reportes", json={"texto": ""}, headers={"X-Secreto-Bot": "x" * 20})
    assert r.status_code == 403


@pytest.mark.parametrize(
    "cambios, campo",
    [
        ({"texto": ""}, "texto"),
        ({"texto": "   "}, "texto"),
        ({"texto": "a" * 4001}, "texto"),
        ({"message_id": 0}, "message_id"),
        ({"chat_id": 0}, "chat_id"),
        ({"usuario_telegram_id": "111"}, "usuario_telegram_id"),
        ({"origen": "real"}, "origen"),
    ],
)
def test_cuerpo_invalido_responde_422_sin_eco_del_texto(cliente, db, cambios, campo):
    r = cliente.post("/reportes", json=cuerpo(**cambios), headers=CABECERA)
    assert r.status_code == 422
    assert r.json()["codigo"] == "contrato_invalido"
    assert campo in r.json()["campos"]
    assert "aaaa" not in json.dumps(r.json())
    assert db.tablas["reportes"] == []


def test_json_malformado_responde_422_con_campo_cuerpo(cliente, db):
    r = cliente.post(
        "/reportes",
        content='{"usuario_telegram_id": 111, "texto": "roto",}',
        headers={**CABECERA, "Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert r.json()["campos"] == ["cuerpo"]
    assert "JSON" in r.json()["mensaje"]


def test_error_de_la_base_responde_503(cliente, db):
    db.error_proximo = APIError({"message": "caída", "code": "XX000"})
    r = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert r.status_code == 503
    assert r.json()["codigo"] == "proveedor_no_disponible" and r.json()["recuperable"] is True
    assert "caída" not in json.dumps(r.json())


def test_lista_ordenada_y_sin_datos_del_remitente(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    cliente.post("/reportes", json=cuerpo(message_id=8, texto="Segundo"), headers=CABECERA)
    r = cliente.get("/reportes")
    assert r.status_code == 200
    textos = [x["registrado"]["entrada"]["texto"] for x in r.json()]
    assert textos == ["Segundo", CUERPO["texto"]]
    crudo = json.dumps(r.json())
    for prohibido in ("remitente_ref", "identificador_externo", "mensaje_externo_id", "111", "-1001"):
        assert prohibido not in crudo
    assert all(x["interpretado"] is None for x in r.json())
    assert all(x["registrado"]["ejecucion_id"] for x in r.json())


EXTRACCION = {
    "resumen": "El remitente declara tres días sin agua en el punto de demo P1.",
    "ubicacion_declarada": "Punto de demo P1",
    "campos": {
        "horas_sin_agua": 72, "personas_afectadas": 120,
        "vulnerabilidad_declarada": None, "institucion_declarada": None,
        "tipo_problema": "sin_suministro",
    },
    "evidencia_textual": ["tres días sin agua"],
    "faltantes": [],
    "requiere_aclaracion": False,
    "fuera_de_alcance": False,
}


@pytest.mark.parametrize("envoltorio", [lambda e: e, lambda e: {"interpretacion": e}])
def test_lista_incluye_la_interpretacion_en_ambas_formas(cliente, db, envoltorio):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    db.tablas["reportes"][0]["interpretacion"] = envoltorio(EXTRACCION)
    item = cliente.get("/reportes").json()[0]
    campos = item["interpretado"]["interpretacion"]["campos"]
    assert campos["horas_sin_agua"] == 72 and campos["institucion_declarada"] is None


def test_interpretacion_invalida_se_muestra_sin_interpretar(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    db.tablas["reportes"][0]["interpretacion"] = {"resumen": "incompleto"}
    assert cliente.get("/reportes").json()[0]["interpretado"] is None


def test_limite_de_la_lista(cliente, db):
    for n in range(1, 4):
        cliente.post("/reportes", json=cuerpo(message_id=n), headers=CABECERA)
    assert len(cliente.get("/reportes?limite=2").json()) == 2
    assert cliente.get("/reportes?limite=0").status_code == 422
    assert cliente.get("/reportes?limite=201").status_code == 422


def test_la_lista_no_exige_secreto(cliente):
    assert cliente.get("/reportes").status_code == 200


def test_salud_sigue_respondiendo(cliente):
    assert cliente.get("/salud").json() == {"estado": "ok"}


def test_lista_incluye_estado_y_etapa_de_la_ejecucion(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    item = cliente.get("/reportes").json()[0]
    assert item["seguimiento"] == {"estado": "pendiente", "etapa": "ingesta"}
    db.tablas["ejecuciones"][0].update(estado="pendiente", etapa="territorial")
    assert cliente.get("/reportes").json()[0]["seguimiento"]["etapa"] == "territorial"


# --- GET /ejecuciones/{id} ---

EVENTO_INGESTA = {
    "agente": "ingesta",
    "actor_tipo": "agente",
    "decision": "Entregar interpretación a Territorial.",
    "herramienta": "gemini.generateContent",
    "resultado": "Extracción validada y citas cotejadas; no se autorizó distribución.",
    "duracion_ms": 2300,
    "siguiente_estado": "pendiente",
    "detalles": {"ingesta_cierre_hash": "abc"},
    "entrada_ids": ["interno"],
}


def test_ejecucion_con_su_traza(cliente, db):
    reporte = cliente.post("/reportes", json=CUERPO, headers=CABECERA).json()
    ejecucion_id = reporte["ejecucion_id"]
    db.tablas["ejecuciones"][0].update(etapa="territorial")
    db.tablas["eventos"].append({
        **EVENTO_INGESTA, "evento_id": str(uuid4()), "ejecucion_id": ejecucion_id,
        "creado_en": "2026-10-16T18:05:00-05:00",
    })
    r = cliente.get(f"/ejecuciones/{ejecucion_id}")
    assert r.status_code == 200
    datos = r.json()
    assert datos["estado"] == "pendiente" and datos["etapa"] == "territorial"
    assert datos["reporte_id"] == reporte["reporte_id"]
    assert len(datos["eventos"]) == 1
    evento = datos["eventos"][0]
    assert evento["agente"] == "ingesta" and evento["duracion_ms"] == 2300
    crudo = json.dumps(datos)
    for interno in ("detalles", "ingesta_cierre_hash", "entrada_ids", "clave_idempotencia"):
        assert interno not in crudo


def test_eventos_ordenados_del_mas_antiguo(cliente, db):
    reporte = cliente.post("/reportes", json=CUERPO, headers=CABECERA).json()
    for minuto, decision in (("09", "Segunda"), ("05", "Primera")):
        db.tablas["eventos"].append({
            **EVENTO_INGESTA, "decision": decision, "evento_id": str(uuid4()),
            "ejecucion_id": reporte["ejecucion_id"], "creado_en": f"2026-10-16T18:{minuto}:00-05:00",
        })
    datos = cliente.get(f"/ejecuciones/{reporte['ejecucion_id']}").json()
    assert [e["decision"] for e in datos["eventos"]] == ["Primera", "Segunda"]


def test_error_de_la_ejecucion_solo_expone_el_codigo(cliente, db):
    reporte = cliente.post("/reportes", json=CUERPO, headers=CABECERA).json()
    db.tablas["ejecuciones"][0].update(
        estado="fallida",
        ultimo_error={"codigo": "proveedor_no_disponible", "mensaje": "detalle interno"},
    )
    datos = cliente.get(f"/ejecuciones/{reporte['ejecucion_id']}").json()
    assert datos["estado"] == "fallida"
    assert datos["error_codigo"] == "proveedor_no_disponible"
    assert "detalle interno" not in json.dumps(datos)


def test_ejecucion_sin_sesion_es_403_y_no_toca_la_base(db):
    r = TestClient(app).get(f"/ejecuciones/{uuid4()}")
    assert r.status_code == 403 and r.json()["codigo"] == "sin_permiso"


def test_ejecucion_inexistente_responde_404(cliente, db):
    assert cliente.get(f"/ejecuciones/{uuid4()}").status_code == 404


def test_id_invalido_responde_422(cliente, db):
    r = cliente.get("/ejecuciones/no-es-un-uuid")
    assert r.status_code == 422
    assert r.json()["campos"] == ["ejecucion_id"]


def test_ejecucion_con_base_caida_responde_503(cliente, db):
    db.error_proximo = APIError({"message": "caída", "code": "XX000"})
    r = cliente.get(f"/ejecuciones/{uuid4()}")
    assert r.status_code == 503 and r.json()["codigo"] == "proveedor_no_disponible"


# --- Destino de origen (chat) para las aclaraciones de V2 ---


def test_grupo_crea_destino_sin_remitente(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert len(db.tablas["destinos"]) == 1
    destino = db.tablas["destinos"][0]
    assert destino["identificador_externo"] == "-1001"
    assert destino["canal"] == "telegram"
    assert destino["remitente_ref"] is None
    assert "autorizado" not in destino  # queda en su valor por defecto (false)


def test_chat_privado_asocia_el_destino_al_remitente(cliente, db):
    cliente.post("/reportes", json=cuerpo(chat_id=111), headers=CABECERA)
    destino = db.tablas["destinos"][0]
    assert destino["remitente_ref"] == db.tablas["remitentes"][0]["remitente_ref"]


def test_otra_persona_en_el_grupo_no_cambia_el_destino(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    antes = dict(db.tablas["destinos"][0])
    r = cliente.post("/reportes", json=cuerpo(usuario_telegram_id=222, message_id=8), headers=CABECERA)
    assert r.status_code == 201
    assert len(db.tablas["destinos"]) == 1
    assert db.tablas["destinos"][0] == antes
    assert len(db.tablas["remitentes"]) == 2


def test_carrera_al_crear_el_destino_reutiliza_el_existente(cliente, db):
    existente = {
        "destino_id": str(uuid4()), "canal": "telegram", "identificador_externo": "-1001",
        "remitente_ref": None, "creado_en": "2026-10-16T18:00:00-05:00",
    }
    db.duplicado_proximo, db.fila_oculta = "destinos", existente
    r = cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert r.status_code == 201
    assert [d["destino_id"] for d in db.tablas["destinos"]] == [existente["destino_id"]]


def test_destino_origen_no_se_guarda_con_el_interruptor_apagado(cliente, db, monkeypatch):
    monkeypatch.setattr(servicio_reportes, "GUARDAR_DESTINO_ORIGEN", False)
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert "destino_origen_id" not in db.tablas["reportes"][0]


def test_destino_origen_se_guarda_por_defecto(cliente, db):
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert db.tablas["reportes"][0]["destino_origen_id"] == db.tablas["destinos"][0]["destino_id"]


def test_la_lista_no_expone_el_destino(cliente, db, monkeypatch):
    monkeypatch.setattr(servicio_reportes, "GUARDAR_DESTINO_ORIGEN", True)
    cliente.post("/reportes", json=CUERPO, headers=CABECERA)
    assert "destino" not in json.dumps(cliente.get("/reportes").json())
