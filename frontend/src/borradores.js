// Borradores del panel: lo que se escribe o se elige en una página se conserva al ir a otra y volver.
// Viven en memoria y, cuando el navegador lo permite, en sessionStorage (solo esta pestaña, se pierden al
// cerrarla). Nunca van a la red. No se usan para contraseñas ni para datos de acceso.
// Al cerrar sesión se descartan todos.

const PREFIJO = 'h2oeste.borrador.'
const memoria = new Map()

function almacen() {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null
  } catch {
    return null
  }
}

export function leerBorrador(clave, inicial) {
  if (memoria.has(clave)) return memoria.get(clave)
  try {
    const crudo = almacen()?.getItem(PREFIJO + clave)
    if (crudo !== null && crudo !== undefined) {
      const valor = JSON.parse(crudo)
      memoria.set(clave, valor)
      return valor
    }
  } catch {
    // Dato ilegible o almacenamiento bloqueado: se parte del valor inicial.
  }
  return inicial
}

export function guardarBorrador(clave, valor) {
  memoria.set(clave, valor)
  try {
    almacen()?.setItem(PREFIJO + clave, JSON.stringify(valor))
  } catch {
    // Sin espacio o bloqueado: queda solo en memoria.
  }
}

export function descartarBorradores() {
  memoria.clear()
  try {
    const guardado = almacen()
    if (!guardado) return
    const claves = []
    for (let i = 0; i < guardado.length; i += 1) {
      const clave = guardado.key(i)
      if (clave?.startsWith(PREFIJO)) claves.push(clave)
    }
    claves.forEach((clave) => guardado.removeItem(clave))
  } catch {
    // Nada más que limpiar.
  }
}
