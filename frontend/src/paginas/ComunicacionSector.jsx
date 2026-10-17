import { useState } from 'react'
import { configurarDestinoEnsayo, estadoSector, seleccionarPlanSector } from '../api/sectores.js'
import './ComunicacionSector.css'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const ESTADOS_SECTOR = {
  sin_plan_vigente: 'Sin plan vigente',
  con_plan_vigente: 'Con plan vigente',
}

const ESTADOS_PUNTO = {
  sin_asignacion: 'Sin asignación',
  asignado: 'Asignado',
}

function Sector({ planes }) {
  const aprobados = planes.filter((p) => p.estado === 'aprobado')
  const [sectorId, setSectorId] = useState('')
  const [estado, setEstado] = useState(null)
  const [eleccion, setEleccion] = useState('')
  const [motivo, setMotivo] = useState('')
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState(null)
  const [resultado, setResultado] = useState(null)

  const sectorValido = UUID.test(sectorId.trim())
  const plan = aprobados.find((p) => `${p.plan_id}:${p.version}` === eleccion)

  async function consultar() {
    setTrabajando(true)
    setError(null)
    try {
      setEstado(await estadoSector(sectorId.trim()))
    } catch (e) {
      setEstado(null)
      setError(e.message)
    } finally {
      setTrabajando(false)
    }
  }

  async function elegir(evento) {
    evento.preventDefault()
    setTrabajando(true)
    setError(null)
    setResultado(null)
    try {
      const r = await seleccionarPlanSector(sectorId.trim(), plan, motivo.trim())
      setResultado(r.repetido ? 'Ese plan ya estaba elegido para el sector.' : 'Plan elegido para el sector.')
      setMotivo('')
      setEstado(await estadoSector(sectorId.trim()))
    } catch (e) {
      setError(e.message)
    } finally {
      setTrabajando(false)
    }
  }

  return (
    <form className="com-bloque" onSubmit={elegir}>
      <h3>Plan que se comunica por sector</h3>
      <p className="aprob-suave">
        Comunicación avisa a la comunidad solo con el plan aprobado que elijas aquí. Pega el identificador del sector.
      </p>
      <div className="com-fila">
        <label>
          Sector
          <input value={sectorId} onChange={(e) => { setSectorId(e.target.value); setEstado(null); setResultado(null) }} placeholder="Identificador del sector" spellCheck={false} />
        </label>
        <button type="button" className="aprob-secundario" disabled={!sectorValido || trabajando} onClick={consultar}>
          Ver estado
        </button>
      </div>
      {sectorId.trim() !== '' && !sectorValido && <p className="aprob-suave">El identificador tiene formato de UUID.</p>}
      {estado && (
        <div className="com-estado" role="status">
          <p>
            <strong>{estado.sector.nombre}</strong> · {ESTADOS_SECTOR[estado.estado] ?? estado.estado}
            {estado.plan_vigente && <> · plan {estado.plan_vigente.plan_id.slice(0, 8)} v{estado.plan_vigente.version}</>}
          </p>
          <ul>
            {estado.puntos.map((p) => (
              <li key={p.punto_atencion_id}>
                <span>{p.nombre}</span>
                <span>{ESTADOS_PUNTO[p.estado] ?? p.estado}{p.litros_asignados ? ` · ${p.litros_asignados.toLocaleString('es-PA')} L` : ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <label>
        Plan aprobado
        <select value={eleccion} onChange={(e) => setEleccion(e.target.value)} disabled={aprobados.length === 0}>
          <option value="">{aprobados.length === 0 ? 'No hay planes aprobados' : 'Elige un plan'}</option>
          {aprobados.map((p) => (
            <option key={`${p.plan_id}:${p.version}`} value={`${p.plan_id}:${p.version}`}>
              Plan {p.plan_id.slice(0, 8)} versión {p.version}
            </option>
          ))}
        </select>
      </label>
      <label>
        Motivo
        <textarea rows={2} maxLength={4000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </label>
      {error && <p className="aprob-error" role="alert">{error}</p>}
      {resultado && <p className="com-ok" role="status">{resultado}</p>}
      <div className="aprob-botones">
        <button type="submit" disabled={!sectorValido || !plan || motivo.trim() === '' || trabajando}>
          {trabajando ? 'Guardando…' : 'Elegir para este sector'}
        </button>
      </div>
    </form>
  )
}

function Destino() {
  const [destinoId, setDestinoId] = useState('')
  const [motivo, setMotivo] = useState('')
  const [trabajando, setTrabajando] = useState(false)
  const [error, setError] = useState(null)
  const [resultado, setResultado] = useState(null)

  const valido = UUID.test(destinoId.trim()) && motivo.trim() !== ''

  async function cambiar(habilitado) {
    setTrabajando(true)
    setError(null)
    setResultado(null)
    try {
      const r = await configurarDestinoEnsayo(destinoId.trim(), habilitado, motivo.trim())
      setResultado(r.habilitado ? 'Destino de ensayo habilitado.' : 'Destino de ensayo deshabilitado.')
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
      </p>
      <label>
        Destino
        <input value={destinoId} onChange={(e) => { setDestinoId(e.target.value); setResultado(null) }} placeholder="Identificador del destino" spellCheck={false} />
      </label>
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
  return (
    <section className="com" aria-labelledby="com-titulo">
      <h2 id="com-titulo">Comunicación a la comunidad</h2>
      <p className="aprob-suave">Después de aprobar, decide qué plan se avisa en cada sector y dónde se ensaya.</p>
      <div className="com-columnas">
        <Sector planes={planes} />
        <Destino />
      </div>
    </section>
  )
}

export default ComunicacionSector
