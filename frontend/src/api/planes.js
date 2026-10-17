import { planesEjemplo } from '../datos/planesEjemplo.js'
import { llamarConSesion } from './sesion.js'

// Por defecto la página lee los planes guardados (GET /planes, con sesión). Para ensayar el diseño sin API:
// VITE_USAR_EJEMPLOS_PLANES=true en frontend/.env y reiniciar el panel.
export const USAR_EJEMPLOS_PLANES = import.meta.env.VITE_USAR_EJEMPLOS_PLANES === 'true'

// GET /planes devuelve PlanPanel (lo guardado en la base). La página dibuja PropuestaDistribucion + `catalogo`,
// así que aquí se traduce sin inventar nada:
// - nombres de los puntos: salen de cada parada (la API ya los resolvió con el catálogo activo);
// - capacidad de las cisternas: la API no la envía, la página no muestra barra de carga;
// - verificación: la API solo dice si es válida. Sin verificación válida no se muestran violaciones, porque no se tienen.
export function adaptarPlan(plan) {
  const puntos = {}
  for (const ruta of plan.rutas ?? []) {
    for (const parada of ruta.paradas ?? []) {
      if (parada.punto?.nombre) puntos[parada.punto_atencion_id] = { nombre: parada.punto.nombre }
    }
  }
  return {
    ...plan,
    estado_solver: plan.estado_solver ?? 'sin_resultado',
    verificacion: plan.verificado ? { valido: true, violaciones: [] } : null,
    no_atendidos: Array.isArray(plan.no_atendidos) ? plan.no_atendidos : [],
    catalogo: { puntos, vehiculos: {} },
  }
}

export async function obtenerPlanes() {
  if (USAR_EJEMPLOS_PLANES) {
    return planesEjemplo
  }
  const planes = await llamarConSesion('/planes')
  if (!Array.isArray(planes)) throw new Error('La API respondió algo inesperado al pedir los planes.')
  return planes.map(adaptarPlan)
}
