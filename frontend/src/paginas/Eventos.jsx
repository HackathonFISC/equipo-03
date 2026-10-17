import { useEffect, useMemo, useRef, useState } from 'react'
import { LIMITE_EVENTOS, obtenerEventos } from '../api/eventos.js'
import { iniciarSondeo } from '../api/sondeo.js'
import './Eventos.css'
import { useBorrador } from '../useBorrador.js'

// Cada agente tiene una sola tarea. Se dice con palabras de quien opera, no con el nombre técnico.
const AGENTES = {
  ingesta: { nombre: 'Ingesta', tarea: 'Lee el mensaje y saca los datos' },
  territorial: { nombre: 'Territorial', tarea: 'Ubica el lugar y agrupa reportes' },
  priorizacion: { nombre: 'Priorización', tarea: 'Calcula cuánta agua hace falta y a quién atender primero' },
  planificacion: { nombre: 'Planificación', tarea: 'Arma las rutas de las cisternas' },
  comunicacion: { nombre: 'Comunicación', tarea: 'Avisa a los sectores' },
}

const PERSONAS = {
  coordinador: 'Coordinación',
  conductor: 'Conductor',
  sistema: 'Sistema',
}

const ORDEN_FILTROS = ['todos', 'ingesta', 'territorial', 'priorizacion', 'planificacion', 'comunicacion', 'personas']

const ESTADOS = {
  pendiente: 'Pendiente',
  ejecutando: 'En proceso',
  espera_aclaracion: 'Espera una aclaración',
  espera_validacion: 'Espera una validación',
  espera_revision: 'Espera una revisión',
  completada: 'Completada',
  fallida: 'Falló',
}

const ORIGENES = { real: 'Real', estimado: 'Estimado', sintetico: 'Sintético' }

const formatoHora = new Intl.DateTimeFormat('es-PA', { timeStyle: 'medium', timeZone: 'America/Panama' })
const formatoDia = new Intl.DateTimeFormat('es', { day: 'numeric', month: 'short', timeZone: 'America/Panama' })

// Un evento es de un agente o de una persona (coordinación, conductor) o del sistema.
function quienDe(evento) {
  if (evento.agente && AGENTES[evento.agente]) return AGENTES[evento.agente]
  return { nombre: PERSONAS[evento.actor_tipo] ?? evento.actor_tipo, tarea: null }
}

function grupoDe(evento) {
  return evento.actor_tipo === 'agente' && evento.agente ? evento.agente : 'personas'
}

