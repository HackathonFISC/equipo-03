# api

**Dueño:** Noel

API de H2Oeste con FastAPI. Recibe los reportes del bot, los guarda en
Supabase, los muestra al panel, conecta el bot con las RPC de aclaración de Emilia y
entrega al panel los incidentes con su necesidad.
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
| `SUPABASE_ANON_KEY` | Clave pública de Supabase. La API la usa solo para preguntarle a Supabase Auth quién es el dueño de un token (`auth.py`). Sin ella, `GET /sesion` y las rutas de coordinador responden 503. Reiniciar la API al cambiarla. |
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
| `rutas/incidentes.py`, `servicios/incidentes.py` | Incidentes consolidados con su necesidad o sus pendientes. |
| `rutas/priorizacion.py`, `servicios/priorizacion.py` | Prepara el lote revisado de priorización: arma el lote con los incidentes reales y la política elegida, bloquea lo que necesita revisión y llama a `ra_preparar_priorizacion_v2`. |
| `rutas/avisos.py`, `servicios/bandeja_salida.py` | Bandeja de salida: reservar el siguiente aviso vigente y registrar su envío. |
| `rutas/politicas.py` | Lista las políticas de prioridad activas para el panel (`GET /politicas`, solo sesión válida). |
| `rutas/sectores.py`, `servicios/sectores.py` | Estado de un sector, selección del plan que Comunicación usará por sector y habilitación de un destino de ensayo. Llaman a las RPC de la migración 0012 (Emilia) y traducen sus errores. |
| `rutas/planes.py`, `servicios/planes.py`, `servicios/aprobacion.py` | Listar planes guardados; aprobar y rechazar una versión del plan: solo coordinador activo; llaman a las RPC de la migración 0003 y traducen sus errores a códigos de D003. |
| `auth.py`, `rutas/sesion.py` | Sesión (V4): verifica el token de Supabase Auth y exige coordinador activo. El usuario sale del token. |

## Rutas

La API inicia y detiene automáticamente el trabajador de agentes desde su ciclo
de vida. No se inicia al importar el módulo. `TRABAJADOR_AUTOMATICO=true` es el
valor predeterminado; usar `false` solo si se administra un trabajador externo.
Reiniciar la API tras actualizar para activar esta integración.
`GET /salud/agentes` informa el estado del proceso, sin credenciales ni contenido
de reportes; no equivale a una prueba de conectividad externa. Ver
[arranque del trabajador](../orquestador/README.md).

