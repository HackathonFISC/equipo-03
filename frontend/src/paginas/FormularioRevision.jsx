import { useEffect, useMemo, useState } from 'react'
import { consultarEtapa, prepararPriorizacion } from '../api/priorizacion.js'

// Estados en los que la RPC acepta un lote (ra_preparar_priorizacion_v2).
const ESTADOS_ACEPTADOS = ['pendiente', 'ejecutando', 'espera_validacion', 'espera_revision']

// Mensaje por código de error de la API; el texto del servidor se muestra debajo cuando existe.
const MENSAJE_ERROR = {
  sin_permiso: 'Hace falta una sesión de coordinador activo para enviar la revisión.',
  version_obsoleta: 'Los incidentes cambiaron mientras revisabas. Actualiza la página y revisa de nuevo.',
  politica_no_activa: 'Esa versión de política no está activa. Confirma cuál usar y vuelve a enviar.',
  datos_insuficientes: 'Falta confirmar datos para calcular. Completa lo que indica el mensaje.',
  contrato_invalido: 'Algún dato no cumple el formato esperado. Revisa los campos marcados.',
  sin_conexion: 'No se pudo conectar con la API.',
}

const VACIA = {
  incluir: false, metodo: 'directa', fuente: '', litros: '', personasDemanda: '', dotacion: '', dias: '', reserva: '',
  capacidad: '', clase: '', inicio: '', fin: '', vulnerabilidad: '', horas: '', personas: '',
}

const num = (v) => (v === '' ? undefined : Number(v))
// Panamá no cambia de hora (UTC−5 todo el año): se fija el desfase explícito.
const instante = (v) => (v ? `${v}:00-05:00` : undefined)

function limpiar(objeto) {
  return Object.fromEntries(Object.entries(objeto).filter(([, v]) => v !== undefined))
}

// Arma la revisión de un incidente con lo que la persona llenó. Lo vacío no se envía: queda pendiente.
function armarRevision(item, f) {
  let demanda
  if (f.fuente.trim()) {
    demanda = f.metodo === 'directa'
      ? limpiar({ metodo: 'directa', fuente: f.fuente.trim(), litros_declarados: num(f.litros) })
      : limpiar({
        metodo: 'formula', fuente: f.fuente.trim(), personas_atendidas: num(f.personasDemanda),
        dotacion_litros_persona_dia: num(f.dotacion), dias_cobertura: num(f.dias), reserva_utilizable_litros: num(f.reserva),
      })
  }
  return limpiar({
    incidente_id: item.incidente_id,
    version_incidente: item.version,
    demanda,
    capacidad_recepcion_litros: num(f.capacidad),
    clase_prioridad: f.clase || undefined,
    ventana_atencion: f.inicio && f.fin ? { inicio: instante(f.inicio), fin: instante(f.fin) } : undefined,
    vulnerabilidad: f.vulnerabilidad || undefined,
    horas_sin_agua: num(f.horas),
    personas_atendidas: num(f.personas),
  })
}

// Revisa en el cliente lo que la API rechazaría, para decirlo junto al campo y no después del envío.
function problemasDe(f) {
  const p = []
  const hayCantidad = f.metodo === 'directa' ? f.litros !== '' : [f.personasDemanda, f.dotacion, f.dias, f.reserva].some((v) => v !== '')
  if (f.fuente.trim() === '' && hayCantidad) p.push('Indica la fuente de la demanda.')
  if (f.fuente.trim() !== '' && f.metodo === 'directa' && f.litros === '') p.push('Indica los litros declarados o borra la fuente: no se confirma una demanda vacía.')
  if (f.fuente.trim() !== '' && f.metodo === 'formula' && [f.personasDemanda, f.dotacion, f.dias].some((v) => v === '')) p.push('Para la fórmula faltan personas, litros por persona o días; complétalos o borra la fuente.')
  if (f.clase === 'critico' && !(f.inicio && f.fin)) p.push('Un punto crítico necesita ventana de atención.')
  if (Boolean(f.inicio) !== Boolean(f.fin)) p.push('La ventana necesita inicio y fin.')
  if (f.inicio && f.fin && f.fin <= f.inicio) p.push('La ventana debe terminar después de empezar.')
  if (f.personas !== '' && !Number.isInteger(Number(f.personas))) p.push('Las personas atendidas son un número entero.')
  return p
}

function Campo({ etiqueta, children }) {
  return <label className="rev-campo"><span>{etiqueta}</span>{children}</label>
}

