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

### Reportes (`src/paginas/Reportes.jsx`)

- Lista de `GET /reportes`, del más reciente al más antiguo.
- Se actualiza automáticamente cinco segundos después de cada consulta completada,
  sin solapar peticiones. Al salir de la página se detiene el sondeo y se ignoran
  respuestas tardías. No es necesario pulsar F5 para ver una interpretación nueva.
- Estado derivado de la interpretación: **Interpretado**, **Necesita aclaración**,
  **Sin interpretar** o **Fuera de alcance**, con filtros y conteos.
- Cada fila se despliega: resumen, ubicación declarada, campos extraídos (un dato
  desconocido dice "No indicado", nunca 0), frases que sustentan la lectura y faltantes.
- **Seguimiento:** al abrir la fila, pide `GET /ejecuciones/{id}` y muestra la etapa actual
  y cada decisión de los agentes, con su resultado, hora, duración y herramienta.
  Mientras la fila siga abierta, actualiza también la traza mediante sondeo.
- Fechas en hora de Panamá.

### Necesidades (`src/paginas/Necesidades.jsx`) — V2

- Lee `GET /incidentes`: un elemento por incidente con vínculos activos. El botón
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
- Los ejemplos (`src/datos/necesidadesEjemplo.js`) son sintéticos, se validaron con
  `IncidenteConsolidado` y `EvaluacionNecesidades` y se convierten a la forma de `GET /incidentes`.
  Incluyen un incidente sin evaluación y otro que requiere recálculo.

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

Con datos de ejemplo, la página muestra un aviso amarillo para que no se confundan con datos reales.

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `src/App.jsx`, `App.css` | Barra superior y navegación entre páginas. |
| `src/index.css` | Colores y tipografía compartidos. |
| `src/api/reportes.js` | `obtenerReportes()` y `obtenerEjecucion(id)`. |
| `src/api/necesidades.js` | `obtenerNecesidades()` (lee `GET /incidentes`). |
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
