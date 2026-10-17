# supabase/migrations

**Dueño:** Emilia (0001) y Noel (0002, 0003)

0001_esquema.sql, 0002_politicas_rls.sql, 0003_aprobacion.sql

Emilia mantiene también `0004_identidad_reportes.sql`: referencia de remitente
con canal y deduplicación Telegram independiente del remitente. Requiere 0001;
0002 y 0003 continúan reservadas a Noel y no son dependencias de 0004.
Coordinar el orden/registro con Noel antes de usar un ejecutor de migraciones.
Ver `../IDENTIDAD_REPORTES.md` y `../tests/0004_identidad_reportes_smoke.sql`.
0004 probada localmente; Emilia confirmó su aplicación y smoke correctos en Supabase desde el SQL Editor. No volver a aplicar si ya está instalada.

Emilia mantiene `0005_ingesta_transaccional.sql` para V1. Crea las RPC
`ra_tomar_ingesta` y `ra_finalizar_ingesta`; solo service_role puede ejecutarlas.
Requiere 0001; no sustituye 0002/0003 de Noel. El cierre guarda interpretación,
evidencias, traza y transición atómicamente y comprueba reserva/snapshot.
Probar con `../tests/0005_ingesta_smoke.sql`. Probada en PostgreSQL temporal;
no aplicada a Supabase real por Codex. Ver `../../agentes/INGESTA_V1.md`.

## V2 de Emilia

Aplicar una vez 0006_aclaraciones_v2.sql y después 0007_territorial_orquestador_v2.sql; requieren 0001/0004/0005. Ejecutar sus smoke completos. No habilitar destino_origen_id en la API hasta aplicar 0006. [Guía](../../docs/V2_EMILIA.md).

## Idempotencia de lotes V2 (0008)

Aplicar una vez `0008_idempotencia_lotes.sql`, completo, después de 0007.
Después ejecutar `../tests/0008_idempotencia_lotes_smoke.sql`, completo: usa datos
sintéticos y termina en ROLLBACK. Requiere el catálogo sembrado y un entorno de
prueba sin otros incidentes activos, igual que el smoke de priorización 0007.

`ra_preparar_priorizacion_v2` conserva su firma y permisos. Repetir el mismo lote
para la misma ejecución devuelve `repetido: true` con su estado/etapa actuales y
`ejecucion_id`, desde la primera aceptación. No añade eventos, guarda necesidades,
borra errores, modifica la entrada original ni reinicia la ejecución o su reserva.
Las comprobaciones de coordinador, política, incidentes activos y versiones se
mantienen: una entrada que ya quedó obsoleta sigue rechazándose.

La comparación ignora el orden de entradas y únicamente las fechas regeneradas
`solicitud_demanda.creado_en`, `evaluacion.creado_en` y `confirmado_en` de las
confirmaciones de demanda, clase y vulnerabilidad en esas entradas. Conserva los
actores, motivos, cantidades y demás campos; la auditoría original no se sobrescribe.
La política completa se compara sin quitar fechas.

Cambiar datos exige una nueva `datos_version`; recalcular el mismo contenido
requiere también una nueva versión explícita. No se puede sustituir un lote
mientras está en ejecución. El nuevo auxiliar `ra_lote_comparable_v2` solo puede
ser ejecutado por service_role. No se modifican contratos, API/bot, el cierre
`ra_finalizar_priorizacion_v2` ni la coordinación entre agentes. No elimina
posibles eventos duplicados históricos.

Verificación local: cinco smoke SQL en PostgreSQL temporal, incluyendo prueba
que falla con 0007 y pasa con 0008, permisos de backend y rechazo de anon y
authenticated. Codex no ha aplicado esta migración a Supabase real.

## Planificación V3 de Emilia (0009)

Aplicar una vez `0009_planificacion_v3.sql` después de 0008 y ejecutar completo
`../tests/0009_planificacion_v3_smoke.sql` (termina en ROLLBACK). Crea registro de
ensayos aislados, cinco RPC backend y `planes.propuesta`; amplía mantenimiento a
reservas de Planificación. No crea cuentas ni aprueba/publica planes. Permite
varios coordinadores activos; el alta es administrativa y separada de la migración.
Guía, firmas, comandos y límites en [V3_EMILIA](../../docs/V3_EMILIA.md).
Probada en PostgreSQL temporal; 0009 no aplicada a Supabase real por Codex.

## Ensayos aislados para cerrar V2 (0010)

`0010_ensayos_priorizacion_v2.sql` requiere 0008 y catálogo, no 0009. Conserva las
firmas V2 y aísla los casos calculable/insuficiente sin cambiar Telegram. Ejecutar
su smoke completo con ROLLBACK. No aplicada por Codex a Supabase real. Guía y
consulta para Noel: [ENSAYO_PRIORIZACION_V2](../../docs/ENSAYO_PRIORIZACION_V2.md).

