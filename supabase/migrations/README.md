# supabase/migrations

**Dueño:** Emilia (0001) y Noel (0002, 0003)

0001_esquema.sql, 0002_politicas_rls.sql, 0003_aprobacion.sql


Emilia mantiene también `0004_identidad_reportes.sql`: referencia de remitente
con canal y deduplicación Telegram independiente del remitente. Requiere 0001;
0002 y 0003 continúan reservadas a Noel y no son dependencias de 0004.
Coordinar el orden/registro con Noel antes de usar un ejecutor de migraciones.
Ver `../IDENTIDAD_REPORTES.md` y `../tests/0004_identidad_reportes_smoke.sql`.
0004 probada localmente; Emilia confirmó su aplicación y smoke correctos en Supabase desde el SQL Editor. No volver a aplicar si ya está instalada.
