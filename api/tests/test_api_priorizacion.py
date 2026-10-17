"""Pruebas de POST /ejecuciones/{id}/priorizacion con base y sesión simuladas (sin red ni claves).

La RPC real es de Emilia (migraciones 0007, 0008 y 0010); aquí se comprueba qué lote arma la API, qué bloquea
antes de llamarla y cómo traduce sus errores.
"""
import copy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.main import app
from contratos.modelos import EvaluacionNecesidades
from contratos.solicitudes import SolicitudValidarNecesidad

TOKEN = "aaa.bbb.ccc"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
USUARIO = uuid4()
EJECUCION = uuid4()
PUNTO_A, PUNTO_B = str(uuid4()), str(uuid4())
INCIDENTE_A, INCIDENTE_B = str(uuid4()), str(uuid4())
URL = f"/ejecuciones/{EJECUCION}/priorizacion"
VENTANA = {"inicio": "2026-10-17T08:00:00-05:00", "fin": "2026-10-17T12:00:00-05:00"}

POLITICA = {
    "politica_version": "pol-1", "estado": "activa", "origen": "sintetico",
    "peso_duracion": 0.4, "peso_vulnerabilidad": 0.4, "peso_poblacion": 0.2,
    "tope_horas": 72.0, "tope_personas": 500, "vulnerabilidad_moderada": 0.5,
    "fundamento": "Política de prueba.",
    "confirmacion_activacion": {"usuario_id": str(uuid4()), "confirmado_en": "2026-10-16T12:00:00+00:00", "motivo": "Activada"},
    "criticos_obligatorios": True, "faltantes_fuera_ranking": True,
    "orden_desempate": "ultima_atencion_luego_incidente_luego_id",
    "creado_en": "2026-10-16T12:00:00+00:00", "creado_por": str(uuid4()),
}


def incidente(incidente_id, punto, **cambios):
    base = {
        "incidente_id": incidente_id, "version": 1, "origen": "real", "punto_atencion_id": punto,
        "primera_deteccion_en": "2026-10-17T06:00:00+00:00", "requiere_revision_urgente": False,
    }
    return {**base, **cambios}


class Respuesta:
    def __init__(self, data):
        self.data = data


class Consulta:
    def __init__(self, db, tabla):
        self.db, self.tabla, self.filtros = db, tabla, []

    def select(self, *_):
        return self

    def eq(self, columna, valor):
        self.filtros.append((columna, str(valor)))
        return self

    def limit(self, _):
        return self

    def execute(self):
        filas = [f for f in self.db.tablas.get(self.tabla, []) if all(str(f.get(c)) == v for c, v in self.filtros)]
        return Respuesta(copy.deepcopy(filas))


class BaseFalsa:
    def __init__(self):
        self.tablas = {
            "usuarios_operativos": [{"usuario_id": str(USUARIO), "rol": "coordinador", "activo": True}],
            "ejecuciones": [{"ejecucion_id": str(EJECUCION), "etapa": "priorizacion", "estado": "espera_revision",
                             "origen": "real", "entrada_priorizacion": None}],
            "politicas_prioridad": [copy.deepcopy(POLITICA)],
        }
        self.incidentes = [incidente(INCIDENTE_A, PUNTO_A), incidente(INCIDENTE_B, PUNTO_B)]
        self.llamadas, self.error = [], None
        self.resultado = {"estado": "pendiente", "etapa": "priorizacion", "ejecucion_id": str(EJECUCION)}

    def table(self, nombre):
        return Consulta(self, nombre)

    def rpc(self, nombre, parametros):
        self.llamadas.append((nombre, parametros))
        base = self

        class Llamada:
            def execute(self):
                if nombre == "ra_incidentes_contexto_v2":
                    return Respuesta(copy.deepcopy(base.incidentes))
                if base.error:
                    raise base.error
                return Respuesta(base.resultado)

        return Llamada()

    def envios(self):
        return [p for n, p in self.llamadas if n == "ra_preparar_priorizacion_v2"]


class VerificadorFalso:
    def usuario_id(self, token):
        return USUARIO


@pytest.fixture
def db():
    return BaseFalsa()


@pytest.fixture
def cliente(db):
    app.dependency_overrides[obtener_db] = lambda: db
    app.dependency_overrides[obtener_verificador] = lambda: VerificadorFalso()
    yield TestClient(app, headers=AUTH)
    app.dependency_overrides.clear()


