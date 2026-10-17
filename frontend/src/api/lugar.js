import { llamarConSesion } from './sesion.js'

// POST /incidentes/{id}/validar-lugar: solo un coordinador activo. La API toma al usuario del token;
// aquí se envía la versión que se revisó y la evidencia escrita.
export function validarLugar(incidenteId, cuerpo) {
  return llamarConSesion(`/incidentes/${encodeURIComponent(incidenteId)}/validar-lugar`, { metodo: 'POST', cuerpo })
}
