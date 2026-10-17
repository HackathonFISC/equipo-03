# frontend

**Dueño:** Noel

React + Leaflet

Panel de H2Oeste con React 19 y Vite. Lee la API; no tiene claves de Supabase
ni de Gemini. Leaflet (mapa) llega en V5.

## Arranque

Con la API corriendo, dentro de `frontend/`:

```bash
npm install
npm run dev
```

Abrir http://localhost:5173. La API debe permitir ese origen (CORS en `api/main.py`).

## Páginas

La barra superior cambia de página; la página activa queda en la dirección
(`#reportes`, `#necesidades`, `#plan`, `#aprobacion`) para que recargar no la pierda.

### Acceso y transiciones

- **El acceso es la primera pantalla.** Sin sesión no se muestra el panel: cualquier dirección (`#necesidades`, etc.) abre el
  inicio de sesión. Al entrar, se abre la página que se pidió en la dirección o Reportes si no hubo ninguna. Si la sesión
  vence, vuelve al acceso con el aviso "Tu sesión venció". Sin `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` el acceso
  lo dice y no hay forma de entrar.
- **Diseño del acceso** (`Acceso.jsx`, `Acceso.css`): a la izquierda, el paisaje de la foto de bienvenida (recorte sin el
  texto incrustado, `h2oeste-paisaje.webp`), el logo, el lema y el recorrido Reporte, Prioridad, Plan y Firma; a la derecha, el
  formulario con iconos, botón para mostrar la contraseña, aviso de Bloq Mayús y estado de carga. En móvil la foto pasa
  arriba. `Mi cuenta` conserva la tarjeta anterior.
- **Transiciones** (`src/transiciones.css`): cada una responde a una acción de la persona. La página nueva entra con un
  movimiento corto (220 ms) al cambiar de sección; lo que se despliega (detalles de un reporte, formulario de un punto,
  mensajes y errores, menú móvil) aparece con un desplazamiento leve; botones, chips y opciones cambian de color y
  borde con suavidad; las barras de aporte crecen una vez. Con "reducir movimiento" en el sistema todo se desactiva
  (regla en `index.css`).

### Barra lateral y cuenta (`src/App.jsx`, `Navegacion.css`, `MenuCuenta.jsx`, `paginas/Cuenta.jsx`)

- **Barra lateral:** dos grupos. "Flujo de trabajo" (Reportes → Necesidades → Plan → Aprobación) son pasos numerados y unidos
  por una línea, porque son una secuencia. "Seguimiento" (Eventos) no es un paso y lleva ícono. `Navegacion.css` se carga
  después de `App.css` y `editorial.css` y reemplaza sus reglas de la barra.
- **Menú de la cuenta (encabezado):** avatar con iniciales, nombre y rol. Abre un menú con "Ver mi cuenta" y "Cerrar sesión"
  desde cualquier página. Se cierra con Esc o al hacer clic fuera.
- **Mi cuenta:** perfil, qué puedes hacer y cuándo vence la sesión. El nombre y el vencimiento salen del token (solo para
  mostrar; `src/perfil.js`); el rol sale de `GET /sesion`. Si esa consulta falla, dice "Rol sin comprobar". La API
  sigue comprobando los permisos en cada acción.

### Eventos (`src/paginas/Eventos.jsx`)

- Registro de decisiones: lee `GET /eventos` (últimos 200) y los muestra en una línea de tiempo, del más reciente al
  más antiguo. Cada evento dice quién actuó (agente o persona), qué decidió, el resultado, la herramienta, cuánto tardó,
  en qué estado quedó la ejecución y el origen del dato.
- Se actualiza sola cada 5 s (`iniciarSondeo`); el botón Pausar la detiene para leer con calma. Lo que llega después se
  resalta un momento.
- Filtros: por quién lo hizo (cada agente, o Personas y sistema) y por ejecución, para seguir un reporte de punta a punta.
  Los eventos que dejan la ejecución esperando a una persona o con fallo se marcan en ámbar y en rojo.
- Sin sesión o con la sesión vencida vuelve al acceso. No muestra texto de ciudadanos ni datos internos de los agentes.

### Reportes (`src/paginas/Reportes.jsx`)

- Lista de `GET /reportes` con sesión iniciada, del más reciente al más antiguo.
- Muestra el pin fijo aceptado por Telegram, su precisión y un enlace para abrirlo en el mapa, incluso fuera del catálogo. Localiza el reporte automáticamente; no aprueba un punto de distribución.
- Se actualiza automáticamente cinco segundos después de cada consulta completada,
  sin solapar peticiones. Al salir de la página se detiene el sondeo y se ignoran
  respuestas tardías. No es necesario pulsar F5 para ver una interpretación nueva.