## Bandeja de salida (0011, Noel)

Aplicar una vez `0011_bandeja_salida.sql`, completo, después de 0001 (no depende de 0004 a 0010).
Después ejecutar `../tests/0011_bandeja_salida_smoke.sql`, completo: usa datos sintéticos, inserta un
usuario temporal en `auth.users` y termina en ROLLBACK. Exige un entorno sin avisos previos.

Añade tres columnas de reserva a `avisos` y cuatro funciones, ejecutables solo por service_role:
`ra_reservar_aviso`, `ra_registrar_envio_aviso`, `ra_revisar_avisos` y `ra_traza_aviso`.
La reserva cancela con motivo un aviso que dejó de ser vigente; una reserva vencida lo deja `incierto`
y nunca se reenvía solo. No crea avisos, no aprueba planes y no sustituye a 0002 ni a 0003.

Verificación local: PostgreSQL 16 con las migraciones 0001 a 0010 aplicadas antes; smoke completo
aprobado. Esa prueba no usa Supabase ni concurrencia real de varios procesos. Sin aplicar a Supabase.

## Aprobación de planes (0003, Noel)

Aplicar una vez `0003_aprobacion.sql`, completo, **después de 0009 y 0011 y antes de 0012** (usa `escenarios_planificacion_v3` y su
snapshot); el número 0003 estaba reservado a Noel desde 0001, no indica el orden. Después ejecutar
`../tests/0003_aprobacion_smoke.sql`, completo: usa datos sintéticos, inserta usuarios temporales en
`auth.users` y termina en ROLLBACK.

Añade dos funciones, ejecutables solo por service_role: `ra_aprobar_plan` y `ra_rechazar_plan`. La API debe
pasar el usuario tomado del token verificado, nunca uno enviado por el navegador. Los errores empiezan por el
código de D003 (`sin_permiso`, `version_obsoleta`, `politica_no_activa`, `plan_no_verificado`,
`cobertura_critica_pendiente`).

`ra_aprobar_plan`, en una sola transacción: exige coordinador activo; que los datos y la política que la
persona revisó sean los del plan y no exista una versión posterior; política activa; que las entradas
(depósito, flota, incidentes, puntos, política) sean las del cálculo (compara `ra_snapshot_planificacion_v3`
con el snapshot guardado al cerrar); verificación independiente válida, solver factible y ejecución esperando
validación; y ningún crítico sin atender. Después crea la aprobación, deja el plan `aprobado`, pasa la
ejecución a `pendiente` en la etapa `comunicacion` y registra un evento. Repetir la misma aprobación devuelve
el acuse sin duplicar; otra distinta se rechaza.

**Decisión sobre los bloqueos (revisar con el equipo):** 0001 exige cero bloqueos en un plan aprobado. Una
aprobación solo puede levantar tres: "Sin verificación independiente ni aprobación autorizada…", "Política
sintética: el cálculo no acredita autorización operativa ni calidad del agua." y "ENSAYO SINTÉTICO: sin
aprobación operativa ni publicación comunitaria.". La persona debe **reconocer cada uno** en la llamada; si
falta alguno se rechaza. Cualquier otro (cobertura crítica, solver sin solución, verificación inválida) no se
levanta con una confirmación. Los bloqueos reconocidos quedan en el evento y en `planes.propuesta`. La
publicación sigue limitada por destinos autorizados (`destinos.autorizado`), que la bandeja (0011) comprueba.

**Concurrencia (caso 21).** La primera operación de `ra_aprobar_plan` es serializar con quien cambie entradas:
si 0012 está instalada usa su bloqueo común `ra_bloqueo_v4()` (todo escritor de entradas lo toma antes de
modificar filas); si no, bloquea (SHARE) las tablas de entradas, igual que `ra_finalizar_planificacion_v3`. No se
combinan los dos: tomar el bloqueo común y luego las tablas podría esperar en círculo con un escritor que ya
tiene la tabla. `ra_rechazar_plan` toma el bloqueo común si existe. Repetir una aprobación solo devuelve el
acuse si el plan sigue vigente (entradas iguales y, con 0012, `ra_plan_valido_v4`); un plan `invalidado` o con
entradas distintas responde `version_obsoleta`, no `plan_ya_resuelto`.

La **invalidación posterior** (pasar a `invalidado` un plan aprobado cuando luego cambia una entrada o su
asignación y cancelar sus avisos pendientes) es de 0012; 0003 no la duplica. Sin 0012 la aprobación sigue
comprobando las entradas en el momento de aprobar, pero un plan ya aprobado no se invalida solo.

