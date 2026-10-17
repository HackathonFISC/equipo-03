import { reportesEjemplo } from '../datos/reportesEjemplo.js'
import { llamarConSesion } from './sesion.js'

// true: la página usa los reportes de ejemplo. false: lee GET /reportes de la API.
// Pásalo a false cuando la API esté corriendo y tenga reportes guardados.
export const USAR_EJEMPLOS = false

// Cada elemento: { registrado: ReporteRegistrado, interpretado: ReporteInterpretado | null }
export async function obtenerReportes() {
  if (USAR_EJEMPLOS) {
    return reportesEjemplo
  }
  return llamarConSesion('/reportes')
}

// Estado, etapa y traza de los agentes de una ejecución (GET /ejecuciones/{id}). Exige sesión válida.
export function obtenerEjecucion(ejecucionId) {
  return llamarConSesion(`/ejecuciones/${encodeURIComponent(ejecucionId)}`)
}
