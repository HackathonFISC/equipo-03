import { useEffect, useState } from 'react'
import { aprobarPlan, listarPlanes, rechazarPlan } from '../api/aprobacion.js'
import { iniciarSondeo } from '../api/sondeo.js'
import { limpiarSesion, obtenerSesion } from '../api/sesion.js'
import ComunicacionSector from './ComunicacionSector.jsx'
import './Aprobacion.css'
import { useBorrador } from '../useBorrador.js'

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
  const borrador = `aprobacion.${plan.plan_id}:${plan.version}`
  const [reconocidos, setReconocidos] = useBorrador(`${borrador}.reconocidos`, [])
  const [motivo, setMotivo] = useBorrador(`${borrador}.motivo`, '')
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
      setMotivo('')
      setReconocidos([])
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

function Aprobacion({ conSesion, alExpirar }) {
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
          alExpirar()
        } else {
          setError(e.message)
        }
      },
    })
  }, [conSesion, recarga, alExpirar])


  const ordenados = planes === null ? null : [...planes].sort((a, b) => Number(b.estado === 'pendiente_revision') - Number(a.estado === 'pendiente_revision'))
  const pendientes = planes === null ? 0 : planes.filter((p) => p.estado === 'pendiente_revision').length

  if (!conSesion) {
    return (
      <section className="aprob"><h1>Aprobación de planes</h1><div className="mensaje"><h2>Inicia sesión para revisar los planes</h2><p>{aviso ?? 'La revisión y aprobación requieren una cuenta. Accede desde el área de cuenta del encabezado.'}</p><a className="cuenta-cta" href="#acceso">Ir al inicio de sesión</a></div></section>
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
