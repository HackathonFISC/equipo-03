# Esquema inicial de RutaAgua Oeste

Dueña de `0001`: Emilia. Compatible con los contratos 1.0 del equipo. Proyecto declarado vacío por el usuario. Esta entrega prepara el esquema; no lo aplica a Supabase ni crea usuarios, puntos, flota o políticas activas.

## Qué haces ahora

1. Revisa `supabase/migrations/0001_esquema.sql` con Noel y José. No necesitas compartir claves para revisar SQL.
2. Abre **el proyecto correcto** en Supabase y entra a **SQL Editor → New query**.
3. Copia el contenido completo de `0001_esquema.sql` y pulsa **Run**, con el rol `postgres` del editor. La migración usa una transacción: un error impide completar la instalación.
4. Cuando termine, abre otra consulta y ejecuta `supabase/tests/0001_esquema_smoke.sql`. Termina en `ROLLBACK`: los datos de prueba se eliminan, no las tablas.
5. Comprueba las 23 tablas en Table Editor. Si la prueba termina sin excepción, registra la aplicación real y el resultado en tu bitácora. Si falla, conserva el mensaje y no intentes borrar tablas para repetirla.
6. Después prepara con Noel `comun/config.py` y `comun/db.py` y verifica guardar un reporte desde la API. La conexión del backend requiere una credencial de servidor que solo vive en su entorno; la URL y una clave pública no conceden acceso a estas tablas cerradas.

Es una migración **de una sola aplicación**, no un script idempotente. No incluye `DROP`, `TRUNCATE` ni sustituciones de tablas existentes. Una segunda ejecución falla deliberadamente; no significa que haya que eliminar lo instalado. Los cambios posteriores necesitan otra migración acordada, no modificar silenciosamente una versión ya aplicada.

Estos nombres `0001`, `0002` y `0003` siguen el acuerdo actual del equipo. Si después usan Supabase CLI y su historial automático, acuerden antes los nombres y el registro de la migración; no mezclar aplicación manual y automática sin reconciliar el historial.

## Tablas y relaciones

| Área | Tablas | Relación principal |
| --- | --- | --- |
| Personas operativas | `usuarios_operativos` | Usuario de Supabase Auth y rol operativo; comienza inactivo |
| Territorio | `sectores`, `puntos_atencion` | Un sector contiene puntos; alias, coordenadas y validación por punto |
| Recursos | `depositos`, `vehiculos` | Cada vehículo referencia un depósito, capacidad y turno |
| Política | `politicas_prioridad` | Parámetros explícitos identificados por versión; sin política activa precargada |
| Canal privado | `remitentes`, `destinos`, `suscripciones_sector` | Identidad externa privada, destinos y autorización para recibir avisos por sector |
| Entradas | `reportes`, `adjuntos` | Reporte original y referencias privadas a Storage |
| Proceso | `ejecuciones`, `aclaraciones`, `eventos` | Cola persistida, preguntas reanudables y trazas |
| Necesidad | `incidentes`, `vinculos_reportes`, `necesidades` | Vínculos reversibles y evaluaciones por versión de entradas y política |
| Distribución | `planes`, `rutas`, `paradas` | Plan lógico con versiones; una ruta por vehículo y una parada por punto en cada versión |
| Autorización y operación | `aprobaciones`, `avisos`, `confirmaciones_entrega` | Aprobación de una versión, bandeja de salida y entrega física separadas |

Las tablas auxiliares evitan guardar depósitos, destinatarios, política, roles y rutas como textos sin relación. No añaden agentes ni amplían el alcance geográfico.

## Qué se valida en la base