| Método y ruta | Quién la usa | Secreto | Qué hace |
| --- | --- | --- | --- |
| `GET /salud` | Cualquiera | No | Prueba de vida. |
| `POST /reportes` | Bot | Sí | Registra un mensaje de Telegram. 201 si es nuevo, 200 si ya estaba. |
| `GET /reportes?limite=50` | Panel | Token | Lista reportes y pines compartidos, del más reciente al más antiguo (1 a 200). 403 sin sesión válida. |
| `GET /ejecuciones/{ejecucion_id}` | Panel | Token | Estado, etapa y traza de los agentes. 403 sin sesión válida; 404 si no existe. |
| `GET /eventos` | Panel | Token | Registro general de eventos, del más nuevo al más antiguo. Filtros opcionales: `agente`, `actor_tipo`, `ejecucion_id`; `limite` (1–200, 100 por defecto). Sin `detalles`, `entrada_ids`, `salida_ids` ni `usuario_id`. 403 sin sesión; 422 filtro inválido; 503. |
| `POST /aclaraciones/reservar` | Bot | Sí | Reserva la siguiente pregunta pendiente. 204 si no hay. |
| `POST /aclaraciones/{aclaracion_id}/envio` | Bot | Sí | Registra `enviado`, `fallido` o `incierto`. 204. |
| `POST /aclaraciones/respuestas` | Bot | Sí | Entrega un reply a una pregunta. Siempre 200 con un resultado. |
| `GET /incidentes` | Panel | Token | Incidentes con vínculos activos, su necesidad calculada o sus pendientes. 403 sin sesión válida. |
| `POST /ejecuciones/{ejecucion_id}/priorizacion` | Panel | Token + coordinador | Cuerpo: `politica_version`, `motivo`, `revisiones` (opcional). 202 con `datos_version`, `incidentes` y `sin_revisar`; repetir el mismo envío da `repetido: true`. 403 / 404 / 409 (`version_obsoleta`, `politica_no_activa`) / 422 (`datos_insuficientes`: ámbito que necesita revisión; `contrato_invalido`) / 503. |
| `POST /avisos/reservar` | Bot | Sí | Reserva el siguiente aviso vigente. 204 si no hay. Requiere la migración 0011. |
| `POST /avisos/{aviso_id}/envio` | Bot | Sí | Registra `enviado`, `fallido` o `incierto`. 204. |
| `GET /planes` | Panel | Token | Las 20 versiones de plan más recientes con rutas y paradas (nombre del punto del catálogo), `datos_version`, `politica_version` y bloqueos. Lectura de tablas; no expone la solicitud ni quién creó el plan. |
| `POST /planes/{plan_id}/versiones/{version}/aprobar` | Panel | Token + coordinador | Cuerpo: `datos_version`, `politica_version`, `motivo`, `bloqueos_reconocidos`. 200 con `aprobacion_id`; repetir lo mismo da `repetido: true`. 403 / 409 (`version_obsoleta`, `politica_no_activa`, `plan_no_verificado`, `cobertura_critica_pendiente`) / 422 (`bloqueos_reconocidos` incompleto) / 503. |
| `POST /planes/{plan_id}/versiones/{version}/rechazar` | Panel | Token + coordinador | Cuerpo: `motivo`. Deja el plan `rechazado` y la ejecución en revisión. Un plan ya resuelto da 409 `version_obsoleta`. |
| `GET /politicas` | Panel | Token | Políticas de prioridad activas (versión, fundamento, pesos y topes) para elegirlas en el formulario de revisión sin escribir la versión. |
| `GET /sectores` | Panel | Token | Catálogo de sectores (id, nombre, distrito, corregimiento, origen) para elegirlos en el panel. No expone fuente ni quién los creó. |
| `GET /destinos` | Panel | Token + coordinador | Destinos de Telegram con `autorizado` y `habilitado_ensayo` (`null` si la migración 0012 no está aplicada). El identificador del chat sale truncado: `terminado en 7387`. |
| `GET /sectores/{sector_id}/estado` | Panel o bot | Token o `X-Secreto-Bot` | `EstadoSector` (contrato de Emilia): plan vigente y estado de cada punto. Sector inexistente: 422; forma inesperada de la RPC: 503, nunca "sin plan". |
| `POST /sectores/{sector_id}/plan-vigente` | Panel | Token + coordinador | Cuerpo: `plan_id`, `version`, `motivo`. Elige el plan aprobado que Comunicación usará en ese sector. 403 / 409 (`version_obsoleta`: sin aprobación vigente o entradas cambiadas) / 422 (sector ajeno al plan). |
| `PUT /destinos/{destino_id}/ensayo` | Panel | Token + coordinador | Cuerpo: `habilitado`, `motivo`. Habilita o deshabilita un destino de Telegram autorizado para recibir planes sintéticos. 403 si el destino no está autorizado. |
| `GET /sesion` | Panel | Token | Quién es la persona con sesión y si es coordinador activo (`usuario_id`, `rol`, `activo`, `es_coordinador`). 403 sin sesión válida. |

Las rutas de lectura del panel no tienen autenticación por decisión del equipo. Separar un
reporte de un incidente sí la necesitará: `ra_separar_reporte` exige un coordinador activo y
su `usuario_id` debe salir del token de sesión, nunca del navegador (acuerdo con Emilia).

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
   es para los avisos de V4, no para las aclaraciones (D006 y D008).
3. **Reporte:** `mensaje_externo_id = "<chat_id>:<message_id>"`
   (`supabase/IDENTIDAD_REPORTES.md`), `modalidad = "texto"`, `origen = "sintetico"` (D003)
   y, si está activo, `destino_origen_id`. Si el mismo mensaje ya existe con otro
   remitente, responde 422 y no reasigna nada.
