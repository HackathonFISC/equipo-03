import { necesidadesEjemplo } from '../datos/necesidadesEjemplo.js'

// false: la página lee GET /incidentes. true: usa los ejemplos sintéticos, sin API.
export const USAR_EJEMPLOS_NECESIDADES = false

const URL_API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Cada elemento es un IncidentePanel (api/esquemas.py): el incidente consolidado, su punto,
// sus conteos y evaluacion_necesidad (EvaluacionNecesidades o null) con pendientes_calculo.
export async function obtenerNecesidades() {
  if (USAR_EJEMPLOS_NECESIDADES) {
    return necesidadesEjemplo
  }
  let respuesta
  try {
    respuesta = await fetch(`${URL_API}/incidentes`)
  } catch {
    throw new Error('No se pudo conectar con la API. Comprueba que esté en marcha.')
  }
  if (!respuesta.ok) {
    throw new Error(`La API respondió con el código ${respuesta.status}.`)
  }
  return respuesta.json()
}
