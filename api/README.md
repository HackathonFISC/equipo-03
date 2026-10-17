# api

**Dueño:** Noel

API de RutaAgua Oeste con FastAPI. Recibe los reportes del bot, los guarda en
Supabase, los muestra al panel y conecta el bot con las RPC de aclaración de Emilia.
Es el único componente con la clave de servicio de Supabase: ni el bot ni el panel la tienen.

## Arranque

Desde la raíz del repositorio, con el entorno virtual activo:

```bash
uvicorn api.main:app --reload
```

- Documentación interactiva: http://localhost:8000/docs
- Prueba de vida: `GET /salud` responde `{"estado": "ok"}`.

## Configuración (`.env` en la raíz)

| Variable | Uso |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Conexión a Supabase mediante `comun/config.py` y `comun/db.py` (de Emilia). Solo backend. |
| `API_SECRETO_BOT` | Secreto compartido con el bot, mínimo 16 caracteres. Sin él, las rutas del bot responden 503. Reiniciar la API al cambiarlo. |

CORS admite solo `http://localhost:5173` (servidor de desarrollo del panel).

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `main.py` | Crea la app, CORS, manejadores de errores y registro de rutas. |
| `dependencias.py` | Verificación del encabezado `X-Secreto-Bot` y cliente de Supabase por proceso. |
| `errores_http.py` | `ErrorApi` y conversión de errores de dominio a HTTP (decisión D003). |
| `esquemas.py` | Cuerpos de petición y respuesta propios de la API (no son contratos compartidos). |
| `rutas/reportes.py`, `servicios/reportes.py` | Crear y listar reportes. |
| `rutas/ejecuciones.py`, `servicios/ejecuciones.py` | Estado de una ejecución y traza de sus agentes. |
| `rutas/aclaraciones.py`, `servicios/aclaraciones.py` | Circuito de aclaración: reservar, registrar envío y entregar respuesta. |

## Rutas

| Método y ruta | Quién la usa | Secreto | Qué hace |
| --- | --- | --- | --- |
| `GET /salud` | Cualquiera | No | Prueba de vida. |
| `POST /reportes` | Bot | Sí | Registra un mensaje de Telegram. 201 si es nuevo, 200 si ya estaba. |
| `GET /reportes?limite=50` | Panel | No (V1) | Lista reportes, del más reciente al más antiguo (1 a 200). |
| `GET /ejecuciones/{ejecucion_id}` | Panel | No (V1) | Estado, etapa y traza de los agentes. 404 si no existe. |
| `POST /aclaraciones/reservar` | Bot | Sí | Reserva la siguiente pregunta pendiente. 204 si no hay. |
| `POST /aclaraciones/{aclaracion_id}/envio` | Bot | Sí | Registra `enviado`, `fallido` o `incierto`. 204. |
| `POST /aclaraciones/respuestas` | Bot | Sí | Entrega un reply a una pregunta. Siempre 200 con un resultado. |

`GET /reportes` y `GET /ejecuciones/{id}` no tienen autenticación en V1 por decisión
del equipo; la autenticación del coordinador llega en V4 (`auth.py`).

### `POST /reportes`

Cuerpo (lo envía el bot):

```json
{"usuario_telegram_id": 111, "chat_id": -1001, "message_id": 7, "texto": "Sin agua desde ayer en P1"}
```

Pasos, cada uno idempotente (el cliente de Supabase no tiene transacciones; un reintento
del mismo mensaje repara lo que falte sin duplicar):

1. **Remitente:** busca o crea `remitentes` por canal e ID de usuario de Telegram.
2. **Destino (chat de origen):** busca o crea `destinos` por ID del chat. En un chat
   privado (ID del chat = ID del usuario) se asocia al remitente; en un grupo queda sin
   remitente. Nunca modifica un destino existente. Queda sin autorizar: la autorización
   es para los avisos de V4, no para las aclaraciones (D005).
3. **Reporte:** `mensaje_externo_id = "<chat_id>:<message_id>"`
   (`supabase/IDENTIDAD_REPORTES.md`), `modalidad = "texto"`, `origen = "sintetico"` (D003)
   y, si está activo, `destino_origen_id`. Si el mismo mensaje ya existe con otro
   remitente, responde 422 y no reasigna nada.
4. **Ejecución:** crea la ejecución pendiente de etapa `ingesta` con
   `clave_idempotencia = "ingesta:<reporte_id>"`.

Responde un `ReporteRegistrado` validado con los contratos de Emilia.

