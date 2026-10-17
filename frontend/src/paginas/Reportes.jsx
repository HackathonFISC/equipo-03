import { useEffect, useMemo, useState } from 'react'
import { obtenerEjecucion, obtenerReportes, USAR_EJEMPLOS } from '../api/reportes.js'
import { iniciarSondeo } from '../api/sondeo.js'
import './Reportes.css'
import { useBorrador } from '../useBorrador.js'
import { useQuitados } from '../useQuitados.js'
import { BarraQuitados, BotonQuitar } from '../componentes/Quitar.jsx'

// Estado que ve la persona operadora. Se deriva de la interpretación;
// el contrato no guarda un campo "estado" para los reportes.
const ESTADOS = {
  interpretado: { etiqueta: 'Interpretado', ayuda: 'Datos suficientes para evaluar' },
  aclaracion: { etiqueta: 'Necesita aclaración', ayuda: 'Falta información del remitente' },
  sin_interpretar: { etiqueta: 'Sin interpretar', ayuda: 'Aún no se analiza el mensaje' },
  fuera_de_alcance: { etiqueta: 'Fuera de alcance', ayuda: 'No es falta de agua en un punto' },
}

const FILTROS = ['todos', 'interpretado', 'aclaracion', 'sin_interpretar', 'fuera_de_alcance']

// Filtro por hora de llegada del mensaje (hora de Panamá, UTC−5 todo el año).
const RANGOS = [
  { id: 'todo', etiqueta: 'Cualquier hora' },
  { id: '15m', etiqueta: 'Últimos 15 min', minutos: 15 },
  { id: '1h', etiqueta: 'Última hora', minutos: 60 },
  { id: 'hoy', etiqueta: 'Hoy' },
  { id: 'personalizado', etiqueta: 'Elegir horas' },
]

const formatoDia = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Panama' })

function inicioDeHoy(ahora) {
  return new Date(`${formatoDia.format(ahora)}T00:00:00-05:00`).getTime()
}

// Devuelve [desde, hasta] en milisegundos; null = sin límite.
function limitesDe(rango, desde, hasta, ahora) {
  if (rango === 'hoy') return [inicioDeHoy(ahora), null]
  if (rango === 'personalizado') {
    return [desde ? new Date(`${desde}:00-05:00`).getTime() : null, hasta ? new Date(`${hasta}:59-05:00`).getTime() : null]
  }
  const r = RANGOS.find((x) => x.id === rango)
  return r?.minutos ? [ahora - r.minutos * 60000, null] : [null, null]
}

const ORIGENES = { real: 'Real', estimado: 'Estimado', sintetico: 'Sintético' }

const TIPOS_PROBLEMA = {
  sin_suministro: 'Sin suministro',
  intermitencia: 'Intermitencia',
  otro: 'Otro',
  desconocido: 'Desconocido',
}

const ESTADOS_EJECUCION = {
  pendiente: 'pendiente',
  ejecutando: 'en proceso',
  espera_aclaracion: 'esperando aclaración',
  espera_validacion: 'esperando validación',
  espera_revision: 'esperando revisión',
  completada: 'completada',
  fallida: 'falló',
}

const ETAPAS = {
  ingesta: 'Ingesta',
  territorial: 'Territorial',
  priorizacion: 'Priorización',
  planificacion: 'Planificación',
  comunicacion: 'Comunicación',
  terminada: 'Terminada',
}

const AGENTES = {
  ingesta: 'Ingesta',
  territorial: 'Territorial',
  priorizacion: 'Priorización',
  planificacion: 'Planificación',
  comunicacion: 'Comunicación',
}

const formatoHora = new Intl.DateTimeFormat('es-PA', {
  timeStyle: 'medium',
  timeZone: 'America/Panama',
})

const formatoFecha = new Intl.DateTimeFormat('es-PA', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Panama',
})

function estadoDe(item) {
  const interpretacion = item.interpretado?.interpretacion
  if (!interpretacion) return 'sin_interpretar'
  if (interpretacion.fuera_de_alcance) return 'fuera_de_alcance'
  if (interpretacion.requiere_aclaracion) return 'aclaracion'
  return 'interpretado'
}

// Un dato desconocido (null) se muestra como "No indicado". Nunca como 0.
function mostrar(valor, unidad) {
  if (valor === null || valor === undefined || valor === '') return 'No indicado'
  return unidad ? `${valor} ${unidad}` : String(valor)
}

function Campo({ nombre, valor }) {
  const sinDato = valor === 'No indicado'
  return (
    <div className="campo">
      <dt>{nombre}</dt>
      <dd className={sinDato ? 'campo-vacio' : undefined}>{valor}</dd>
    </div>
  )
}

function segundos(ms) {
  return `${(ms / 1000).toLocaleString('es-PA', { maximumFractionDigits: 1 })} s`
}

