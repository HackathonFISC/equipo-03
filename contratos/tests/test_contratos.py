"""Pruebas de frontera y compatibilidad de los contratos, no evals de los agentes."""
import importlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from contratos.modelos import (
    AvisoComunidad, EntradaReporte, EvaluacionNecesidades, ExtraccionReporteLLM,
    IncidenteConsolidado, InformeVerificacion, PoliticaPrioridad,
    PropuestaDistribucion, ReporteInterpretado, VentanaTiempo,
)
from contratos.solicitudes import (
    MatrizTiempos, ResultadoPriorizarNecesidades, ResultadoValidarNecesidad,
    SolicitudPriorizarNecesidades, SolicitudResolverRutas,
    SolicitudValidarNecesidad, SolicitudVerificarPlan,
)

EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"


def ejemplo(nombre):
    return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))


class TestContratos(unittest.TestCase):
    def rechaza(self, modelo, payload):
        with self.assertRaises(ValidationError):
            modelo.model_validate(payload)

    def test_todos_los_ejemplos_y_roundtrip_json(self):
        manifest = json.loads((EJEMPLOS / "manifest.json").read_text())
        self.assertGreaterEqual(len(manifest), 24)
        for archivo, referencia in manifest.items():
            with self.subTest(archivo=archivo):
                modulo, nombre = referencia.split(":")
                modelo = getattr(importlib.import_module(modulo), nombre)
                obj = modelo.model_validate_json((EJEMPLOS / archivo).read_text())
                self.assertEqual(obj, modelo.model_validate_json(obj.model_dump_json()))

    def test_fecha_sin_zona_no_pasa(self):
        x = ejemplo("reporte_interpretado"); x["creado_en"] = "2026-10-16T18:00:00"
        self.rechaza(ReporteInterpretado, x)

    def test_valor_negativo_no_pasa(self):
        x = ejemplo("reporte_interpretado"); x["interpretacion"]["campos"]["horas_sin_agua"] = -1
        self.rechaza(ReporteInterpretado, x)

    def test_booleano_no_es_cantidad(self):
        x = ejemplo("evaluacion_necesidades"); x["demanda_litros"] = True
        self.rechaza(EvaluacionNecesidades, x)

    def test_infinito_no_es_cantidad(self):
        x = ejemplo("evaluacion_necesidades"); x["demanda_litros"] = float("inf")
        self.rechaza(EvaluacionNecesidades, x)

    def test_llm_no_puede_inyectar_aprobacion(self):
        x = ejemplo("extraccion_reporte_llm"); x["aprobado"] = True
        self.rechaza(ExtraccionReporteLLM, x)

    def test_llm_no_puede_inventar_coordenadas_en_extraccion(self):
        x = ejemplo("extraccion_reporte_llm"); x["latitud"] = 8.9
        self.rechaza(ExtraccionReporteLLM, x)

    def test_llm_no_asigna_identificadores(self):
        x = ejemplo("extraccion_reporte_llm"); x["reporte_id"] = str(uuid4())
        self.rechaza(ExtraccionReporteLLM, x)

    def test_aclaracion_necesita_faltantes(self):
        x = ejemplo("extraccion_reporte_llm"); x["requiere_aclaracion"] = True
        self.rechaza(ExtraccionReporteLLM, x)

    def test_reporte_texto_no_puede_estar_vacio(self):
        x = ejemplo("reporte_registrado")["entrada"]; x["texto"] = "  "
        self.rechaza(EntradaReporte, x)

    def test_evidencia_de_otro_reporte_no_pasa(self):
        x = ejemplo("reporte_interpretado"); x["evidencias"][0]["reporte_id"] = str(uuid4())
        self.rechaza(ReporteInterpretado, x)

    def test_vinculos_no_repiten_reporte(self):
        x = ejemplo("incidente_consolidado"); x["reportes_ids"].append(x["reportes_ids"][0])
        self.rechaza(IncidenteConsolidado, x)

    def test_ubicacion_ambigua_no_pasa_como_validada(self):
        x = ejemplo("incidente_consolidado"); x["ubicacion"]["representa_punto_atencion"] = None
        self.rechaza(IncidenteConsolidado, x)

    def test_reserva_desconocida_se_conserva(self):
        x = SolicitudValidarNecesidad.model_validate(ejemplo("solicitud_validar_formula_pendiente"))
        self.assertIsNone(x.demanda.reserva_utilizable_litros)

    def test_directa_sin_confirmacion_admite_entrada_pendiente(self):
        x = ejemplo("solicitud_validar_directa"); x["demanda"]["confirmacion"] = None
        self.assertIsNone(SolicitudValidarNecesidad.model_validate(x).demanda.confirmacion)

    def test_resultado_validado_requiere_confirmacion(self):
        x = ejemplo("resultado_validar_necesidad"); x["confirmacion"] = None
        self.rechaza(ResultadoValidarNecesidad, x)

    def test_demanda_cero_explicita_no_es_desconocida(self):
        x = ejemplo("resultado_validar_necesidad"); x["demanda_litros"] = 0
        self.assertEqual(ResultadoValidarNecesidad.model_validate(x).demanda_litros, 0)

    def test_pendiente_no_tiene_puntaje(self):
        x = ejemplo("evaluacion_pendiente"); x["puntaje"] = 0
        self.rechaza(EvaluacionNecesidades, x)

    def test_falta_vulnerabilidad_no_equivale_a_cero(self):
        x = ejemplo("evaluacion_necesidades"); x["vulnerabilidad"] = None
        self.rechaza(EvaluacionNecesidades, x)

    def test_critico_requiere_ventana(self):
        x = ejemplo("evaluacion_necesidades"); x["ventana_atencion"] = None
        self.rechaza(EvaluacionNecesidades, x)

    def test_clase_no_confirmada_no_pasa(self):
        x = ejemplo("evaluacion_necesidades"); x["confirmacion_clase"] = None
        self.rechaza(EvaluacionNecesidades, x)

    def test_desglose_coincide_con_puntaje(self):
        x = ejemplo("evaluacion_necesidades"); x["puntaje"] = 99
        self.rechaza(EvaluacionNecesidades, x)

    def test_pesos_suman_uno(self):
        x = ejemplo("politica_prioridad"); x["peso_poblacion"] = .8
        self.rechaza(PoliticaPrioridad, x)

    def test_politica_no_se_autoactiva(self):
        x = ejemplo("politica_prioridad"); x["estado"] = "activa"
        self.rechaza(PoliticaPrioridad, x)

    def test_ranking_no_admite_volumen_de_quejas(self):
        x = ejemplo("evaluacion_necesidades"); x["report_count"] = 10000
        self.rechaza(EvaluacionNecesidades, x)

    def test_necesidades_no_mezclan_versiones(self):
        x = ejemplo("solicitud_priorizar"); x["necesidades"][0]["datos_version"] = "otra"
        self.rechaza(SolicitudPriorizarNecesidades, x)

    def test_clase_critica_no_queda_detras_de_general(self):
        x = ejemplo("resultado_priorizar")
        critica = x["evaluaciones"][0]; critica["posicion"] = 2
        general = deepcopy(critica); general.update(punto_atencion_id=str(uuid4()),incidente_id=str(uuid4()),clase_prioridad="general",posicion=1)
        x["evaluaciones"].append(general)
        self.rechaza(ResultadoPriorizarNecesidades, x)

    def test_matriz_cuadrada(self):
        x = ejemplo("solicitud_resolver_rutas")["matriz"]; x["minutos"][0].pop()
        self.rechaza(MatrizTiempos, x)

    def test_arco_bloqueado_admite_null(self):
        x = ejemplo("solicitud_resolver_rutas")["matriz"]; x["minutos"][0][1] = None
        self.assertIsNone(MatrizTiempos.model_validate(x).minutos[0][1])

    def test_sin_vehiculos_es_escenario_representable(self):
        x = ejemplo("solicitud_resolver_rutas"); x["vehiculos"] = []
        self.assertEqual(SolicitudResolverRutas.model_validate(x).vehiculos, [])

    def test_sin_recargas(self):
        x = ejemplo("solicitud_resolver_rutas"); x["recargas_permitidas"] = True
        self.rechaza(SolicitudResolverRutas, x)

    def test_ventana_invertida_no_pasa(self):
        self.rechaza(VentanaTiempo, {"inicio":"2026-10-17T09:00:00-05:00","fin":"2026-10-17T08:00:00-05:00"})

    def test_plan_no_divide_punto_entre_vehiculos(self):
        x = ejemplo("propuesta_distribucion"); x["rutas"][1]["paradas"][0]["punto_atencion_id"] = x["rutas"][0]["paradas"][0]["punto_atencion_id"]
        self.rechaza(PropuestaDistribucion, x)

    def test_timeout_no_declara_rutas(self):
        x = ejemplo("propuesta_distribucion"); x["estado_solver"] = "timeout_sin_solucion"
        self.rechaza(PropuestaDistribucion, x)

    def test_critico_no_atendido_bloquea(self):
        x = ejemplo("plan_timeout"); x["estado_solver"] = "factible"; x["bloqueos_publicacion"] = []
        self.rechaza(PropuestaDistribucion, x)

    def test_aprobacion_sin_verificacion_no_pasa(self):
        x = ejemplo("plan_aprobado_simulado"); x["verificacion"] = None
        self.rechaza(PropuestaDistribucion, x)

    def test_plan_bloqueado_no_se_aprueba(self):
        x = ejemplo("plan_aprobado_simulado"); x["bloqueos_publicacion"] = ["Sin cobertura crítica"]
        self.rechaza(PropuestaDistribucion, x)

    def test_verificacion_obsoleta_no_pasa(self):
        x = ejemplo("propuesta_distribucion"); x["verificacion"]["version"] = 2
        self.rechaza(PropuestaDistribucion, x)

    def test_verificacion_incompleta_no_es_valida(self):
        x = ejemplo("informe_verificacion"); x["comprobaciones"].remove("capacidad")
        self.rechaza(InformeVerificacion, x)

    def test_snapshot_distinto_no_pasa(self):
        x = ejemplo("solicitud_verificar_plan"); x["solicitud_original"]["version"] = 2
        self.rechaza(SolicitudVerificarPlan, x)

    def test_enviado_requiere_confirmacion(self):
        x = ejemplo("aviso_comunidad"); x["estado_envio"] = "enviado"
        self.rechaza(AvisoComunidad, x)

    def test_incierto_exige_motivo(self):
        x = ejemplo("aviso_comunidad"); x["estado_envio"] = "incierto"
        self.rechaza(AvisoComunidad, x)

    def test_idempotencia_distingue_version_y_punto(self):
        x = ejemplo("aviso_comunidad"); uno = AvisoComunidad.model_validate(x)
        dos = AvisoComunidad.model_validate(dict(x,version=2))
        tres = AvisoComunidad.model_validate(dict(x,punto_atencion_id=str(uuid4())))
        self.assertNotEqual(uno.clave_idempotencia, dos.clave_idempotencia)
        self.assertNotEqual(uno.clave_idempotencia, tres.clave_idempotencia)


if __name__ == "__main__":
    unittest.main()
