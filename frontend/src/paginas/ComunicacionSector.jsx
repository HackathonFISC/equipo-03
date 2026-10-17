import { useEffect, useRef, useState } from 'react'
import { configurarDestinoEnsayo, estadoSector, listarDestinos, listarSectores, seleccionarPlanSector } from '../api/sectores.js'
import './ComunicacionSector.css'
import { useBorrador } from '../useBorrador.js'

const ESTADOS_SECTOR = {
  sin_plan_vigente: 'Sin plan vigente',
  con_plan_vigente: 'Con plan vigente',
}

// El origen decide a quién puede llegar un aviso: lo sintético solo va a destinos de ensayo.
const ORIGENES = {
  real: 'Real',
  estimado: 'Estimado',
  sintetico: 'Sintético (ensayo)',
}

function Origen({ valor }) {
  return <span className={`com-origen com-origen-${valor}`}>{ORIGENES[valor] ?? valor}</span>
}

const ESTADOS_PUNTO = {
  sin_asignacion: 'Sin asignación',
  asignado: 'Asignado',
}

function Sector({ planes, sectores }) {
  const aprobados = planes.filter((p) => p.estado === 'aprobado')
  const [sectorId, setSectorId] = useBorrador('comunicacion.sector', '')
  // Cada respuesta guarda el sector que se pidió: solo se muestra si sigue siendo el que está escrito.
  const [consulta, setConsulta] = useState(null)
  const [mensaje, setMensaje] = useState(null)
  const [eleccion, setEleccion] = useBorrador('comunicacion.eleccion', '')
  const [motivo, setMotivo] = useBorrador('comunicacion.motivo', '')
  const [trabajando, setTrabajando] = useState(false)
  const sectorActual = useRef(sectorId.trim())

  const idSector = sectorId.trim()
  const sectorValido = idSector !== ''
  const estado = consulta?.sectorId === idSector ? consulta.datos : null
  const aviso = mensaje?.sectorId === idSector ? mensaje : null
  const plan = aprobados.find((p) => `${p.plan_id}:${p.version}` === eleccion)

  function cambiarSector(valor) {
    setSectorId(valor)
    sectorActual.current = valor.trim()
  }

  async function cargarEstado(id) {
    const datos = await estadoSector(id)
    if (datos.sector.sector_id !== id) throw new Error('La API respondió por otro sector. Vuelve a consultar.')
    // Si cambiaron el sector mientras esperaba, esta respuesta ya no corresponde a lo que se ve.
    if (sectorActual.current === id) setConsulta({ sectorId: id, datos })
  }

  async function consultar() {
    const id = idSector
    setTrabajando(true)
    setMensaje(null)
    try {
      await cargarEstado(id)
    } catch (e) {
      setConsulta(null)
      setMensaje({ sectorId: id, tipo: 'error', texto: e.message })
    } finally {
      setTrabajando(false)
    }
  }

  async function elegir(evento) {
    evento.preventDefault()
    const id = idSector
    setTrabajando(true)
    setMensaje(null)
    try {
      const r = await seleccionarPlanSector(id, plan, motivo.trim())
      setMensaje({ sectorId: id, tipo: 'ok', texto: r.repetido ? 'Ese plan ya estaba elegido para el sector.' : 'Plan elegido para el sector.' })
      setMotivo('')
      await cargarEstado(id)
    } catch (e) {
      setMensaje({ sectorId: id, tipo: 'error', texto: e.message })
    } finally {
      setTrabajando(false)
    }
  }

  return (
    <form className="com-bloque" onSubmit={elegir}>
      <h3>Plan que se comunica por sector</h3>
      <p className="aprob-suave">
        Comunicación avisa a la comunidad solo con el plan aprobado que elijas aquí.
      </p>
      <div className="com-fila">
        <label>
          Sector
          <select value={sectorId} onChange={(e) => cambiarSector(e.target.value)} disabled={sectores.length === 0}>
            <option value="">{sectores.length === 0 ? 'No hay sectores en el catálogo' : 'Elige un sector'}</option>
            {sectores.map((s) => (
              <option key={s.sector_id} value={s.sector_id}>
                {s.nombre} · {s.distrito} · {ORIGENES[s.origen] ?? s.origen}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="aprob-secundario" disabled={!sectorValido || trabajando} onClick={consultar}>
          Ver estado
        </button>
      </div>
      {estado && (
        <div className="com-estado" role="status">
          <p>
            <strong>{estado.sector.nombre}</strong> <Origen valor={estado.origen} /> · {ESTADOS_SECTOR[estado.estado] ?? estado.estado}
            {estado.plan_vigente && (
              <>
                {' '}· plan {estado.plan_vigente.plan_id.slice(0, 8)} v{estado.plan_vigente.version}{' '}
                <Origen valor={estado.plan_vigente.origen} />
              </>
            )}
          </p>
          <ul>
            {estado.puntos.map((p) => (
              <li key={p.punto_atencion_id}>
                <span>{p.nombre} <Origen valor={p.origen} /></span>
                <span>{ESTADOS_PUNTO[p.estado] ?? p.estado}{p.litros_asignados ? ` · ${p.litros_asignados.toLocaleString('es-PA')} L` : ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <label>
        Plan aprobado
        <select value={plan ? eleccion : ''} onChange={(e) => setEleccion(e.target.value)} disabled={aprobados.length === 0}>
          <option value="">{aprobados.length === 0 ? 'No hay planes aprobados' : 'Elige un plan'}</option>
          {aprobados.map((p) => (
            <option key={`${p.plan_id}:${p.version}`} value={`${p.plan_id}:${p.version}`}>
              Plan {p.plan_id.slice(0, 8)} versión {p.version} · {ORIGENES[p.origen] ?? p.origen}
            </option>
          ))}
        </select>
      </label>
      {plan && plan.origen !== 'real' && (
        <p className="aprob-aviso" role="status">
          Este plan es {ORIGENES[plan.origen]?.toLowerCase() ?? plan.origen}: solo debe llegar a destinos de ensayo, no a la comunidad.
        </p>
      )}
      <label>
        Motivo
        <textarea rows={2} maxLength={4000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </label>
      {aviso?.tipo === 'error' && <p className="aprob-error" role="alert">{aviso.texto}</p>}
      {aviso?.tipo === 'ok' && <p className="com-ok" role="status">{aviso.texto}</p>}
      <div className="aprob-botones">
        <button type="submit" disabled={!sectorValido || !plan || motivo.trim() === '' || trabajando}>
          {trabajando ? 'Guardando…' : 'Elegir para este sector'}
        </button>
      </div>
    </form>
  )
}

function estadoEnsayo(destino) {
  if (destino.habilitado_ensayo === null) return 'ensayo sin migración 0012'
  return destino.habilitado_ensayo ? 'ensayo habilitado' : 'ensayo apagado'
}

function Destino({ destinos, alCambiar }) {
  const [destinoId, setDestinoId] = useBorrador('comunicacion.destino', '')
  const [motivo, setMotivo] = useBorrador('comunicacion.destino_motivo', '')
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState(null)
  const [resultado, setResultado] = useState(null)

  const destino = destinos.find((d) => d.destino_id === destinoId)
  const valido = destino !== undefined && destino.autorizado && motivo.trim() !== ''

  async function cambiar(habilitado) {
    setTrabajando(true)
    setError(null)
    setResultado(null)
    try {
      const r = await configurarDestinoEnsayo(destinoId, habilitado, motivo.trim())
      setResultado(r.habilitado ? 'Destino de ensayo habilitado.' : 'Destino de ensayo deshabilitado.')
      setMotivo('')
      alCambiar()
    } catch (e) {
      setError(e.message)
    } finally {
      setTrabajando(false)
    }
  }

  return (
    <div className="com-bloque">
      <h3>Destino de ensayo en Telegram</h3>
      <p className="aprob-suave">
        Un destino habilitado recibe planes sintéticos para ensayar el aviso. Solo funciona con chats ya autorizados.
        Por seguridad solo se muestra el final del identificador del chat.
      </p>
      <label>
        Destino
        <select value={destino ? destinoId : ''} onChange={(e) => { setDestinoId(e.target.value); setResultado(null) }} disabled={destinos.length === 0}>
          <option value="">{destinos.length === 0 ? 'No hay destinos de Telegram' : 'Elige un destino'}</option>
          {destinos.map((d) => (
            <option key={d.destino_id} value={d.destino_id}>
              Telegram {d.referencia} · {d.autorizado ? 'autorizado' : 'sin autorizar'} · {estadoEnsayo(d)}
            </option>
          ))}
        </select>
      </label>
      {destino && !destino.autorizado && (
        <p className="aprob-aviso" role="status">Este destino aún no está autorizado: no se puede habilitar para ensayos.</p>
      )}
      <label>
        Motivo
        <textarea rows={2} maxLength={4000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </label>
      {error && <p className="aprob-error" role="alert">{error}</p>}
      {resultado && <p className="com-ok" role="status">{resultado}</p>}
      <div className="aprob-botones">
        <button type="button" disabled={!valido || trabajando} onClick={() => cambiar(true)}>Habilitar ensayo</button>
        <button type="button" className="aprob-secundario" disabled={!valido || trabajando} onClick={() => cambiar(false)}>Deshabilitar</button>
      </div>
    </div>
  )
}

function ComunicacionSector({ planes }) {
  const [listas, setListas] = useState(null)
  const [errorListas, setErrorListas] = useState(null)
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    let activo = true
    Promise.all([listarSectores(), listarDestinos()])
      .then(([sectores, destinos]) => {
        if (!activo) return
        setListas({ sectores, destinos })
        setErrorListas(null)
      })
      .catch((e) => {
        if (activo) setErrorListas(e.message)
      })
    return () => {
      activo = false
    }
  }, [recarga])

  return (
    <section className="com" aria-labelledby="com-titulo">
      <h2 id="com-titulo">Comunicación a la comunidad</h2>
      <p className="aprob-suave">Después de aprobar, decide qué plan se avisa en cada sector y dónde se ensaya.</p>
      {errorListas && (
        <p className="aprob-error" role="alert">
          No se pudieron cargar los sectores y destinos: {errorListas}{' '}
          <button type="button" className="aprob-secundario" onClick={() => setRecarga((n) => n + 1)}>Reintentar</button>
        </p>
      )}
      {listas === null && !errorListas && <p className="aprob-suave">Cargando sectores y destinos…</p>}
      {listas && (
        <div className="com-columnas">
          <Sector planes={planes} sectores={listas.sectores} />
          <Destino destinos={listas.destinos} alCambiar={() => setRecarga((n) => n + 1)} />
        </div>
      )}
    </section>
  )
}

export default ComunicacionSector