// La fila abierta consulta periódicamente la traza de su ejecución.
function Seguimiento({ ejecucionId, seguimiento, traza, onReintentar }) {
  return (
    <div className="seguimiento">
      <h3>Seguimiento</h3>
      {seguimiento && (
        <p className="seguimiento-estado">
          Etapa actual: <strong>{ETAPAS[seguimiento.etapa] ?? seguimiento.etapa}</strong> (
          {ESTADOS_EJECUCION[seguimiento.estado] ?? seguimiento.estado}).
        </p>
      )}
      {traza.estado === 'cargando' && <p className="traza-nota">Cargando decisiones de los agentes…</p>}
      {traza.estado === 'error' && (
        <p className="traza-nota">
          No se pudo cargar la traza. {traza.error}{' '}
          <button type="button" className="enlace" onClick={onReintentar}>
            Reintentar
          </button>
        </p>
      )}
      {traza.estado === 'listo' && traza.datos.eventos.length === 0 && (
        <p className="traza-nota">Ningún agente ha procesado este reporte todavía.</p>
      )}
      {traza.estado === 'listo' && traza.datos.eventos.length > 0 && (
        <ol className="traza" aria-label={`Decisiones de la ejecución ${ejecucionId}`}>
          {traza.datos.eventos.map((e) => (
            <li key={e.evento_id}>
              <p className="traza-decision">
                <strong>{AGENTES[e.agente] ?? e.actor_tipo}</strong>: {e.decision}
              </p>
              <p className="traza-resultado">{e.resultado}</p>
              <p className="traza-meta">
                <time dateTime={e.creado_en}>{formatoHora.format(new Date(e.creado_en))}</time>, en{' '}
                {segundos(e.duracion_ms)}
                {e.herramienta ? `, con ${e.herramienta}` : ''}.
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function FilaReporte({ item, alQuitar }) {
  const { registrado, interpretado, seguimiento, localizacion_resuelta: localizacion } = item
  const ubicacion = item.ubicacion_reportada ?? localizacion?.ubicacion
  const esGoogle = ubicacion?.fuente === 'geocodificada'
  const estado = estadoDe(item)
  const interpretacion = interpretado?.interpretacion ?? null
  const campos = interpretacion?.campos
  const ejecucionId = registrado.ejecucion_id
  const [traza, setTraza] = useState({ estado: 'inactivo' })
  const [abierto, setAbierto] = useState(false)

  useEffect(() => {
    if (!abierto || !ejecucionId || USAR_EJEMPLOS) return
    return iniciarSondeo(() => obtenerEjecucion(ejecucionId), {
      onDatos: (datos) => setTraza({ estado: 'listo', datos }),
      onError: (e) => setTraza({ estado: 'error', error: e.message }),
    })
  }, [abierto, ejecucionId])

  function cargarTraza() {
    setTraza({ estado: 'cargando' })
    obtenerEjecucion(ejecucionId)
      .then((datos) => setTraza({ estado: 'listo', datos }))
      .catch((e) => setTraza({ estado: 'error', error: e.message }))
  }

  function alAbrir(evento) {
    setAbierto(evento.currentTarget.open)
  }

  return (
    <li className="reporte" data-estado={estado}>
      <details onToggle={alAbrir}>
        <summary>
          <span className="reporte-texto">{registrado.entrada.texto}</span>
          <span className="reporte-meta">
            <span className="sello" data-estado={estado}>
              {ESTADOS[estado].etiqueta}
            </span>
            <time dateTime={registrado.creado_en}>
              {formatoFecha.format(new Date(registrado.creado_en))}
            </time>
          </span>
        </summary>

        <div className="ficha">
          {ubicacion && (
            <div className="evidencia">
              <h3>{localizacion ? 'Ubicación resuelta automáticamente' : 'Ubicación recibida por Telegram'}</h3>
              <p>{ubicacion.latitud.toFixed(6)}, {ubicacion.longitud.toFixed(6)}
                {ubicacion.precision_metros != null && ` · Precisión informada: ${ubicacion.precision_metros} m`}
              </p>
              <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${ubicacion.latitud},${ubicacion.longitud}`)}`}
                target="_blank" rel="noopener noreferrer">Ver ubicación en el mapa</a>
              {esGoogle && <p translate="no" style={{ fontFamily: 'sans-serif', fontSize: '14px', fontWeight: 400 }}>Google Maps</p>}
              <p>{localizacion ? 'El reporte ya está localizado; no requiere revisión de ubicación.' : 'El reporte se localizará automáticamente al procesar el pin.'}</p>
            </div>
          )}
          {!ubicacion && localizacion?.place_id && (
            <div className="evidencia">
              <h3>Ubicación resuelta automáticamente</h3>
              <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(interpretacion?.ubicacion_declarada ?? 'Ubicación')}&query_place_id=${encodeURIComponent(localizacion.place_id)}`}
                target="_blank" rel="noopener noreferrer">Ver ubicación en Google Maps</a>
            </div>
          )}
          {interpretacion ? (
            <>
              <p className="ficha-resumen">{interpretacion.resumen}</p>
              <dl className="campos">
                <Campo nombre="Ubicación declarada" valor={mostrar(interpretacion.ubicacion_declarada)} />
                <Campo nombre="Tipo de problema" valor={TIPOS_PROBLEMA[campos.tipo_problema] ?? 'No indicado'} />
                <Campo nombre="Horas sin agua" valor={mostrar(campos.horas_sin_agua, 'h')} />
                <Campo nombre="Personas afectadas" valor={mostrar(campos.personas_afectadas)} />
                <Campo nombre="Institución" valor={mostrar(campos.institucion_declarada)} />
                <Campo nombre="Vulnerabilidad declarada" valor={mostrar(campos.vulnerabilidad_declarada)} />
              </dl>
              {interpretacion.faltantes.length > 0 && (
                <div className="faltantes">
                  <h3>Falta por aclarar</h3>
                  <ul>
                    {interpretacion.faltantes.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}
              {interpretacion.evidencia_textual.length > 0 && (
                <div className="evidencia">
                  <h3>Frases que sustentan la lectura</h3>
                  {interpretacion.evidencia_textual.map((e) => (
                    <blockquote key={e}>{e}</blockquote>
                  ))}
                </div>
              )}
            </>
          ) : (
            <p className="ficha-resumen">{ESTADOS[estado].ayuda}. Este reporte ya quedó guardado.</p>
          )}
          {ejecucionId && !USAR_EJEMPLOS && (
            <Seguimiento
              ejecucionId={ejecucionId}
              seguimiento={seguimiento}
              traza={traza}
              onReintentar={cargarTraza}
            />
          )}
          <p className="ficha-pie">
            Canal {registrado.entrada.canal}. Origen: {ORIGENES[registrado.origen] ?? registrado.origen}.
          </p>
        </div>
      </details>
      <div className="quitar-fila">
        <BotonQuitar tipo="reporte" nombre={registrado.entrada.texto.slice(0, 160)} alConfirmar={alQuitar} />
      </div>
    </li>
  )
}

export default function Reportes() {
  const [recibidos, setReportes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [sinSesion, setSinSesion] = useState(false)
  const [filtro, setFiltro] = useBorrador('reportes.filtro', 'todos')
  const [intento, setIntento] = useState(0)
  const [rango, setRango] = useBorrador('reportes.rango', 'todo')
  const [desde, setDesde] = useBorrador('reportes.desde', '')
  const [hasta, setHasta] = useBorrador('reportes.hasta', '')
  const [orden, setOrden] = useBorrador('reportes.orden', 'recientes')
  // "Ahora" se refresca con cada consulta, para que "Últimos 15 min" se mueva solo.
  const [ahora, setAhora] = useState(() => Date.now())
  const { quitados, quitar, restaurarTodos } = useQuitados('reporte')
  const reportes = useMemo(() => recibidos.filter((r) => !quitados.has(r.registrado.reporte_id)), [recibidos, quitados])
  const cantidadQuitados = recibidos.length - reportes.length

  useEffect(() => {
    return iniciarSondeo(obtenerReportes, {
      onDatos: (datos) => {
        setAhora(Date.now())
        setReportes(datos)
        setSinSesion(false)
        setError(null)
        setCargando(false)
      },
      onError: (e) => {
        setSinSesion(e.codigo === 'sin_permiso')
        if (e.codigo === 'sin_permiso') setReportes([])
        setError(e.message)
        setCargando(false)
      },
      intervalo: USAR_EJEMPLOS ? null : 5000,
    })
  }, [intento])

  function reintentar() {
    setCargando(true)
    setError(null)
    setIntento((n) => n + 1)
  }

  const [limiteInicio, limiteFin] = limitesDe(rango, desde, hasta, ahora)
  const ordenados = useMemo(() => {
    const lista = reportes.filter((r) => {
      const t = new Date(r.registrado.creado_en).getTime()
      return (limiteInicio === null || t >= limiteInicio) && (limiteFin === null || t <= limiteFin)
    })
    const signo = orden === 'recientes' ? -1 : 1
    return lista.sort((a, b) => signo * (new Date(a.registrado.creado_en) - new Date(b.registrado.creado_en)))
  }, [reportes, limiteInicio, limiteFin, orden])

  const conteos = useMemo(() => {
    const c = { todos: ordenados.length, interpretado: 0, aclaracion: 0, sin_interpretar: 0, fuera_de_alcance: 0 }
    for (const item of ordenados) c[estadoDe(item)] += 1
    return c
  }, [ordenados])

  const visibles = filtro === 'todos' ? ordenados : ordenados.filter((i) => estadoDe(i) === filtro)
  const hayFiltroDeTiempo = rango !== 'todo'
  const rangoInvalido = rango === 'personalizado' && desde && hasta && hasta < desde

  function quitarFiltros() {
    setRango('todo')
    setDesde('')
    setHasta('')
    setFiltro('todos')
  }

  return (
    <section className="reportes" aria-labelledby="titulo-reportes">
      <header className="reportes-cabecera">
        <span className="seccion-etiqueta">COMUNIDAD / RECEPCIÓN</span>
        <h1 id="titulo-reportes">Reportes recibidos</h1>
        <p>Mensajes de la comunidad. Filtra por la hora en que llegaron para ir revisándolos por tandas.</p>
      </header>

      {!cargando && !error && reportes.length > 0 && (
        <dl className="bandeja-resumen" aria-label="Resumen de reportes recibidos">
          <div><dt>Reportes recibidos</dt><dd>{reportes.length}</dd></div>
          <div><dt>Interpretados</dt><dd>{reportes.filter((i) => estadoDe(i) === 'interpretado').length}</dd></div>
          <div className="resumen-atencion"><dt>Necesitan aclaración</dt><dd>{reportes.filter((i) => estadoDe(i) === 'aclaracion').length}</dd></div>
        </dl>
      )}

      {USAR_EJEMPLOS && (
        <p className="aviso-ejemplos" role="note">
          Datos de ejemplo. Los reportes de esta lista son sintéticos y no vienen de la API.
        </p>
      )}

      <fieldset className="tiempo">
        <legend>Hora de llegada</legend>
        <div className="tiempo-chips">
          {RANGOS.map((r) => (
            <button key={r.id} type="button" className="chip-tiempo" aria-pressed={rango === r.id} onClick={() => setRango(r.id)}>
              {r.etiqueta}
            </button>
          ))}
        </div>
        {rango === 'personalizado' && (
          <div className="tiempo-rango">
            <label>Desde<input type="datetime-local" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
            <label>Hasta<input type="datetime-local" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
            <p className="tiempo-nota">Hora de Panamá. Deja uno vacío para no poner límite.</p>
          </div>
        )}
        {rangoInvalido && <p className="tiempo-error" role="alert">La hora final es anterior a la inicial: no puede haber reportes en ese rango.</p>}
        <label className="tiempo-orden">
          Orden
          <select value={orden} onChange={(e) => setOrden(e.target.value)}>
            <option value="recientes">Más recientes primero</option>
            <option value="antiguos">Más antiguos primero</option>
          </select>
        </label>
      </fieldset>

      <p className="tiempo-resumen" role="status">
        Mostrando {visibles.length} de {reportes.length} reportes
        {hayFiltroDeTiempo ? ' en la hora elegida' : ''}.
        {(hayFiltroDeTiempo || filtro !== 'todos') && <> <button type="button" className="enlace" onClick={quitarFiltros}>Quitar filtros</button></>}
      </p>

      <div className="filtros" role="group" aria-label="Filtrar por estado">
        {FILTROS.map((f) => (
          <button
            key={f}
            type="button"
            className="filtro"
            aria-pressed={filtro === f}
            onClick={() => setFiltro(f)}
          >
            {f === 'todos' ? 'Todos' : ESTADOS[f].etiqueta}
            <span className="filtro-conteo">{conteos[f]}</span>
          </button>
        ))}
      </div>

      {cargando && <p className="mensaje">Cargando reportes…</p>}

      {error && (
        <div className="mensaje mensaje-error" role="alert">
          <p>No se pudieron cargar los reportes. {error}</p>
          {sinSesion ? (
            <a className="cuenta-cta" href="#acceso">Ir al inicio de sesión</a>
          ) : (
            <button type="button" onClick={reintentar}>Reintentar</button>
          )}
        </div>
      )}

      {!cargando && !error && <BarraQuitados cantidad={cantidadQuitados} unidad="reporte" plural="reportes" alMostrar={restaurarTodos} />}

      {!cargando && !error && visibles.length === 0 && (
        <p className="mensaje">
          {recibidos.length === 0
            ? 'Todavía no hay reportes. Aparecerán aquí cuando alguien escriba al bot.'
            : reportes.length === 0
              ? 'Quitaste todos los reportes de este panel. Muéstralos de nuevo si los necesitas.'
              : 'Ningún reporte coincide con los filtros elegidos. Prueba con otra hora o quita los filtros.'}
        </p>
      )}

      {!cargando && !error && visibles.length > 0 && (
        <ul className="lista">
          {visibles.map((item) => (
            <FilaReporte key={item.registrado.reporte_id} item={item} alQuitar={() => quitar(item.registrado.reporte_id)} />
          ))}
        </ul>
      )}
    </section>
  )
}
