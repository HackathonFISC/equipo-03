// Registros que el coordinador quitó de su panel (reportes, incidentes y planes).
// Quitar NO borra nada en la base de datos: el registro sigue en el historial y en los cálculos.
// Solo deja de mostrarse en este navegador. Se guarda en localStorage; si el navegador lo bloquea,
// dura lo que dure la página.

const LLAVE = 'h2oeste.quitados'
export const TIPOS = ['reporte', 'incidente', 'plan']

function almacen() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

function cargar() {
  const estado = Object.fromEntries(TIPOS.map((t) => [t, new Set()]))
  try {
    const guardado = JSON.parse(almacen()?.getItem(LLAVE) ?? 'null')
    if (guardado && typeof guardado === 'object') {
      for (const tipo of TIPOS) {
        if (Array.isArray(guardado[tipo])) estado[tipo] = new Set(guardado[tipo].filter((x) => typeof x === 'string'))
      }
    }
  } catch {
    // Dato ilegible: se parte de cero.
  }
  return estado
}

let estado = cargar()
const oyentes = new Set()

function persistir() {
  try {
    almacen()?.setItem(LLAVE, JSON.stringify(Object.fromEntries(TIPOS.map((t) => [t, [...estado[t]]]))))
  } catch {
    // Sin espacio o bloqueado: queda solo en memoria.
  }
}

function cambiar(tipo, conjunto) {
  if (!TIPOS.includes(tipo)) throw new Error(`Tipo desconocido: ${tipo}`)
  estado = { ...estado, [tipo]: conjunto }
  persistir()
  oyentes.forEach((oyente) => oyente())
}

export const quitadosDe = (tipo) => estado[tipo]
export const suscribirQuitados = (oyente) => {
  oyentes.add(oyente)
  return () => oyentes.delete(oyente)
}
export function quitar(tipo, id) {
  if (!id || estado[tipo]?.has(id)) return
  cambiar(tipo, new Set([...estado[tipo], id]))
}
export function restaurar(tipo, id) {
  if (!estado[tipo]?.has(id)) return
  const nuevo = new Set(estado[tipo])
  nuevo.delete(id)
  cambiar(tipo, nuevo)
}
export function restaurarTodos(tipo) {
  if (estado[tipo]?.size) cambiar(tipo, new Set())
}