function duracion(ms) {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toLocaleString('es-PA', { maximumFractionDigits: 1 })} s`
}

// Lo que más importa de un evento: ¿pide la mano de una persona o falló?
function atencionDe(evento) {
  if (evento.siguiente_estado === 'fallida') return 'fallo'
  if (evento.siguiente_estado?.startsWith('espera_')) return 'espera'
  return null
}

function corto(id) {
  return id.slice(0, 8)
}

function Evento({ evento, nuevo, enfocado, alEnfocar }) {
  const quien = quienDe(evento)
  const atencion = atencionDe(evento)
  const clases = ['evento', nuevo ? 'evento-nuevo' : ''].filter(Boolean).join(' ')
  return (
    <li className={clases} data-grupo={grupoDe(evento)} data-atencion={atencion ?? undefined}>
      <div className="evento-cuando">
        <time dateTime={evento.creado_en}>{formatoHora.format(new Date(evento.creado_en))}</time>
        <span>{formatoDia.format(new Date(evento.creado_en))}</span>
      </div>
      <div className="evento-cuerpo">
        <p className="evento-quien">
          <strong>{quien.nombre}</strong>
          {quien.tarea && <span>{quien.tarea}</span>}
        </p>
        <p className="evento-decision">{evento.decision}</p>
        <p className="evento-resultado">{evento.resultado}</p>
        <ul className="evento-datos" aria-label="Detalles del evento">
          {evento.herramienta && <li>Herramienta: <code>{evento.herramienta}</code></li>}
          <li>Tardó {duracion(evento.duracion_ms)}</li>
          {evento.siguiente_estado && (
            <li className="evento-estado" data-atencion={atencion ?? undefined}>
              Después: {ESTADOS[evento.siguiente_estado] ?? evento.siguiente_estado}
            </li>
          )}
          <li>Origen: {ORIGENES[evento.origen] ?? evento.origen}</li>
          <li>
            <button type="button" className="enlace" aria-pressed={enfocado} onClick={() => alEnfocar(evento.ejecucion_id)}>
              {enfocado ? 'Ver todas las ejecuciones' : `Seguir ejecución ${corto(evento.ejecucion_id)}`}
            </button>
          </li>
        </ul>
      </div>
    </li>
  )
}

export default function Eventos({ alExpirar }) {
  const [eventos, setEventos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [enVivo, setEnVivo] = useState(true)
  const [filtro, setFiltro] = useBorrador('eventos.filtro', 'todos')
  const [ejecucion, setEjecucion] = useState('')
  const [intento, setIntento] = useState(0)
  const [actualizado, setActualizado] = useState(null)
  // Ids ya mostrados: lo que llega después se resalta un momento.
  const vistos = useRef(null)
  const [nuevos, setNuevos] = useState(() => new Set())

  useEffect(() => {
    if (!enVivo) return
    return iniciarSondeo(obtenerEventos, {
      onDatos: (datos) => {
        const ids = new Set(datos.map((e) => e.evento_id))
        if (vistos.current) setNuevos(new Set([...ids].filter((id) => !vistos.current.has(id))))
        vistos.current = ids
        setEventos(datos)
        setActualizado(new Date())
        setError(null)
        setCargando(false)
      },
      onError: (e) => {
        if (e.codigo === 'sin_permiso') alExpirar?.()
        setError(e.message)
        setCargando(false)
      },
    })
  }, [enVivo, intento, alExpirar])

  function reintentar() {
    setCargando(true)
    setError(null)
    setIntento((n) => n + 1)
  }

  const deLaEjecucion = useMemo(
    () => (ejecucion ? eventos.filter((e) => e.ejecucion_id === ejecucion) : eventos),
    [eventos, ejecucion],
  )

  const conteos = useMemo(() => {
    const c = Object.fromEntries(ORDEN_FILTROS.map((f) => [f, 0]))
    for (const e of deLaEjecucion) {
      c.todos += 1
      c[grupoDe(e)] += 1
    }
    return c
  }, [deLaEjecucion])

  const visibles = filtro === 'todos' ? deLaEjecucion : deLaEjecucion.filter((e) => grupoDe(e) === filtro)

  const ejecuciones = useMemo(() => {
    const porId = new Map()
    for (const e of eventos) {
      const previo = porId.get(e.ejecucion_id)
      porId.set(e.ejecucion_id, { id: e.ejecucion_id, total: (previo?.total ?? 0) + 1, ultimo: previo?.ultimo ?? e.creado_en })
    }
    return [...porId.values()]
  }, [eventos])

  const esperan = deLaEjecucion.filter((e) => atencionDe(e) === 'espera').length
  const fallos = deLaEjecucion.filter((e) => atencionDe(e) === 'fallo').length
  const hayFiltros = filtro !== 'todos' || ejecucion !== ''

  function quitarFiltros() {
    setFiltro('todos')
    setEjecucion('')
  }

  function enfocar(id) {
    setEjecucion((actual) => (actual === id ? '' : id))
    setFiltro('todos')
  }

  return (
    <section className="eventos" aria-labelledby="titulo-eventos">
      <header className="eventos-cabecera">
        <span className="seccion-etiqueta">TRAZABILIDAD / DECISIONES</span>
        <h1 id="titulo-eventos">Qué decidió cada agente</h1>
        <p>
          Cada paso de un agente, de una herramienta o de una persona queda anotado aquí, con su resultado. Sirve para
          comprobar por qué el sistema hizo lo que hizo.
        </p>
      </header>

      <div className="eventos-estado" role="status" aria-live="polite">
        <span className="eventos-vivo" data-activo={enVivo && !error ? 'si' : 'no'}>
          {enVivo ? (error ? 'Sin conexión' : 'Actualizando cada 5 s') : 'Actualización en pausa'}
        </span>
        {actualizado && <span>Última lectura {formatoHora.format(actualizado)}</span>}
        <button type="button" className="eventos-pausa" onClick={() => setEnVivo((v) => !v)} aria-pressed={!enVivo}>
          {enVivo ? 'Pausar' : 'Reanudar'}
        </button>
      </div>

      {cargando && <p className="eventos-nota" role="status">Cargando eventos…</p>}

      {error && (
        <div className="eventos-error" role="alert">
          <p>No se pudieron cargar los eventos. {error}</p>
          <button type="button" onClick={reintentar}>Reintentar</button>
        </div>
      )}

      {!cargando && !error && eventos.length === 0 && (
        <div className="eventos-vacio">
          <h2>Todavía no hay eventos</h2>
          <p>Aparecen cuando llega un reporte y un agente empieza a procesarlo. Envía un mensaje de prueba al bot y vuelve aquí.</p>
        </div>
      )}

      {eventos.length > 0 && (
        <>
          <dl className="eventos-resumen" aria-label="Resumen de eventos">
            <div><dt>Eventos {ejecucion ? 'de la ejecución' : 'recientes'}</dt><dd>{conteos.todos}</dd></div>
            <div className={esperan ? 'resumen-atencion' : undefined}><dt>Esperan a una persona</dt><dd>{esperan}</dd></div>
            <div className={fallos ? 'resumen-fallo' : undefined}><dt>Con fallo</dt><dd>{fallos}</dd></div>
          </dl>

          <fieldset className="eventos-filtros">
            <legend>Quién lo hizo</legend>
            <div className="eventos-chips">
              {ORDEN_FILTROS.map((id) => (
                <button key={id} type="button" className="chip-evento" aria-pressed={filtro === id} onClick={() => setFiltro(id)}>
                  {id === 'todos' ? 'Todos' : id === 'personas' ? 'Personas' : AGENTES[id].nombre}
                  <span className="chip-conteo">{conteos[id]}</span>
                </button>
              ))}
            </div>
            <label className="eventos-ejecucion">
              <span>Seguir una ejecución</span>
              <select value={ejecucion} onChange={(e) => { setEjecucion(e.target.value); setFiltro('todos') }}>
                <option value="">Todas ({ejecuciones.length})</option>
                {ejecuciones.map((x) => (
                  <option key={x.id} value={x.id}>
                    {corto(x.id)} · {x.total} {x.total === 1 ? 'evento' : 'eventos'} · {formatoHora.format(new Date(x.ultimo))}
                  </option>
                ))}
              </select>
            </label>
            {hayFiltros && <button type="button" className="enlace" onClick={quitarFiltros}>Quitar filtros</button>}
          </fieldset>

          {visibles.length === 0 ? (
            <p className="eventos-nota">Ningún evento coincide con estos filtros. <button type="button" className="enlace" onClick={quitarFiltros}>Quitar filtros</button></p>
          ) : (
            <ol className="eventos-lista" aria-label="Eventos, del más reciente al más antiguo">
              {visibles.map((e) => (
                <Evento key={e.evento_id} evento={e} nuevo={nuevos.has(e.evento_id)} enfocado={ejecucion === e.ejecucion_id} alEnfocar={enfocar} />
              ))}
            </ol>
          )}
          <p className="eventos-pie">
            Se muestran los últimos {LIMITE_EVENTOS} eventos, del más reciente al más antiguo. El texto de las personas y los datos internos de los agentes no aparecen aquí.
          </p>
        </>
      )}
    </section>
  )
}
