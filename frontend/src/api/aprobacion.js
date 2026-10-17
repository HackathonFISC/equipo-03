import { llamarConSesion } from './sesion.js'

// Versiones de plan guardadas (GET /planes), con rutas, paradas y bloqueos.
export const listarPlanes = () => llamarConSesion('/planes')

// Quién aprueba sale del token en la API; aquí solo va lo que la persona revisó.
export const aprobarPlan = (plan, { motivo, bloqueosReconocidos }) =>
  llamarConSesion(`/planes/${encodeURIComponent(plan.plan_id)}/versiones/${plan.version}/aprobar`, {
    metodo: 'POST',
    cuerpo: {
      datos_version: plan.datos_version,
      politica_version: plan.politica_version,
      motivo,
      bloqueos_reconocidos: bloqueosReconocidos,
    },
  })

export const rechazarPlan = (plan, { motivo }) =>
  llamarConSesion(`/planes/${encodeURIComponent(plan.plan_id)}/versiones/${plan.version}/rechazar`, {
    metodo: 'POST',
    cuerpo: { motivo },
  })