4. **Ejecución:** crea la ejecución pendiente de etapa `ingesta` con
   `clave_idempotencia = "ingesta:<reporte_id>"`.

Responde un `ReporteRegistrado` validado con los contratos de Emilia.

### `GET /reportes`

Requiere sesión válida (`Authorization: Bearer`). Cada elemento: `{registrado, interpretado, seguimiento, ubicacion_reportada}`.

- `ubicacion_reportada`: último pin aceptado de Telegram (latitud, longitud y precisión) o `null`. Se lee de las aclaraciones aceptadas, sin esperar al reprocesamiento. No crea un punto de atención ni confirma una entrega.

- `registrado`: ID, ejecución, fecha, origen y entrada (canal, modalidad, texto).
  **No incluye** `remitente_ref`, `mensaje_externo_id` ni el destino.
- `interpretado`: `{interpretacion: ExtraccionReporteLLM}` o `null` si la Ingesta no lo
  procesó. Acepta la extracción directa (forma de Emilia) o envuelta en un
  `ReporteInterpretado`. Una interpretación que no cumple el contrato se muestra como sin interpretar.
- `seguimiento`: `{estado, etapa}` de la ejecución.

### `GET /ejecuciones/{ejecucion_id}`

Requiere sesión válida (`Authorization: Bearer`). Estado, etapa, intentos, código del último error (solo el código, nunca el mensaje)
y eventos de traza: agente, decisión, herramienta, resultado, duración y siguiente estado.
No expone `detalles`, `entrada_ids` ni `salida_ids`.

### Aclaraciones (V2, decisiones D006 y D008)

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

### Sesión y rol de coordinador (V4)

El panel inicia sesión directamente con Supabase Auth (la contraseña no pasa por esta API) y envía solo
el token en `Authorization: Bearer <token>`. `auth.py` le pregunta a Supabase Auth (`GET /auth/v1/user`) a quién
pertenece, rechaza sesiones anónimas y devuelve el `usuario_id`. Un `usuario_id` enviado en el cuerpo, la URL o
un encabezado **no se usa nunca**.

- `usuario_autenticado`: sesión válida. Sin encabezado, con un token mal formado, vencido o rechazado: 403 `sin_permiso`.
  Si Supabase Auth no responde o no está configurada la API: 503 `proveedor_no_disponible` (recuperable).
- `coordinador_actual`: además exige fila activa de rol `coordinador` en `usuarios_operativos` (403 si no).
  Es un control temprano; las RPC de aprobación (`0003`) lo repiten dentro de la transacción.
- `GET /sesion` informa el rol y si la persona puede aprobar. Sirve al panel para mostrar u ocultar acciones.

### Bandeja de salida de avisos (V4, migración 0011)

Las dos rutas llaman a `ra_reservar_aviso` y `ra_registrar_envio_aviso` con `service_role`. La API no
crea avisos (los crea Comunicación) ni los aprueba: solo entrega al bot uno a la vez.

- **Vigencia al reservar:** la RPC cancela, con motivo, un aviso cuyo plan ya no está aprobado, tiene
  una versión más reciente aprobada, cuya suscripción o destino dejó de estar autorizado, o cuyos litros
  o ventana no coinciden con la parada aprobada. Un aviso cancelado no se envía.
- **Qué recibe el bot:** solo `aviso_id`, `chat_id`, `tipo`, `version`, `punto_nombre`, `litros_asignados`
  y la ventana. El texto lo arma el bot con `bot/plantillas.py`; el texto libre del aviso no se envía.
- **Sin reenvío:** una reserva de 60 s que vence sin resultado deja el aviso `incierto`. Un acuse tardío
  de quien reservó puede resolverlo con el ID real. Repetir el mismo resultado es seguro; uno distinto se rechaza.
- Los nombres de las RPC están solo en `servicios/bandeja_salida.py`.

### `GET /incidentes` (V2)

Requiere sesión válida (`Authorization: Bearer`); sin ella, 403.

Se arma con las RPC de la migración `0007_territorial_orquestador_v2.sql`:

1. `ra_incidentes_snapshot_v2()`: incidentes con al menos un vínculo activo.
2. `ra_catalogo_v2()`: nombre, distrito y corregimiento de los puntos activos.
3. `vinculos_reportes` con `desvinculado_en IS NULL`: cuántos reportes tiene cada incidente.

