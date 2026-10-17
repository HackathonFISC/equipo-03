import { useEffect, useState } from 'react'
import Icono from '../Iconos.jsx'
import { minutosRestantes } from '../perfil.js'
import banner from '../assets/h2oeste-bienvenida.webp'
import './Cuenta.css'

const hora = new Intl.DateTimeFormat('es-PA', { timeStyle: 'short', timeZone: 'America/Panama' })

function cuantoFalta(minutos) {
  if (minutos === null) return null
  if (minutos < 1) return 'menos de un minuto'
  if (minutos < 60) return `${minutos} min`
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

// Cuenta de quien ya inició sesión: quién es, qué puede hacer y cuánto le dura la sesión.
export default function Cuenta({ perfil, alSalir }) {
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 30000)
    return () => clearInterval(t)
  }, [])
  const falta = minutosRestantes(perfil.vence, ahora)

  return (
    <section className="cuenta" aria-labelledby="cuenta-titulo">
      <header className="cuenta-cabecera">
        <h1 id="cuenta-titulo">Mi cuenta</h1>
        <p>Quién eres en el panel, qué puedes hacer en él y cuánto dura tu sesión.</p>
      </header>

      <div className="cuenta-rejilla">
        <article className="cuenta-tarjeta cuenta-perfil" aria-label="Tu perfil">
          <div className="cuenta-portada"><img src={banner} width="1400" height="781" alt="" /></div>
          <div className="cuenta-identidad">
            <span className="avatar avatar-enorme" aria-hidden="true">{perfil.iniciales}</span>
            <h2>{perfil.nombre}</h2>
            <p className="cuenta-correo">{perfil.correo ?? 'No se pudo leer el correo de la sesión'}</p>
            <p className="cuenta-rol" data-tono={perfil.tono}>{perfil.rol ?? 'Comprobando rol…'}</p>
          </div>
        </article>

        <div className="cuenta-lado">
          <section className="cuenta-tarjeta" aria-labelledby="cuenta-puedes">
            <h2 id="cuenta-puedes">Qué puedes hacer</h2>
            {perfil.rol === null ? (
              <p className="cuenta-nota">Comprobando los permisos de tu cuenta…</p>
            ) : (
              <ul className="cuenta-permisos">
                {perfil.permisos.map((p) => <li key={p} data-tipo="si"><Icono nombre="ok" tamano={18} /><span>{p}</span></li>)}
                {perfil.limites.map((p) => <li key={p} data-tipo="no"><Icono nombre="limite" tamano={18} /><span>{p}</span></li>)}
              </ul>
            )}
            <p className="cuenta-nota">Esto es un resumen. La API vuelve a comprobar tus permisos en cada acción.</p>
          </section>

          <section className="cuenta-tarjeta" aria-labelledby="cuenta-sesion">
            <h2 id="cuenta-sesion">Tu sesión</h2>
            <dl className="cuenta-datos">
              <div>
                <dt>Estado de la cuenta</dt>
                <dd>{perfil.activo === null ? (perfil.rol === null ? 'Comprobando…' : 'Sin comprobar') : perfil.activo ? 'Activa' : 'Pendiente de activación'}</dd>
              </div>
              {perfil.vence !== null && (
                <div>
                  <dt>La sesión vence</dt>
                  <dd>
                    <Icono nombre="reloj" tamano={16} />
                    {falta === 0 ? 'Ya venció' : <>a las {hora.format(new Date(perfil.vence))} <span>(en {cuantoFalta(falta)})</span></>}
                  </dd>
                </div>
              )}
            </dl>
            <p className="cuenta-nota">Cuando venza, el panel te llevará al inicio de sesión. Vuelve a entrar para seguir.</p>
            <div className="cuenta-acciones">
              <a className="cuenta-volver" href="#reportes"><Icono nombre="volver" tamano={18} />Volver al panel</a>
              <button type="button" className="cuenta-cerrar" onClick={alSalir}><Icono nombre="salir" tamano={18} />Cerrar sesión</button>
            </div>
          </section>
        </div>
      </div>
    </section>
  )
}
