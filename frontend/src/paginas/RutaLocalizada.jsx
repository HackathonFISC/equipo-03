import { useState } from 'react'
import { llamarConSesion } from '../api/sesion.js'

export default function RutaLocalizada() {
  const [opciones, setOpciones] = useState(null)
  const [deposito, setDeposito] = useState('')
  const [seleccion, setSeleccion] = useState([])
  const [ruta, setRuta] = useState(null)
  const [error, setError] = useState(null)
  const [ocupado, setOcupado] = useState(false)

  async function cargar() {
    setOcupado(true); setError(null); setRuta(null); setSeleccion([]); setOpciones(null)
    try {
      const datos = await llamarConSesion('/planes/destinos-localizados')
      setOpciones(datos); setDeposito(datos.depositos[0]?.deposito_id ?? '')
    } catch (e) { setError(e.message) }
    finally { setOcupado(false) }
  }

  function elegir(id, marcado) {
    setSeleccion((actual) => marcado ? [...actual, id] : actual.filter((x) => x !== id))
    setRuta(null); setError(null)
  }

  async function calcular(evento) {
    evento.preventDefault(); setOcupado(true); setError(null); setRuta(null)
    try {
      setRuta(await llamarConSesion('/planes/ruta-localizada', {
        metodo: 'POST', cuerpo: { deposito_id: deposito, reportes_ids: seleccion },
      }))
    } catch (e) { setError(e.message) }
    finally { setOcupado(false) }
  }

  return <section className="mensaje" aria-labelledby="titulo-ruta-localizada">
    <h2 id="titulo-ruta-localizada">Recorrido de reportes localizados</h2>
    <p>Elige hasta seis lugares para comparar un recorrido por carretera desde el depósito y de regreso.</p>
    <button type="button" onClick={cargar} disabled={ocupado}>{ocupado ? 'Consultando…' : 'Cargar destinos disponibles'}</button>
    {error && <p role="alert">{error}</p>}
    {opciones && <form onSubmit={calcular}>
      {opciones.depositos.length === 0 ? <p>No hay un depósito activo con coordenadas. Registra el depósito para calcular el recorrido.</p> : <>
        <label>Depósito <select value={deposito} disabled={ocupado} onChange={(e) => { setDeposito(e.target.value); setRuta(null) }}>
          {opciones.depositos.map((d) => <option key={d.deposito_id} value={d.deposito_id}>{d.nombre}</option>)}
        </select></label>
        <fieldset disabled={ocupado}><legend>Destinos ({seleccion.length}/6)</legend>
          {opciones.destinos.length === 0 && <p>Aún no hay reportes con coordenadas disponibles.</p>}
          {opciones.destinos.map((d) => <label key={d.reporte_id} style={{ display: 'block', marginBlock: '0.5rem' }}>
            <input type="checkbox" checked={seleccion.includes(d.reporte_id)}
              disabled={!seleccion.includes(d.reporte_id) && seleccion.length >= 6}
              onChange={(e) => elegir(d.reporte_id, e.target.checked)} />{' '}
            {d.nombre} · {d.ubicacion.latitud.toFixed(5)}, {d.ubicacion.longitud.toFixed(5)}
            {d.ubicacion.fuente === 'geocodificada' && <span translate="no"> · Google Maps</span>}
          </label>)}
        </fieldset>
        <button type="submit" disabled={ocupado || seleccion.length === 0 || !deposito}>Calcular recorrido</button>
      </>}
    </form>}
    {ruta && <div aria-live="polite">
      <h3>Recorrido sugerido</h3>
      <p>{ruta.duracion_minutos} min de conducción · {(ruta.distancia_metros / 1000).toFixed(1)} km · incluye regreso al depósito</p>
      <ol>{ruta.paradas.map((p, i) => <li key={p.reporte_id}>
        {p.nombre}{' '}<a href={ruta.tramos_navegacion[i]} target="_blank" rel="noopener noreferrer">Navegar a esta parada</a>
      </li>)}</ol>
      <p><a href={ruta.tramos_navegacion.at(-1)} target="_blank" rel="noopener noreferrer">Navegar de regreso al depósito</a></p>
      <p><a href={ruta.navegacion_url} target="_blank" rel="noopener noreferrer">Abrir recorrido completo en Google Maps</a></p>
      <p>Tiempo estimado sin tráfico en vivo. La asignación de agua, las descargas y la disponibilidad del camión se revisan en el plan de distribución.</p>
      <p translate="no" style={{ fontFamily: 'sans-serif', fontSize: '14px', fontWeight: 400 }}>Google Maps</p>
    </div>}
  </section>
}