def cuerpo(**cambios):
    return {"politica_version": "pol-1", "motivo": "Revisado con el equipo", **cambios}


def revision(incidente_id, **cambios):
    base = {
        "incidente_id": incidente_id, "version_incidente": 1,
        "demanda": {"metodo": "directa", "litros_declarados": 5000.0, "fuente": "Llamada a la junta de agua"},
        "clase_prioridad": "general", "vulnerabilidad": "alta", "horas_sin_agua": 30.0, "personas_atendidas": 120,
        "capacidad_recepcion_litros": 8000.0,
    }
    return {**base, **cambios}


def error_rpc(mensaje, codigo="55000"):
    return APIError({"message": mensaje, "code": codigo, "hint": None, "details": None})


# --- Lo que arma la API ---


def test_sin_revisiones_cubre_todos_los_incidentes_y_deja_todo_pendiente(cliente, db):
    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 202
    datos = r.json()
    assert datos["estado"] == "pendiente" and datos["incidentes"] == 2 and datos["sin_revisar"] == 2
    [envio] = db.envios()
    assert envio["p_usuario_id"] == str(USUARIO) and envio["p_ejecucion_id"] == str(EJECUCION)
    entradas = envio["p_lote"]["entradas"]
    assert {e["solicitud_demanda"]["incidente_id"] for e in entradas} == {INCIDENTE_A, INCIDENTE_B}
    for entrada in entradas:
        evaluacion = EvaluacionNecesidades.model_validate(entrada["evaluacion"])
        SolicitudValidarNecesidad.model_validate(entrada["solicitud_demanda"])
        assert evaluacion.estado_prioridad == "pendiente" and evaluacion.puntaje is None and evaluacion.posicion is None
        assert evaluacion.confirmacion_demanda is None and evaluacion.confirmacion_clase is None
        assert evaluacion.clase_prioridad is None and evaluacion.vulnerabilidad is None
        assert entrada["solicitud_demanda"]["demanda"]["confirmacion"] is None
        assert any("revisión del coordinador" in p.lower() for p in evaluacion.pendientes)
        assert evaluacion.origen.value == "real"


def test_la_politica_va_tal_como_esta_guardada_sin_columnas_administrativas(cliente, db):
    cliente.post(URL, json=cuerpo())

    politica = db.envios()[0]["p_lote"]["politica"]
    assert "creado_en" not in politica and "creado_por" not in politica
    assert politica == {k: v for k, v in POLITICA.items() if k not in ("creado_en", "creado_por")}


def test_la_confirmacion_usa_el_usuario_de_la_sesion(cliente, db):
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A)]))

    assert r.status_code == 202 and r.json()["sin_revisar"] == 1
    entradas = {e["solicitud_demanda"]["incidente_id"]: e for e in db.envios()[0]["p_lote"]["entradas"]}
    revisada = entradas[INCIDENTE_A]
    evaluacion = revisada["evaluacion"]
    for campo in ("confirmacion_demanda", "confirmacion_clase", "confirmacion_vulnerabilidad"):
        assert evaluacion[campo]["usuario_id"] == str(USUARIO)
        assert evaluacion[campo]["motivo"].endswith("Revisado con el equipo")
    assert revisada["solicitud_demanda"]["demanda"]["confirmacion"]["usuario_id"] == str(USUARIO)
    assert evaluacion["clase_prioridad"] == "general" and evaluacion["vulnerabilidad"] == "alta"
    assert evaluacion["horas_sin_agua"] == 30.0 and evaluacion["personas_atendidas"] == 120
    assert evaluacion["estado_prioridad"] == "pendiente" and evaluacion["puntaje"] is None
    # El otro incidente no se inventa: sigue pendiente y sin confirmaciones.
    assert entradas[INCIDENTE_B]["evaluacion"]["confirmacion_demanda"] is None


def test_el_usuario_en_el_cuerpo_se_rechaza(cliente, db):
    r = cliente.post(URL, json=cuerpo(usuario_id=str(uuid4())))

    assert r.status_code == 422 and db.envios() == []


