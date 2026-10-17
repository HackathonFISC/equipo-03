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
(`#reportes`, `#necesidades`) para que recargar no la pierda.

### Reportes (`src/paginas/Reportes.jsx`)

- Lista de `GET /reportes`, del más reciente al más antiguo.
- Estado derivado de la interpretación: **Interpretado**, **Necesita aclaración**,
  **Sin interpretar** o **Fuera de alcance**, con filtros y conteos.
- Cada fila se despliega: resumen, ubicación declarada, campos extraídos (un dato
  desconocido dice "No indicado", nunca 0), frases que sustentan la lectura y faltantes.
- **Seguimiento:** al abrir la fila, pide `GET /ejecuciones/{id}` y muestra la etapa actual
  y cada decisión de los agentes, con su resultado, hora, duración y herramienta.
- Fechas en hora de Panamá.

### Necesidades (`src/paginas/Necesidades.jsx`) — V2, con datos de ejemplo

- **Orden de atención:** necesidades con prioridad calculada, numeradas por la `posicion`
  del cálculo; la página no reordena.
- **Urgencia y confianza por separado:**
  - Urgencia: puntaje sobre 100 y sus aportes según la política demo-1.0 (tiempo sin agua
    sobre 50, vulnerabilidad sobre 30, personas sobre 20), más horas, personas y vulnerabilidad.
  - Confianza: confianza de la consolidación, estado del incidente, reportes vinculados e
    independientes, conflictos y faltantes.
- **Pendientes de revisión:** sin puntaje, fuera del orden, con lo que falta y la alerta de
  revisión urgente. Un dato faltante nunca se cuenta como cero.
- Los ejemplos (`src/datos/necesidadesEjemplo.js`) son sintéticos y se validaron con
  `IncidenteConsolidado` y `EvaluacionNecesidades`. `punto.nombre` no está en los contratos:
  es una propuesta para que la API lo traiga de `puntos_atencion`.

## Configuración

| Dónde | Qué controla |
| --- | --- |
| `src/api/reportes.js`, `USAR_EJEMPLOS` | `false`: lee la API (actual). `true`: usa `src/datos/reportesEjemplo.js` sin API. |
| `src/api/necesidades.js`, `USAR_EJEMPLOS_NECESIDADES` | `true` hasta que exista `GET /necesidades`. |
| `VITE_API_URL` (en `frontend/.env`) | Opcional. Por defecto `http://localhost:8000`. |

Con datos de ejemplo, la página muestra un aviso amarillo para que no se confundan con datos reales.

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `src/App.jsx`, `App.css` | Barra superior y navegación entre páginas. |
| `src/index.css` | Colores y tipografía compartidos. |
| `src/api/reportes.js` | `obtenerReportes()` y `obtenerEjecucion(id)`. |
| `src/api/necesidades.js` | `obtenerNecesidades()`. |
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

- V2: conectar Necesidades a `GET /necesidades` y corrección de agrupaciones de incidentes.
- V3: página Plan (rutas por cisterna; las horas llegan en UTC y se muestran en hora de Panamá).
- V4: páginas Aprobación y Eventos, con sesión de coordinador.
- V5: mapa Leaflet de rutas y déficit.
