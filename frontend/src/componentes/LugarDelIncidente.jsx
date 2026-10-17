import { useId, useRef, useState } from 'react'
import { validarLugar } from '../api/lugar.js'
import { useBorrador } from '../useBorrador.js'
import {
  coordenadasDe, enlaceMapa, EVIDENCIA_MAX, EVIDENCIA_MIN, evidenciaValida,
  lugarPorValidar, textoCoordenadas, urlMapaIncrustado,
} from '../lugar.js'
import './LugarDelIncidente.css'

const ESTADO = {
  pendiente: ['Lugar por validar', 'aviso'],
  validada: ['Lugar validado', 'ok'],
  rechazada: ['Lugar rechazado', 'error'],
}

const MENSAJE_ERROR = {
  sin_permiso: 'Solo un coordinador activo puede validar un lugar.',
  version_obsoleta: 'El incidente cambió mientras lo revisabas. Cierra esta ventana, actualiza la página y revisa de nuevo.',
  datos_insuficientes: 'Este incidente no tiene un punto con ubicación y reportes vinculados que se pueda validar.',
  contrato_invalido: 'La evidencia no es válida. Escribe cómo confirmaste el lugar.',
  sin_conexion: 'No se pudo conectar con la API.',
}

function Mapa({ coordenadas, nombre }) {
  const url = urlMapaIncrustado(coordenadas)
  if (!coordenadas) {
    return <p className="lugar-sin-mapa" role="note">Este punto no tiene coordenadas en el catálogo, así que no se puede ver en el mapa.</p>
  }
  if (!url) {
    return (
      <div className="lugar-sin-mapa" role="note">
        <p>
          El mapa incrustado necesita la clave de Google Maps (<code>VITE_GOOGLE_MAPS_API_KEY</code> en <code>frontend/.env</code>).
          Mientras tanto, abre el punto directamente en Google Maps.
        </p>
      </div>
    )
  }
  return (
    <iframe
      className="lugar-mapa" title={`Mapa de ${nombre}`} src={url} loading="lazy"
      referrerPolicy="strict-origin-when-cross-origin" allowFullScreen
    />
  )
}