- Estado derivado de la interpretación: **Interpretado**, **Necesita aclaración**,
  **Sin interpretar** o **Fuera de alcance**, con filtros y conteos.
- Cada fila se despliega: resumen, ubicación declarada, campos extraídos (un dato
  desconocido dice "No indicado", nunca 0), frases que sustentan la lectura y faltantes.
- **Seguimiento:** al abrir la fila, pide `GET /ejecuciones/{id}` (con la sesión; sin ella la API responde 403) y muestra la etapa actual
  y cada decisión de los agentes, con su resultado, hora, duración y herramienta.
  Mientras la fila siga abierta, actualiza también la traza mediante sondeo.
- Fechas en hora de Panamá.

- **Filtro por hora de llegada** (Reportes): Cualquier hora, Últimos 15 min, Última hora, Hoy, o un rango Desde/Hasta
  en hora de Panamá, más el orden (recientes o antiguos primero). Se combina con el filtro por estado; los conteos de los
  estados siguen el rango elegido y el aviso "Mostrando N de M" tiene un enlace para quitar los filtros. La lista se
  refresca cada 5 s y los rangos relativos se mueven con ella.
- **Sondeo tras enviar una revisión** (Necesidades): después de enviar, la página consulta `GET /incidentes` cada 5 s hasta
  ver una evaluación con la `datos_version` del envío (máximo 2 minutos) y lo dice en el formulario. Si tarda, avisa de
  que se compruebe el trabajador de agentes. "Revisar ahora" actualiza sin ocultar el formulario.

### Necesidades (`src/paginas/Necesidades.jsx`) — V2

- Lee `GET /incidentes` con la sesión (sin ella la API responde 403 y la página ofrece ir al inicio de sesión): un elemento por incidente con vínculos activos. El botón
  **Actualizar** vuelve a pedirlos (útil mientras el trabajador de Emilia procesa).
- **Orden de atención:** necesidades con prioridad calculada, numeradas por la `posicion`
  del cálculo; la página no reordena.
- **Urgencia y confianza por separado:**
  - Urgencia: puntaje sobre 100 y sus aportes según la política demo-1.0 (tiempo sin agua
    sobre 50, vulnerabilidad sobre 30, personas sobre 20), más horas, personas y vulnerabilidad.
  - Confianza: confianza de la consolidación, estado del incidente, reportes vinculados e
    independientes (son cifras distintas), tipo de problema, primera detección, conflictos
    y faltantes.
- **Pendientes de revisión:** sin puntaje, fuera del orden, con lo que falta y la alerta de
  revisión urgente. Un dato faltante nunca se cuenta como cero.
  - Sin evaluación (no hay lote de cálculo): "Sin evaluación de necesidad todavía".
  - Después de separar un reporte, la RPC de Emilia invalida las evaluaciones: sello
    **Requiere recálculo** y el motivo en la lista de pendientes.
- Un incidente sin punto identificado se muestra como "Lugar sin identificar".
- **Confirmar datos y calcular el orden** (`src/paginas/FormularioRevision.jsx`, solo con sesión), en tres pasos
  visibles: (1) elegir la política en una lista de las activas (`GET /politicas`), con sus pesos y topes explicados,
  y escribir el motivo; (2) confirmar los datos de cada punto en secciones con lenguaje llano: agua que necesita y
  capacidad de recepción, qué tan urgente es (clase, horas sin agua, personas, vulnerabilidad) y ventana de entrega;
  (3) enviar. Cada campo trae su ayuda; el dato que el sistema ya tiene se ofrece con "Usar este dato", nunca se
  confirma solo. Cada punto muestra "N de 6 datos" y qué quedará pendiente. El botón explica por qué está
  desactivado. Los puntos sin cálculo vienen marcados. Envía `POST /ejecuciones/{id}/priorizacion`
  (`src/api/priorizacion.js`); lo vacío no se envía y queda pendiente. La ejecución se elige sola: la más reciente en
  etapa `priorizacion` con estado aceptado. Ventanas con desfase −05:00. Quién confirma y cuándo lo pone el servidor.
  Si `GET /politicas` falla, el campo vuelve a ser de texto. La API exige cubrir todo el ámbito con un incidente por
  punto; si falta, devuelve 422 y se muestra el mensaje.
- La página abre con una guía de tres pasos (Mira, Confirma, Envía) y los datos técnicos de cada tarjeta van en un
  desplegable "Detalles técnicos".

### Aprobación (`src/paginas/Aprobacion.jsx`) — V4

- Inicio de sesión con correo y contraseña **directamente contra Supabase Auth**: la contraseña no
  pasa por nuestra API. La API recibe solo el token (`Authorization: Bearer`), que se guarda en
  `sessionStorage` (se pierde al cerrar la pestaña). Solo se usa la clave pública (anon).
