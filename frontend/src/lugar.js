// Ayudas para validar el lugar de un incidente en el mapa.
// La clave de Google Maps es de uso público en el navegador (Maps Embed API): hay que restringirla por
// dirección web y por API en Google Cloud, y no debe ser la misma clave que usa el servidor o Gemini.
// Si falta, el panel sigue funcionando: muestra las coordenadas y un enlace a Google Maps (sin clave).

export const CLAVE_MAPS = (import.meta.env?.VITE_GOOGLE_MAPS_API_KEY ?? '').trim()

// Coordenadas del catálogo del punto; null si faltan o no son válidas (nunca se inventan).
export function coordenadasDe(punto) {
  const latitud = Number(punto?.latitud)
  const longitud = Number(punto?.longitud)
  if (punto?.latitud == null || punto?.longitud == null) return null
  if (!Number.isFinite(latitud) || !Number.isFinite(longitud)) return null
  if (Math.abs(latitud) > 90 || Math.abs(longitud) > 180) return null
  return { latitud, longitud }
}

// El lugar espera la validación de una persona: hay punto y el incidente sigue pendiente.
export function lugarPorValidar(item) {
  return item?.estado_validacion === 'pendiente' && Boolean(item?.punto_atencion_id)
}

export function textoCoordenadas({ latitud, longitud }) {
  return `${latitud.toFixed(5)}, ${longitud.toFixed(5)}`
}

// Enlace a Google Maps que no necesita clave.
export function enlaceMapa({ latitud, longitud }) {
  return `https://www.google.com/maps/search/?api=1&query=${latitud}%2C${longitud}`
}

// Mapa incrustado (Maps Embed API). null sin clave o sin coordenadas.
export function urlMapaIncrustado(coordenadas, clave = CLAVE_MAPS) {
  if (!clave || !coordenadas) return null
  const { latitud, longitud } = coordenadas
  return `https://www.google.com/maps/embed/v1/place?key=${encodeURIComponent(clave)}&q=${latitud}%2C${longitud}&zoom=17`
}

export const EVIDENCIA_MIN = 10
export const EVIDENCIA_MAX = 2000
export const evidenciaValida = (texto) => {
  const n = texto.trim().length
  return n >= EVIDENCIA_MIN && n <= EVIDENCIA_MAX
}
