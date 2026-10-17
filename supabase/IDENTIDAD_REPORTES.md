# Identidad de remitentes y deduplicación de reportes

Emilia revisa el esquema; Noel implementa el adaptador del bot y el servicio
de persistencia. Esta entrega prepara la migración 0004 y una prueba de SQL;
no modifica el bot. Emilia confirmó que ejecutó correctamente la migración y su prueba en el SQL Editor de Supabase. Esa confirmación no es una verificación remota de Codex; esta integración al repositorio no vuelve a aplicar SQL.

## Qué permite 0001

- `remitentes.remitente_ref` es un UUID interno, generado al dar de alta la fila.
- `UNIQUE(canal, identificador_externo)` evita dos UUID para la misma identidad
  externa en un canal. El mismo valor en otro canal representa otra identidad.
- `reportes.remitente_ref` referencia ese UUID, no el ID numérico de Telegram.
- `UNIQUE(canal, remitente_ref, mensaje_externo_id)` deduplica reintentos del
  mismo mensaje y remitente.

Había dos huecos: la FK no vinculaba el canal y la unicidad de reportes permitía
repetir un mensaje Telegram si se usaba otro remitente. 0004 añade la FK compuesta
`(remitente_ref, canal)` y unicidad parcial de `(canal, mensaje_externo_id)` para
Telegram. Conserva la regla de panel y la migración 0001 sin cambios.

## Convención de integración para Noel

Diseño técnico para revisión con Noel y José, con un único bot del proyecto:

1. Obtener identidad y mensaje del objeto recibido de Telegram. Para mensajes
   de una persona, usar `str(message.from_user.id)` como `identificador_externo`
   de `remitentes`, con `canal='telegram'`. No usar nombre visible, username,
   chat ID, identidad del autor original de un reenvío ni valores inventados
   por el LLM. Si hay `sender_chat` o no hay usuario real identificable, rechazar
   o escalar ese tipo de entrada hasta acordar su soporte; no confundirlo con
   una persona. El chat de un grupo no identifica a su remitente.
2. Buscar o crear la fila con control de conflicto sobre
   `(canal, identificador_externo)`. Si otro proceso la creó primero, consultar
   la fila existente y conservar su UUID. No generar un UUID nuevo en cada
   reintento ni sobrescribir la identidad del remitente existente.
3. Construir `mensaje_externo_id = f"{message.chat.id}:{message.message_id}"`.
   Convertir desde enteros a decimal canónico, conservando el signo de chat ID,
   sin espacios ni ceros añadidos. Rechazar `message_id=0` o IDs ausentes.
   No usar solo `message_id`, texto, hora de recepción ni `update_id` como clave
   del reporte. [Telegram documenta que message_id es único dentro del chat](https://core.telegram.org/bots/api#message).
4. Guardar el reporte usando el UUID interno obtenido. En reintento, recuperar
   el mismo `reporte_id` y no generar otro reporte o trabajo de ingesta.
   Si la clave ya existe con otro remitente, tratarlo como inconsistencia:
   no reasignar el reporte ni devolver datos de otra persona al solicitante.
5. La consulta previa no basta ante dos procesos: usar la unicidad de BD y una
   transacción para crear reporte y ejecución. La restricción parcial Telegram
   no reemplaza automáticamente el `on_conflict` de PostgREST: Noel debe manejar
   el conflicto concreto y recuperar la fila de forma autorizada o usar una
   función transaccional del servidor. No convertir cualquier error de BD en
   «duplicado» ni reintentar a ciegas.
6. Usar una clave estable de ejecución inicial, por ejemplo
   `ingesta:<reporte_id>`, en `ejecuciones.clave_idempotencia`. Es una propuesta
   del servicio, no algo que esta migración implemente. Un duplicado no debe
   modificar antigüedad del incidente ni provocar otra priorización.

Una edición del mismo mensaje conserva la identidad del mensaje: no se crea
otro reporte para eludir la deduplicación. Cómo actualizar el contenido requiere
una política explícita del servicio de Noel. Un reenvío publicado como mensaje
nuevo tiene otra pareja chat/mensaje; deduplicar contenido o consolidar incidentes
es otro paso. La BD no verifica que un texto como `123:7` provenga de Telegram
ni normaliza cadenas: el adaptador es responsable de construirlo correctamente.

## Aplicación de 0004 en otros entornos

El número 0004 reserva 0002 y 0003 para Noel. Solo depende de 0001; no declara
que las migraciones reservadas existan o estén aplicadas. Si el equipo usa un
ejecutor ordenado de migraciones, coordinar su registro con Noel antes de aplicar.

1. Revisar `migrations/0004_identidad_reportes.sql` y aplicarlo una vez en el
   SQL Editor con rol administrativo, dentro del proyecto correcto.
2. La migración bloquea escrituras en ambas tablas mientras comprueba datos e
   instala restricciones. Si hay canales incompatibles o mensajes Telegram
   repetidos entre remitentes, aborta sin borrar ni fusionar datos. Resolverlos
   con Noel y volver a aplicar; no repetir 0001.
3. Ejecutar `tests/0004_identidad_reportes_smoke.sql`. Todo es sintético y termina
   en `ROLLBACK`. Si termina en error, revertir la transacción antes de reintentar.

No se cambia RLS, privilegios, contratos JSON, destinos ni avisos. Los IDs
externos permanecen privados. La migración no autentica usuarios, comprueba
suscripciones, implementa reintentos de Telegram ni acredita la API de Noel.
