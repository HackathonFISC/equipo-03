import { useEffect, useState } from 'react'
import RutaLocalizada from './RutaLocalizada.jsx'
import { obtenerPlanes, USAR_EJEMPLOS_PLANES } from '../api/planes.js'
import './Plan.css'
import { useQuitados } from '../useQuitados.js'
import { BarraQuitados, BotonQuitar } from '../componentes/Quitar.jsx'

const ESTADO_PLAN = {
  calculando: 'Calculando',
  pendiente_revision: 'Pendiente de revisión',
  aprobado: 'Aprobado',
  rechazado: 'Rechazado',
  invalidado: 'Invalidado',
}

const ESTADO_SOLVER = {
  factible: 'Plan encontrado',
  timeout_sin_solucion: 'Sin plan: se agotó el tiempo de cálculo. Esto no prueba que sea imposible.',
  inviabilidad_demostrada: 'Sin plan: con los datos actuales no se puede entregar agua a ningún punto.',
  error: 'El cálculo terminó con un error.',
  sin_resultado: 'Todavía no hay resultado del cálculo para esta versión.',
}

const MOTIVO_PENDIENTE = {
  sin_capacidad: 'Sin capacidad suficiente',
  demanda_supera_vehiculo: 'La demanda supera una cisterna',
  ventana: 'No cabe en su ventana de entrega',
  sin_acceso: 'Sin acceso en la red de rutas',
  datos_pendientes: 'Faltan datos',
  timeout: 'Se agotó el tiempo de cálculo',
  otro: 'Otro motivo',
}

const REVISION = {
  capacidad: 'Capacidad',
  horario: 'Horarios',
  ventana: 'Ventana de entrega',
  retorno: 'Retorno al depósito',
  asignacion: 'Asignación de paradas',
  demanda: 'Demanda',
  version: 'Versión de los datos',
  cobertura_critica: 'Cobertura crítica',
  otro: 'Otra comprobación',
}

const ORIGEN = { real: 'reales', estimado: 'estimados', sintetico: 'sintéticos' }

const numero = new Intl.NumberFormat('es-PA', { maximumFractionDigits: 0 })
const hora = new Intl.DateTimeFormat('es-PA', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Panama' })
const fecha = new Intl.DateTimeFormat('es-PA', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  timeZone: 'America/Panama',
})

function plural(n, uno, varios) {
  return `${n} ${n === 1 ? uno : varios}`
}

function Id({ valor }) {
  return (
    <code className="id-corto" title={valor}>
      {valor.slice(0, 8)}
    </code>
  )
}

function nombreDelPunto(plan, id) {
  return plan.catalogo?.puntos?.[id]?.nombre ?? null
}

