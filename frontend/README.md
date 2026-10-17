# frontend

**Dueño:** Noel

React + Leaflet

Panel de RutaAgua Oeste con React 19 y Vite. Lee la API; no tiene claves de Supabase
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
(`#reportes`, `#necesidades`, `#plan`) para que recargar no la pierda.

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

### Plan (`src/paginas/Plan.jsx`) — V3, con datos de ejemplo

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
- Todavía no existe `GET /planes`: `USAR_EJEMPLOS_PLANES = true` usa `src/datos/planesEjemplo.js`,
  tres casos que salieron de `solve_routes` y `verify_plan` sobre el escenario ficticio de
  `calculo/` (seis puntos y dos cisternas; una cisterna; crítico de 12 000 L). No hay botón de
  aprobar: llega en V4.

## Configuración

| Dónde | Qué controla |
| --- | --- |
| `src/api/reportes.js`, `USAR_EJEMPLOS` | `false`: lee la API (actual). `true`: usa `src/datos/reportesEjemplo.js` sin API. |
| `src/api/necesidades.js`, `USAR_EJEMPLOS_NECESIDADES` | `false`: lee `GET /incidentes` (actual). `true`: usa los ejemplos sin API. |
| `src/api/planes.js`, `USAR_EJEMPLOS_PLANES` | `true` (actual): usa los ejemplos, porque `GET /planes` aún no existe. `false`: lee `GET /planes`. |
| `VITE_API_URL` (en `frontend/.env`) | Opcional. Por defecto `http://localhost:8000`. |

Con datos de ejemplo, la página muestra un aviso amarillo para que no se confundan con datos reales.

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `src/App.jsx`, `App.css` | Barra superior y navegación entre páginas. |
| `src/index.css` | Colores y tipografía compartidos. |
| `src/api/reportes.js` | `obtenerReportes()` y `obtenerEjecucion(id)`. |
| `src/api/necesidades.js` | `obtenerNecesidades()` (lee `GET /incidentes`). |
| `src/api/planes.js` | `obtenerPlanes()` (ejemplos hasta que exista `GET /planes`). |
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
- V4: páginas Aprobación y Eventos, con sesión de coordinador.
- V5: mapa Leaflet de rutas y déficit.