Cada elemento trae identidad y versión (`incidente_id`, `ejecucion_id`, `version`, `origen`),
lugar (`sector_id`, `punto_atencion_id`, `punto`), consolidación (`estado_validacion`,
`tipo_problema`, `episodio_establecido`, período, `primera_deteccion_en`, `confianza`,
`conflictos`, `faltantes`, `requiere_revision_urgente`), conteos y cálculo
(`evaluacion_necesidad`, `pendientes_calculo`).

- `reportes_vinculados` cuenta vínculos activos; `reportes_independientes` cuenta remitentes
  distintos. No son lo mismo: tres mensajes de una persona son 3 y 1.
- `evaluacion_necesidad` se valida con `EvaluacionNecesidades`. Si no cumple el contrato se
  devuelve `null` y se agrega un pendiente: nunca se muestra como calculada.
- Sin lote de cálculo, la evaluación es `null` y `pendientes_calculo` dice por qué. Después
  de separar un reporte, la RPC de Emilia invalida las evaluaciones de todos los incidentes
  y deja "recalcular" en los pendientes.
- `punto` es `null` si el incidente no tiene punto o este no está activo en el catálogo.
- **No incluye** remitentes, chats, mensajes, textos de reportes, `creado_por`, `motivo` ni
  `ubicacion`.
- Orden: del detectado más recientemente al más antiguo; la página ordena por prioridad.

### `POST /ejecuciones/{ejecucion_id}/priorizacion` (V2)

Prepara el lote que el trabajador automático calculará (`validate_need` y `score_needs`). La ejecución debe estar en la
etapa `priorizacion` y ya existir: esta ruta no crea otra. La decisión de aceptar el lote la toma la RPC
`ra_preparar_priorizacion_v2` (Emilia); la API ensambla y comprueba antes.

- **Quién:** coordinador activo con sesión. El usuario que confirma sale del token; un `usuario_id` en el cuerpo se rechaza.
- **Política:** `politica_version` es obligatoria y se lee de `politicas_prioridad` con estado `activa`. Nunca se elige la
  primera ni la más reciente. Va al lote tal como está guardada, sin columnas administrativas.
- **Ámbito completo:** el lote cubre todos los incidentes de `ra_incidentes_contexto_v2(ejecucion_id)`, que no se limita al
  sector que se ve en pantalla. Se bloquea con 422 (`datos_insuficientes`) si hay incidentes sin punto, dos en el mismo
  punto o datos de distinto origen: no se omite, no se suman demandas y no se recorta en silencio.
- **Sin inventar:** `revisiones` lleva lo que el coordinador confirma por incidente (demanda directa o por fórmula, capacidad de recepción
  del punto, clase,
  ventana si es crítico, vulnerabilidad, horas sin agua, personas, última atención). Cada confirmación lleva el usuario de la
  sesión, la hora y el motivo. Lo que no se envía queda pendiente con su motivo, sin confirmaciones.
- **Origen:** el del lote es el de la ejecución. Esta ruta no convierte datos reales en sintéticos.
- **Idempotencia:** `datos_version` es una huella de la política, el motivo y las revisiones; el mismo envío da la misma
  versión y el mismo lote. Cambiar cualquier entrada cambia la versión. `sin_revisar` cuenta los incidentes sin revisión.
- **Seguimiento:** un lote aceptado queda `pendiente`. Tras la migración 0015 el seguimiento puede mostrar `espera_validacion`
  en la etapa `ingesta` por un reintento programado; no significa que se espere la aprobación de un plan.
- **Aún no probado contra la base real:** las pruebas usan RPC simuladas. Falta ejecutarla contra Supabase con la 0014 y la 0015.

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
Está en `True`: la migración `0006` está aplicada en Supabase. Con `False`, el destino se
registra pero no se enlaza al reporte, y las aclaraciones de ese reporte pasan a revisión
(`destino_origen_pendiente`). Va junto con `ACLARACIONES_ACTIVAS` del bot. Los reportes
anteriores a la activación no tienen destino de origen: la migración no lo infiere.