def test_revision_por_formula_y_punto_critico_con_ventana(cliente, db):
    formula = {"metodo": "formula", "fuente": "Censo", "personas_atendidas": 200,
               "dotacion_litros_persona_dia": 50.0, "dias_cobertura": 1.0, "reserva_utilizable_litros": 0.0}
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A, demanda=formula, clase_prioridad="critico", ventana_atencion=VENTANA)]))

    assert r.status_code == 202
    entrada = next(e for e in db.envios()[0]["p_lote"]["entradas"] if e["solicitud_demanda"]["incidente_id"] == INCIDENTE_A)
    assert entrada["evaluacion"]["clase_prioridad"] == "critico" and entrada["evaluacion"]["ventana_atencion"] is not None
    assert entrada["solicitud_demanda"]["demanda"]["metodo"] == "formula"


def test_critico_sin_ventana_es_422(cliente, db):
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A, clase_prioridad="critico")]))

    assert r.status_code == 422 and db.envios() == []


def test_demanda_directa_con_campos_de_formula_es_422(cliente, db):
    mala = {"metodo": "directa", "fuente": "x", "litros_declarados": 10.0, "personas_atendidas": 5}
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A, demanda=mala)]))

    assert r.status_code == 422 and db.envios() == []


# --- Idempotencia y versión de datos ---


def test_repetir_el_mismo_envio_da_la_misma_version_y_el_mismo_lote(cliente, db):
    primero = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A)])).json()
    db.tablas["ejecuciones"][0]["entrada_priorizacion"] = db.envios()[0]["p_lote"]
    segundo = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A)])).json()

    assert primero["datos_version"] == segundo["datos_version"]
    assert db.envios()[0]["p_lote"] == db.envios()[1]["p_lote"]


def test_cambiar_una_revision_cambia_la_version_de_datos(cliente, db):
    a = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A)])).json()
    b = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A, personas_atendidas=121)])).json()

    assert a["datos_version"] != b["datos_version"]
    assert a["datos_version"].startswith("real-priorizacion-")


def test_la_rpc_que_dice_repetido_se_refleja(cliente, db):
    db.resultado = {"estado": "pendiente", "etapa": "priorizacion", "ejecucion_id": str(EJECUCION), "repetido": True}

    assert cliente.post(URL, json=cuerpo()).json()["repetido"] is True


# --- Lo que se bloquea antes de llamar a la RPC ---


def test_dos_incidentes_en_el_mismo_punto_bloquean_el_lote(cliente, db):
    db.incidentes = [incidente(INCIDENTE_A, PUNTO_A), incidente(INCIDENTE_B, PUNTO_A)]

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 422 and r.json()["codigo"] == "datos_insuficientes"
    assert db.envios() == []


def test_incidente_sin_punto_bloquea_el_lote(cliente, db):
    db.incidentes = [incidente(INCIDENTE_A, PUNTO_A), incidente(INCIDENTE_B, None)]

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 422 and db.envios() == []


def test_origen_mezclado_bloquea_y_no_recorta_el_ambito(cliente, db):
    db.incidentes = [incidente(INCIDENTE_A, PUNTO_A), incidente(INCIDENTE_B, PUNTO_B, origen="sintetico")]

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 422 and "origen" in r.json()["mensaje"]
    assert db.envios() == []


def test_sin_incidentes_es_422(cliente, db):
    db.incidentes = []

    assert cliente.post(URL, json=cuerpo()).status_code == 422
    assert db.envios() == []


def test_politica_inexistente_o_inactiva_es_409(cliente, db):
    assert cliente.post(URL, json=cuerpo(politica_version="no-existe")).status_code == 409
    db.tablas["politicas_prioridad"][0]["estado"] = "propuesta_demo"
    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 409 and r.json()["codigo"] == "politica_no_activa"
    assert db.envios() == []


def test_varias_copias_de_la_misma_version_no_se_eligen_solas(cliente, db):
    db.tablas["politicas_prioridad"].append(copy.deepcopy(POLITICA))

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 409 and db.envios() == []


def test_ejecucion_fuera_de_la_etapa_es_409(cliente, db):
    db.tablas["ejecuciones"][0]["etapa"] = "territorial"

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 409 and r.json()["codigo"] == "version_obsoleta" and db.envios() == []


def test_ejecucion_inexistente_es_404(cliente, db):
    assert cliente.post(f"/ejecuciones/{uuid4()}/priorizacion", json=cuerpo()).status_code == 404


def test_revision_de_un_incidente_ajeno_al_ambito_es_422(cliente, db):
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(str(uuid4()))]))

    assert r.status_code == 422 and db.envios() == []