function Verificacion({ plan }) {
  const informe = plan.verificacion
  if (!informe) {
    return (
      <section className="verificacion verificacion-pendiente" aria-label="Verificación">
        <h3>Sin verificar</h3>
        <p>Esta versión no tiene una verificación independiente válida, así que no se puede aprobar.</p>
      </section>
    )
  }
  if (informe.valido) {
    return (
      <section className="verificacion verificacion-ok" aria-label="Verificación">
        <h3>Cumple las restricciones</h3>
        <p>
          El verificador volvió a calcular capacidad, horarios, ventanas, retorno, asignación única, demanda
          completa, versión de los datos y cobertura crítica. No garantiza que sea el mejor plan, ni
          equivale a una aprobación.
        </p>
      </section>
    )
  }
  return (
    <section className="verificacion verificacion-falla" aria-label="Verificación">
      <h3>No cumple las restricciones</h3>
      <p>No se puede aprobar ni publicar esta versión hasta resolver:</p>
      <ul>
        {informe.violaciones.map((v) => (
          <li key={`${v.codigo}-${v.referencia_id ?? v.detalle}`}>
            <strong>{REVISION[v.codigo] ?? v.codigo}:</strong> {v.detalle}
            {v.referencia_id && (
              <>
                {' '}
                (<Id valor={v.referencia_id} />)
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function RutaCisterna({ plan, ruta, numeroCisterna }) {
  const capacidad = plan.catalogo?.vehiculos?.[ruta.vehiculo_id]?.capacidad_litros ?? null
  const carga = ruta.paradas.reduce((suma, p) => suma + p.litros_asignados, 0)
  return (
    <li className="ruta">
      <header className="ruta-cabecera">
        <h3>Cisterna {numeroCisterna}</h3>
        <p className="ruta-horario">
          Sale a las {hora.format(new Date(ruta.salida_estimada))} y regresa al depósito a las{' '}
          {hora.format(new Date(ruta.retorno_estimado))}
        </p>
      </header>
      <p className="ruta-carga">
        <span className="carga-valor">{numero.format(carga)} litros</span>
        {capacidad !== null && <span className="carga-escala"> de {numero.format(capacidad)} de capacidad</span>}
      </p>
      {capacidad !== null && (
        <span className="carga-barra" aria-hidden="true">
          <span style={{ width: `${Math.min(100, (carga / capacidad) * 100)}%` }} />
        </span>
      )}
      {ruta.navegacion_url && (
        <p><a href={ruta.navegacion_url} target="_blank" rel="noopener noreferrer">Abrir recorrido en Google Maps</a></p>
      )}
      {ruta.tramos_navegacion?.length > 0 && (
        <details><summary>Navegar por tramos</summary><ol>
          {ruta.tramos_navegacion.map((url, i) => <li key={url + i}>
            <a href={url} target="_blank" rel="noopener noreferrer">{i === ruta.paradas.length ? 'Regreso al depósito' : `Ir a parada ${i + 1}`}</a>
          </li>)}
        </ol></details>
      )}
      <ol className="paradas">
        {ruta.paradas.map((p) => (
          <li key={p.parada_id} className="parada">
            <span className="parada-orden" aria-label={`Parada ${p.orden}`}>
              {p.orden}
            </span>
            <div className="parada-texto">
              <p className="parada-nombre">
                {nombreDelPunto(plan, p.punto_atencion_id) ?? (
                  <>
                    Punto <Id valor={p.punto_atencion_id} />
                  </>
                )}
              </p>
              <p className="parada-detalle">
                {numero.format(p.litros_asignados)} litros · llega {hora.format(new Date(p.llegada_estimada))} ·
                descarga de {hora.format(new Date(p.inicio_descarga))} a {hora.format(new Date(p.fin_descarga))}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </li>
  )
}

function SinSalida({ plan, rutas }) {
  const usadas = new Set(rutas.map((r) => r.vehiculo_id))
  const sin = Object.entries(plan.catalogo?.vehiculos ?? {}).filter(([id]) => !usadas.has(id))
  if (sin.length === 0) return null
  return (
    <ul className="sin-salida">
      {sin.map(([id, v]) => (
        <li key={id}>
          Cisterna <Id valor={id} />: {v.disponible === false ? 'no disponible' : 'sin salida en este plan'}.
        </li>
      ))}
    </ul>
  )
}

function Pendientes({ plan }) {
  if (plan.no_atendidos.length === 0) return null
  return (
    <section className="pendientes-plan" aria-label="Puntos sin atender">
      <h3>Puntos sin atender</h3>
      <ul>
        {plan.no_atendidos.map((n) => (
          <li key={n.punto_atencion_id} data-clase={n.clase_prioridad ?? 'sin_clase'}>
            <p className="pendiente-nombre">
              {nombreDelPunto(plan, n.punto_atencion_id) ?? (
                <>
                  Punto <Id valor={n.punto_atencion_id} />
                </>
              )}
              {n.clase_prioridad === 'critico' && <span className="sello-critico">Crítico</span>}
            </p>
            <p className="pendiente-detalle">
              {n.demanda_pendiente_litros === null
                ? 'Demanda por confirmar'
                : `${numero.format(n.demanda_pendiente_litros)} litros pendientes`}{' '}
              · {MOTIVO_PENDIENTE[n.codigo] ?? n.codigo}
            </p>
            <p className="pendiente-motivo">{n.motivo}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}

function TarjetaPlan({ plan, alQuitar }) {
  const factible = plan.estado_solver === 'factible'
  const paradas = plan.rutas.flatMap((r) => r.paradas)
  const litros = paradas.reduce((suma, p) => suma + p.litros_asignados, 0)
  const huella = plan.supuestos.find((s) => s.startsWith('HUELLA_ENTRADAS_SHA256='))
  const supuestos = plan.supuestos.filter((s) => s !== huella)
  const estado = ESTADO_PLAN[plan.estado] ?? plan.estado

  return (
    <article className="plan" aria-label={`Plan versión ${plan.version}`}>
      <header className="plan-cabecera">
        <div>
          <h2>Plan versión {plan.version}</h2>
          {plan.ejemplo && <p className="plan-ejemplo">Ejemplo: {plan.ejemplo}</p>}
          <p className="plan-fecha">Calculado el {fecha.format(new Date(plan.creado_en))}</p>
        </div>
        <span className="sello-estado" data-estado={plan.estado}>
          {estado}
        </span>
      </header>

      {!factible && <p className="aviso-solver">{ESTADO_SOLVER[plan.estado_solver] ?? plan.estado_solver}</p>}

      <dl className="resumen">
        <div>
          <dt>Litros asignados</dt>
          <dd>{numero.format(litros)}</dd>
        </div>
        <div>
          <dt>Puntos atendidos</dt>
          <dd>{paradas.length}</dd>
        </div>
        <div>
          <dt>Puntos sin atender</dt>
          <dd>{plan.no_atendidos.length}</dd>
        </div>
        <div>
          <dt>Cisternas en ruta</dt>
          <dd>{plan.rutas.length}</dd>
        </div>
      </dl>

      <Verificacion plan={plan} />

      {plan.bloqueos_publicacion.length > 0 && (
        <section className="bloqueos" aria-label="Pendiente antes de publicar">
          <h3>Pendiente antes de publicar</h3>
          <ul>
            {plan.bloqueos_publicacion.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </section>
      )}

      {plan.rutas.length > 0 && (
        <>
          <h3 className="titulo-rutas">Rutas</h3>
          <ul className="rutas">
            {plan.rutas.map((r, i) => (
              <RutaCisterna key={r.ruta_id ?? r.vehiculo_id} plan={plan} ruta={r} numeroCisterna={i + 1} />
            ))}
          </ul>
          <SinSalida plan={plan} rutas={plan.rutas} />
        </>
      )}
      {plan.rutas.length === 0 && factible && <p className="mensaje">Este plan no incluye ninguna parada.</p>}

      <Pendientes plan={plan} />

      {supuestos.length > 0 && (
        <details className="supuestos-plan">
          <summary>{plural(supuestos.length, 'supuesto', 'supuestos')}</summary>
          <ul>
            {supuestos.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </details>
      )}

      <p className="pie">
        Plan <Id valor={plan.plan_id} />, ejecución <Id valor={plan.ejecucion_id} />, datos{' '}
        {ORIGEN[plan.origen] ?? plan.origen} ({plan.datos_version}), política {plan.politica_version}
        {huella && <>, huella de entradas {huella.split('=')[1].slice(0, 12)}</>}.
      </p>
      <div className="quitar-fila">
        <BotonQuitar tipo="plan" nombre={`Plan versión ${plan.version}`} alConfirmar={alQuitar} />
      </div>
    </article>
  )
}

export default function Plan() {
  const [planes, setPlanes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [sinSesion, setSinSesion] = useState(false)
  const [intento, setIntento] = useState(0)
  const { quitados, quitar, restaurarTodos } = useQuitados('plan')
  const clavePlan = (p) => `${p.plan_id}:${p.version}`
  const vigentes = planes.filter((p) => !quitados.has(clavePlan(p)))
  const cantidadQuitados = planes.length - vigentes.length

  useEffect(() => {
    let cancelado = false
    obtenerPlanes()
      .then((datos) => {
        if (cancelado) return
        setPlanes(datos)
        setError(null)
        setSinSesion(false)
        setCargando(false)
      })
      .catch((e) => {
        if (cancelado) return
        setPlanes([])
        setSinSesion(e.codigo === 'sin_permiso')
        setError(e.message)
        setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [intento])

  function reintentar() {
    setCargando(true)
    setError(null)
    setSinSesion(false)
    setIntento((n) => n + 1)
  }

  return (
    <section className="plan-pagina" aria-labelledby="titulo-plan">
      <header className="plan-pagina-cabecera">
        <span className="seccion-etiqueta">DISTRIBUCIÓN / PROPUESTA</span>
        <div className="plan-pagina-titulo">
          <h1 id="titulo-plan">Plan</h1>
          <button type="button" className="actualizar" onClick={reintentar} disabled={cargando}>
            {cargando ? 'Actualizando…' : 'Actualizar'}
          </button>
        </div>
        <p>Rutas propuestas para las cisternas, con lo que queda sin atender y su verificación.</p>
      </header>

      {!USAR_EJEMPLOS_PLANES && !sinSesion && !cargando && <RutaLocalizada />}

      {USAR_EJEMPLOS_PLANES && (
        <p className="aviso-ejemplos" role="note">
          Datos de ejemplo. Estos planes salen del escenario ficticio y no vienen de la API.
        </p>
      )}

      {cargando && planes.length === 0 && <p className="mensaje">Cargando planes…</p>}

      {error && sinSesion && (
        <div className="mensaje" role="status">
          <p>Para ver los planes guardados hay que iniciar sesión.</p>
          <a className="cuenta-cta" href="#acceso">Ir al inicio de sesión</a>
        </div>
      )}

      {error && !sinSesion && (
        <div className="mensaje mensaje-error" role="alert">
          <p>No se pudieron cargar los planes. {error}</p>
          <button type="button" onClick={reintentar}>
            Reintentar
          </button>
        </div>
      )}

      {!cargando && !error && planes.length === 0 && (
        <p className="mensaje">Todavía no hay planes. Aparecerán cuando se calcule una propuesta.</p>
      )}

      {!cargando && !error && <BarraQuitados cantidad={cantidadQuitados} unidad="plan" plural="planes" alMostrar={restaurarTodos} />}

      {!cargando && !error && vigentes.length > 0 && (
        <div className="lista-planes">
          {vigentes.map((p) => (
            <TarjetaPlan key={`${p.plan_id}-${p.version}-${p.ejemplo ?? ''}`} plan={p} alQuitar={() => quitar(clavePlan(p))} />
          ))}
        </div>
      )}
    </section>
  )
}