## Pruebas

```bash
python -m pytest api/tests -q
```

Usan una base de datos y RPC simuladas: no necesitan red, claves ni Supabase.

- `tests/test_api_reportes.py`: creación, repetición, carreras, reparación de la ejecución,
  destino de origen, validación, errores, lista y seguimiento de ejecuciones.
- `tests/test_api_aclaraciones.py`: reservas, registro de envío, los seis resultados,
  ubicación, remitente desconocido, secreto y errores de la base.
- `tests/test_api_incidentes.py`: lista vacía, conteos, evaluación calculada e inválida,
  recálculo, punto ausente, orden, campos ocultos y errores de la base.
- `tests/test_auth.py`: lectura del encabezado, verificación del token con Supabase Auth simulado (rechazos,
  proveedor caído, respuesta inesperada, sesión anónima, sin redirecciones ni filtrar el token), rol de coordinador
  y que el usuario salga siempre del token.
- `tests/test_api_planes.py`: listar, aprobar y rechazar con RPC simuladas: usuario tomado del token, cuerpo inválido,
  traducción de cada error de la RPC, acceso solo de coordinador activo y respuestas inesperadas.
- `tests/test_api_sectores.py`: estado con sesión y con secreto del bot, rechazo sin credencial, forma inesperada de la RPC,
  selección de plan y destino de ensayo con usuario tomado del token, cuerpo inválido, cada error de la RPC y solo coordinador.
- `tests/test_api_sectores_listas.py`: listas de sectores y destinos con tablas simuladas: columnas pedidas, identificador
  truncado, tabla de 0012 ausente (`null`) frente a otros fallos (503), acceso solo de coordinador.
- `tests/test_api_priorizacion.py`: lote con todos los incidentes, política tal como está guardada, confirmaciones con el usuario
  de la sesión, lo no revisado queda pendiente, idempotencia y cambio de versión de datos, bloqueos (mismo punto, sin punto,
  origen mezclado, política inactiva o duplicada, etapa), acceso solo de coordinador y cada error de la RPC.
- `tests/test_api_avisos.py`: reserva, forma inesperada de la RPC, campos que no se exponen,
  registro de envío coherente, reserva ajena, secreto y errores de la base.

## Pendiente

- V2: separar un reporte de un incidente (`ra_separar_reporte`), con la sesión mínima del
  coordinador acordada con Emilia.
- V4: la migración `0002`. `auth.py`, el inicio de sesión del panel, las rutas de aprobar y rechazar y las de sector/destino
  (sobre la migración `0012`) ya están, probadas con RPC simuladas; falta aplicar las migraciones en Supabase real.
  La bandeja de salida ya está (migración `0011`, sin aplicar todavía).


### Localización automática (0018)

`GET /reportes` incluye `localizacion_resuelta`: `{ubicacion, place_id, resuelta_en, expira_en}`
o `null`. La ubicación puede proceder de Telegram (`compartida`) o de Google Maps
(`geocodificada`). No requiere revisión del coordinador. Los pines originales se
siguen mostrando en `ubicacion_reportada` antes del procesamiento. La API omite
coordenadas Google vencidas; el mantenimiento elimina la copia temporal. Los
place IDs permanecen disponibles para abrir Google Maps.

La RPC `ra_finalizar_localizacion` cierra la localización en `completada/terminada`;
no crea incidentes, puntos, vínculos ni modifica cálculos. El circuito de lugares
reconocidos del catálogo sigue utilizando `ra_finalizar_territorial`.
Ver [activación y límites](../docs/LOCALIZACION_AUTOMATICA.md).


### Rutas Google

Con sesión: GET `/planes/destinos-localizados` lista reportes con coordenadas vigentes y depósitos activos. POST `/planes/ruta-localizada` recibe `{deposito_id, reportes_ids}` (1–6 IDs únicos); devuelve orden vial, minutos, metros y navegación, sin guardar un plan ni asignar litros. GET `/planes` agrega `navegacion_url` y `tramos_navegacion` por cisterna, usando coordenadas del snapshot. Ver [guía](../docs/RUTAS_GOOGLE.md).
