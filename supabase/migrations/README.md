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

Aplicar una vez `0003_aprobacion.sql`, completo, **después de 0009** (usa `escenarios_planificacion_v3` y su
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

`ra_rechazar_plan` deja el plan `rechazado` y la ejecución en `espera_revision`, con el motivo en el evento.

Verificación local: PostgreSQL 16 con 0001 a 0011 aplicadas; smoke aprobado (también se comprobó que falla si
se quita el control de vigencia de entradas) y smoke de 0011 aprobado con 0003 instalada. No usa Supabase ni
concurrencia real de varios procesos. Sin aplicar a Supabase. La etapa `comunicacion` no la procesa aún ningún
trabajador: el trabajador de Emilia solo toma ingesta, territorial, priorización y planificación.