function FilaRevision({ item, valor, alCambiar }) {
  const id = item.incidente_id
  const problemas = valor.incluir ? problemasDe(valor) : []
  const set = (clave) => (e) => alCambiar(id, { ...valor, [clave]: e.target.value })
  return (
    <fieldset className="rev-incidente" data-incluido={valor.incluir}>
      <legend>
        <label className="rev-incluir">
          <input type="checkbox" checked={valor.incluir} onChange={(e) => alCambiar(id, { ...valor, incluir: e.target.checked })} />
          {item.punto?.nombre ?? 'Lugar sin identificar'}
        </label>
        <small>Incidente <code title={id}>{id.slice(0, 8)}</code>, versión {item.version}</small>
      </legend>
      {valor.incluir && (
        <div className="rev-campos">
          <Campo etiqueta="Cómo se conoce la demanda">
            <select value={valor.metodo} onChange={set('metodo')}>
              <option value="directa">Litros declarados</option>
              <option value="formula">Por personas y dotación</option>
            </select>
          </Campo>
          <Campo etiqueta="Fuente de la demanda">
            <input type="text" maxLength={500} value={valor.fuente} onChange={set('fuente')} placeholder="Quién la confirmó" />
          </Campo>
          {valor.metodo === 'directa' ? (
            <Campo etiqueta="Litros declarados"><input type="number" min="0" step="any" value={valor.litros} onChange={set('litros')} /></Campo>
          ) : (
            <>
              <Campo etiqueta="Personas a abastecer"><input type="number" min="0" step="1" value={valor.personasDemanda} onChange={set('personasDemanda')} /></Campo>
              <Campo etiqueta="Litros por persona al día"><input type="number" min="0" step="any" value={valor.dotacion} onChange={set('dotacion')} /></Campo>
              <Campo etiqueta="Días de cobertura"><input type="number" min="0" step="any" value={valor.dias} onChange={set('dias')} /></Campo>
              <Campo etiqueta="Reserva utilizable (litros)"><input type="number" min="0" step="any" value={valor.reserva} onChange={set('reserva')} /></Campo>
            </>
          )}
          <Campo etiqueta="Capacidad de recepción (litros)">
            <input type="number" min="0" step="any" value={valor.capacidad} onChange={set('capacidad')} />
          </Campo>
          <Campo etiqueta="Clase de prioridad">
            <select value={valor.clase} onChange={set('clase')}>
              <option value="">Sin confirmar</option>
              <option value="general">General</option>
              <option value="critico">Crítico</option>
            </select>
          </Campo>
          <Campo etiqueta="Vulnerabilidad">
            <select value={valor.vulnerabilidad} onChange={set('vulnerabilidad')}>
              <option value="">Sin confirmar</option>
              <option value="sin_condicion_identificada">Sin condición identificada</option>
              <option value="moderada">Moderada</option>
              <option value="alta">Alta</option>
            </select>
          </Campo>
          <Campo etiqueta="Horas sin agua"><input type="number" min="0" step="any" value={valor.horas} onChange={set('horas')} /></Campo>
          <Campo etiqueta="Personas atendidas"><input type="number" min="0" step="1" value={valor.personas} onChange={set('personas')} /></Campo>
          <Campo etiqueta={valor.clase === 'critico' ? 'Ventana: inicio (obligatoria)' : 'Ventana: inicio'}>
            <input type="datetime-local" value={valor.inicio} onChange={set('inicio')} />
          </Campo>
          <Campo etiqueta="Ventana: fin"><input type="datetime-local" value={valor.fin} onChange={set('fin')} /></Campo>
        </div>
      )}
      {problemas.length > 0 && <ul className="rev-problemas" role="alert">{problemas.map((m) => <li key={m}>{m}</li>)}</ul>}
    </fieldset>
  )
}