def test_dos_revisiones_del_mismo_incidente_es_422(cliente, db):
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A), revision(INCIDENTE_A)]))

    assert r.status_code == 422 and db.envios() == []


def test_revision_de_una_version_vieja_del_incidente_es_409(cliente, db):
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A, version_incidente=2)]))

    assert r.status_code == 409 and r.json()["codigo"] == "version_obsoleta" and db.envios() == []


# --- Quién puede ---


def test_sin_sesion_es_403_y_no_toca_la_base(db):
    app.dependency_overrides[obtener_db] = lambda: db
    try:
        r = TestClient(app).post(URL, json=cuerpo())
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 403 and r.json()["codigo"] == "sin_permiso"
    assert db.llamadas == []


def test_quien_no_es_coordinador_no_llega_a_la_rpc(cliente, db):
    db.tablas["usuarios_operativos"][0]["rol"] = "operador"

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 403 and db.llamadas == []


def test_coordinador_inactivo_no_llega_a_la_rpc(cliente, db):
    db.tablas["usuarios_operativos"][0]["activo"] = False

    assert cliente.post(URL, json=cuerpo()).status_code == 403
    assert db.llamadas == []


# --- Errores de la RPC ---


@pytest.mark.parametrize(
    "mensaje,codigo_sql,estado,codigo",
    [
        ("Sin permiso de coordinador", "42501", 403, "sin_permiso"),
        ("Hay un cálculo en curso; no se puede sustituir su lote", "55000", 409, "version_obsoleta"),
        ("Ejecución no disponible para preparar cálculo", "55000", 409, "version_obsoleta"),
        ("Cambiar datos_version al modificar un lote", "22023", 409, "version_obsoleta"),
        ("Faltan incidentes activos en el lote", "22023", 409, "version_obsoleta"),
        ("Lote con identidad, versión u origen incompatible", "22023", 409, "version_obsoleta"),
        ("Política sin activar o diferente de la registrada", "55000", 409, "politica_no_activa"),
        ("Consolidar un incidente por punto en el lote; sin omitir episodios pendientes", "22023", 422, "datos_insuficientes"),
        ("otro motivo de validación", "22023", 422, "contrato_invalido"),
    ],
)
def test_errores_de_la_rpc_se_traducen(cliente, db, mensaje, codigo_sql, estado, codigo):
    db.error = error_rpc(mensaje, codigo_sql)

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == estado and r.json()["codigo"] == codigo


def test_fallo_de_la_base_responde_503_sin_filtrar_el_detalle(cliente, db):
    db.error = error_rpc("conexion rota con secreto", "XX000")

    r = cliente.post(URL, json=cuerpo())

    assert r.status_code == 503 and "secreto" not in r.text


def test_respuesta_inesperada_de_la_rpc_es_503(cliente, db):
    db.resultado = None

    assert cliente.post(URL, json=cuerpo()).status_code == 503


def test_la_capacidad_de_recepcion_confirmada_llega_a_la_solicitud_de_validacion(cliente, db):
    cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A)]))

    entradas = {e["solicitud_demanda"]["incidente_id"]: e for e in db.envios()[0]["p_lote"]["entradas"]}
    confirmada = entradas[INCIDENTE_A]
    assert confirmada["solicitud_demanda"]["capacidad_recepcion_litros"] == 8000.0
    assert not any("capacidad" in p.lower() for p in confirmada["evaluacion"]["pendientes"])
    sin_revisar = entradas[INCIDENTE_B]
    assert sin_revisar["solicitud_demanda"]["capacidad_recepcion_litros"] is None


def test_sin_capacidad_de_recepcion_no_se_inventa_y_queda_pendiente(cliente, db):
    revisada = revision(INCIDENTE_A)
    del revisada["capacidad_recepcion_litros"]
    cliente.post(URL, json=cuerpo(revisiones=[revisada]))

    entrada = next(e for e in db.envios()[0]["p_lote"]["entradas"] if e["solicitud_demanda"]["incidente_id"] == INCIDENTE_A)
    assert entrada["solicitud_demanda"]["capacidad_recepcion_litros"] is None
    assert any("capacidad de recepción" in p for p in entrada["evaluacion"]["pendientes"])


def test_capacidad_de_recepcion_negativa_se_rechaza(cliente):
    r = cliente.post(URL, json=cuerpo(revisiones=[revision(INCIDENTE_A, capacidad_recepcion_litros=-1.0)]))

    assert r.status_code == 422