`ra_rechazar_plan` deja el plan `rechazado` y la ejecución en `espera_revision`, con el motivo en el evento.

Verificación local: PostgreSQL 16, dos pilas: 0001 a 0011 y 0003 (sin 0012) y esa misma más 0012. El smoke de
0003 pasa en las dos (la invalidación posterior solo se comprueba con 0012); el de 0011 aplica sin 0012 (con 0012
la reserva es más estricta y lo cubre el smoke de 0012, que también pasa). `../tests/0003_concurrencia.sh
<base_desechable>` lanza sesiones reales de psql y comprueba: un cambio de entradas sin confirmar hace esperar a
la aprobación y la deja `version_obsoleta`; un cambio durante la aprobación espera (y con 0012 deja el plan
`invalidado`); dos aprobaciones iguales guardan una sola; aprobar y rechazar a la vez deja una sola decisión. Pasó
tres veces seguidas en cada pila. No usa Supabase; sin aplicar a Supabase.

## Comunicación y vigencia V4 (0012, Emilia)

Aplicar `0012_comunicacion_v4.sql` después de 0009, 0010, 0011 y **0003 de Noel**.
Ejecutar `../tests/0012_comunicacion_v4_smoke.sql` completo; termina en ROLLBACK.
Crea avisos por punto/destino, selección única de plan por sector y consulta del
contrato EstadoSector. Extiende reserva de avisos sin cambiar firma/forma; no
modifica 0003 ni API/bot/frontend. Los sintéticos solo salen a destinos de ensayo
expresamente habilitados; no habilita ninguno al aplicar la migración.

La aprobación concurrente requiere el ajuste de Noel documentado en
[V4_EMILIA](../../docs/V4_EMILIA.md). No aplicada a Supabase real por Codex.

## Feedback de aclaraciones de ubicación (0013, Emilia)

Aplicar `0013_feedback_aclaraciones.sql` una vez tras 0006. Puede aplicarse
sin 0012: no depende de V4. Conserva la firma de `ra_crear_aclaracion`, reconoce
respuestas previas y detiene repreguntas de ubicación tras dos respuestas sin
resolución. No modifica ni reenvía preguntas existentes. Probar el smoke
`../tests/0013_feedback_aclaraciones_smoke.sql` completo, con Territorial y
catálogo instalados; termina en ROLLBACK. Sin cambios en API/bot de Noel.
No aplicada a Supabase real por Codex. Ver [V2](../../docs/V2_EMILIA.md).

## 0014 Recuperación del trabajador y Comunicación

Nueva migración posterior a 0012; no modifica archivos históricos. Añade
Comunicación al vencimiento conservador de reservas de `ra_mantenimiento_v2` y
`ra_marcar_error_trabajador(uuid,text)` para revisión condicionada al propietario.
No cambia aprobación, bandeja, destinos ni política. RPC SECURITY INVOKER con
permisos exclusivos de service_role y recarga de esquema PostgREST.

Ejecutar `0014_recuperacion_trabajador.sql` una sola vez en cada entorno, después
`supabase/tests/0014_recuperacion_trabajador_smoke.sql` completo en entorno aislado.
El smoke usa mantenimiento global dentro de una transacción y termina ROLLBACK;
prueba caducidad, reserva vigente, propietario distinto, cierre confirmado,
idempotencia y permisos. Preparado pero aún no ejecutado en esta revisión.

## 0015 Ingesta recuperable A4

Aplicar completo una vez **después de 0014**, antes de arrancar el código A4.
Añade `reintentos_ingesta` (0–2), `proximo_intento_ingesta` e índice de esperas.
Sustituye las implementaciones vigentes de toma/cierre y mantenimiento, conservando
las firmas, snapshots, aclaraciones, caducidad de Comunicación y permisos exclusivos
de service_role. Los archivos históricos no se modifican; NOTIFY recarga PostgREST.

Un error recuperable confirmado programa espera de cinco/diez segundos y libera
reserva. Mantenimiento reanuda al vencer, sin reactivar resultados inciertos o
fallos históricos. El presupuesto agotado o error de configuración queda en revisión.
El cierre idéntico repetido no aumenta el contador ni duplica eventos.

Ejecutar `../tests/0015_ingesta_recuperable_smoke.sql` completo en entorno aislado:
usa mantenimiento global, datos sintéticos y ROLLBACK. Probado en PostgreSQL temporal
PGlite, junto a regresiones 0006/0013/0014; pendiente de aplicación y roles reales en
Supabase. El smoke 0005 es histórico y espera el comportamiento anterior de error
recuperable terminal; para el comportamiento nuevo usar 0015. Guía: `../../docs/INGESTA_A4.md`.
