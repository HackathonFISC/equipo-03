import { useState } from 'react'
import { autenticacionConfigurada, iniciarSesion } from '../api/sesion.js'
import logoCircular from '../assets/h2oeste-circular.webp'
import banner from '../assets/h2oeste-bienvenida.webp'
import paisaje from '../assets/h2oeste-paisaje.webp'
import './Aprobacion.css'
import './Acceso.css'

const RECORRIDO = ['Reporte', 'Prioridad', 'Plan', 'Firma']

function Icono({ nombre }) {
  const trazo = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round' }
  return (
    <svg className="login-icono" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...trazo}>
      {nombre === 'correo' && <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>}
      {nombre === 'clave' && <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>}
      {nombre === 'ojo' && <><path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.6" /></>}
      {nombre === 'ojo-cerrado' && <><path d="M3 3l18 18" /><path d="M10.6 6.1A10 10 0 0 1 12 6c6.4 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.5 7.6A17 17 0 0 0 2 12s3.6 6 10 6c1.5 0 2.8-.3 4-.8" /></>}
      {nombre === 'alerta' && <><circle cx="12" cy="12" r="9" /><path d="M12 7.5v5.5M12 16.5h.01" /></>}
    </svg>
  )
}

// Cuenta de quien ya inició sesión (se abre desde el encabezado del panel).
function MiCuenta({ alSalir }) {
  return (
    <section className="acceso cuenta-pagina" aria-labelledby="acceso-titulo">
      <aside className="acceso-lema" aria-hidden="true">
        <img className="acceso-banner" src={banner} width="1400" height="781" alt="" />
        <p className="acceso-frase">Ningún aviso sale a la comunidad sin la firma de un coordinador.</p>
      </aside>
      <div className="acceso-lado">
        <div className="acceso-form">
          <h2 id="acceso-titulo">Mi cuenta</h2>
          <p className="aprob-suave">Tienes una sesión iniciada. Los permisos para decidir se verifican al consultar los planes.</p>
          <button type="button" onClick={alSalir}>Cerrar sesión</button>
          <a className="acceso-volver" href="#reportes">Volver al panel</a>
        </div>
      </div>
    </section>
  )
}

export default function Acceso({ aviso, alEntrar, conSesion, alSalir }) {
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [verClave, setVerClave] = useState(false)
  const [mayusculas, setMayusculas] = useState(false)
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)

  if (conSesion) return <MiCuenta alSalir={alSalir} />

  async function enviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      await iniciarSesion(correo.trim(), contrasena)
      setContrasena('')
      alEntrar()
    } catch (e) {
      setError(e.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section className="login" aria-labelledby="login-titulo">
      <div className="login-hero">
        <img className="login-foto" src={paisaje} alt="" width="787" height="1536" />
        <div className="login-velo" aria-hidden="true" />
        <div className="login-marca">
          <img src={logoCircular} width="56" height="56" alt="" />
          <p><strong>H2Oeste</strong><span>Sistema de coordinación y logística</span></p>
        </div>
        <div className="login-mensaje">
          <p className="login-lema">Ningún aviso sale a la comunidad sin la firma de un coordinador.</p>
          <ol className="login-ruta" aria-label="Recorrido de un reporte hasta el aviso">
            {RECORRIDO.map((paso) => <li key={paso}>{paso}</li>)}
          </ol>
        </div>
      </div>

      <div className="login-panel">
        {!autenticacionConfigurada ? (
          <div className="login-form">
            <h1 id="login-titulo">Acceso sin configurar</h1>
            <p className="login-error" role="status">
              <Icono nombre="alerta" />
              <span>
                Falta configurar <code>VITE_SUPABASE_URL</code> y <code>VITE_SUPABASE_ANON_KEY</code> en{' '}
                <code>frontend/.env</code> y reiniciar el panel.
              </span>
            </p>
          </div>
        ) : (
          <form className="login-form" onSubmit={enviar}>
            <h1 id="login-titulo">Acceso de coordinación</h1>
            <p className="login-ayuda">Entra con tu cuenta para revisar reportes, confirmar datos y aprobar planes.</p>
            {aviso && <p className="login-aviso" role="status">{aviso}</p>}

            <label className="login-campo">
              <span>Correo</span>
              <span className="login-entrada">
                <Icono nombre="correo" />
                <input
                  type="email" autoComplete="username" autoFocus required value={correo}
                  onChange={(e) => setCorreo(e.target.value)} placeholder="nombre@correo.com"
                />
              </span>
            </label>

            <label className="login-campo">
              <span>Contraseña</span>
              <span className="login-entrada">
                <Icono nombre="clave" />
                <input
                  type={verClave ? 'text' : 'password'} autoComplete="current-password" required value={contrasena}
                  onChange={(e) => setContrasena(e.target.value)}
                  onKeyUp={(e) => setMayusculas(e.getModifierState?.('CapsLock') ?? false)}
                  onBlur={() => setMayusculas(false)}
                />
                <button
                  type="button" className="login-ver" aria-pressed={verClave}
                  aria-label={verClave ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  onClick={() => setVerClave(!verClave)}
                >
                  <Icono nombre={verClave ? 'ojo-cerrado' : 'ojo'} />
                </button>
              </span>
              {mayusculas && <span className="login-nota" role="status">Bloq Mayús está activado.</span>}
            </label>

            {error && (
              <p className="login-error" role="alert"><Icono nombre="alerta" /><span>{error}</span></p>
            )}

            <button className="login-entrar" type="submit" disabled={enviando}>
              {enviando && <span className="login-giro" aria-hidden="true" />}
              {enviando ? 'Entrando…' : 'Entrar'}
            </button>
            <p className="login-pie">Si no puedes entrar, pide ayuda a quien administra tu cuenta.</p>
          </form>
        )}
        <p className="login-lugar">Arraiján, Panamá Oeste</p>
      </div>
    </section>
  )
}
