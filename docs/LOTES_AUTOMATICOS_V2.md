# Preparación automática de lotes confirmados

17 de octubre de 2026. Ampliación solicitada por Emilia: reutilizar datos y
confirmaciones vigentes; pedir intervención por faltantes, conflictos o cambios.
Requiere 0016 y la nueva migración 0017. No cambia contratos, herramientas,
API de revisión ni aprobación humana de planes.

La preparación ocurre antes de reservar priorización. Si ya existe un lote,
continúa por el cálculo existente. Si no existe, busca la revisión humana más
reciente del mismo ámbito completo, origen y ensayo. La política elegida es
`oeste-prioridad-apoyo-pa-1`, que debe seguir activa y coincidir con la revisada.
No elige arbitrariamente entre políticas activas ni usa datos del fixture.

0017 captura las nuevas revisiones aceptadas por `ra_preparar_priorizacion_v2`
en `revisiones_lote_v2`, enlazadas con el evento humano y una instantánea del
ámbito. Solo las revisiones humanas generan esa fuente; una preparación
automática no se convierte en una nueva autorización humana.

Antes de preparar exige:

- Ámbito completo e idéntico: incidentes y versiones, reportes y vínculos,
  procedencia, ensayo y catálogo de puntos. Un incidente por punto.
- Lugar validado y sin faltantes, conflictos ni revisión urgente pendiente.
- Política sin cambios; coordinadores de revisión y confirmaciones aún activos.
- Demanda, recepción, clase, vulnerabilidad, horas y población confirmadas,
  ventana de atención no vencida y confirmaciones con fechas válidas.
- Contratos válidos y `validate_need` sin faltantes ni recepción insuficiente.

Se conservan literalmente cantidades, fuentes, supuestos y confirmaciones
(incluidos autores y fechas). Solo cambian contexto de ejecución, fecha de
creación del cálculo y `datos_version` determinista. La base compara el lote
completo con esa transformación permitida. El cálculo posterior vuelve a
usar `validate_need` y `score_needs`; no se reutilizan resultados como aprobación.

Si no cumple, queda en `espera_revision`, con código
`lote_confirmaciones_pendientes` y motivo. Una revisión humana nueva vuelve a
poner pendientes las esperas de ese origen/ensayo para comprobarlas otra vez.
Errores de conexión o snapshot concurrente no se convierten en faltantes.
La reserva se adquiere después de preparar; la repetición no duplica eventos.

## Instalación y límite de revisiones previas

Aplicar `supabase/migrations/0017_lotes_confirmados_automaticos.sql`, ejecutar
`supabase/tests/0017_lotes_confirmados_smoke.sql` completo (termina en ROLLBACK)
y reiniciar el trabajador con este código. No se ejecutó SQL remoto desde Codex.

Los lotes que ya estaban preparados siguen funcionando sin otra preparación.
Las revisiones anteriores a 0017 no tienen la instantánea histórica necesaria
para reutilizarlas en otra ejecución: no se inventa su vigencia. La primera
revisión posterior a 0017 establece la fuente reutilizable.

El flujo territorial deja el marcador «Validación operativa del lugar y de la
necesidad». Revisar cantidades en Necesidades no elimina ese pendiente ni valida
el lugar. Noel debe conservar la revisión humana del lugar y su estado validado;
este preparador no lo cambia a validado automáticamente. Tampoco supone que una
nueva queja queda confirmada: un reporte nuevo o cambio de versión requiere revisión.

La aprobación final del plan, selección por sector y destino de ensayo autorizado
siguen vigentes. No se activa `AVISOS_ACTIVOS` ni se declara entrega física.

## Verificación reproducible

- Pruebas de Python: `agentes/tests/test_lotes_confirmados.py`.
- Smoke SQL: procedencias real/estimada/sintética, ausencia de fuente, cambios
  de versión/punto/reporte/ámbito/política, conflicto, urgencia, coordinador inactivo,
  ventana vencida, datos/confirmaciones/recepción faltantes, concurrencia,
  sustitución de demanda, repetición y permisos de servicio.
- Integración aislada de cinco agentes: ejecutar
  `supabase/tests/0016_integracion_local.mjs` con
  `RA_PROBAR_LOTE_AUTOMATICO=1`, `RA_PGLITE_PACKAGE` apuntando al paquete temporal
  con PGlite y `RA_PYTHON` al Python del proyecto. Usar `RA_EVIDENCIA` para guardar
  una evidencia distinta a la integración 0016. Proveedor, revisión del lugar,
  confirmaciones y aprobación humanos son fixtures explícitos; no envía Telegram.

Resultado local sobre ca54140: 894 pruebas y 66 subpruebas aprobadas; smokes
0016/0017 e integración de cinco agentes con 15 000 L y seis avisos de ensayo.
Evidencia: `agentes/evidencias/lote_automatico_v2_local.json`.
