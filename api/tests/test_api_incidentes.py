"""Pruebas de GET /incidentes con RPC y tablas simuladas (sin red ni claves).

Las RPC reales son de Emilia (migración 0007); aquí solo se comprueba lo que hace la API
con lo que devuelven.
"""
import copy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from api.dependencias import obtener_db
from api.main import app

EJEMPLOS = Path(__file__).resolve().parents[2] / "contratos" / "ejemplos"
EVALUACION = json.loads((EJEMPLOS / "evaluacion_necesidades.json").read_text(encoding="utf-8"))
PUNTO = EVALUACION["punto_atencion_id"]
SECTOR = str(uuid4())


class Respuesta:
    def __init__(self, data):
        self.data = data


class Llamada:
    def __init__(self, db, nombre):
        self.db, self.nombre = db, nombre

    def execute(self):
        self.db.llamadas.append(self.nombre)
        if self.db.error:
            raise self.db.error
        return Respuesta(copy.deepcopy(self.db.rpcs.get(self.nombre)))


class Vinculos:
    """Solo lo que usa la API: vínculos activos de ciertos incidentes."""

    def __init__(self, db):
        self.db, self.activos, self.ids = db, False, None

    def select(self, _columnas):
        return self

    def is_(self, columna, valor):
        self.activos = columna == "desvinculado_en" and valor == "null"
        return self

    def in_(self, columna, valores):
        assert columna == "incidente_id"
        self.ids = set(valores)
        return self

    def execute(self):
        assert self.activos, "Solo deben contarse vínculos activos"
        filas = [
            {"incidente_id": v["incidente_id"]}
            for v in self.db.vinculos
            if v["desvinculado_en"] is None and v["incidente_id"] in self.ids
        ]
        return Respuesta(filas)


class BaseFalsa:
    def __init__(self):
        self.rpcs = {"ra_incidentes_snapshot_v2": [], "ra_catalogo_v2": []}
        self.vinculos = []
        self.llamadas = []
        self.error = None

    def rpc(self, nombre, parametros):
        assert parametros == {}
        return Llamada(self, nombre)

    def table(self, nombre):
        assert nombre == "vinculos_reportes"
        return Vinculos(self)


def incidente(**cambios):
    """Fila como la devuelve to_jsonb(incidentes) en ra_incidentes_snapshot_v2."""
    fila = {
        "incidente_id": str(uuid4()),
        "ejecucion_id": str(uuid4()),
        "version": 1,
        "sector_id": SECTOR,
        "punto_atencion_id": PUNTO,
        "estado_validacion": "pendiente",
        "ubicacion": {"latitud": 8.9, "longitud": -79.7},
        "confianza": None,
        "reportes_independientes": 2,
        "conflictos": [],
        "faltantes": ["personas_afectadas"],
        "requiere_revision_urgente": False,
        "periodo_inicio": "2026-10-16T14:00:00+00:00",
        "periodo_fin": "2026-10-16T18:00:00.000001+00:00",
        "primera_deteccion_en": "2026-10-16T18:00:00+00:00",
        "origen": "sintetico",
        "creado_en": "2026-10-16T18:00:00+00:00",
        "actualizado_en": "2026-10-16T18:05:00+00:00",
        "creado_por": str(uuid4()),
        "motivo": "Separación por coordinador",
        "tipo_problema": "sin_suministro",
        "episodio_establecido": True,
        "evaluacion_necesidad": None,
        "pendientes_calculo": ["Sin evaluación de necesidad"],
    }
    return {**fila, **cambios}


def vincular(db, fila, activos, desvinculados=0):
    for _ in range(activos):
        db.vinculos.append({"incidente_id": fila["incidente_id"], "desvinculado_en": None})
    for _ in range(desvinculados):
        db.vinculos.append({"incidente_id": fila["incidente_id"], "desvinculado_en": "2026-10-16T19:00:00+00:00"})


@pytest.fixture
def db():
    base = BaseFalsa()
    base.rpcs["ra_catalogo_v2"] = [
        {
            "punto_atencion_id": PUNTO,
            "sector_id": SECTOR,
            "nombre": "Escuela El Coco",
            "alias": ["El Coco"],
            "distrito": "La Chorrera",
            "corregimiento": "El Coco",
            "capacidad_recepcion_litros": None,
        }
    ]
    app.dependency_overrides[obtener_db] = lambda: base
    yield base
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(db):
    return TestClient(app)


def test_sin_incidentes_responde_lista_vacia(cliente, db):
    respuesta = cliente.get("/incidentes")
    assert respuesta.status_code == 200
    assert respuesta.json() == []
    assert db.llamadas == ["ra_incidentes_snapshot_v2"]


