import { useEffect, useMemo, useState } from 'react'
import { consultarEtapa, consultarConfirmaciones, listarPoliticas, prepararPriorizacion } from '../api/priorizacion.js'
import { lugaresDelAmbito, razonDeLugar, SIN_LUGAR } from './lugares.js'
import './FormularioRevision.css'
import { useBorrador } from '../useBorrador.js'
import { lugarPorValidar } from '../lugar.js'

// Estados en los que la RPC acepta un lote (ra_preparar_priorizacion_v2).
const ESTADOS_ACEPTADOS = ['pendiente', 'ejecutando', 'espera_validacion', 'espera_revision']

// Mensaje por código de error de la API; el texto del servidor se muestra debajo cuando existe.
const MENSAJE_ERROR = {
  sin_permiso: 'Hace falta una sesión de coordinador activo para enviar la revisión.',
  version_obsoleta: 'Los incidentes cambiaron mientras revisabas. Actualiza la página y revisa de nuevo.',
  politica_no_activa: 'Esa política ya no está activa. Elige otra de la lista.',
  datos_insuficientes: 'Falta cubrir algún punto para poder calcular. Lee el detalle y corrige.',
  contrato_invalido: 'Algún dato no cumple el formato esperado. Revisa los campos marcados.',
  sin_conexion: 'No se pudo conectar con la API.',
}

const VULNERABILIDAD = [
  ['sin_condicion_identificada', 'Sin condición identificada', 'No hay barreras ni dependencia documentadas.'],
  ['moderada', 'Moderada', 'Hay barreras documentadas, pero existe una alternativa para obtener agua.'],
  ['alta', 'Alta', 'Depende del suministro y no tiene una alternativa suficiente.'],
]

const VACIA = {
  metodo: 'directa', fuente: '', litros: '', personasDemanda: '', dotacion: '', dias: '', reserva: '',
  capacidad: '', clase: '', vulnerabilidad: '', horas: '', personas: '', inicio: '', fin: '',
}

const num = (v) => (v === '' ? undefined : Number(v))
// Panamá no cambia de hora (UTC−5 todo el año): se fija el desfase explícito.
const instante = (v) => (v ? `${v}:00-05:00` : undefined)
const formato = new Intl.NumberFormat('es-PA', { maximumFractionDigits: 1 })
const porcentaje = (v) => `${Math.round(v * 100)} %`

function limpiar(objeto) {
  return Object.fromEntries(Object.entries(objeto).filter(([, v]) => v !== undefined))
}

function demandaCompleta(f) {
  if (f.fuente.trim() === '') return false
  return f.metodo === 'directa' ? f.litros !== '' : [f.personasDemanda, f.dotacion, f.dias].every((v) => v !== '')
}

// Lo que todavía no se confirmó. Se envía igual: queda pendiente y no se cuenta como cero.
function faltantesDe(f) {
  const faltan = []
  if (!demandaCompleta(f)) faltan.push('agua que necesita')
  if (f.capacidad === '') faltan.push('capacidad de recepción')
  if (f.clase === '') faltan.push('clase de prioridad')
  if (f.vulnerabilidad === '') faltan.push('vulnerabilidad')
  if (f.horas === '') faltan.push('horas sin agua')
  if (f.personas === '') faltan.push('personas atendidas')
  if (f.clase === 'critico' && !(f.inicio && f.fin)) faltan.push('ventana de entrega')
  return faltan
}
const TOTAL_DATOS = 6

// Errores que la API rechazaría; se dicen junto al punto y antes de enviar.
function problemasDe(f) {
  const p = []
  const hayCantidad = f.metodo === 'directa' ? f.litros !== '' : [f.personasDemanda, f.dotacion, f.dias, f.reserva].some((v) => v !== '')
  if (f.fuente.trim() === '' && hayCantidad) p.push('Indica quién confirma la demanda de agua.')
  if (f.fuente.trim() !== '' && !demandaCompleta(f)) p.push('Completa las cantidades de agua o borra quién la confirma: no se guarda una demanda vacía.')
  if (f.clase === 'critico' && !(f.inicio && f.fin)) p.push('Un punto crítico necesita ventana de entrega, con inicio y fin.')
  if (Boolean(f.inicio) !== Boolean(f.fin)) p.push('La ventana necesita inicio y fin.')
  if (f.inicio && f.fin && f.fin <= f.inicio) p.push('La ventana debe terminar después de empezar.')
  if (f.personas !== '' && !Number.isInteger(Number(f.personas))) p.push('Las personas atendidas son un número entero.')
  return p
}

