import { useState } from 'react'
import { autenticacionConfigurada, iniciarSesion } from '../api/sesion.js'
import './Aprobacion.css'

export default function Acceso({ aviso, alEntrar, conSesion, alSalir }) {
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState(null)
  const [enviando, setEnviando] = useState(false)

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
    <section className="acceso cuenta-pagina" aria-labelledby="acceso-titulo">
      <aside className="acceso-lema" aria-hidden="true">
        <p className="acceso-marca">H2Oeste</p>
        <p className="acceso-frase">Ningún aviso sale a la comunidad sin la firma de un coordinador.</p>
      </aside>
      <div className="acceso-lado">
        {conSesion ? (<div className="acceso-form"><h2 id="acceso-titulo">Mi cuenta</h2><p className="aprob-suave">Tienes una sesión iniciada. Los permisos para decidir se verifican al consultar los planes.</p><button type="button" onClick={alSalir}>Cerrar sesión</button><a className="acceso-volver" href="#reportes">Volver al panel</a></div>) : !autenticacionConfigurada ? (
          <div className="acceso-form">
            <h2 id="acceso-titulo">Acceso sin configurar</h2>
            <p className="aprob-aviso" role="status">
              Falta configurar <code>VITE_SUPABASE_URL</code> y <code>VITE_SUPABASE_ANON_KEY</code> en{' '}
              <code>frontend/.env</code> y reiniciar el panel.
            </p>
            <a className="acceso-volver" href="#reportes">Volver al panel</a>
          </div>
        ) : (
          <form className="acceso-form" onSubmit={enviar}>
            <h2 id="acceso-titulo">Acceso de coordinación</h2>
            <p className="aprob-suave">Inicia sesión para acceder a las funciones de tu cuenta. La autorización para aprobar depende de tu rol.</p>
            {aviso && <p className="aprob-aviso" role="status">{aviso}</p>}
            <label>
              Correo
              <input type="email" autoComplete="username" required value={correo} onChange={(e) => setCorreo(e.target.value)} />
            </label>
            <label>
              Contraseña
              <input
                type="password"
                autoComplete="current-password"
                required
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
              />
            </label>
            {error && <p className="aprob-error" role="alert">{error}</p>}
            <button type="submit" disabled={enviando}>{enviando ? 'Entrando…' : 'Entrar'}</button>
            <a className="acceso-volver" href="#reportes">Volver al panel</a>
          </form>
        )}
      </div>
    </section>
  )
}

