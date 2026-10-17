import { useSyncExternalStore } from 'react'
import { quitadosDe, quitar, restaurarTodos, suscribirQuitados } from './quitados.js'

// Los registros quitados de un tipo ('reporte', 'incidente' o 'plan') y cómo quitarlos o volver a mostrarlos.
export function useQuitados(tipo) {
  const quitados = useSyncExternalStore(suscribirQuitados, () => quitadosDe(tipo))
  return {
    quitados,
    quitar: (id) => quitar(tipo, id),
    restaurarTodos: () => restaurarTodos(tipo),
  }
}