function armarRevision(item, f) {
  const demanda = f.fuente.trim()
    ? (f.metodo === 'directa'
      ? limpiar({ metodo: 'directa', fuente: f.fuente.trim(), litros_declarados: num(f.litros) })
      : limpiar({
        metodo: 'formula', fuente: f.fuente.trim(), personas_atendidas: num(f.personasDemanda),
        dotacion_litros_persona_dia: num(f.dotacion), dias_cobertura: num(f.dias), reserva_utilizable_litros: num(f.reserva),
      }))
    : undefined
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

function Campo({ id, etiqueta, ayuda, children }) {
  return (
    <div className="rev-campo">
      <label htmlFor={id}>{etiqueta}</label>
      {children}
      {ayuda && <p className="rev-ayuda" id={`${id}-ayuda`}>{ayuda}</p>}
    </div>
  )
}

// Dato que el sistema ya tiene: se ofrece, nunca se confirma solo.
function DatoActual({ texto, alUsar }) {
  if (!texto) return null
  return (
    <p className="rev-actual">
      El sistema tiene: <strong>{texto}</strong>{' '}
      <button type="button" className="rev-enlace" onClick={alUsar}>Usar este dato</button>
    </p>
  )
}

function Opciones({ nombre, valor, opciones, alCambiar, ayudaId }) {
  return (
    <div className="rev-opciones" role="radiogroup" aria-describedby={ayudaId}>
      {opciones.map(([v, etiqueta, ayuda]) => (
        <label key={v} className="rev-opcion" data-activa={valor === v}>
          <input type="radio" name={nombre} value={v} checked={valor === v} onChange={() => alCambiar(v)} />
          <span><strong>{etiqueta}</strong>{ayuda && <small>{ayuda}</small>}</span>
        </label>
      ))}
    </div>
  )
}

function EstadoPunto({ incluir, faltan, problemas, lugar }) {
  // El lugar bloquea el envío de todo el ámbito, esté el punto marcado o no.
  if (lugar) return <span className="rev-chip rev-chip-error">{lugar === SIN_LUGAR ? 'Falta el lugar' : 'Lugar repetido'}</span>
  if (!incluir) return <span className="rev-chip rev-chip-neutro">No se revisará</span>
  if (problemas.length > 0) return <span className="rev-chip rev-chip-error">Hay que corregir</span>
  if (faltan.length === 0) return <span className="rev-chip rev-chip-ok">Completo</span>
  const hechos = TOTAL_DATOS - faltan.filter((x) => x !== 'ventana de entrega').length
  return <span className="rev-chip rev-chip-aviso">{hechos} de {TOTAL_DATOS} datos</span>
}

function PuntoRevision({ item, valor, incluir, alCambiar, alIncluir, problemaLugar }) {
  const id = item.incidente_id
  const base = `rev-${id.slice(0, 8)}`
  const faltan = faltantesDe(valor)
  const problemas = incluir ? problemasDe(valor) : []
  const actual = item.evaluacion_necesidad
  const set = (clave) => (e) => alCambiar(id, { ...valor, [clave]: e.target.value })
  const poner = (clave, v) => alCambiar(id, { ...valor, [clave]: v })
  const lugar = [item.punto?.corregimiento, item.punto?.distrito].filter(Boolean).join(', ')
  const vulnActual = VULNERABILIDAD.find(([v]) => v === actual?.vulnerabilidad)

  return (
    <fieldset className="rev-punto" data-incluido={incluir}>
      <legend className="rev-punto-cabecera">
        <label className="rev-incluir">
          <input type="checkbox" checked={incluir} onChange={(e) => alIncluir(id, e.target.checked)} />
          <span>
            <strong>{item.punto?.nombre ?? 'Lugar sin identificar'}</strong>
            <small>{lugar || 'Sin ubicación'} · Reporte {id.slice(0, 8)}{lugarPorValidar(item) ? ' · Lugar por validar' : ''}</small>
          </span>
        </label>
        <EstadoPunto incluir={incluir} faltan={faltan} problemas={problemas} lugar={problemaLugar} />
      </legend>

      {problemaLugar && (
        <p className="rev-aviso-lugar" role="alert">
          {problemaLugar === SIN_LUGAR
            ? 'Este reporte aún no tiene un lugar identificado. Hace falta saber a qué punto de atención corresponde antes de calcular el orden.'
            : 'Otro incidente ya usa este mismo punto de atención. Consolida el episodio: no se suman ni se omiten.'}
        </p>
      )}

      {incluir && (
        <div className="rev-cuerpo">
          <section className="rev-seccion" aria-labelledby={`${base}-agua`}>
            <h4 id={`${base}-agua`}>Agua que necesita</h4>
            <Opciones
              nombre={`${base}-metodo`} valor={valor.metodo} alCambiar={(v) => poner('metodo', v)}
              opciones={[['directa', 'Ya sé cuántos litros', 'Un dato dicho por quien conoce el punto.'], ['formula', 'Calcular por personas', 'Personas × litros por persona × días.']]}
            />
            <div className="rev-grilla">
              <Campo id={`${base}-fuente`} etiqueta="¿Quién o qué lo confirma?" ayuda="Ej.: llamada con la junta de agua.">
                <input id={`${base}-fuente`} type="text" maxLength={500} value={valor.fuente} onChange={set('fuente')} aria-describedby={`${base}-fuente-ayuda`} />
              </Campo>
              {valor.metodo === 'directa' ? (
                <Campo id={`${base}-litros`} etiqueta="Litros necesarios">
                  <input id={`${base}-litros`} type="number" inputMode="decimal" min="0" step="any" value={valor.litros} onChange={set('litros')} />
                </Campo>
              ) : (
                <>
                  <Campo id={`${base}-pd`} etiqueta="Personas a abastecer"><input id={`${base}-pd`} type="number" min="0" step="1" value={valor.personasDemanda} onChange={set('personasDemanda')} /></Campo>
                  <Campo id={`${base}-dot`} etiqueta="Litros por persona al día"><input id={`${base}-dot`} type="number" min="0" step="any" value={valor.dotacion} onChange={set('dotacion')} /></Campo>
                  <Campo id={`${base}-dias`} etiqueta="Días a cubrir"><input id={`${base}-dias`} type="number" min="0" step="any" value={valor.dias} onChange={set('dias')} /></Campo>
                  <Campo id={`${base}-res`} etiqueta="Agua que ya tiene (litros)" ayuda="Opcional. Reserva que se puede usar.">
                    <input id={`${base}-res`} type="number" min="0" step="any" value={valor.reserva} onChange={set('reserva')} aria-describedby={`${base}-res-ayuda`} />
                  </Campo>
                </>
              )}
              <Campo id={`${base}-cap`} etiqueta="Capacidad de recepción (litros)" ayuda="Cuánta agua puede recibir el punto: tanque, cisterna o depósito.">
                <input id={`${base}-cap`} type="number" inputMode="decimal" min="0" step="any" value={valor.capacidad} onChange={set('capacidad')} aria-describedby={`${base}-cap-ayuda`} />
              </Campo>
            </div>
          </section>

          <section className="rev-seccion" aria-labelledby={`${base}-prio`}>
            <h4 id={`${base}-prio`}>Qué tan urgente es</h4>
            <p className="rev-ayuda" id={`${base}-clase-ayuda`}>
              <strong>Crítico</strong>: la falta de agua compromete un servicio sanitario esencial o a una persona dependiente sin
              alternativa. El nombre de una escuela o institución no basta.
            </p>
            <Opciones
              nombre={`${base}-clase`} valor={valor.clase} alCambiar={(v) => poner('clase', v)} ayudaId={`${base}-clase-ayuda`}
              opciones={[['general', 'General'], ['critico', 'Crítico', 'Se atiende antes que los generales.']]}
            />
            {valor.clase === '' && actual?.clase_prioridad && (
              <DatoActual texto={actual.clase_prioridad === 'critico' ? 'Crítico' : 'General'} alUsar={() => poner('clase', actual.clase_prioridad)} />
            )}
            <div className="rev-grilla">
              <Campo id={`${base}-horas`} etiqueta="Horas seguidas sin agua">
                <input id={`${base}-horas`} type="number" inputMode="decimal" min="0" step="any" value={valor.horas} onChange={set('horas')} />
                {valor.horas === '' && actual?.horas_sin_agua != null && (
                  <DatoActual texto={`${formato.format(actual.horas_sin_agua)} h`} alUsar={() => poner('horas', String(actual.horas_sin_agua))} />
                )}
              </Campo>
              <Campo id={`${base}-pers`} etiqueta="Personas que recibirán el agua" ayuda="Las que se atenderán, no la población total del corregimiento.">
                <input id={`${base}-pers`} type="number" min="0" step="1" value={valor.personas} onChange={set('personas')} aria-describedby={`${base}-pers-ayuda`} />
                {valor.personas === '' && actual?.personas_atendidas != null && (
                  <DatoActual texto={formato.format(actual.personas_atendidas)} alUsar={() => poner('personas', String(actual.personas_atendidas))} />
                )}
              </Campo>
            </div>
            <p className="rev-subtitulo" id={`${base}-vuln-t`}>Vulnerabilidad de quienes dependen del punto</p>
            <p className="rev-ayuda">Es una clasificación para ordenar la atención, no un diagnóstico médico.</p>
            <Opciones nombre={`${base}-vuln`} valor={valor.vulnerabilidad} alCambiar={(v) => poner('vulnerabilidad', v)} opciones={VULNERABILIDAD} />
            {valor.vulnerabilidad === '' && vulnActual && (
              <DatoActual texto={vulnActual[1]} alUsar={() => poner('vulnerabilidad', vulnActual[0])} />
            )}
          </section>

          <section className="rev-seccion" aria-labelledby={`${base}-vent`}>
            <h4 id={`${base}-vent`}>Ventana de entrega {valor.clase === 'critico' ? <span className="rev-obligatorio">obligatoria</span> : <span className="rev-opcional">opcional</span>}</h4>
            <p className="rev-ayuda">Entre qué horas debe llegar el agua. Hora de Panamá.</p>
            <div className="rev-grilla">
              <Campo id={`${base}-ini`} etiqueta="Desde"><input id={`${base}-ini`} type="datetime-local" value={valor.inicio} onInput={set('inicio')} onChange={set('inicio')} /></Campo>
              <Campo id={`${base}-fin`} etiqueta="Hasta"><input id={`${base}-fin`} type="datetime-local" value={valor.fin} onInput={set('fin')} onChange={set('fin')} /></Campo>
            </div>
          </section>

          {problemas.length > 0 && <ul className="rev-problemas" role="alert">{problemas.map((m) => <li key={m}>{m}</li>)}</ul>}
          {problemas.length === 0 && faltan.length > 0 && (
            <p className="rev-pendiente">Quedará pendiente: {faltan.join(', ')}. No se cuenta como cero.</p>
          )}
        </div>
      )}
    </fieldset>
  )
}

export default function FormularioRevision({ items, calculo, alEnviar, alActualizar }) {
  // Clave estable: la lista de ejecuciones no se vuelve a consultar cada vez que se refrescan los datos.
  const clave = useMemo(() => [...new Set(items.map((i) => i.ejecucion_id))].slice(0, 12).join(','), [items])
  const [ejecucion, setEjecucion] = useState({ estado: 'buscando' })
  const [politicas, setPoliticas] = useState({ estado: 'cargando', lista: [] })
  const [politica, setPolitica] = useBorrador('revision.politica', '')
  const [motivo, setMotivo] = useBorrador('revision.motivo', '')
  const [filas, setFilas] = useBorrador('revision.filas', {})
  const [excluidos, setExcluidos] = useBorrador('revision.excluidos', {})
  const [envio, setEnvio] = useState({ estado: 'libre' })
  const [confirmaciones, setConfirmaciones] = useState({ clave: '', lista: [] })

  // Busca una ejecución que acepte el lote: etapa priorización y un estado que la RPC admita.
  useEffect(() => {
    let cancelado = false
    Promise.allSettled(clave.split(',').map((id) => consultarEtapa(id))).then((resultados) => {
      if (cancelado) return
      const validas = resultados.filter((r) => r.status === 'fulfilled').map((r) => r.value)
        .filter((e) => e.etapa === 'priorizacion' && ESTADOS_ACEPTADOS.includes(e.estado))
      if (validas.length > 0) {
        validas.sort((a, b) => new Date(b.actualizado_en) - new Date(a.actualizado_en))
        setEjecucion({ estado: 'lista', id: validas[0].ejecucion_id })
      } else {
        const falla = resultados.find((r) => r.status === 'rejected')
        setEjecucion({ estado: 'ninguna', error: falla?.reason?.message })
      }
    })
    return () => { cancelado = true }
  }, [clave])

  useEffect(() => {
    let cancelado = false
    listarPoliticas()
      .then((lista) => { if (!cancelado) setPoliticas({ estado: 'lista', lista }) })
      .catch((e) => { if (!cancelado) setPoliticas({ estado: 'error', lista: [], mensaje: e.message }) })
    return () => { cancelado = true }
  }, [])

  const politicaElegida = politica || (politicas.lista.length === 1 ? politicas.lista[0].politica_version : '')
  const versiones = items.map((i) => `${i.incidente_id}:${i.version}`).sort().join(',')
  const claveConfirmaciones = `${ejecucion.id}:${politicaElegida}:${versiones}`
  useEffect(() => {
    if (!ejecucion.id || !politicaElegida) return
    let cancelado = false
    consultarConfirmaciones(ejecucion.id, politicaElegida)
      .then((lista) => { if (!cancelado) setConfirmaciones({ clave: claveConfirmaciones, lista }) })
      .catch(() => { if (!cancelado) setConfirmaciones({ clave: claveConfirmaciones, lista: [] }) })
    return () => { cancelado = true }
  }, [ejecucion.id, politicaElegida, claveConfirmaciones])
  const conservada = (item) => confirmaciones.clave === claveConfirmaciones && confirmaciones.lista.some(
    (c) => c.incidente_id === item.incidente_id && c.version === item.version,
  )
  // Solo los puntos modificados requieren datos nuevos. El servidor lo revalida al enviar.
  const incluido = (item) => !conservada(item) && (excluidos[item.incidente_id] === undefined
    ? item.evaluacion_necesidad?.estado_prioridad !== 'calculada'
    : !excluidos[item.incidente_id])
  const filaDe = (id) => filas[id] ?? VACIA
  const cambiar = (id, valor) => setFilas((f) => ({ ...f, [id]: valor }))
  const alIncluir = (id, si) => setExcluidos((e) => ({ ...e, [id]: !si }))

  const incluidos = items.filter(incluido)
  const detallePolitica = politicas.lista.find((p) => p.politica_version === politicaElegida)
  const conProblemas = incluidos.filter((i) => problemasDe(filaDe(i.incidente_id)).length > 0)
  const incompletos = incluidos.filter((i) => faltantesDe(filaDe(i.incidente_id)).length > 0)

  const lugaresPorValidar = items.filter(lugarPorValidar).length
  const lugares = useMemo(() => lugaresDelAmbito(items), [items])
  const razonLugar = razonDeLugar(lugares)

  const razon = ejecucion.estado !== 'lista' ? 'Todavía no hay una ejecución lista para priorizar.'
    : razonLugar ? razonLugar
      : !politicaElegida ? 'Elige la política de prioridad.'
      : !motivo.trim() ? 'Escribe el motivo de la revisión.'
        : conProblemas.length > 0 ? `Corrige ${conProblemas[0].punto?.nombre ?? 'un punto'} antes de enviar.`
          : null
  const puedeEnviar = !razon && envio.estado !== 'enviando'

  async function enviar(evento) {
    evento.preventDefault()
    if (!puedeEnviar) return
    setEnvio({ estado: 'enviando' })
    try {
      const resultado = await prepararPriorizacion(ejecucion.id, {
        politica_version: politicaElegida,
        motivo: motivo.trim(),
        revisiones: incluidos.map((i) => armarRevision(i, filaDe(i.incidente_id))),
      })
      setEnvio({ estado: 'enviado', resultado })
      alEnviar?.(resultado)
    } catch (e) {
      setEnvio({ estado: 'error', codigo: e.codigo, mensaje: e.message })
    }
  }

  return (
    <section className="revision" id="revision" aria-labelledby="titulo-revision">
      <header className="rev-encabezado">
        <h2 id="titulo-revision">Confirmar datos y calcular el orden</h2>
        <p>
          El orden de atención solo se calcula con datos que una persona confirmó. Marca los puntos que vas a revisar y
          llena lo que sepas. Lo que dejes vacío queda pendiente: <strong>no se cuenta como cero</strong>.
        </p>
      </header>

      {ejecucion.estado === 'buscando' && <p className="mensaje" role="status">Buscando una ejecución lista para priorizar…</p>}
      {ejecucion.estado === 'ninguna' && (
        <p className="mensaje" role="status">
          Ninguna ejecución está esperando la revisión de prioridad, así que por ahora no se puede enviar.
          {ejecucion.error ? ` ${ejecucion.error}` : ''}
        </p>
      )}

      {ejecucion.estado === 'lista' && (
        <form className="rev-form" onSubmit={enviar} noValidate>
          <section className="rev-bloque" aria-labelledby="rev-paso1">
            <h3 id="rev-paso1"><span className="rev-paso">1</span> Cómo se ordena la atención</h3>
            {politicas.estado === 'cargando' && <p className="rev-ayuda">Cargando las políticas disponibles…</p>}
            {politicas.estado === 'lista' && politicas.lista.length === 0 && (
              <p className="mensaje mensaje-error" role="alert">No hay ninguna política activa. Pide que activen una antes de enviar.</p>
            )}
            {politicas.estado === 'error' && (
              <div className="rev-campo">
                <p className="rev-ayuda" role="alert">No se pudo cargar la lista de políticas ({politicas.mensaje}). Escribe la versión que te indicó la persona de datos.</p>
                <input aria-label="Versión de la política" type="text" maxLength={200} value={politica} onChange={(e) => setPolitica(e.target.value)} />
              </div>
            )}
            {politicas.lista.length > 0 && (
              <Campo id="rev-politica" etiqueta="Política de prioridad" ayuda="Es la regla con la que se calcula el orden. Solo aparecen las activas.">
                <select id="rev-politica" value={politicaElegida} onChange={(e) => setPolitica(e.target.value)} aria-describedby="rev-politica-ayuda">
                  {politicas.lista.length > 1 && <option value="">Elige una política</option>}
                  {politicas.lista.map((p) => <option key={p.politica_version} value={p.politica_version}>{p.politica_version}</option>)}
                </select>
              </Campo>
            )}
            {detallePolitica && (
              <div className="rev-politica">
                <p>{detallePolitica.fundamento}</p>
                <dl>
                  <div><dt>Tiempo sin agua</dt><dd>{porcentaje(detallePolitica.peso_duracion)}</dd></div>
                  <div><dt>Vulnerabilidad</dt><dd>{porcentaje(detallePolitica.peso_vulnerabilidad)}</dd></div>
                  <div><dt>Personas atendidas</dt><dd>{porcentaje(detallePolitica.peso_poblacion)}</dd></div>
                </dl>
                <p className="rev-ayuda">Los puntos críticos confirmados van primero. Tope de {formato.format(detallePolitica.tope_horas)} h y {formato.format(detallePolitica.tope_personas)} personas.</p>
              </div>
            )}
            <Campo id="rev-motivo" etiqueta="Motivo de la revisión" ayuda="Queda registrado con tu nombre y la hora. Ej.: confirmado por llamada a las 9:10.">
              <textarea id="rev-motivo" maxLength={2000} rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} aria-describedby="rev-motivo-ayuda" />
            </Campo>
          </section>

          <section className="rev-bloque" aria-labelledby="rev-paso2">
            <h3 id="rev-paso2"><span className="rev-paso">2</span> Confirma los datos de cada punto</h3>
            <p className="rev-ayuda">Revisa los puntos modificados. Las confirmaciones anteriores se conservan únicamente si sus datos siguen vigentes.</p>
            <div className="rev-puntos">
              {items.map((item) => conservada(item) ? (
                <p key={item.incidente_id} className="rev-ok">
                  {item.punto?.nombre ?? 'Punto'}: confirmación anterior vigente. Se conservarán sus datos y se recalculará su prioridad.{' '}
                  <button type="button" onClick={() => {
                    setConfirmaciones((c) => ({ ...c, lista: c.lista.filter((v) => v.incidente_id !== item.incidente_id) }))
                    alIncluir(item.incidente_id, true)
                  }}>Modificar estos datos</button>
                </p>
              ) : (
                <PuntoRevision
                  key={item.incidente_id} item={item} valor={filaDe(item.incidente_id)} incluir={incluido(item)}
                  alCambiar={cambiar} alIncluir={alIncluir} problemaLugar={lugares.problemas[item.incidente_id]}
                />
              ))}
            </div>
          </section>

          <section className="rev-bloque" aria-labelledby="rev-paso3">
            <h3 id="rev-paso3"><span className="rev-paso">3</span> Enviar</h3>
            <p className="rev-resumen" role="status">
              {incluidos.length} de {items.length} puntos con revisión
              {incompletos.length > 0 ? `; ${incompletos.length} con datos pendientes` : incluidos.length > 0 ? '; todos completos' : ''}.
              {' '}Todos los puntos participan en el cálculo. Se conservan las confirmaciones vigentes; los demás que no revises quedan pendientes.
            </p>
            {lugaresPorValidar > 0 && (
              <p className="rev-aviso-lugar-pendiente" role="note">
                {lugaresPorValidar} {lugaresPorValidar === 1 ? 'punto tiene' : 'puntos tienen'} el lugar por validar. Valídalo{lugaresPorValidar === 1 ? '' : 's'} en la
                tarjeta de cada incidente: mientras no conste esa validación, el cálculo automático de lotes se mantiene en revisión humana.
              </p>
            )}
            {envio.estado === 'error' && (
              <div className="mensaje mensaje-error" role="alert">
                <p>{MENSAJE_ERROR[envio.codigo] ?? 'No se pudo enviar la revisión.'}</p>
                <p className="rev-detalle">{envio.mensaje}</p>
              </div>
            )}
            {envio.estado === 'enviado' && (
              <div className="mensaje rev-ok" role="status">
                <p><strong>{envio.resultado.repetido ? 'Este mismo envío ya estaba registrado: no se duplicó.' : 'Revisión enviada.'}</strong></p>
                <p className="rev-detalle">{envio.resultado.incidentes} puntos en el envío, {envio.resultado.sin_revisar} sin revisar.</p>
                {calculo?.estado === 'esperando' && <p className="rev-calculo">Calculando el orden. Se consulta cada 5 segundos; no hace falta recargar.</p>}
                {calculo?.estado === 'listo' && <p className="rev-calculo rev-calculo-ok">Listo: el orden de atención ya está actualizado arriba.</p>}
                {calculo?.estado === 'tarda' && (
                  <p className="rev-calculo rev-calculo-aviso">
                    El cálculo tarda más de lo normal. Comprueba que el trabajador de agentes esté en marcha y vuelve a revisar.
                  </p>
                )}
                <button type="button" className="actualizar" onClick={alActualizar}>Revisar ahora</button>
              </div>
            )}
            <div className="rev-barra">
              <button type="submit" className="rev-enviar" disabled={!puedeEnviar} aria-describedby="rev-razon">
                {envio.estado === 'enviando' ? 'Enviando…' : 'Enviar revisión'}
              </button>
              <p id="rev-razon" className="rev-razon" aria-live="polite">{razon ?? 'Todo listo para enviar.'}</p>
            </div>
          </section>
        </form>
      )}
    </section>
  )
}
