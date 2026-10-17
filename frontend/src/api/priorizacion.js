import { llamarConSesion } from './sesion.js'

// POST /ejecuciones/{id}/priorizacion: deja pendiente el lote que revisó el coordinador.
// El servidor arma el lote con los incidentes reales; aquí solo se envía lo que la persona confirmó.
export function prepararPriorizacion(ejecucionId, cuerpo) {
  return llamarConSesion(`/ejecuciones/${encodeURIComponent(ejecucionId)}/priorizacion`, { metodo: 'POST', cuerpo })
}

// GET /ejecuciones/{id} exige sesión. Se usa para saber en qué etapa está una ejecución.
export function consultarEtapa(ejecucionId) {
  return llamarConSesion(`/ejecuciones/${encodeURIComponent(ejecucionId)}`)
}

// GET /politicas: políticas de prioridad activas, para elegirlas en el formulario sin escribir su versión.
export function listarPoliticas() {
  return llamarConSesion('/politicas')
}