// Estado del lugar de un incidente y, para el coordinador, la acción de validarlo con evidencia.
export default function LugarDelIncidente({ item, conSesion, alActualizar }) {
  const dialogo = useRef(null)
  const id = useId()
  const [abierto, setAbierto] = useState(false)
  const [evidencia, setEvidencia] = useBorrador(`lugar.${item.incidente_id}:${item.version}.evidencia`, '')
  const [confirmo, setConfirmo] = useState(false)
  const [estado, setEstado] = useState({ fase: 'libre' })

  const punto = item.punto
  const coordenadas = coordenadasDe(punto)
  const [etiqueta, tono] = ESTADO[item.estado_validacion] ?? [item.estado_validacion, 'aviso']
  const puedeValidar = conSesion && lugarPorValidar(item) && coordenadas !== null
  const listo = evidenciaValida(evidencia) && confirmo && estado.fase !== 'enviando'

  function abrir() {
    setEstado({ fase: 'libre' })
    setConfirmo(false)
    setAbierto(true)
    dialogo.current?.showModal()
  }

  function cerrar() {
    dialogo.current?.close()
  }

  async function enviar(evento) {
    evento.preventDefault()
    if (!listo) return
    setEstado({ fase: 'enviando' })
    try {
      await validarLugar(item.incidente_id, { version_incidente: item.version, evidencia: evidencia.trim() })
      setEvidencia('')
      setEstado({ fase: 'libre' })
      dialogo.current?.close()
      alActualizar?.()
    } catch (e) {
      setEstado({ fase: 'error', codigo: e.codigo, mensaje: e.message })
    }
  }

  return (
    <div className="lugar" data-tono={tono}>
      <span className="lugar-chip" data-tono={tono}>{etiqueta}</span>
      {punto && <span className="lugar-nombre">{punto.nombre}</span>}
      <button type="button" className="lugar-boton" onClick={abrir} disabled={!punto}>
        {puedeValidar ? 'Validar el lugar' : 'Ver en el mapa'}
      </button>

      <dialog
        ref={dialogo} className="lugar-dialogo" aria-labelledby={`${id}-t`}
        onClose={() => setAbierto(false)}
        onClick={(e) => { if (e.target === dialogo.current) cerrar() }}
      >
        {abierto && punto && (
          <form onSubmit={enviar} noValidate>
            <h2 id={`${id}-t`}>{puedeValidar ? 'Validar el lugar' : 'Lugar del incidente'}</h2>
            <p className="lugar-punto"><strong>{punto.nombre}</strong>{[punto.corregimiento, punto.distrito].filter(Boolean).length > 0 && ` · ${[punto.corregimiento, punto.distrito].filter(Boolean).join(', ')}`}</p>
            <Mapa coordenadas={coordenadas} nombre={punto.nombre} />
            {coordenadas && (
              <p className="lugar-datos">
                {textoCoordenadas(coordenadas)}
                {punto.fuente_ubicacion && ` · fuente: ${punto.fuente_ubicacion}`}
                {punto.precision_metros != null && ` · precisión ${punto.precision_metros} m`}
                {' · '}
                <a href={enlaceMapa(coordenadas)} target="_blank" rel="noopener noreferrer">Abrir en Google Maps</a>
              </p>
            )}

            {puedeValidar ? (
              <>
                <p className="lugar-aviso">
                  Validar el lugar confirma que este punto del mapa es donde ocurre el reporte. No acredita que haya agua,
                  ni la capacidad de recepción, ni que se pueda entregar.
                </p>
                <label className="lugar-campo" htmlFor={`${id}-ev`}>
                  <span>¿Cómo lo confirmaste?</span>
                  <small>Ej.: llamada a la junta comunal a las 9:10; coincide con el punto del mapa. Queda registrado con tu nombre y la hora.</small>
                </label>
                <textarea
                  id={`${id}-ev`} rows={3} maxLength={EVIDENCIA_MAX} value={evidencia}
                  onChange={(e) => setEvidencia(e.target.value)}
                />
                <p className="lugar-contador" aria-live="polite">
                  {evidencia.trim().length < EVIDENCIA_MIN
                    ? `Escribe al menos ${EVIDENCIA_MIN} caracteres (${evidencia.trim().length}).`
                    : `${evidencia.trim().length} de ${EVIDENCIA_MAX} caracteres.`}
                </p>
                <label className="lugar-confirmo">
                  <input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} />
                  <span>Confirmo que este es el lugar del reporte.</span>
                </label>
                {estado.fase === 'error' && (
                  <div className="lugar-error" role="alert">
                    <p>{MENSAJE_ERROR[estado.codigo] ?? 'No se pudo validar el lugar.'}</p>
                    {estado.mensaje && <p className="lugar-detalle">{estado.mensaje}</p>}
                  </div>
                )}
              </>
            ) : (
              <p className="lugar-aviso">
                {item.estado_validacion === 'validada'
                  ? 'Una persona ya validó este lugar. El detalle queda en Eventos.'
                  : !conSesion
                    ? 'Inicia sesión como coordinador para validar el lugar.'
                    : !coordenadas
                      ? 'Sin coordenadas en el catálogo no se puede validar el lugar en el mapa.'
                      : 'Este lugar no está pendiente de validación.'}
              </p>
            )}

            <div className="lugar-acciones">
              <button type="button" className="lugar-cancelar" onClick={cerrar}>{puedeValidar ? 'Cancelar' : 'Cerrar'}</button>
              {puedeValidar && (
                <button type="submit" className="lugar-confirmar" disabled={!listo}>
                  {estado.fase === 'enviando' ? 'Validando…' : 'Validar lugar'}
                </button>
              )}
            </div>
          </form>
        )}
      </dialog>
    </div>
  )
}
