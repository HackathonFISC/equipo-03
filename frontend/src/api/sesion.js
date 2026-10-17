// Sesión del coordinador. El panel inicia sesión directamente con Supabase Auth: la contraseña
// no pasa por nuestra API. A la API solo se le envía el token (Authorization: Bearer).
// Solo se usa la clave pública (anon) de Supabase; nunca una clave de servicio.
const URL_SUPABASE = import.meta.env?.VITE_SUPABASE_URL?.replace(/\/+$/, '')
const CLAVE_PUBLICA = import.meta.env?.VITE_SUPABASE_ANON_KEY
const URL_API = import.meta.env?.VITE_API_URL ?? 'http://localhost:8000'
const LLAVE = 'ra_sesion_token'

export const autenticacionConfigurada = Boolean(URL_SUPABASE && CLAVE_PUBLICA)

let token = null
try {
  token = window.sessionStorage.getItem(LLAVE)
} catch {
  // Sin almacenamiento (ventana privada, bloqueado): la sesión vive solo en memoria.
}

export function obtenerToken() {
  return token
}

function guardarToken(nuevo) {
  token = nuevo
  try {
    if (nuevo) window.sessionStorage.setItem(LLAVE, nuevo)
    else window.sessionStorage.removeItem(LLAVE)
  } catch {
    // Se ignora: la memoria ya tiene el valor correcto.
  }
}

export function limpiarSesion() {
  guardarToken(null)
}

export class ErrorDeApi extends Error {
  constructor(mensaje, codigo) {
    super(mensaje)
    this.codigo = codigo
  }
}

export async function iniciarSesion(correo, contrasena) {
  if (!autenticacionConfigurada) {
    throw new ErrorDeApi('Falta configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en frontend/.env.', 'sin_configurar')
  }
  let respuesta
  try {
    respuesta = await fetch(`${URL_SUPABASE}/auth/v1/token?grant_type=password`, {
      method: 'POST',
      headers: { apikey: CLAVE_PUBLICA, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: correo, password: contrasena }),
    })
  } catch {
    throw new ErrorDeApi('No se pudo conectar con el servicio de inicio de sesión.', 'sin_conexion')
  }
  if (respuesta.status === 400 || respuesta.status === 401) {
    throw new ErrorDeApi('Correo o contraseña incorrectos.', 'credenciales')
  }
  if (!respuesta.ok) {
    throw new ErrorDeApi(`El inicio de sesión falló (código ${respuesta.status}).`, 'proveedor')
  }
  let datos
  try {
    datos = await respuesta.json()
  } catch {
    datos = null
  }
  if (!datos || typeof datos.access_token !== 'string') {
    throw new ErrorDeApi('El servicio de inicio de sesión respondió algo inesperado.', 'proveedor')
  }
  guardarToken(datos.access_token)
}

export async function cerrarSesion() {
  const actual = token
  guardarToken(null)
  if (!actual || !autenticacionConfigurada) return
  try {
    await fetch(`${URL_SUPABASE}/auth/v1/logout`, {
      method: 'POST',
      headers: { apikey: CLAVE_PUBLICA, Authorization: `Bearer ${actual}` },
    })
  } catch {
    // La sesión local ya se borró; si Supabase no respondió, el token vence solo.
  }
}

// Llama a la API con el token. Los errores de dominio (ErrorDominio) se vuelven ErrorDeApi con su código.
export async function llamarConSesion(ruta, { metodo = 'GET', cuerpo } = {}) {
  if (!token) throw new ErrorDeApi('Inicia sesión para continuar.', 'sin_permiso')
  let respuesta
  try {
    respuesta = await fetch(`${URL_API}${ruta}`, {
      method: metodo,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(cuerpo === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    })
  } catch {
    throw new ErrorDeApi('No se pudo conectar con la API. Comprueba que esté en marcha.', 'sin_conexion')
  }
  if (respuesta.ok) return respuesta.json()
  let detalle = null
  try {
    detalle = await respuesta.json()
  } catch {
    // Cuerpo que no es JSON: se usa el mensaje genérico.
  }
  const mensaje = typeof detalle?.mensaje === 'string' ? detalle.mensaje : `La API respondió con el código ${respuesta.status}.`
  throw new ErrorDeApi(mensaje, detalle?.codigo ?? `http_${respuesta.status}`)
}

export const obtenerSesion = () => llamarConSesion('/sesion')
