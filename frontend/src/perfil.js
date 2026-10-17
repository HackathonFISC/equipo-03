// Quién es la persona con sesión, armado con lo que ya sabe el panel: el token (correo y vencimiento)
// y GET /sesion (rol). Solo sirve para mostrar; los permisos reales los verifica siempre la API.

// El token es un JWT: la parte central es JSON en base64url. No se valida aquí (lo hace la API).
export function datosDelToken(token) {
  try {
    const parte = token.split('.')[1]
    const base64 = parte.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(parte.length / 4) * 4, '=')
    const carga = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))))
    return {
      correo: typeof carga.email === 'string' ? carga.email : null,
      vence: Number.isFinite(carga.exp) ? carga.exp * 1000 : null,
    }
  } catch {
    return { correo: null, vence: null }
  }
}

// "noel.echer15@correo.com" -> "Noel Echer"
export function nombreDe(correo) {
  const local = (correo ?? '').split('@')[0]
  const palabras = local.split(/[._-]+/).map((p) => p.replace(/\d+$/, '')).filter(Boolean)
  if (palabras.length === 0) return 'Tu cuenta'
  return palabras.map((p) => p[0].toUpperCase() + p.slice(1)).join(' ')
}

export function inicialesDe(nombre) {
  const palabras = nombre.split(/\s+/).filter(Boolean)
  const letras = palabras.length > 1 ? palabras[0][0] + palabras[1][0] : (palabras[0] ?? '?').slice(0, 2)
  return letras.toUpperCase()
}

const VER = 'Ver reportes, necesidades, planes y eventos.'

// sesion: respuesta de GET /sesion; null mientras llega; false si la consulta falló.
export function perfilDe({ correo, vence }, sesion) {
  const nombre = nombreDe(correo)
  const base = { nombre, correo, iniciales: inicialesDe(nombre), vence, rol: null, tono: 'neutro', activo: null, permisos: [], limites: [] }
  if (sesion === false) {
    return { ...base, rol: 'Rol sin comprobar', tono: 'aviso', limites: ['No se pudo comprobar tu rol. Recarga la página; si sigue igual, avisa a quien administra el sistema.'] }
  }
  if (!sesion) return base
  if (!sesion.rol) {
    return { ...base, rol: 'Sin rol asignado', tono: 'aviso', activo: false, limites: ['Tu cuenta no tiene un rol. Pide a quien administra el sistema que te asigne uno.'] }
  }
  const rol = { coordinador: 'Coordinación', conductor: 'Conductor', consulta: 'Consulta' }[sesion.rol] ?? sesion.rol
  if (sesion.es_coordinador) {
    return {
      ...base, rol, tono: 'ok', activo: true,
      permisos: [VER, 'Revisar y confirmar la prioridad de cada punto.', 'Aprobar y publicar planes de distribución.'],
    }
  }
  if (!sesion.activo) {
    return { ...base, rol, tono: 'aviso', activo: false, limites: ['Tu cuenta todavía no está activa. Pide que la activen para poder decidir.'] }
  }
  return {
    ...base, rol, tono: 'neutro', activo: true,
    permisos: [VER],
    limites: ['No puedes revisar la prioridad ni aprobar planes. Eso lo hace Coordinación.'],
  }
}

// Minutos que le quedan a la sesión; null si no se sabe.
export function minutosRestantes(vence, ahora = Date.now()) {
  return vence === null ? null : Math.max(0, Math.round((vence - ahora) / 60000))
}