- Lee `GET /sesion` y `GET /planes` (cada 10 s). Muestra estado, versiones de datos y política, solver,
  verificación, supuestos, rutas y paradas con el nombre del punto.
- Si la cuenta es **coordinador activo** y el plan está pendiente de revisión: hay que reconocer cada
  bloqueo, escribir un motivo y confirmar en un segundo paso. **Aprobar** envía lo que se revisó
  (`datos_version`, `politica_version`, bloqueos reconocidos, motivo); **Rechazar** solo pide motivo.
  Quién decide sale del token en la API, nunca de este formulario. Otra cuenta solo puede ver.
- Un plan invalidado (cambió una entrada tras aprobarlo) se marca y no tiene acciones.
- Si el token vence, vuelve al formulario de acceso con un aviso. No hay renovación automática.
- No se ha probado contra un Supabase real: necesita un usuario en Auth y su fila de coordinador activo
  en `usuarios_operativos`.

### Plan (`src/paginas/Plan.jsx`) — V3; lee los planes guardados desde V4

- Muestra una `PropuestaDistribucion` por tarjeta: estado del plan, litros asignados, puntos
  atendidos y sin atender, y cisternas en ruta.
- **Verificación:** "Cumple las restricciones" o "No cumple las restricciones" con cada
  violación. Que cumpla las restricciones no significa que sea el mejor plan ni que esté
  aprobado; el texto lo dice. Sin informe: "Sin verificar".
- **Rutas por cisterna:** salida y retorno, litros contra capacidad y cada parada con su
  llegada y ventana de descarga.
- **Puntos sin atender:** motivo del cálculo, litros pendientes (un dato desconocido dice
  "Demanda por confirmar") y sello Crítico.
- **Pendiente antes de publicar:** los bloqueos de publicación del plan, tal como vienen.
- Lee `GET /planes` con la sesión del panel (sin sesión muestra un enlace al acceso). `src/api/planes.js` traduce el
  `PlanPanel` de la API a lo que dibuja la página: los nombres de los puntos salen de las paradas; la API no envía
  la capacidad de las cisternas, así que no hay barra de carga; y solo dice si la verificación es válida, así que sin
  verificación válida la página no lista violaciones (no las tiene). Sin resultado del solver dice «Todavía no hay
  resultado del cálculo». Aprobar y rechazar se hace en la página Aprobación.
- Para ensayar el diseño sin API: `VITE_USAR_EJEMPLOS_PLANES=true` en `frontend/.env` y reiniciar el panel usa
  `src/datos/planesEjemplo.js`, tres casos que salieron de `solve_routes` y `verify_plan` sobre el escenario ficticio
  de `calculo/` (seis puntos y dos cisternas; una cisterna; crítico de 12 000 L), con aviso amarillo.

## Configuración

| Dónde | Qué controla |
| --- | --- |
| `src/api/reportes.js`, `USAR_EJEMPLOS` | `false`: lee la API (actual). `true`: usa `src/datos/reportesEjemplo.js` sin API. |
| `src/api/necesidades.js`, `USAR_EJEMPLOS_NECESIDADES` | `false`: lee `GET /incidentes` (actual). `true`: usa los ejemplos sin API. |
| `src/api/planes.js`, `VITE_USAR_EJEMPLOS_PLANES` | Sin definir (actual): lee `GET /planes` con sesión. `true`: usa los ejemplos sin API. |
| `VITE_API_URL` (en `frontend/.env`) | Opcional. Por defecto `http://localhost:8000`. |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (en `frontend/.env`) | Necesarias para iniciar sesión en Aprobación. Clave pública; nunca la clave de servicio. Reiniciar `npm run dev` al cambiarlas. |
| `VITE_GOOGLE_MAPS_API_KEY` (en `frontend/.env`) | Opcional. Clave de Google Maps (Maps Embed API) para ver el lugar en el mapa al validarlo. Sin ella el panel funciona: muestra coordenadas y un enlace a Google Maps. Es pública en el navegador: restringirla por dirección web y por API; no usar la clave de Gemini ni la del servidor. |

