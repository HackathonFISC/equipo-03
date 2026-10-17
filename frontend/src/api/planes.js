import { planesEjemplo } from '../datos/planesEjemplo.js'

// true: usa los ejemplos sintéticos (todavía no existe GET /planes). false: lee la API.
export const USAR_EJEMPLOS_PLANES = true

const URL_API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Cada elemento es una PropuestaDistribucion (contratos/modelos.py) más `catalogo`:
// nombres de los puntos, capacidad de cada cisterna y depósito, para no mostrar solo UUID.
export async function obtenerPlanes() {
  if (USAR_EJEMPLOS_PLANES) {
    return planesEjemplo
  }
  let respuesta
  try {
    respuesta = await fetch(`${URL_API}/planes`)
  } catch {
    throw new Error('No se pudo conectar con la API. Comprueba que esté en marcha.')
  }
  if (!respuesta.ok) {
    throw new Error(`La API respondió con el código ${respuesta.status}.`)
  }
  return respuesta.json()
}
