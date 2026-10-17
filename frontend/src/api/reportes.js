import { reportesEjemplo } from '../datos/reportesEjemplo.js'

// Mientras la API no devuelva reportes, la página usa los datos de ejemplo.
// Cuando exista el endpoint, se cambia a false y se completa obtenerReportes.
export const USAR_EJEMPLOS = true

// Cada elemento: { registrado: ReporteRegistrado, interpretado: ReporteInterpretado | null }
export async function obtenerReportes() {
  if (USAR_EJEMPLOS) {
    return reportesEjemplo
  }
  throw new Error('La API de reportes todavía no está conectada.')
}