Con datos de ejemplo, la página muestra un aviso amarillo para que no se confundan con datos reales.

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `src/App.jsx`, `App.css` | Barra superior y navegación entre páginas. |
| `src/index.css` | Colores y tipografía compartidos. |
| `src/api/reportes.js` | `obtenerReportes()` y `obtenerEjecucion(id)`. |
| `src/api/eventos.js` | `obtenerEventos()` (lee `GET /eventos`). |
| `src/perfil.js` | Nombre, iniciales, rol y permisos que se muestran en la cuenta (con prueba en `tests/perfil.test.mjs`). |
| `src/api/necesidades.js` | `obtenerNecesidades()` (lee `GET /incidentes`). |
| `src/api/priorizacion.js` | `prepararPriorizacion(ejecucionId, cuerpo)` y `consultarEtapa(id)`. |
| `src/assets/` | Logo circular (cabecera, favicon) y banner de bienvenida (acceso), en WebP optimizado. |
| `src/api/sesion.js`, `src/api/aprobacion.js` | Inicio y cierre de sesión (Supabase Auth), llamadas a la API con token, `listarPlanes`, `aprobarPlan`, `rechazarPlan`. |
| `src/api/planes.js` | `obtenerPlanes()`: planes guardados (`GET /planes`) o ejemplos, y `adaptarPlan()`. |
| `src/paginas/` | Una página por archivo, con su hoja de estilos. |
| `src/datos/` | Datos de ejemplo sintéticos. |

## Verificación

```bash
npm run lint
npm run build
```

Las páginas manejan carga, error con "Reintentar" y lista vacía; tienen foco visible y
funcionan desde 390 px de ancho.

## Pendiente

- V2: corrección de agrupaciones (separar un reporte) con la sesión mínima del coordinador.
- V3: página Plan (rutas por cisterna; las horas llegan en UTC y se muestran en hora de Panamá).
- V4: página Eventos.
- V5: mapa Leaflet de rutas y déficit.

## Diseño visual — Agua institucional

La navegación usa una barra lateral de escritorio y un menú desplegable hasta 900 px.
Conserva los enlaces por hash, permite cerrar el menú con Escape y ofrece un enlace
para saltar al contenido. Los títulos del navegador reflejan la página seleccionada.

- `src/index.css`: tokens de la paleta A, tipografía y accesibilidad global.
- `src/App.css`: estructura, navegación y comportamiento responsivo.
- `src/design-system.css`: apariencia compartida de las páginas existentes, cargada
  después de sus estilos particulares.
- Inter se carga mediante Google Fonts con `display=swap`; sin conexión se utiliza
  la fuente del sistema.

Esta primera fase aplica la identidad a Reportes, Necesidades, Plan, Aprobación,
el acceso y la comunicación por sector. Conserva los contratos y controles actuales.
La actividad de agentes sigue dentro del detalle del reporte. La página independiente
Eventos, el mapa y la unificación de Plan con los datos reales quedan pendientes.

Validación de esta fase: ESLint, compilación con `npm run build -- --configLoader native`
y cuatro pruebas de sondeo con `node --test --test-isolation=none tests/sondeo.test.mjs`.
Los cargadores alternativos evitan subprocesos que este entorno restringe (EPERM).
La comprobación visual de escritorio y móvil queda pendiente: el navegador automatizado
no pudo abrir la sesión. No se verificó una aprobación real con estos cambios.

### Cuenta independiente

El acceso vive en `#acceso` y `src/paginas/Acceso.jsx`, desde el avatar del encabezado.
Aprobación ya no contiene el formulario ni el cierre de sesión. Los permisos para
aprobar siguen dependiendo de la API. Lint y compilación comprobados; recorrido
visual y login real no verificados en esta sesión.

## Refinamiento visual por función — 17 de octubre

Se añadió `src/editorial.css`, cargado después de la capa compartida, para diferenciar
las pantallas manteniendo la paleta Agua institucional y el nombre actual H2Oeste.

- Reportes: bandeja con filas continuas, filtros subrayados, sellos suaves, títulos
  serif y resumen derivado de los reportes recibidos. El resumen solo aparece con
  una respuesta válida y no vacía.
- Necesidades: rangos tipográficos, separación entre puntaje de urgencia y confianza,
  barras de aportes diferenciadas y resumen real de calculadas/pendientes.
- Aprobación: expediente con metadatos compactos y bloque de firma independiente.
- Plan: rutas y métricas con una jerarquía distinta de la bandeja ciudadana.

Georgia es la serif local para títulos editoriales; Inter se conserva en controles,
cuerpo y datos. No se cambian contratos, permisos, cálculos ni selección de origen.
Lint y build con configLoader native aprobados. No hubo inspección visual en navegador.
Las tres imágenes nuevas adjuntas no se incorporaron porque su descarga falló.


### Rutas Google en Plan

La página Plan permite previsualizar un recorrido de hasta seis reportes localizados desde un depósito activo. Los planes de cisternas tienen navegación completa y por tramos con retorno. Activación: [Rutas Google](../docs/RUTAS_GOOGLE.md).


Reportes distingue las transcripciones de audio mediante una etiqueta en el detalle del mensaje. Requiere API y migración 0020; ver [guía de audio](../docs/AUDIO_TELEGRAM.md).
