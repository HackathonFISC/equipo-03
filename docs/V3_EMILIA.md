# V3 de Emilia: Planificación integrada, ensayo separado

V3 añade Planificación al trabajador sin cambiar los módulos de cálculo de José ni API, bot o frontend de Noel. Recibe `SolicitudResolverRutas`, decide si calcular o solicitar revisión, ejecuta `solve_routes`, ejecuta siempre `verify_plan` independiente y conserva propuesta/informe/traza. Un informe adjunto al solver no se acepta como verificación. No se crea un sexto agente: verificación es una herramienta independiente del agente Planificación.

## Alcance y límites

Esta entrega integra **el fixture sintético separado que eligió Emilia**. No promociona automáticamente el incidente de Telegram a planificación ni sustituye sus 120 personas/48 horas por las 140/96 del escenario. La demanda/prioridad del fixture se genera con las funciones reales de José. El paso de necesidades ciudadanas a un escenario operativo revisado queda pendiente de definir con el equipo; no se fabrica una transición automática sin validación.

Los puntos conservan los UUID del catálogo. Cada ensayo tiene ejecución, plan, incidentes, depósito, flota, política y datos_version exclusivos. Sus incidentes no tienen vínculos a reportes, por lo que no entran en `ra_incidentes_snapshot_v2` ni contaminan la página de incidentes V2. Se guardan planes, rutas y paradas en las tablas compartidas existentes; Noel debe identificar siempre origen y escenario al mostrarlos. `planes.propuesta` conserva el contrato completo para lectura.

La copia de política se activa **solo como política sintética revisada del ensayo**. Confirmar sus supuestos no acredita agua potable, acceso, recepción ni operación física. Fechas, ventanas y primera detección pertenecen al fixture del 17/10/2026: para otro día se prepara una versión explícita revisada. No se desplazan fechas ni se geocodifica silenciosamente.

Gemini recibe un resumen estructurado, sin textos ciudadanos, credenciales ni permisos. Puede pedir revisión y explicar la decisión; no calcula, cambia restricciones, verifica ni aprueba. Fallo del proveedor/salida inválida deja revisión, sin un fallback silencioso a reglas. El modo local sin IA es explícito y se registra como `reglas`.

## Probar localmente (macOS)

Desde la raíz del repositorio:

```bash
source .venv/bin/activate
python -m scripts.ensayar_v3 local --salida /tmp/ensayo_v3_local.json
python -m scripts.ensayar_v3 local --con-ia --salida /tmp/ensayo_v3_gemini.json
python -m scripts.evaluar_planificacion_v3 --salida /tmp/evals_v3.json
```

Las salidas se crean sin sobrescribir. Para repetir, elegir otro nombre. Solo `--con-ia` llama al proveedor; ningún modo local escribe en Supabase. Las claves siguen en `.env` backend.

## Instalar en Supabase

1. Aplicar completo `supabase/migrations/0009_planificacion_v3.sql`, una vez, después de 0008.
2. Ejecutar completo `supabase/tests/0009_planificacion_v3_smoke.sql`. Usa un coordinador y entradas ficticias, prueba también con service_role y termina en ROLLBACK. Requiere el catálogo sembrado; conserva el snapshot V2 anterior.
3. Usar cuentas reales de Authentication → Users. Se permite más de un coordinador activo. Emilia ya tiene rol activo, verificado en esta sesión; Noel requiere su propio User UID. La plantilla `supabase/admin/registrar_coordinadores.sql` permite registrar ambos explícitamente; no es una migración y el arreglo vacío se rechaza.
4. Revisar parámetros, cantidades, criticidad, ventanas y política con la coordinadora. Generar un archivo con su UID y motivo explícito:

```bash
python -m scripts.ensayar_v3 preparar --coordinador-uid UUID_REVISADO --motivo "Revisión de supuestos del ensayo sintético, sin aprobación operativa" --salida /tmp/entrada_v3_revisada.json
python -m scripts.ensayar_v3 registrar --coordinador-uid UUID_REVISADO --motivo "Revisión de supuestos del ensayo sintético, sin aprobación operativa" --entrada /tmp/entrada_v3_revisada.json
python -m orquestador.trabajador --una-vuelta --planificacion-id EJECUCION_DEVUELTA
```

