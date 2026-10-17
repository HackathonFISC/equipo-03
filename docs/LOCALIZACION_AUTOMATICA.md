# Localización automática de reportes

El reporte puede localizarse fuera del diccionario sin revisión del coordinador.

1. Un pin fijo de Telegram aceptado como respuesta a una aclaración determina las
   coordenadas directamente, sin consultar Google.
2. Sin pin, una coincidencia única con el catálogo conserva el circuito existente.
3. Sin coincidencia, el backend envía a Google Geocoding API v4 solo la dirección
   extraída del reporte. Nunca envía el mensaje completo ni la identidad Telegram.
4. Un único resultado detallado en Panamá (ROOFTOP o RANGE_INTERPOLATED y tipo de
   dirección/premisa compatible) localiza automáticamente el reporte.
5. Con resultado ambiguo, localidad amplia, error, cuota agotada o clave ausente,
   el bot pide un pin al remitente mediante el circuito existente. No elige el
   primer resultado entre varios ni manda coordenadas utilizables a revisión.

Google no devuelve en v4 una probabilidad universal de exactitud. Las reglas
anteriores son criterios del proyecto; un resultado aceptado puede contener errores.
La dirección escrita puede corresponder a un lugar distinto del que quiso decir
el remitente. Un pin explícito siempre prevalece sobre una dirección geocodificada.

## Activación

1. En Google Cloud habilitar Geocoding API con soporte v4 y facturación. Crear una
   clave para el backend restringida a esa API (y a IPs del servidor cuando aplique).
2. En `.env` del backend agregar `GOOGLE_MAPS_API_KEY=...`. No pegarla en el chat,
   no usar prefijo VITE_ y no subir `.env` al repositorio. La clave se transmite
   mediante X-Goog-Api-Key, fuera de la URL, y no se devuelve al panel.
3. Aplicar `supabase/migrations/0018_localizacion_automatica.sql` en el SQL Editor
   de Supabase, después de 0017. La implementación local no aplica migraciones al
   proyecto remoto. Aplicar antes de reiniciar API/trabajador porque el panel
   consulta la nueva columna.
4. Reiniciar API/trabajador y bot; reconstruir el frontend.
5. Probar una dirección concreta fuera del catálogo. El panel Reportes debe mostrar
   «Ubicación resuelta automáticamente» con un enlace al mapa. Probar también un
   pin fijo como respuesta a una pregunta de ubicación.

La localización automática termina la ejecución en `completada/terminada` y guarda
la ubicación en el reporte. No crea automáticamente incidentes o puntos de atención,
no vincula personas por cercanía y no calcula ni autoriza distribución. El circuito
original continúa para reportes identificados con un punto del catálogo. Completar
una localización y completar una entrega son acciones distintas.

## Contenido Google y costos

Se hace como máximo una petición por intento territorial que necesita buscar una
dirección, con timeout de cinco segundos y sin reintentos inmediatos. No se llama
Google si hay un pin o un punto conocido. La API no genera una confianza numérica
inventada ni conserva la respuesta completa o la dirección formateada de Google.

Se conservan coordenadas Google temporalmente con vencimiento a los 29 días; la
API deja de mostrarlas al vencer y el mantenimiento del trabajador elimina la copia.
El worker debe mantenerse activo para ejecutar esa limpieza. Los place IDs se
conservan y permiten abrir Google Maps después. Los pines aportados por usuarios
no son contenido Google. El panel atribuye a Google Maps las coordenadas del proveedor.

Referencias: [Geocoding v4](https://developers.google.com/maps/documentation/geocoding/geocoding),
[atribución y almacenamiento](https://developers.google.com/maps/documentation/geocoding/policies).

## Verificación local

Python: `python -m pytest bot/tests api/tests agentes/tests geografia/tests -q`.
Google se simula; no se consume cuota real. El test SQL
`supabase/tests/0018_localizacion_automatica_smoke.sql` verifica permisos, reservas,
snapshots obsoletos, coordenadas inválidas, cierre sin revisión y limpieza temporal.
El harness `supabase/tests/0018_integracion_local.mjs` crea PostgreSQL efímero con
PGlite, aplica migraciones locales y ejecuta regresiones. No usa el Supabase remoto.
