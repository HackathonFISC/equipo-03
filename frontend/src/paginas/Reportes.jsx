import { useEffect, useMemo, useState } from 'react'
import { obtenerEjecucion, obtenerReportes, USAR_EJEMPLOS } from '../api/reportes.js'
import { iniciarSondeo } from '../api/sondeo.js'
import './Reportes.css'

// Estado que ve la persona operadora. Se deriva de la interpretación;
// el contrato no guarda un campo "estado" para los reportes.
const ESTADOS = {
  interpretado: { etiqueta: 'Interpretado', ayuda: 'Datos suficientes para evaluar' },
  aclaracion: { etiqueta: 'Necesita aclaración', ayuda: 'Falta información del remitente' },
  sin_interpretar: { etiqueta: 'Sin interpretar', ayuda: 'Aún no se analiza el mensaje' },
  fuera_de_alcance: { etiqueta: 'Fuera de alcance', ayuda: 'No es falta de agua en un punto' },
}

const FILTROS = ['todos', 'interpretado', 'aclaracion', 'sin_interpretar', 'fuera_de_alcance']

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

function FilaReporte({ item }) {
  const { registrado, interpretado, seguimiento } = item
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
    </li>
  )
}

export default function Reportes() {
  const [reportes, setReportes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [filtro, setFiltro] = useState('todos')
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    return iniciarSondeo(obtenerReportes, {
      onDatos: (datos) => {
        setReportes(datos)
        setError(null)
        setCargando(false)
      },
      onError: (e) => {
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

  const ordenados = useMemo(
    () =>
      [...reportes].sort(
        (a, b) => new Date(b.registrado.creado_en) - new Date(a.registrado.creado_en),
      ),
    [reportes],
  )

  const conteos = useMemo(() => {
    const c = { todos: ordenados.length, interpretado: 0, aclaracion: 0, sin_interpretar: 0, fuera_de_alcance: 0 }
    for (const item of ordenados) c[estadoDe(item)] += 1
    return c
  }, [ordenados])

  const visibles = filtro === 'todos' ? ordenados : ordenados.filter((i) => estadoDe(i) === filtro)

  return (
    <section className="reportes" aria-labelledby="titulo-reportes">
      <header className="reportes-cabecera">
        <span className="seccion-etiqueta">COMUNIDAD / RECEPCIÓN</span>
        <h1 id="titulo-reportes">Reportes recibidos</h1>
        <p>Mensajes de la comunidad, del más reciente al más antiguo.</p>
      </header>

      {!cargando && !error && reportes.length > 0 && (
        <dl className="bandeja-resumen" aria-label="Resumen de reportes recibidos">
          <div><dt>Reportes recibidos</dt><dd>{conteos.todos}</dd></div>
          <div><dt>Interpretados</dt><dd>{conteos.interpretado}</dd></div>
          <div className="resumen-atencion"><dt>Necesitan aclaración</dt><dd>{conteos.aclaracion}</dd></div>
        </dl>
      )}

      {USAR_EJEMPLOS && (
        <p className="aviso-ejemplos" role="note">
          Datos de ejemplo. Los reportes de esta lista son sintéticos y no vienen de la API.
        </p>
      )}

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
          <button type="button" onClick={reintentar}>
            Reintentar
          </button>
        </div>
      )}

      {!cargando && !error && visibles.length === 0 && (
        <p className="mensaje">
          {filtro === 'todos'
            ? 'Todavía no hay reportes. Aparecerán aquí cuando alguien escriba al bot.'
            : 'Ningún reporte tiene este estado.'}
        </p>
      )}

      {!cargando && !error && visibles.length > 0 && (
        <ul className="lista">
          {visibles.map((item) => (
            <FilaReporte key={item.registrado.reporte_id} item={item} />
          ))}
        </ul>
      )}
    </section>
  )
}
