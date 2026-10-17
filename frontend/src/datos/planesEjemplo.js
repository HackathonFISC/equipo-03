// Ejemplos sintéticos: salida real de solve_routes y verify_plan (calculo/) sobre el escenario ficticio
// de José, con nombres del catálogo de puntos. No son un plan operativo ni están aprobados.
// Forma de cada elemento: PropuestaDistribucion + catalogo (puntos, vehiculos, deposito) + ejemplo.
export const planesEjemplo = [
  {
    "esquema_version": "1.0",
    "ejecucion_id": "b4d31018-6400-54e0-a5a0-0f6f30eea239",
    "creado_en": "2026-10-17T07:00:00-05:00",
    "origen": "sintetico",
    "plan_id": "5b2ebe8d-30c7-5efb-a85b-f647d3498a90",
    "version": 4,
    "datos_version": "oeste-1.0-ensayo-3-completo",
    "politica_version": "oeste-prioridad-apoyo-pa-1-fixture-3",
    "estado": "pendiente_revision",
    "estado_solver": "factible",
    "rutas": [
      {
        "vehiculo_id": "cafb1a61-101b-5fda-98b3-c9b5c0d0468f",
        "deposito_id": "b510bbba-5a8e-5778-9feb-209ac69fc88a",
        "salida_estimada": "2026-10-17T13:00:00Z",
        "retorno_estimado": "2026-10-17T15:07:00Z",
        "paradas": [
          {
            "parada_id": "8c17d94e-51d9-59c2-bd43-cdac20d5522f",
            "punto_atencion_id": "9459ff87-0377-5622-8255-caaf79dc9898",
            "incidente_id": "413b7809-030a-5ae2-b93b-fb0bc08c49b4",
            "orden": 1,
            "litros_asignados": 2500.0,
            "llegada_estimada": "2026-10-17T13:35:00Z",
            "inicio_descarga": "2026-10-17T13:35:00Z",
            "fin_descarga": "2026-10-17T13:49:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "8adb3144-a364-54af-8ed5-b325882b784c",
            "punto_atencion_id": "4b89af3e-444a-5103-880c-fe1c886530ed",
            "incidente_id": "c98983eb-ad99-5167-af73-ece92f9a9f6b",
            "orden": 2,
            "litros_asignados": 3000.0,
            "llegada_estimada": "2026-10-17T13:57:00Z",
            "inicio_descarga": "2026-10-17T13:57:00Z",
            "fin_descarga": "2026-10-17T14:12:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "9ba142b7-00df-5fa9-a237-19bde477a8ad",
            "punto_atencion_id": "b2478919-28e8-592d-ae1f-c450057cb229",
            "incidente_id": "0e675ead-c994-5b1e-b31b-1e1c41d5009f",
            "orden": 3,
            "litros_asignados": 1500.0,
            "llegada_estimada": "2026-10-17T14:27:00Z",
            "inicio_descarga": "2026-10-17T14:27:00Z",
            "fin_descarga": "2026-10-17T14:37:00Z",
            "estado": "programada"
          }
        ]
      },
      {
        "vehiculo_id": "f2c6a5ef-f9f3-5515-84c3-00fb0ba65210",
        "deposito_id": "b510bbba-5a8e-5778-9feb-209ac69fc88a",
        "salida_estimada": "2026-10-17T13:00:00Z",
        "retorno_estimado": "2026-10-17T14:42:00Z",
        "paradas": [
          {
            "parada_id": "11b2b9ad-1272-5823-9658-06812f4ab658",
            "punto_atencion_id": "1e35ede2-8fc7-51b0-8830-6eec337f6a24",
            "incidente_id": "8804b10c-7e7c-532e-8c63-44d91f421926",
            "orden": 1,
            "litros_asignados": 3000.0,
            "llegada_estimada": "2026-10-17T13:18:00Z",
            "inicio_descarga": "2026-10-17T13:18:00Z",
            "fin_descarga": "2026-10-17T13:33:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "a318a63d-03b5-5e96-887b-3b698bd4846e",
            "punto_atencion_id": "66597297-f57e-54ac-b7f1-7a66cc35253f",
            "incidente_id": "582785a7-2184-5a91-a55d-2dead460af08",
            "orden": 2,
            "litros_asignados": 2000.0,
            "llegada_estimada": "2026-10-17T13:45:00Z",
            "inicio_descarga": "2026-10-17T13:45:00Z",
            "fin_descarga": "2026-10-17T13:57:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "695e3664-9aed-5069-bcc7-175833cd22e8",
            "punto_atencion_id": "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e",
            "incidente_id": "8567e5a8-3a1c-51f6-9f6f-6feeca2e43d1",
            "orden": 3,
            "litros_asignados": 3000.0,
            "llegada_estimada": "2026-10-17T14:12:00Z",
            "inicio_descarga": "2026-10-17T14:12:00Z",
            "fin_descarga": "2026-10-17T14:27:00Z",
            "estado": "programada"
          }
        ]
      }
    ],
    "no_atendidos": [],
    "verificacion": {
      "esquema_version": "1.0",
      "ejecucion_id": "b4d31018-6400-54e0-a5a0-0f6f30eea239",
      "creado_en": "2026-10-17T07:00:00-05:00",
      "origen": "sintetico",
      "plan_id": "5b2ebe8d-30c7-5efb-a85b-f647d3498a90",
      "version": 4,
      "datos_version": "oeste-1.0-ensayo-3-completo",
      "politica_version": "oeste-prioridad-apoyo-pa-1-fixture-3",
      "valido": true,
      "violaciones": [],
      "comprobaciones": [
        "capacidad",
        "horarios",
        "ventanas",
        "retorno",
        "asignacion_unica",
        "demanda_completa",
        "version_entradas",
        "cobertura_critica"
      ]
    },
    "supuestos": [
      "Una salida por vehículo, sin recargas ni entregas divididas; matriz dirigida por UUID y descarga completa dentro de ventana.",
      "Objetivo: máximo número de críticos cubiertos, luego orden lexicográfico del ranking, luego mínima duración total de rutas.",
      "Óptimo demostrado para ese objetivo en este snapshot.",
      "Matriz oeste-1.0-ensayo-3-matriz-1, origen sintetico; no certifica acceso vial, recepción ni condiciones sanitarias.",
      "Cantidades exactas hasta mililitros; fechas y viajes con precisión de microsegundos.",
      "HUELLA_ENTRADAS_SHA256=cdef5ad43a7c0a0ae207768f8bc03e5a53b034d837571ec280cef282c2308318"
    ],
    "bloqueos_publicacion": [
      "Sin verificación independiente ni aprobación autorizada de esta versión.",
      "Política sintética: el cálculo no acredita autorización operativa ni calidad del agua."
    ],
    "aprobacion": null,
    "catalogo": {
      "puntos": {
        "1e35ede2-8fc7-51b0-8830-6eec337f6a24": {
          "nombre": "Junta Comunal de Vista Alegre",
          "distrito": "Arraiján",
          "corregimiento": "Vista Alegre"
        },
        "66597297-f57e-54ac-b7f1-7a66cc35253f": {
          "nombre": "C.E.B.G. Burunga",
          "distrito": "Arraiján",
          "corregimiento": "Burunga"
        },
        "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e": {
          "nombre": "Junta Comunal Nuevo Arraiján",
          "distrito": "Arraiján",
          "corregimiento": "Juan Demóstenes Arosemena"
        },
        "4b89af3e-444a-5103-880c-fe1c886530ed": {
          "nombre": "C.E. Virgen de Guadalupe",
          "distrito": "La Chorrera",
          "corregimiento": "Guadalupe"
        },
        "9459ff87-0377-5622-8255-caaf79dc9898": {
          "nombre": "Escuela El Coco",
          "distrito": "La Chorrera",
          "corregimiento": "El Coco"
        },
        "b2478919-28e8-592d-ae1f-c450057cb229": {
          "nombre": "Centro Educativo Guillermo Endara",
          "distrito": "La Chorrera",
          "corregimiento": "Playa Leona"
        }
      },
      "vehiculos": {
        "cafb1a61-101b-5fda-98b3-c9b5c0d0468f": {
          "capacidad_litros": 10000.0,
          "disponible": true
        },
        "f2c6a5ef-f9f3-5515-84c3-00fb0ba65210": {
          "capacidad_litros": 10000.0,
          "disponible": true
        }
      },
      "deposito": {
        "nombre": "Depósito ficticio del ensayo"
      }
    },
    "ejemplo": "Seis puntos, dos cisternas"
  },
  {
    "esquema_version": "1.0",
    "ejecucion_id": "b4d31018-6400-54e0-a5a0-0f6f30eea239",
    "creado_en": "2026-10-17T07:00:00-05:00",
    "origen": "sintetico",
    "plan_id": "5b2ebe8d-30c7-5efb-a85b-f647d3498a90",
    "version": 5,
    "datos_version": "oeste-1.0-ensayo-3-una_cisterna",
    "politica_version": "oeste-prioridad-apoyo-pa-1-fixture-3",
    "estado": "pendiente_revision",
    "estado_solver": "factible",
    "rutas": [
      {
        "vehiculo_id": "cafb1a61-101b-5fda-98b3-c9b5c0d0468f",
        "deposito_id": "b510bbba-5a8e-5778-9feb-209ac69fc88a",
        "salida_estimada": "2026-10-17T13:00:00Z",
        "retorno_estimado": "2026-10-17T15:54:00Z",
        "paradas": [
          {
            "parada_id": "f9a059d0-2d97-5d95-87c7-6b5472e9fb92",
            "punto_atencion_id": "66597297-f57e-54ac-b7f1-7a66cc35253f",
            "incidente_id": "582785a7-2184-5a91-a55d-2dead460af08",
            "orden": 1,
            "litros_asignados": 2000.0,
            "llegada_estimada": "2026-10-17T13:25:00Z",
            "inicio_descarga": "2026-10-17T13:25:00Z",
            "fin_descarga": "2026-10-17T13:37:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "ba82d475-4f39-555d-bfec-e4d38824ab28",
            "punto_atencion_id": "9459ff87-0377-5622-8255-caaf79dc9898",
            "incidente_id": "413b7809-030a-5ae2-b93b-fb0bc08c49b4",
            "orden": 2,
            "litros_asignados": 2500.0,
            "llegada_estimada": "2026-10-17T14:22:00Z",
            "inicio_descarga": "2026-10-17T14:22:00Z",
            "fin_descarga": "2026-10-17T14:36:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "1df54cd3-0ea9-5d0a-9ffd-0eb15c447513",
            "punto_atencion_id": "4b89af3e-444a-5103-880c-fe1c886530ed",
            "incidente_id": "c98983eb-ad99-5167-af73-ece92f9a9f6b",
            "orden": 3,
            "litros_asignados": 3000.0,
            "llegada_estimada": "2026-10-17T14:44:00Z",
            "inicio_descarga": "2026-10-17T14:44:00Z",
            "fin_descarga": "2026-10-17T14:59:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "1a24aeb4-a3d3-5468-8f27-b56630978268",
            "punto_atencion_id": "b2478919-28e8-592d-ae1f-c450057cb229",
            "incidente_id": "0e675ead-c994-5b1e-b31b-1e1c41d5009f",
            "orden": 4,
            "litros_asignados": 1500.0,
            "llegada_estimada": "2026-10-17T15:14:00Z",
            "inicio_descarga": "2026-10-17T15:14:00Z",
            "fin_descarga": "2026-10-17T15:24:00Z",
            "estado": "programada"
          }
        ]
      }
    ],
    "no_atendidos": [
      {
        "incidente_id": "8804b10c-7e7c-532e-8c63-44d91f421926",
        "punto_atencion_id": "1e35ede2-8fc7-51b0-8830-6eec337f6a24",
        "clase_prioridad": "general",
        "demanda_pendiente_litros": 3000.0,
        "codigo": "sin_capacidad",
        "motivo": "No cabe íntegramente en la capacidad restante de las rutas elegidas por prioridad."
      },
      {
        "incidente_id": "8567e5a8-3a1c-51f6-9f6f-6feeca2e43d1",
        "punto_atencion_id": "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e",
        "clase_prioridad": "general",
        "demanda_pendiente_litros": 3000.0,
        "codigo": "sin_capacidad",
        "motivo": "No cabe íntegramente en la capacidad restante de las rutas elegidas por prioridad."
      }
    ],
    "verificacion": {
      "esquema_version": "1.0",
      "ejecucion_id": "b4d31018-6400-54e0-a5a0-0f6f30eea239",
      "creado_en": "2026-10-17T07:00:00-05:00",
      "origen": "sintetico",
      "plan_id": "5b2ebe8d-30c7-5efb-a85b-f647d3498a90",
      "version": 5,
      "datos_version": "oeste-1.0-ensayo-3-una_cisterna",
      "politica_version": "oeste-prioridad-apoyo-pa-1-fixture-3",
      "valido": true,
      "violaciones": [],
      "comprobaciones": [
        "capacidad",
        "horarios",
        "ventanas",
        "retorno",
        "asignacion_unica",
        "demanda_completa",
        "version_entradas",
        "cobertura_critica"
      ]
    },
    "supuestos": [
      "Una salida por vehículo, sin recargas ni entregas divididas; matriz dirigida por UUID y descarga completa dentro de ventana.",
      "Objetivo: máximo número de críticos cubiertos, luego orden lexicográfico del ranking, luego mínima duración total de rutas.",
      "Óptimo demostrado para ese objetivo en este snapshot.",
      "Matriz oeste-1.0-ensayo-3-matriz-1, origen sintetico; no certifica acceso vial, recepción ni condiciones sanitarias.",
      "Cantidades exactas hasta mililitros; fechas y viajes con precisión de microsegundos.",
      "HUELLA_ENTRADAS_SHA256=01194353cd4227944b6d1afe90da2f4ed9039ef11162c7e98130144de1b33401"
    ],
    "bloqueos_publicacion": [
      "Sin verificación independiente ni aprobación autorizada de esta versión.",
      "Política sintética: el cálculo no acredita autorización operativa ni calidad del agua."
    ],
    "aprobacion": null,
    "catalogo": {
      "puntos": {
        "1e35ede2-8fc7-51b0-8830-6eec337f6a24": {
          "nombre": "Junta Comunal de Vista Alegre",
          "distrito": "Arraiján",
          "corregimiento": "Vista Alegre"
        },
        "66597297-f57e-54ac-b7f1-7a66cc35253f": {
          "nombre": "C.E.B.G. Burunga",
          "distrito": "Arraiján",
          "corregimiento": "Burunga"
        },
        "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e": {
          "nombre": "Junta Comunal Nuevo Arraiján",
          "distrito": "Arraiján",
          "corregimiento": "Juan Demóstenes Arosemena"
        },
        "4b89af3e-444a-5103-880c-fe1c886530ed": {
          "nombre": "C.E. Virgen de Guadalupe",
          "distrito": "La Chorrera",
          "corregimiento": "Guadalupe"
        },
        "9459ff87-0377-5622-8255-caaf79dc9898": {
          "nombre": "Escuela El Coco",
          "distrito": "La Chorrera",
          "corregimiento": "El Coco"
        },
        "b2478919-28e8-592d-ae1f-c450057cb229": {
          "nombre": "Centro Educativo Guillermo Endara",
          "distrito": "La Chorrera",
          "corregimiento": "Playa Leona"
        }
      },
      "vehiculos": {
        "cafb1a61-101b-5fda-98b3-c9b5c0d0468f": {
          "capacidad_litros": 10000.0,
          "disponible": true
        },
        "f2c6a5ef-f9f3-5515-84c3-00fb0ba65210": {
          "capacidad_litros": 10000.0,
          "disponible": false
        }
      },
      "deposito": {
        "nombre": "Depósito ficticio del ensayo"
      }
    },
    "ejemplo": "Una cisterna disponible"
  },
  {
    "esquema_version": "1.0",
    "ejecucion_id": "b4d31018-6400-54e0-a5a0-0f6f30eea239",
    "creado_en": "2026-10-17T07:00:00-05:00",
    "origen": "sintetico",
    "plan_id": "5b2ebe8d-30c7-5efb-a85b-f647d3498a90",
    "version": 6,
    "datos_version": "oeste-1.0-ensayo-3-critico_supera_cisterna",
    "politica_version": "oeste-prioridad-apoyo-pa-1-fixture-3",
    "estado": "pendiente_revision",
    "estado_solver": "factible",
    "rutas": [
      {
        "vehiculo_id": "cafb1a61-101b-5fda-98b3-c9b5c0d0468f",
        "deposito_id": "b510bbba-5a8e-5778-9feb-209ac69fc88a",
        "salida_estimada": "2026-10-17T13:00:00Z",
        "retorno_estimado": "2026-10-17T14:41:00Z",
        "paradas": [
          {
            "parada_id": "fdc7cdcf-f0ec-5686-b5c4-76fe496e3bb4",
            "punto_atencion_id": "9459ff87-0377-5622-8255-caaf79dc9898",
            "incidente_id": "413b7809-030a-5ae2-b93b-fb0bc08c49b4",
            "orden": 1,
            "litros_asignados": 2500.0,
            "llegada_estimada": "2026-10-17T13:35:00Z",
            "inicio_descarga": "2026-10-17T13:35:00Z",
            "fin_descarga": "2026-10-17T13:49:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "b2c89b17-4ea7-53ba-b834-aab14b499d95",
            "punto_atencion_id": "b2478919-28e8-592d-ae1f-c450057cb229",
            "incidente_id": "0e675ead-c994-5b1e-b31b-1e1c41d5009f",
            "orden": 2,
            "litros_asignados": 1500.0,
            "llegada_estimada": "2026-10-17T14:01:00Z",
            "inicio_descarga": "2026-10-17T14:01:00Z",
            "fin_descarga": "2026-10-17T14:11:00Z",
            "estado": "programada"
          }
        ]
      },
      {
        "vehiculo_id": "f2c6a5ef-f9f3-5515-84c3-00fb0ba65210",
        "deposito_id": "b510bbba-5a8e-5778-9feb-209ac69fc88a",
        "salida_estimada": "2026-10-17T13:00:00Z",
        "retorno_estimado": "2026-10-17T14:42:00Z",
        "paradas": [
          {
            "parada_id": "daf40577-1107-5b3a-ada7-90d7395157e3",
            "punto_atencion_id": "1e35ede2-8fc7-51b0-8830-6eec337f6a24",
            "incidente_id": "8804b10c-7e7c-532e-8c63-44d91f421926",
            "orden": 1,
            "litros_asignados": 3000.0,
            "llegada_estimada": "2026-10-17T13:18:00Z",
            "inicio_descarga": "2026-10-17T13:18:00Z",
            "fin_descarga": "2026-10-17T13:33:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "9a9fbbe1-0e59-50bb-b47a-ad21b28228b9",
            "punto_atencion_id": "66597297-f57e-54ac-b7f1-7a66cc35253f",
            "incidente_id": "582785a7-2184-5a91-a55d-2dead460af08",
            "orden": 2,
            "litros_asignados": 2000.0,
            "llegada_estimada": "2026-10-17T13:45:00Z",
            "inicio_descarga": "2026-10-17T13:45:00Z",
            "fin_descarga": "2026-10-17T13:57:00Z",
            "estado": "programada"
          },
          {
            "parada_id": "c69d3a16-e922-5eea-8e17-bcf250faea24",
            "punto_atencion_id": "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e",
            "incidente_id": "8567e5a8-3a1c-51f6-9f6f-6feeca2e43d1",
            "orden": 3,
            "litros_asignados": 3000.0,
            "llegada_estimada": "2026-10-17T14:12:00Z",
            "inicio_descarga": "2026-10-17T14:12:00Z",
            "fin_descarga": "2026-10-17T14:27:00Z",
            "estado": "programada"
          }
        ]
      }
    ],
    "no_atendidos": [
      {
        "incidente_id": "c98983eb-ad99-5167-af73-ece92f9a9f6b",
        "punto_atencion_id": "4b89af3e-444a-5103-880c-fe1c886530ed",
        "clase_prioridad": "critico",
        "demanda_pendiente_litros": 12000.0,
        "codigo": "demanda_supera_vehiculo",
        "motivo": "Demanda indivisible mayor que cualquier cisterna disponible; sin dividir ni recargar."
      }
    ],
    "verificacion": {
      "esquema_version": "1.0",
      "ejecucion_id": "b4d31018-6400-54e0-a5a0-0f6f30eea239",
      "creado_en": "2026-10-17T07:00:00-05:00",
      "origen": "sintetico",
      "plan_id": "5b2ebe8d-30c7-5efb-a85b-f647d3498a90",
      "version": 6,
      "datos_version": "oeste-1.0-ensayo-3-critico_supera_cisterna",
      "politica_version": "oeste-prioridad-apoyo-pa-1-fixture-3",
      "valido": false,
      "violaciones": [
        {
          "codigo": "cobertura_critica",
          "detalle": "Crítico o posible urgencia sin cubrir: escalar; no aprobar publicación.",
          "referencia_id": "4b89af3e-444a-5103-880c-fe1c886530ed"
        }
      ],
      "comprobaciones": [
        "capacidad",
        "horarios",
        "ventanas",
        "retorno",
        "asignacion_unica",
        "demanda_completa",
        "version_entradas",
        "cobertura_critica"
      ]
    },
    "supuestos": [
      "Una salida por vehículo, sin recargas ni entregas divididas; matriz dirigida por UUID y descarga completa dentro de ventana.",
      "Objetivo: máximo número de críticos cubiertos, luego orden lexicográfico del ranking, luego mínima duración total de rutas.",
      "Óptimo demostrado para ese objetivo en este snapshot.",
      "Matriz oeste-1.0-ensayo-3-matriz-1, origen sintetico; no certifica acceso vial, recepción ni condiciones sanitarias.",
      "Cantidades exactas hasta mililitros; fechas y viajes con precisión de microsegundos.",
      "HUELLA_ENTRADAS_SHA256=20e17593b8c7dfb1820c8db124c008ef40e808b5e854eb72337634dd066c4837"
    ],
    "bloqueos_publicacion": [
      "Sin verificación independiente ni aprobación autorizada de esta versión.",
      "Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.",
      "Cobertura crítica o posible urgencia pendiente: escalar y bloquear publicación."
    ],
    "aprobacion": null,
    "catalogo": {
      "puntos": {
        "1e35ede2-8fc7-51b0-8830-6eec337f6a24": {
          "nombre": "Junta Comunal de Vista Alegre",
          "distrito": "Arraiján",
          "corregimiento": "Vista Alegre"
        },
        "66597297-f57e-54ac-b7f1-7a66cc35253f": {
          "nombre": "C.E.B.G. Burunga",
          "distrito": "Arraiján",
          "corregimiento": "Burunga"
        },
        "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e": {
          "nombre": "Junta Comunal Nuevo Arraiján",
          "distrito": "Arraiján",
          "corregimiento": "Juan Demóstenes Arosemena"
        },
        "4b89af3e-444a-5103-880c-fe1c886530ed": {
          "nombre": "C.E. Virgen de Guadalupe",
          "distrito": "La Chorrera",
          "corregimiento": "Guadalupe"
        },
        "9459ff87-0377-5622-8255-caaf79dc9898": {
          "nombre": "Escuela El Coco",
          "distrito": "La Chorrera",
          "corregimiento": "El Coco"
        },
        "b2478919-28e8-592d-ae1f-c450057cb229": {
          "nombre": "Centro Educativo Guillermo Endara",
          "distrito": "La Chorrera",
          "corregimiento": "Playa Leona"
        }
      },
      "vehiculos": {
        "cafb1a61-101b-5fda-98b3-c9b5c0d0468f": {
          "capacidad_litros": 10000.0,
          "disponible": true
        },
        "f2c6a5ef-f9f3-5515-84c3-00fb0ba65210": {
          "capacidad_litros": 10000.0,
          "disponible": true
        }
      },
      "deposito": {
        "nombre": "Depósito ficticio del ensayo"
      }
    },
    "ejemplo": "Crítico de 12 000 L"
  }
]