- IDs UUID, referencias válidas, unidades explícitas y fechas `timestamptz`.
- Cantidades finitas no negativas; capacidad y litros asignados positivos. Un desconocido admite `NULL`, sin convertirlo automáticamente en cero.
- Coordenadas completas por pareja y rangos válidos; un punto validado tiene ubicación confirmada.
- Un mensaje externo por canal y remitente; un vínculo activo por reporte. Una corrección cierra el vínculo viejo y crea otro; no borra el historial.
- Clases y estados con los mismos valores serializados que los contratos.
- Necesidad pendiente sin puntaje ni posición y con motivo; necesidad calculada con factores, confirmaciones y desglose.
- Los pesos suman uno y una política activa tiene datos de activación. Esto no autentica por sí solo al coordinador que figure en ese JSON.
- Clave de plan `(plan_id, version)`. Una nueva versión conserva el `plan_id` e incrementa `version`; no deja que el valor por defecto cree otro plan por accidente.
- Sin repetir vehículo o punto dentro de una versión; ventanas y secuencias temporales básicas válidas.
- Un plan aprobado necesita estado factible, verificación válida, aprobación referenciada y ningún bloqueo declarado. Un crítico marcado como no atendido exige bloqueo.
- Una aprobación corresponde a la misma versión de plan, entradas y política. La FK circular diferida permite que Noel registre aprobación y estado del plan en una sola transacción.
- Avisos con referencia a aprobación, punto/sector y suscripción existente; unicidad por plan, versión, sector, punto, destino y tipo. `enviado` necesita fecha e ID del proveedor; `incierto` o `fallido` necesita motivo.
- Eventos, aprobaciones y confirmaciones físicas solo admiten inserciones: corregir mediante nueva versión o evento adicional. Las demás modificaciones deben conservar autor, hora, motivo y evento desde el backend.

## Qué siguen implementando Noel y José

**Noel en 0002:** privilegios por operación y RLS por rol. Las 23 tablas de 0001 empiezan con RLS activado, sin acceso directo para `anon` o `authenticated`; no se depende de que Noel alcance V5 para cerrar tablas. La cuenta de servicio del backend tiene permisos y omite RLS, así que la API siempre debe verificar a la persona y su rol. Una sesión autenticada o un UUID no bastan para aprobar.

**Noel en 0003 y servicios:** bloquear/comparar versiones de entradas, comprobar rol activo de coordinador y verificador real, registrar aprobación atómica e invalidar por cambios relevantes. Antes de publicar, comprobar que plan y suscripción siguen vigentes y el destino autorizado, y que litros/ventana coinciden con la parada aprobada. La existencia de una FK no verifica esas condiciones dinámicas.

**José:** capacidad acumulada, disponibilidad, matriz y accesos, duración del servicio, retorno, cobertura completa, criticidad y coherencia entre datos y resultados. Los checks de SQL no sustituyen a `verify_plan`. La tabla `rutas` no prueba que OR-Tools haya calculado una ruta.

**Emilia y Noel:** reclamación atómica de trabajos de `ejecuciones` para evitar dos trabajadores sobre la misma ejecución, control de reintentos e idempotencia. `bloqueada_hasta` y `trabajador_id` permiten implementar una reserva; las columnas solas no ejecutan ese mecanismo.

La pérdida de una cisterna y la edición de política/demanda no invalidan automáticamente planes en 0001. Los servicios posteriores deben implementar ese cambio y una nueva verificación. El esquema todavía no es un flujo operativo completo ni una autorización de publicación.

## Cómo guardar y reconstruir los contratos

No enviar `model_dump()` completo directamente a una tabla: los contratos son objetos de intercambio y las tablas tienen relaciones. Usar un adaptador de persistencia.