export default function FormularioRevision({ items, alActualizar }) {
  const idsEjecucion = useMemo(() => [...new Set(items.map((i) => i.ejecucion_id))].slice(0, 12), [items])
  const [ejecucion, setEjecucion] = useState({ estado: 'buscando' })
  const [politica, setPolitica] = useState('')
  const [motivo, setMotivo] = useState('')
  const [filas, setFilas] = useState({})
  const [envio, setEnvio] = useState({ estado: 'libre' })

  // Busca una ejecución que acepte el lote: etapa priorización y un estado que la RPC admita.
  useEffect(() => {
    let cancelado = false
    Promise.allSettled(idsEjecucion.map((id) => consultarEtapa(id))).then((resultados) => {
      if (cancelado) return
      const validas = resultados.filter((r) => r.status === 'fulfilled').map((r) => r.value)
        .filter((e) => e.etapa === 'priorizacion' && ESTADOS_ACEPTADOS.includes(e.estado))
      if (validas.length > 0) {
        validas.sort((a, b) => new Date(b.actualizado_en) - new Date(a.actualizado_en))
        setEjecucion({ estado: 'lista', id: validas[0].ejecucion_id, total: validas.length })
      } else {
        const falla = resultados.find((r) => r.status === 'rejected')
        setEjecucion({ estado: 'ninguna', error: falla?.reason?.message })
      }
    })
    return () => { cancelado = true }
  }, [idsEjecucion])

  const filaDe = (id) => filas[id] ?? VACIA
  const cambiar = (id, valor) => setFilas((f) => ({ ...f, [id]: valor }))
  const incluidos = items.filter((i) => filaDe(i.incidente_id).incluir)
  const hayProblemas = incluidos.some((i) => problemasDe(filaDe(i.incidente_id)).length > 0)
  const puedeEnviar = ejecucion.estado === 'lista' && politica.trim() && motivo.trim() && !hayProblemas && envio.estado !== 'enviando'

  async function enviar(evento) {
    evento.preventDefault()
    setEnvio({ estado: 'enviando' })
    try {
      const resultado = await prepararPriorizacion(ejecucion.id, {
        politica_version: politica.trim(),
        motivo: motivo.trim(),
        revisiones: incluidos.map((i) => armarRevision(i, filaDe(i.incidente_id))),
      })
      setEnvio({ estado: 'enviado', resultado })
    } catch (e) {
      setEnvio({ estado: 'error', codigo: e.codigo, mensaje: e.message })
    }
  }

  return (
    <section className="revision" aria-labelledby="titulo-revision">
      <h2 id="titulo-revision" className="grupo-titulo">Revisar y enviar a priorización</h2>
      <p className="grupo-nota">
        Confirma solo lo que sabes. Lo que dejes sin confirmar queda pendiente y no se cuenta como cero. Quién revisa
        y cuándo lo registra el servidor con tu sesión.
      </p>

      {ejecucion.estado === 'buscando' && <p className="mensaje" role="status">Buscando una ejecución lista para priorizar…</p>}
      {ejecucion.estado === 'ninguna' && (
        <p className="mensaje" role="status">
          Ninguna ejecución está en la etapa de priorización, así que por ahora no se puede enviar una revisión.
          {ejecucion.error ? ` ${ejecucion.error}` : ''}
        </p>
      )}

      {ejecucion.estado === 'lista' && (
        <form className="rev-form" onSubmit={enviar}>
          <div className="rev-cabecera">
            <Campo etiqueta="Versión de la política">
              <input type="text" required maxLength={200} value={politica} onChange={(e) => setPolitica(e.target.value)} placeholder="Debe coincidir con la política activa" />
            </Campo>
            <Campo etiqueta="Motivo de la revisión">
              <textarea required maxLength={2000} rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
            </Campo>
          </div>
          <p className="rev-ejecucion">Ejecución <code title={ejecucion.id}>{ejecucion.id.slice(0, 8)}</code>
            {ejecucion.total > 1 ? `, la más reciente de ${ejecucion.total} en priorización` : ''}.</p>

          {items.map((item) => (
            <FilaRevision key={item.incidente_id} item={item} valor={filaDe(item.incidente_id)} alCambiar={cambiar} />
          ))}

          <p className="rev-resumen" role="status">
            {incluidos.length} de {items.length} incidentes con revisión. El ámbito completo debe quedar cubierto,
            con un incidente por punto.
          </p>
          {envio.estado === 'error' && (
            <div className="mensaje mensaje-error" role="alert">
              <p>{MENSAJE_ERROR[envio.codigo] ?? 'No se pudo enviar la revisión.'}</p>
              <p className="rev-detalle">{envio.mensaje}</p>
            </div>
          )}
          {envio.estado === 'enviado' && (
            <div className="mensaje rev-ok" role="status">
              <p>
                {envio.resultado.repetido
                  ? 'Este mismo lote ya estaba enviado: no se duplicó.'
                  : 'Revisión enviada. El cálculo queda pendiente y se mostrará aquí al actualizar.'}
              </p>
              <p className="rev-detalle">
                {envio.resultado.incidentes} incidentes en el lote, {envio.resultado.sin_revisar} sin revisar.
                Estado {envio.resultado.estado}, etapa {envio.resultado.etapa}.
              </p>
              <button type="button" className="actualizar" onClick={alActualizar}>Actualizar necesidades</button>
            </div>
          )}
          <button type="submit" className="rev-enviar" disabled={!puedeEnviar}>
            {envio.estado === 'enviando' ? 'Enviando…' : 'Enviar revisión'}
          </button>
        </form>
      )}
    </section>
  )
}
