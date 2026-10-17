import { reportesEjemplo } from '../datos/reportesEjemplo.js'

// true: la página usa los reportes de ejemplo. false: lee GET /reportes de la API.
// Pásalo a false cuando la API esté corriendo y tenga reportes guardados.
export const USAR_EJEMPLOS = false

const URL_API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Cada elemento: { registrado: ReporteRegistrado, interpretado: ReporteInterpretado | null }
export async function obtenerReportes() {
  if (USAR_EJEMPLOS) {
    return reportesEjemplo
  }
  let respuesta
  try {
    respuesta = await fetch(`${URL_API}/reportes`)
  } catch {
    throw new Error('No se pudo conectar con la API. Comprueba que esté en marcha.')
  }
  if (!respuesta.ok) {
    throw new Error(`La API respondió con el código ${respuesta.status}.`)
  }
  return respuesta.json()
}

// Estado, etapa y traza de los agentes de una ejecución (GET /ejecuciones/{id}).
export async function obtenerEjecucion(ejecucionId) {
  let respuesta
  try {
    respuesta = await fetch(`${URL_API}/ejecuciones/${encodeURIComponent(ejecucionId)}`)
  } catch {
    throw new Error('No se pudo conectar con la API.')
  }
  if (!respuesta.ok) {
    throw new Error(`La API respondió con el código ${respuesta.status}.`)
  }
  return respuesta.json()
}