### `GET /reportes`

Cada elemento: `{registrado, interpretado, seguimiento}`.

- `registrado`: ID, ejecución, fecha, origen y entrada (canal, modalidad, texto).
  **No incluye** `remitente_ref`, `mensaje_externo_id` ni el destino.
- `interpretado`: `{interpretacion: ExtraccionReporteLLM}` o `null` si la Ingesta no lo
  procesó. Acepta la extracción directa (forma de Emilia) o envuelta en un
  `ReporteInterpretado`. Una interpretación que no cumple el contrato se muestra como sin interpretar.
- `seguimiento`: `{estado, etapa}` de la ejecución.

### `GET /ejecuciones/{ejecucion_id}`

Estado, etapa, intentos, código del último error (solo el código, nunca el mensaje)
y eventos de traza: agente, decisión, herramienta, resultado, duración y siguiente estado.
No expone `detalles`, `entrada_ids` ni `salida_ids`.

### Aclaraciones (V2, decisión D005)

Las tres rutas llaman a las RPC de la migración `0006_aclaraciones_v2.sql` con
`service_role`. La API no cambia estados de ejecución: lo hacen las RPC en una transacción.

| Ruta | RPC de Emilia |
| --- | --- |
| `POST /aclaraciones/reservar` | `ra_reservar_aclaracion(p_trabajador_id)`; reserva de 60 s. |
| `POST /aclaraciones/{id}/envio` | `ra_registrar_envio_aclaracion(...)`. `enviado` exige ID de mensaje y ningún error; `fallido` e `incierto` exigen error y ningún ID. |
| `POST /aclaraciones/respuestas` | `ra_aceptar_respuesta_aclaracion(...)`. |

Resultados de una respuesta: `aceptada`, `repetida`, `ya_respondida`, `autor_distinto`,
`no_encontrada` y `vencida`. La API busca el remitente de quien responde sin crearlo; si
no existe, devuelve `autor_distinto` sin llamar a la RPC. Una ubicación se envía según el
contrato `Ubicacion` con `fuente = "compartida"` y `representa_punto_atencion = null`.
Los nombres de las RPC están solo en `servicios/aclaraciones.py`.

## Errores

El cuerpo de un error es el `ErrorDominio` completo de `contratos/errores.py`. Códigos HTTP (D003):

| HTTP | Códigos de dominio |
| --- | --- |
| 422 | `contrato_invalido`, `datos_insuficientes`, `ubicacion_ambigua`, `fuera_de_area` |
| 403 | `sin_permiso` |
| 409 | `politica_no_activa`, `version_obsoleta`, `plan_no_verificado`, `cobertura_critica_pendiente` |
| 503 | `proveedor_no_disponible` |
| 502 | `envio_incierto` |

- Un cuerpo inválido da 422 con los nombres de campo en `campos`, nunca con el valor
  recibido. Un JSON mal formado da `campos: ["cuerpo"]`.
- Un error de la API no pertenece a una ejecución: su `ejecucion_id` es un UUID nuevo que
  solo cumple el contrato.
- `GET /ejecuciones/{id}` inexistente responde el 404 estándar de FastAPI, porque D003 no
  define un código de dominio para "no encontrado".
- Un fallo de Supabase responde 503 recuperable; el registro solo guarda el tipo de error.

## Interruptor

`GUARDAR_DESTINO_ORIGEN` en `servicios/reportes.py` guarda `reportes.destino_origen_id`.
Requiere la migración `0006` aplicada en Supabase. Mientras sea `False`, el destino se
registra pero no se enlaza al reporte, y las aclaraciones de ese reporte pasan a revisión
(`destino_origen_pendiente`). Va junto con `ACLARACIONES_ACTIVAS` del bot.

## Pruebas

```bash
python -m pytest api/tests -q
```

Usan una base de datos y RPC simuladas: no necesitan red, claves ni Supabase.

- `tests/test_api_reportes.py`: creación, repetición, carreras, reparación de la ejecución,
  destino de origen, validación, errores, lista y seguimiento de ejecuciones.
- `tests/test_api_aclaraciones.py`: reservas, registro de envío, los seis resultados,
  ubicación, remitente desconocido, secreto y errores de la base.

## Pendiente

- V2: `rutas/incidentes.py` (consultar y corregir incidentes) y `GET /necesidades` para el panel.
- V4: `auth.py` (rol de coordinador), `servicios/aprobacion.py`, `servicios/bandeja_salida.py`
  y migraciones `0002`/`0003`.