`preparar` solo guarda el archivo. `registrar` valida el contrato y escribe en Supabase. Conservar archivo y motivo exactos para reintentos; regenerar otro archivo crea **otro ensayo**, no es un reintento. El comando de registro es una herramienta administrativa backend: Noel deberá derivar la identidad autenticada si lo expone mediante API; nunca aceptar un UID libre del navegador.

El trabajador usa Gemini por defecto en Planificación. Usar `--planificacion-id` con el ID devuelto por el registro para procesar solo ese ensayo, incluido su mantenimiento de reserva; no toca la cola histórica. Sin ese filtro procesa también V2. No levantar un segundo bot.

## Persistencia y concurrencia

| RPC | Firma y resultado |
| --- | --- |
| `ra_preparar_ensayo_v3` | `(p_usuario_id uuid, p_solicitud jsonb, p_motivo text)` → ejecución/estado/etapa/repetido. Exige coordinador activo y revisiones con su identidad. |
| `ra_tomar_planificacion_v3` | `(p_ejecucion_id uuid, p_trabajador_id text)` → snapshot de solicitud e inventario, o null si no está pendiente. Reserva exclusiva de 300 segundos. |
| `ra_finalizar_planificacion_v3` | `(p_ejecucion_id uuid, p_trabajador_id text, p_snapshot jsonb, p_resultado jsonb)` → estado/etapa/plan/version/repetido. Persiste cierre, plan, rutas, paradas y eventos atómicamente. |
| `ra_mantenimiento_planificacion_v3` | `(p_ejecucion_id uuid)` → cantidad revisada (0/1); solo la reserva de ese ensayo. |
| `ra_snapshot_planificacion_v3` | `(p_ejecucion_id uuid)` → snapshot backend para comprobar solicitud, depósito, flota, incidentes, catálogo y política. |

Solo service_role puede llamar estas RPC; anon/authenticated no pueden. La autorización de coordinador se comprueba además dentro del registro, toma y cierre. No se relajan RLS existentes. Dos coordinadores pueden registrar ensayos; no se exige doble firma. El mismo escenario no puede sustituirse mientras calcula ni después del cierre.

El cierre rechaza reservas vencidas/ajenas y snapshots modificados. Repetir el cierre idéntico devuelve el acuse anterior sin escribir. Un cierre diferente se rechaza. La reserva vencida pasa a espera_revision con mantenimiento; no se recalcula automáticamente. Límite de solver admitido por el registro: 1–60 segundos, con margen para las llamadas a IA.

Se conserva `pendiente_revision` en el plan. La ejecución queda `espera_validacion` solo con solución factible, informe válido y decisión de presentar; los demás casos quedan `espera_revision`. La publicación tiene siempre el bloqueo explícito de ensayo. No se crean aprobaciones ni avisos. Si no se pudo producir propuesta, se guarda traza y revisión sin inventar un plan.

## Validación de esta entrega

- 15 evals locales con expectativas, resultados, tiempos y tasa de éxito en `evals/resultados/planificacion_agente_v3.json`; fallos de proveedor/LLM/herramienta están identificados como simulaciones.
- Pruebas del agente y regresión Python del equipo.
- Seis smoke SQL en PostgreSQL temporal, incluyendo aislamiento, rol, reserva, snapshot, persistencia normalizada e idempotencia.
- Prueba Gemini real: `agentes/evidencias/planificacion_v3_gemini.json`. Se conservó el diagnóstico inicial de falso pendiente, corregido aclarando el resumen; no se oculta como éxito.
- Resultado del agente con Gemini persistido además en PostgreSQL temporal, con un incidente V2 anterior intacto: `agentes/evidencias/planificacion_v3_postgres.json`.

Codex no aplicó 0009 ni cargó el ensayo en Supabase real. El alta de Emilia sí se realizó y comprobó por su solicitud. Integración visual de V3 y API de planes corresponden a Noel; aprobación/vigencia y mensajería de planes quedan para V4. No se acredita concurrencia entre servidores reales ni mediciones viales/sanitarias.
