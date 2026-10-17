import { necesidadesEjemplo } from '../datos/necesidadesEjemplo.js'
import { llamarConSesion } from './sesion.js'

// false: la página lee GET /incidentes. true: usa los ejemplos sintéticos, sin API.
export const USAR_EJEMPLOS_NECESIDADES = false

// Cada elemento es un IncidentePanel (api/esquemas.py): el incidente consolidado, su punto,
// sus conteos y evaluacion_necesidad (EvaluacionNecesidades o null) con pendientes_calculo.
export async function obtenerNecesidades() {
  if (USAR_EJEMPLOS_NECESIDADES) {
    return necesidadesEjemplo
  }
  // GET /incidentes exige sesión válida: sin ella la API responde 403.
  return llamarConSesion('/incidentes')
}
