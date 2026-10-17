# datos/escenario

**Dueño:** José

vehiculos.json, demandas.json, politica_v1.json

## Escenario sintético V0

Los archivos reutilizan los identificadores y valores del ejemplo de Emilia en `contratos/ejemplos/solicitud_resolver_rutas.json`. No representan flota, lugares ni demandas operativas verificadas.

- `vehiculos.json`: contexto y versión, depósito sintético, dos vehículos de 10 000 litros cada uno, disponibles en el ensayo del 17 de octubre de 08:00 a 12:00 (UTC−05:00), sin recargas ni entregas parciales.
- `demandas.json`: contexto, seis puntos sintéticos, necesidades estimadas de 2 500, 3 000, 3 500, 2 500, 3 000 y 3 500 litros (18 000 en total), seis solicitudes de validación y descargas propuestas de diez minutos. Las ventanas se conservan en cada necesidad. La capacidad de recepción permanece desconocida (`null`).
- `politica_v1.json`: objeto `PoliticaPrioridad` completo, sin envoltorio: propuesta `demo-1.0`, duración 50 %, vulnerabilidad 30 %, población 20 %, escalas de 168 horas y 500 personas. No está activada.

Los envoltorios de vehículos y demandas organizan archivos locales; no son nuevos contratos de intercambio. Validar sus objetos internos con `Deposito`, `Vehiculo`, `PuntoAtencion`, `EvaluacionNecesidades`, `SolicitudValidarNecesidad` y `TiempoServicio`. Validar la política directamente con `PoliticaPrioridad`.

Se eliminaron las confirmaciones ficticias del ejemplo en las necesidades y solicitudes. Las necesidades conservan estimaciones, pero están pendientes, sin clase confirmada, puntaje ni ranking. El posible caso crítico conserva una alerta de revisión urgente. Confirmar demanda, recepción, criticidad y vulnerabilidad antes de priorizar; activar la política por el servicio autorizado. La política propuesta no habilita un ranking operativo.

La matriz de tiempos sigue en el ejemplo de contratos; su preparación corresponde a `calculo/matriz.py` en V1/V3. Estos tres archivos no constituyen por sí solos una solicitud completa de rutas ni prueban factibilidad. Los horarios son del escenario de reparto sintético, no del cronograma de desarrollo.

## Preparación territorial para V3

`oeste-1.0-ensayo-1/` contiene una versión aparte con los seis UUID del catálogo de Emilia, dos cisternas ficticias, depósito ficticio y matriz manual sintética de siete nodos. Conserva referencias geográficas documentales y distingue los parámetros inventados del ensayo. Sus demandas permanecen pendientes, recepción desconocida y política sin activar. Consultar su README y ejecutar `python scripts/verificar_escenario_v3.py`. Los tres JSON originales de V0 permanecen intactos.

`politica_apoyo_panama_v1.json` define la nueva propuesta de prioridad del proyecto: 40 % duración, 40 % vulnerabilidad y 20 % población, con críticos confirmados primero. Su fundamento y límites están en `docs/politica_prioridad_oeste.md`; los porcentajes no son oficiales del Estado. Se incorpora en `oeste-1.0-ensayo-2/` sin activar política ni confirmar demandas. Comprobar con `python scripts/verificar_escenario_v3.py --carpeta datos/escenario/oeste-1.0-ensayo-2`.

`oeste-1.0-ensayo-3/` añade perfiles domésticos ficticios, demanda por fórmula y recepción calculada a partir de tanques/agua almacenada/margen. Su copia de política y confirmaciones son ficticias para probar validate_need y score_needs: no son activación operativa. Ejecutar `python -m calculo.demo_escenario_v3`; su README documenta hipótesis, fuentes y límites. Los ensayos 1/2 y la política compartida se conservan sin activar.

Estado de implementación: [solver/verificador V3](../../calculo/PLAN_V3.md),
[Planificación integrada localmente](../../docs/V3_EMILIA.md) y
[casos aislados para cerrar priorización V2](../../docs/ENSAYO_PRIORIZACION_V2.md).
Los README de cada ensayo describen sus propios archivos y no prueban despliegue.
