import { llamarConSesion } from './sesion.js'

// Los eventos más recientes, del más nuevo al más antiguo (GET /eventos). Exige sesión válida.
export const LIMITE_EVENTOS = 200

export function obtenerEventos() {
  return llamarConSesion(`/eventos?limite=${LIMITE_EVENTOS}`)
}
