// Necesidades de ejemplo para desarrollar la página sin la API.
// Sintéticas: el primer par sale de contratos/ejemplos; las otras dos se derivaron de él
// y se validaron con IncidenteConsolidado y EvaluacionNecesidades antes de copiarlas aquí.
// 'punto.nombre' no está en los contratos: es una propuesta para que la API lo una desde puntos_atencion.

export const necesidadesEjemplo = [
  {
    "punto": {
      "nombre": "Punto de demo P1"
    },
    "incidente": {
      "esquema_version": "1.0",
      "ejecucion_id": "efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e",
      "creado_en": "2026-10-16T18:00:00-05:00",
      "origen": "sintetico",
      "incidente_id": "bbb05f27-8cf4-5ab9-80ac-0fab439876e1",
      "version": 1,
      "sector_id": "973bc96c-73f6-578e-9873-be50e57cb2eb",
      "punto_atencion_id": "e42009e1-0718-57dd-bacf-6c0a8d6a8521",
      "reportes_ids": [
        "bc815641-f5cc-5c37-aaf5-e85bf7d84f23",
        "54c360e4-0f60-517b-9e88-430aa9984154",
        "0bf57912-73fa-5bd2-b4c5-a75201d54b78"
      ],
      "reportes_independientes": 2,
      "ubicacion": {
        "latitud": 8.901,
        "longitud": -79.699,
        "fuente": "escenario",
        "precision_metros": null,
        "representa_punto_atencion": true
      },
      "estado_validacion": "validada",
      "confianza": 0.8,
      "conflictos": [],
      "faltantes": [],
      "requiere_revision_urgente": false,
      "periodo_incidente": {
        "inicio": "2026-10-16T14:00:00-05:00",
        "fin": "2026-10-16T18:00:00-05:00"
      },
      "primera_deteccion_en": "2026-10-16T14:00:00-05:00"
    },
    "evaluacion": {
      "esquema_version": "1.0",
      "ejecucion_id": "efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e",
      "creado_en": "2026-10-16T18:00:00-05:00",
      "origen": "sintetico",
      "incidente_id": "bbb05f27-8cf4-5ab9-80ac-0fab439876e1",
      "punto_atencion_id": "e42009e1-0718-57dd-bacf-6c0a8d6a8521",
      "datos_version": "escenario-1.0",
      "politica_version": "demo-1.0",
      "estado_demanda": "validada",
      "demanda_litros": 2500.0,
      "metodo_demanda": "directa",
      "confirmacion_demanda": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "clase_prioridad": "critico",
      "confirmacion_clase": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "ventana_atencion": {
        "inicio": "2026-10-17T08:00:00-05:00",
        "fin": "2026-10-17T09:00:00-05:00"
      },
      "horas_sin_agua": 72.0,
      "personas_atendidas": 130,
      "vulnerabilidad": "alta",
      "confirmacion_vulnerabilidad": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "ultima_atencion_confirmada_en": null,
      "primera_deteccion_en": "2026-10-16T14:00:00-05:00",
      "estado_prioridad": "calculada",
      "puntaje": 56.628571428571426,
      "componentes": {
        "duracion_normalizada": 0.42857142857142855,
        "vulnerabilidad_normalizada": 1.0,
        "poblacion_normalizada": 0.26,
        "aporte_duracion": 21.428571428571427,
        "aporte_vulnerabilidad": 30.0,
        "aporte_poblacion": 5.2
      },
      "posicion": 1,
      "pendientes": [],
      "supuestos": [
        "Demanda y factores sintéticos; no se calculó una dotación oficial."
      ],
      "requiere_revision_urgente": false
    }
  },
  {
    "punto": {
      "nombre": "Punto de demo P2"
    },
    "incidente": {
      "esquema_version": "1.0",
      "ejecucion_id": "efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e",
      "creado_en": "2026-10-16T18:00:00-05:00",
      "origen": "sintetico",
      "incidente_id": "00000000-0000-4000-8000-00000000b002",
      "version": 1,
      "sector_id": "973bc96c-73f6-578e-9873-be50e57cb2eb",
      "punto_atencion_id": "00000000-0000-4000-8000-00000000c002",
      "reportes_ids": [
        "00000000-0000-4000-8000-000000000011",
        "00000000-0000-4000-8000-000000000012"
      ],
      "reportes_independientes": 2,
      "ubicacion": {
        "latitud": 8.912,
        "longitud": -79.71,
        "fuente": "escenario",
        "precision_metros": null,
        "representa_punto_atencion": true
      },
      "estado_validacion": "validada",
      "confianza": 0.65,
      "conflictos": [],
      "faltantes": [],
      "requiere_revision_urgente": false,
      "periodo_incidente": {
        "inicio": "2026-10-16T15:30:00-05:00",
        "fin": "2026-10-16T18:00:00-05:00"
      },
      "primera_deteccion_en": "2026-10-16T15:30:00-05:00"
    },
    "evaluacion": {
      "esquema_version": "1.0",
      "ejecucion_id": "efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e",
      "creado_en": "2026-10-16T18:00:00-05:00",
      "origen": "sintetico",
      "incidente_id": "00000000-0000-4000-8000-00000000b002",
      "punto_atencion_id": "00000000-0000-4000-8000-00000000c002",
      "datos_version": "escenario-1.0",
      "politica_version": "demo-1.0",
      "estado_demanda": "validada",
      "demanda_litros": 4000.0,
      "metodo_demanda": "directa",
      "confirmacion_demanda": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "clase_prioridad": "general",
      "confirmacion_clase": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "ventana_atencion": null,
      "horas_sin_agua": 24.0,
      "personas_atendidas": 500,
      "vulnerabilidad": "sin_condicion_identificada",
      "confirmacion_vulnerabilidad": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "ultima_atencion_confirmada_en": null,
      "primera_deteccion_en": "2026-10-16T15:30:00-05:00",
      "estado_prioridad": "calculada",
      "puntaje": 27.142857142857142,
      "componentes": {
        "duracion_normalizada": 0.14285714285714285,
        "vulnerabilidad_normalizada": 0.0,
        "poblacion_normalizada": 1.0,
        "aporte_duracion": 7.142857142857142,
        "aporte_vulnerabilidad": 0.0,
        "aporte_poblacion": 20.0
      },
      "posicion": 2,
      "pendientes": [],
      "supuestos": [
        "Demanda y factores sintéticos; no se calculó una dotación oficial."
      ],
      "requiere_revision_urgente": false
    }
  },
  {
    "punto": {
      "nombre": "Punto de demo P3"
    },
    "incidente": {
      "esquema_version": "1.0",
      "ejecucion_id": "efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e",
      "creado_en": "2026-10-16T18:00:00-05:00",
      "origen": "sintetico",
      "incidente_id": "00000000-0000-4000-8000-00000000b003",
      "version": 1,
      "sector_id": "973bc96c-73f6-578e-9873-be50e57cb2eb",
      "punto_atencion_id": "00000000-0000-4000-8000-00000000c003",
      "reportes_ids": [
        "00000000-0000-4000-8000-000000000021"
      ],
      "reportes_independientes": 1,
      "ubicacion": {
        "latitud": 8.901,
        "longitud": -79.699,
        "fuente": "escenario",
        "precision_metros": null,
        "representa_punto_atencion": true
      },
      "estado_validacion": "pendiente",
      "confianza": 0.35,
      "conflictos": [
        "Dos mensajes dan cantidades distintas de personas."
      ],
      "faltantes": [
        "Cantidad de personas atendidas"
      ],
      "requiere_revision_urgente": true,
      "periodo_incidente": {
        "inicio": "2026-10-16T16:10:00-05:00",
        "fin": "2026-10-16T18:00:00-05:00"
      },
      "primera_deteccion_en": "2026-10-16T16:10:00-05:00"
    },
    "evaluacion": {
      "esquema_version": "1.0",
      "ejecucion_id": "efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e",
      "creado_en": "2026-10-16T18:00:00-05:00",
      "origen": "sintetico",
      "incidente_id": "00000000-0000-4000-8000-00000000b003",
      "punto_atencion_id": "00000000-0000-4000-8000-00000000c003",
      "datos_version": "escenario-1.0",
      "politica_version": "demo-1.0",
      "estado_demanda": "pendiente",
      "demanda_litros": null,
      "metodo_demanda": "directa",
      "confirmacion_demanda": null,
      "clase_prioridad": "critico",
      "confirmacion_clase": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "ventana_atencion": {
        "inicio": "2026-10-17T08:00:00-05:00",
        "fin": "2026-10-17T09:00:00-05:00"
      },
      "horas_sin_agua": 72.0,
      "personas_atendidas": null,
      "vulnerabilidad": "alta",
      "confirmacion_vulnerabilidad": {
        "usuario_id": "b57c3e03-741d-5ceb-8c43-4a754c0ade31",
        "confirmado_en": "2026-10-16T18:00:00-05:00",
        "motivo": "FIXTURE SINTÉTICO; no acredita autorización ni validación real"
      },
      "ultima_atencion_confirmada_en": null,
      "primera_deteccion_en": "2026-10-16T16:10:00-05:00",
      "estado_prioridad": "pendiente",
      "puntaje": null,
      "componentes": null,
      "posicion": null,
      "pendientes": [
        "Demanda por confirmar.",
        "Personas atendidas sin confirmar."
      ],
      "supuestos": [
        "Demanda y factores sintéticos; no se calculó una dotación oficial."
      ],
      "requiere_revision_urgente": true
    }
  }
]