| Contrato | Persistencia |
| --- | --- |
| `ReporteRegistrado` | Entrada original en `reportes`; `ejecucion_id` en `ejecuciones`, referencia al reporte |
| `ReporteInterpretado` | `interpretacion` contiene solo `ExtraccionReporteLLM`; `evidencias` guarda su lista; la ejecución aporta el ID de contexto |
| `IncidenteConsolidado` | Columnas de `incidentes`; `reportes_ids` se reconstruye con vínculos activos; `periodo_incidente` se separa en inicio y fin |
| `EvaluacionNecesidades` | Una fila por ejecución, versión de datos, política y punto; `necesidad_id` es interno y no pertenece al contrato; fechas de ventana van en columnas |
| `PropuestaDistribucion` | `planes` + `rutas` + `paradas`; `verificacion` y `no_atendidos` son JSON estructurado; `solicitud_snapshot` conserva la solicitud íntegra del solver, incluidos flota, puntos, matriz, demandas y servicios |
| `AvisoComunidad` | `avisos`; `ventana_estimada` se separa en inicio/fin; su clave de idempotencia corresponde a la restricción única compuesta |
| `SolicitudAclaracion` y respuesta | Una fila de `aclaraciones` con pregunta, estado de envío y respuesta; no exige plan ni aprobación de ruta |
| `EventoTraza` | `eventos`, con `actor_tipo=agente`; eventos humanos/sistema pueden dejar agente nulo |
| `ConfirmacionEntrega` | `confirmaciones_entrega`; no cambia `litros_asignados` ni el aviso anterior |

Validar JSON con Pydantic antes de escribir o servir una respuesta. Los JSON de contratos contienen usuarios/fechas y aprobaciones ficticias; no son semillas listas para insertar en Supabase Auth. Los seis puntos, flota y política del escenario se cargan después en los archivos de semillas de Emilia y José.

`adjuntos` guarda bucket/ruta privada, nunca una URL pública permanente ni una clave. Puede recibir un adjunto de ciudadano antes de vincularlo a su reporte. Para audio de salida generado por el sistema usar `procedencia=sistema`; no inventar un remitente ciudadano. Noel crea el bucket privado y sus políticas; 0001 no modifica `storage.objects`.

`ultima_atencion_confirmada_en`, pesos, litros y estados desconocidos no se deducen por ausencia de fila. Los timestamps se envían con zona y se muestran en `America/Panama`; `timestamptz` representa el instante, no conserva la zona de texto original.

## Verificación y límites

La prueba SQL usa datos sintéticos, no toca `auth.users` y revierte todas sus inserciones. Comprueba tablas, cierre inicial de permisos, reporte y ejecución, deduplicación, vínculos reversibles, rangos y cantidades, necesidad pendiente, plan sin aprobación, bloqueo crítico, unicidad de parada y eventos históricos.

Se comprobó además la migración en un PostgreSQL temporal en memoria mediante PGlite y los enums frente a `contratos/estados.py`. El resultado local no prueba Supabase Auth/Storage ni sustituye la aplicación y prueba en el proyecto real. La bitácora distingue esos resultados.

## Referencias técnicas

- Supabase, tablas: https://supabase.com/docs/guides/database/tables
- Supabase, privilegios y RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- PostgreSQL, constraints y claves compuestas: https://www.postgresql.org/docs/current/ddl-constraints.html
- PGlite, PostgreSQL temporal para validación local: https://pglite.dev/docs/

Consulta: 16 de octubre de 2026. Las credenciales y el proyecto real nunca se usan en la prueba local.

## Revisión de identidad y deduplicación

Ver [identidad y reportes](IDENTIDAD_REPORTES.md) para la integración del bot
de Noel. `remitente_ref` es un UUID interno; Telegram se resuelve a través de
`remitentes(canal, identificador_externo)`. El adaptador construye una identidad
de mensaje estable por chat e ID de mensaje; no usa solo message_id.

La migración adicional `0004_identidad_reportes.sql` requiere 0001 y conserva
0002/0003 para Noel. Añade correspondencia obligatoria entre canal del reporte
y del remitente y unicidad de mensaje Telegram independiente del remitente.
La regla previa de panel permanece. Si hay datos incompatibles, aborta sin
corregirlos ni eliminarlos. Emilia confirmó en esta conversación la ejecución correcta de la migración y su smoke en Supabase; no se volvió a ejecutar desde Codex.

Probada en PostgreSQL temporal PGlite: dos guardas de datos previos, smoke 0004,
regresión smoke 0001, restricciones con service_role, permisos de navegador
cerrados y ROLLBACK de datos sintéticos. No prueba el bot ni concurrencia real
de procesos de la API. Ejecutar `tests/0004_identidad_reportes_smoke.sql` después
de aplicar 0004, con rol administrativo; revierte sus inserciones.
