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
