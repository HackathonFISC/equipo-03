import { necesidadesEjemplo } from '../datos/necesidadesEjemplo.js'

// true mientras la API no tenga GET /necesidades: la página usa los ejemplos.
// Las necesidades reales llegan en V2 (Territorial y Priorización de Emilia, cálculo de José).
export const USAR_EJEMPLOS_NECESIDADES = true

const URL_API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Cada elemento: { punto: { nombre } | null, incidente: IncidenteConsolidado, evaluacion: EvaluacionNecesidades }
export async function obtenerNecesidades() {
  if (USAR_EJEMPLOS_NECESIDADES) {
    return necesidadesEjemplo
  }
  let respuesta
  try {
    respuesta = await fetch(`${URL_API}/necesidades`)
  } catch {
    throw new Error('No se pudo conectar con la API. Comprueba que esté en marcha.')
  }
  if (!respuesta.ok) {
    throw new Error(`La API respondió con el código ${respuesta.status}.`)
  }
  return respuesta.json()
}
