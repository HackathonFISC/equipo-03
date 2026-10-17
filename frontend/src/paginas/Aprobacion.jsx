import { useEffect, useState } from 'react'
import { aprobarPlan, listarPlanes, rechazarPlan } from '../api/aprobacion.js'
import { iniciarSondeo } from '../api/sondeo.js'
import {
  autenticacionConfigurada,
  cerrarSesion,
  iniciarSesion,
  limpiarSesion,
  obtenerSesion,
  obtenerToken,
} from '../api/sesion.js'
import ComunicacionSector from './ComunicacionSector.jsx'
import './Aprobacion.css'

const ESTADOS = {
  calculando: 'Calculando',
  pendiente_revision: 'Pendiente de revisión',
  aprobado: 'Aprobado',
  rechazado: 'Rechazado',
  invalidado: 'Invalidado',
}

const formato = new Intl.DateTimeFormat('es-PA', { dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Panama' })
const horaSola = new Intl.DateTimeFormat('es-PA', { timeStyle: 'short', timeZone: 'America/Panama' })
const hora = (texto) => formato.format(new Date(texto))
const soloHora = (texto) => horaSola.format(new Date(texto))

function Acceso({ aviso, alEntrar }) {
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
    <div className="acceso" role="dialog" aria-modal="true" aria-labelledby="acceso-titulo">
      <aside className="acceso-lema" aria-hidden="true">
        <p className="acceso-marca">RutaAgua Oeste</p>
        <p className="acceso-frase">Ningún aviso sale a la comunidad sin la firma de un coordinador.</p>
      </aside>
      <div className="acceso-lado">
        {!autenticacionConfigurada ? (
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
            <p className="aprob-suave">Aprobar o rechazar un plan es una decisión firmada. Solo entra un coordinador activo.</p>
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
    </div>
  )
}

function Rutas({ rutas }) {
  if (rutas.length === 0) return <p className="aprob-suave">Este plan no tiene rutas.</p>
  return (
    <div className="aprob-rutas">
      {rutas.map((ruta, i) => {
        const litros = ruta.paradas.reduce((suma, p) => suma + p.litros_asignados, 0)
        return (
          <section key={ruta.ruta_id} className="aprob-ruta" aria-label={`Ruta ${i + 1}`}>
            <header>
              <h4>Cisterna {i + 1}</h4>
              <p>
                Sale {hora(ruta.salida_estimada)} · regresa {hora(ruta.retorno_estimado)} ·{' '}
                <strong>{litros.toLocaleString('es-PA')} L</strong> en {ruta.paradas.length} parada{ruta.paradas.length === 1 ? '' : 's'}
              </p>
            </header>
            <ol className="aprob-paradas">
              {ruta.paradas.map((p) => (
                <li key={p.parada_id}>
                  <div>
                    <strong>{p.punto?.nombre ?? 'Punto sin nombre en el catálogo'}</strong>
                    <span>
                      Llega {soloHora(p.llegada_estimada)} · descarga {soloHora(p.inicio_descarga)} a {soloHora(p.fin_descarga)}
                    </span>
                  </div>
                  <b className="aprob-litros">{p.litros_asignados.toLocaleString('es-PA')} L</b>
                </li>
              ))}
            </ol>
          </section>
        )
      })}
    </div>
  )
}

function Decision({ plan, alDecidir }) {
  const [reconocidos, setReconocidos] = useState([])
  const [motivo, setMotivo] = useState('')
  const [confirmando, setConfirmando] = useState(false)
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState(null)

  const todosReconocidos = plan.bloqueos_publicacion.every((b) => reconocidos.includes(b))
  const hayMotivo = motivo.trim().length > 0
  const sePuedeAprobar = plan.verificado && plan.estado_solver === 'factible' && todosReconocidos && hayMotivo

  function alternar(bloqueo) {
    setConfirmando(false)
    setReconocidos((actuales) => (actuales.includes(bloqueo) ? actuales.filter((b) => b !== bloqueo) : [...actuales, bloqueo]))
  }

  async function ejecutar(accion) {
    setTrabajando(true)
    setError(null)
    try {
      await accion()
      alDecidir()
    } catch (e) {
      setError(e.message)
      setConfirmando(false)
    } finally {
      setTrabajando(false)
    }
  }

  return (
    <div className="aprob-decision">
      <h4>Firma del coordinador</h4>
      {plan.bloqueos_publicacion.length > 0 && (
        <fieldset>
          <legend>Reconoce cada bloqueo para poder aprobar</legend>
          {plan.bloqueos_publicacion.map((b) => (
            <label key={b} className="aprob-check">
              <input type="checkbox" checked={reconocidos.includes(b)} onChange={() => alternar(b)} />
              {b}
            </label>
          ))}
        </fieldset>
      )}
      {!plan.verificado && <p className="aprob-error">El plan no tiene verificación independiente válida: no se puede aprobar.</p>}
      <label>
        Motivo de la decisión
        <textarea rows={3} maxLength={4000} value={motivo} onChange={(e) => { setMotivo(e.target.value); setConfirmando(false) }} />
      </label>
      {error && <p className="aprob-error" role="alert">{error}</p>}
      <div className="aprob-botones">
        {confirmando ? (
          <>
            <button type="button" disabled={trabajando} onClick={() => ejecutar(() => aprobarPlan(plan, { motivo: motivo.trim(), bloqueosReconocidos: reconocidos }))}>
              {trabajando ? 'Aprobando…' : `Confirmar aprobación de la versión ${plan.version}`}
            </button>
            <button type="button" className="aprob-secundario" disabled={trabajando} onClick={() => setConfirmando(false)}>Cancelar</button>
          </>
        ) : (
          <>
            <button type="button" disabled={!sePuedeAprobar || trabajando} onClick={() => setConfirmando(true)}>Aprobar plan</button>
            <button type="button" className="aprob-peligro" disabled={!hayMotivo || trabajando} onClick={() => ejecutar(() => rechazarPlan(plan, { motivo: motivo.trim() }))}>
              Rechazar plan
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function TarjetaPlan({ plan, puedeDecidir, alDecidir }) {
  return (
    <article className={`aprob-plan aprob-plan-${plan.estado}`}>
      <header>
        <h3>Plan {plan.plan_id.slice(0, 8)} <small>versión {plan.version}</small></h3>
        <span className={`aprob-estado aprob-estado-${plan.estado}`}>{ESTADOS[plan.estado]}</span>
      </header>
      <dl className="aprob-meta">
        <div><dt>Creado</dt><dd>{hora(plan.creado_en)}</dd></div>
        <div><dt>Datos</dt><dd><code>{plan.datos_version}</code></dd></div>
        <div><dt>Política</dt><dd><code>{plan.politica_version}</code></dd></div>
        <div><dt>Solver</dt><dd>{plan.estado_solver ?? 'sin resultado'}</dd></div>
        <div><dt>Verificación</dt><dd>{plan.verificado ? 'válida' : 'sin verificación válida'}</dd></div>
        <div><dt>Origen</dt><dd>{plan.origen}</dd></div>
      </dl>
      {plan.estado === 'invalidado' && (
        <p className="aprob-error">Cambió una entrada del cálculo después de la aprobación. Hay que calcular una versión nueva.</p>
      )}
      {plan.no_atendidos.length > 0 && <p className="aprob-aviso">{plan.no_atendidos.length} punto(s) sin atender en este plan.</p>}
      {plan.supuestos.length > 0 && (
        <details>
          <summary>Supuestos ({plan.supuestos.length})</summary>
          <ul>{plan.supuestos.map((s) => <li key={s}>{s}</li>)}</ul>
        </details>
      )}
      <Rutas rutas={plan.rutas} />
      {plan.estado === 'pendiente_revision' && puedeDecidir && <Decision plan={plan} alDecidir={alDecidir} />}
      {plan.estado === 'pendiente_revision' && !puedeDecidir && (
        <p className="aprob-suave">Tu cuenta no es coordinador activo: puedes ver el plan, no decidirlo.</p>
      )}
    </article>
  )
}

function Aprobacion() {
  const [conSesion, setConSesion] = useState(() => Boolean(obtenerToken()))
  const [aviso, setAviso] = useState(null)
  const [sesion, setSesion] = useState(null)
  const [planes, setPlanes] = useState(null)
  const [error, setError] = useState(null)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    if (!conSesion) return undefined
    return iniciarSondeo(() => Promise.all([obtenerSesion(), listarPlanes()]), {
      intervalo: 10000,
      onDatos: ([s, p]) => {
        setSesion(s)
        setPlanes(p)
        setError(null)
      },
      onError: (e) => {
        if (e.codigo === 'sin_permiso') {
          limpiarSesion()
          setAviso('Tu sesión venció o no es válida. Inicia sesión de nuevo.')
          setConSesion(false)
        } else {
          setError(e.message)
        }
      },
    })
  }, [conSesion, recarga])

  async function salir() {
    await cerrarSesion()
    setSesion(null)
    setPlanes(null)
    setAviso(null)
    setConSesion(false)
  }

  const ordenados = planes === null ? null : [...planes].sort((a, b) => Number(b.estado === 'pendiente_revision') - Number(a.estado === 'pendiente_revision'))
  const pendientes = planes === null ? 0 : planes.filter((p) => p.estado === 'pendiente_revision').length

  if (!conSesion) {
    return (
      <Acceso aviso={aviso} alEntrar={() => { setAviso(null); setConSesion(true) }} />
    )
  }
  return (
    <section className="aprob">
      <div className="aprob-cabecera">
        <div>
          <h2>Aprobación de planes</h2>
          <p className="aprob-suave">
            {pendientes === 0 ? 'No hay planes esperando decisión.' : `${pendientes} plan${pendientes === 1 ? '' : 'es'} esperando decisión.`}
          </p>
        </div>
        <div className="aprob-sesion">
          <span className={sesion?.es_coordinador ? 'aprob-rol' : 'aprob-rol aprob-rol-lectura'}>
            {sesion === null ? '…' : sesion.es_coordinador ? 'Coordinador activo' : 'Solo lectura'}
          </span>
          <button type="button" className="aprob-secundario" onClick={salir}>Cerrar sesión</button>
        </div>
      </div>
      {error && <p className="aprob-error" role="alert">{error}</p>}
      {planes === null && !error && <p className="aprob-suave">Cargando planes…</p>}
      {planes !== null && planes.length === 0 && <p className="aprob-suave">Todavía no hay planes guardados.</p>}
      {ordenados?.map((plan) => (
        <TarjetaPlan
          key={`${plan.plan_id}-${plan.version}`}
          plan={plan}
          puedeDecidir={sesion?.es_coordinador === true}
          alDecidir={() => setRecarga((n) => n + 1)}
        />
      ))}
      {sesion?.es_coordinador === true && planes !== null && <ComunicacionSector planes={planes} />}
    </section>
  )
}

export default Aprobacion
