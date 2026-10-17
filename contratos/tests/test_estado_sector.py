"""Fronteras de la proyección de estado; no prueban vigencia ni permisos en BD."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from contratos.consultas import EstadoSector, SolicitudEstadoSector

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"


def ejemplo(nombre="estado_sector_con_plan"):
    return json.loads((EJEMPLOS / f"{nombre}.json").read_text())


class TestEstadoSector(unittest.TestCase):
    def rechaza(self, payload):
        with self.assertRaises(ValidationError):
            EstadoSector.model_validate(payload)

    def test_solicitud_no_inventa_contexto_de_ejecucion(self):
        solicitud = SolicitudEstadoSector.model_validate(ejemplo("solicitud_estado_sector"))
        self.assertEqual(set(solicitud.model_dump()), {"esquema_version", "sector_id"})
        with self.assertRaises(ValidationError):
            SolicitudEstadoSector.model_validate({"sector_id": "nombre libre"})

    def test_respuesta_y_roundtrip(self):
        for nombre in ["estado_sector_con_plan", "estado_sector_sin_plan", "estado_sector_sin_puntos"]:
            with self.subTest(nombre=nombre):
                objeto = EstadoSector.model_validate(ejemplo(nombre))
                self.assertEqual(objeto, EstadoSector.model_validate_json(objeto.model_dump_json()))

    def test_sin_asignacion_no_significa_cero(self):
        x = ejemplo()
        punto = next(p for p in x["puntos"] if p["estado"] == "sin_asignacion")
        self.assertIsNone(punto["litros_asignados"])
        punto["litros_asignados"] = 0
        self.rechaza(x)

    def test_sin_plan_no_admite_asignaciones_historicas(self):
        x = ejemplo(); x.update(estado="sin_plan_vigente", plan_vigente=None)
        self.rechaza(x)

    def test_estado_coincide_con_plan(self):
        for nombre, estado in [("estado_sector_con_plan", "sin_plan_vigente"), ("estado_sector_sin_plan", "con_plan_vigente")]:
            x = ejemplo(nombre); x["estado"] = estado
            self.rechaza(x)

    def test_solo_plan_aprobado(self):
        for estado in ["calculando", "pendiente_revision", "rechazado", "invalidado"]:
            x = ejemplo(); x["plan_vigente"]["estado"] = estado
            self.rechaza(x)

    def test_verificacion_explicita_y_booleana(self):
        for valor in [False, None, 1, "true"]:
            x = ejemplo(); x["plan_vigente"]["verificado"] = valor
            self.rechaza(x)
        x = ejemplo(); del x["plan_vigente"]["verificado"]
        self.rechaza(x)

    def test_aprobacion_y_version_obligatorias(self):
        for campo in ["aprobacion_id", "aprobado_en", "datos_version", "politica_version", "ejecucion_id"]:
            x = ejemplo(); del x["plan_vigente"][campo]
            self.rechaza(x)
        for version in [0, -1, True]:
            x = ejemplo(); x["plan_vigente"]["version"] = version
            self.rechaza(x)

    def test_sin_aprobacion_futura(self):
        x = ejemplo(); x["plan_vigente"]["aprobado_en"] = "2026-10-18T18:00:00-05:00"
        self.rechaza(x)

    def test_puntos_del_mismo_sector(self):
        x = ejemplo(); x["puntos"][0]["sector_id"] = str(uuid4())
        self.rechaza(x)

    def test_ids_de_punto_y_parada_no_repetidos(self):
        x = ejemplo(); x["puntos"].append(deepcopy(x["puntos"][0]))
        self.rechaza(x)
        x = ejemplo(); nuevo = deepcopy(x["puntos"][0]); nuevo["punto_atencion_id"] = str(uuid4())
        x["puntos"].append(nuevo)
        self.rechaza(x)

    def test_asignacion_requiere_campos_completos(self):
        for campo in ["parada_id", "litros_asignados", "ventana_estimada"]:
            x = ejemplo(); x["puntos"][0][campo] = None
            self.rechaza(x)
        x = ejemplo(); x["puntos"][0]["motivo_sin_asignacion"] = "Incompatible"
        self.rechaza(x)

    def test_sin_asignacion_requiere_motivo(self):
        x = ejemplo("estado_sector_sin_plan"); x["puntos"][0]["motivo_sin_asignacion"] = None
        self.rechaza(x)

    def test_cantidades_positivas_finitas_y_no_booleanas(self):
        for cantidad in [0, -1, True, float("inf"), float("nan")]:
            x = ejemplo(); x["puntos"][0]["litros_asignados"] = cantidad
            self.rechaza(x)

    def test_ventana_ordenada_y_con_zona(self):
        x = ejemplo(); ventana = x["puntos"][0]["ventana_estimada"]
        ventana["fin"] = ventana["inicio"]
        self.rechaza(x)
        x = ejemplo(); x["puntos"][0]["ventana_estimada"]["inicio"] = "2026-10-17T08:10:00"
        self.rechaza(x)
        x = ejemplo(); x["consultado_en"] = "2026-10-16T18:05:00"
        self.rechaza(x)

    def test_conserva_origen_sintetico(self):
        x = ejemplo(); x["origen"] = "real"
        self.rechaza(x)
        x = ejemplo(); x["puntos"][0]["origen"] = "real"
        self.rechaza(x)

    def test_origen_real_o_estimado_coherente(self):
        for origen in ["real", "estimado"]:
            x = ejemplo(); x["origen"] = x["sector"]["origen"] = x["plan_vigente"]["origen"] = origen
            for punto in x["puntos"]:
                punto["origen"] = origen
            EstadoSector.model_validate(x)

    def test_estados_de_parada_conservados(self):
        for estado in ["programada", "iniciada", "atendida", "con_incidencia"]:
            x = ejemplo(); x["puntos"][0]["estado"] = estado
            EstadoSector.model_validate(x)
        x = ejemplo(); x["puntos"][0]["estado"] = "enviado"
        self.rechaza(x)

    def test_sector_vacio_con_plan_tambien_es_valido(self):
        x = ejemplo(); x["puntos"] = []
        EstadoSector.model_validate(x)

    def test_campos_privados_o_extra_no_admitidos(self):
        x = ejemplo(); x["puntos"][0]["chat_id"] = "privado"
        self.rechaza(x)
        x = ejemplo(); x["plan_vigente"]["bloqueos_publicacion"] = ["no publicar"]
        self.rechaza(x)


if __name__ == "__main__":
    unittest.main()