def test_snapshot_nulo_responde_lista_vacia(cliente, db):
    db.rpcs["ra_incidentes_snapshot_v2"] = None
    assert cliente.get("/incidentes").json() == []


def test_incidente_pendiente_con_punto_y_conteos(cliente, db):
    fila = incidente()
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]
    vincular(db, fila, activos=3, desvinculados=1)

    [dato] = cliente.get("/incidentes").json()

    assert dato["incidente_id"] == fila["incidente_id"]
    assert dato["punto"] == {
        "punto_atencion_id": PUNTO,
        "nombre": "Escuela El Coco",
        "distrito": "La Chorrera",
        "corregimiento": "El Coco",
    }
    # Vínculos activos (3) y remitentes distintos (2) son cifras distintas.
    assert dato["reportes_vinculados"] == 3
    assert dato["reportes_independientes"] == 2
    assert dato["evaluacion_necesidad"] is None
    assert dato["pendientes_calculo"] == ["Sin evaluación de necesidad"]
    assert dato["faltantes"] == ["personas_afectadas"]
    assert dato["tipo_problema"] == "sin_suministro"
    assert dato["episodio_establecido"] is True


def test_evaluacion_calculada_se_devuelve_validada(cliente, db):
    fila = incidente(
        incidente_id=EVALUACION["incidente_id"],
        evaluacion_necesidad=EVALUACION,
        pendientes_calculo=[],
    )
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]
    vincular(db, fila, activos=1)

    [dato] = cliente.get("/incidentes").json()

    evaluacion = dato["evaluacion_necesidad"]
    assert evaluacion["estado_prioridad"] == "calculada"
    assert evaluacion["posicion"] == 1
    assert evaluacion["demanda_litros"] == 2500.0
    assert dato["pendientes_calculo"] == []


def test_evaluacion_invalida_no_se_muestra_como_calculada(cliente, db):
    rota = {**EVALUACION, "demanda_litros": -5}
    fila = incidente(evaluacion_necesidad=rota, pendientes_calculo=[])
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]

    [dato] = cliente.get("/incidentes").json()

    assert dato["evaluacion_necesidad"] is None
    assert len(dato["pendientes_calculo"]) == 1
    assert "no cumple el contrato" in dato["pendientes_calculo"][0]


def test_recalculo_pendiente_se_conserva(cliente, db):
    # Tras separar un reporte, la RPC de Emilia invalida las evaluaciones con este motivo.
    fila = incidente(pendientes_calculo=["Asociación corregida; revisar lote y recalcular"])
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]

    [dato] = cliente.get("/incidentes").json()

    assert dato["evaluacion_necesidad"] is None
    assert dato["pendientes_calculo"] == ["Asociación corregida; revisar lote y recalcular"]


def test_incidente_sin_punto_ni_sector(cliente, db):
    fila = incidente(punto_atencion_id=None, sector_id=None)
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]

    [dato] = cliente.get("/incidentes").json()

    assert dato["punto"] is None
    assert dato["punto_atencion_id"] is None
    assert dato["reportes_vinculados"] == 0


def test_punto_fuera_del_catalogo_activo(cliente, db):
    fila = incidente(punto_atencion_id=str(uuid4()))
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]

    [dato] = cliente.get("/incidentes").json()

    assert dato["punto"] is None
    assert dato["punto_atencion_id"] == fila["punto_atencion_id"]


def test_orden_por_deteccion_mas_reciente(cliente, db):
    antiguo = incidente(primera_deteccion_en="2026-10-16T10:00:00+00:00")
    reciente = incidente(primera_deteccion_en="2026-10-16T20:00:00+00:00")
    db.rpcs["ra_incidentes_snapshot_v2"] = [antiguo, reciente]

    datos = cliente.get("/incidentes").json()

    assert [d["incidente_id"] for d in datos] == [reciente["incidente_id"], antiguo["incidente_id"]]


def test_no_expone_identidades_ni_campos_internos(cliente, db):
    fila = incidente()
    db.rpcs["ra_incidentes_snapshot_v2"] = [fila]

    [dato] = cliente.get("/incidentes").json()

    for campo in ("creado_por", "motivo", "ubicacion", "remitente_ref", "chat_id", "mensaje_externo_id"):
        assert campo not in dato
    assert fila["creado_por"] not in json.dumps(dato)


def test_fallo_de_la_base_responde_503(cliente, db):
    db.error = APIError({"message": "caida", "code": "XX000"})

    respuesta = cliente.get("/incidentes")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["codigo"] == "proveedor_no_disponible"
    assert cuerpo["recuperable"] is True
    assert "caida" not in json.dumps(cuerpo)
