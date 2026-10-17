import { llamarConSesion } from './sesion.js'

const id = encodeURIComponent

// Estado de un sector: plan vigente y situación de cada punto (contrato EstadoSector de Emilia).
export const estadoSector = (sectorId) => llamarConSesion(`/sectores/${id(sectorId)}/estado`)

// Elige el plan aprobado que Comunicación usará en el sector. Quién lo elige sale del token en la API.
export const seleccionarPlanSector = (sectorId, plan, motivo) =>
  llamarConSesion(`/sectores/${id(sectorId)}/plan-vigente`, {
    metodo: 'POST',
    cuerpo: { plan_id: plan.plan_id, version: plan.version, motivo },
  })

// Habilita o deshabilita un destino de Telegram de ensayo (solo recibe planes sintéticos).
export const configurarDestinoEnsayo = (destinoId, habilitado, motivo) =>
  llamarConSesion(`/destinos/${id(destinoId)}/ensayo`, {
    metodo: 'PUT',
    cuerpo: { habilitado, motivo },
  })

// Catálogo de sectores y destinos de Telegram para elegirlos sin pegar identificadores.
export const listarSectores = () => llamarConSesion('/sectores')
export const listarDestinos = () => llamarConSesion('/destinos')
