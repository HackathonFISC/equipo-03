# Validación humana del lugar

Cierra el pendiente del relevo A1 (`HANDOFF_NOEL_A1.md`, «Pendiente de tu parte»).

## Flujo

1. Territorial deja el incidente con `estado_validacion=pendiente` y el faltante
   «Validación operativa del lugar y de la necesidad».
2. En **Necesidades**, cada tarjeta muestra el chip *Lugar por validar* y el botón **Validar el lugar**.
3. El diálogo muestra el punto del catálogo en Google Maps (nombre, coordenadas, fuente, precisión).
   La persona escribe cómo lo confirmó (10–2000 caracteres) y marca la confirmación.
4. `POST /incidentes/{id}/validar-lugar` con `version_incidente` y `evidencia` llama a
   `ra_validar_lugar_v1` (migración 0021): exige coordinador activo, bloqueo `ra_bloqueo_v4()`,
   versión vigente, punto con ubicación y reportes vinculados.
5. La RPC pasa el incidente a `validada`, quita **solo** ese faltante, sube la versión y escribe un evento
   de auditoría (coordinador, evidencia, versión anterior y nueva).
6. La siguiente revisión humana del ámbito completo puede disparar el lote automático (0017); mientras
   quede un lugar sin validar, el preparador mantiene el caso en revisión.

## Qué no hace

- No acredita agua, capacidad de recepción ni entrega física.
- No se activa desde texto de Telegram ni por origen del reporte.
- No rellena confirmaciones, cantidades ni ventanas incompletas.
- Sin coordenadas en el catálogo no se puede validar: el botón solo permite ver.

## Configuración

`VITE_GOOGLE_MAPS_API_KEY` va en **`frontend/.env`** (ver `frontend/.env.example`), no en el `.env` de la raíz:
Vite no lee ese archivo. Clave de *Maps Embed API*, restringida por referrer y por API; distinta de la clave
de Gemini o del servidor. Sin clave el panel sigue funcionando con coordenadas y enlace a Google Maps.
Reiniciar `npm run dev` al cambiarla.

## Despliegue

Aplicar `0021_validar_lugar.sql` y su smoke en Supabase (después de 0020), reiniciar la API.

## Pruebas

Local: PGlite (migración + smoke), `pytest api bot orquestador` (433), `node --test frontend/tests`.
Sin probar contra Supabase ni Google reales.
