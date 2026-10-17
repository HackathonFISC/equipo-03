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

## Bandeja de salida (0009, Noel)

Aplicar una vez `0009_bandeja_salida.sql`, completo, después de 0001 (no depende de 0004 a 0008).
Después ejecutar `../tests/0009_bandeja_salida_smoke.sql`, completo: usa datos sintéticos, inserta un
usuario temporal en `auth.users` y termina en ROLLBACK. Exige un entorno sin avisos previos.

Añade tres columnas de reserva a `avisos` y cuatro funciones, ejecutables solo por service_role:
`ra_reservar_aviso`, `ra_registrar_envio_aviso`, `ra_revisar_avisos` y `ra_traza_aviso`.
La reserva cancela con motivo un aviso que dejó de ser vigente; una reserva vencida lo deja `incierto`
y nunca se reenvía solo. No crea avisos, no aprueba planes y no sustituye a 0002 ni a 0003.

Verificación local: PostgreSQL 16 con las migraciones 0001 a 0008 aplicadas antes; smoke completo
aprobado. Esa prueba no usa Supabase ni concurrencia real de varios procesos. Sin aplicar a Supabase.
