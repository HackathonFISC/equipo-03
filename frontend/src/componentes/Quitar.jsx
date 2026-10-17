import { useId, useRef } from 'react'
import './Quitar.css'

const ARTICULO = { reporte: 'este reporte', incidente: 'este incidente', plan: 'este plan' }

// Botón con ventana de confirmación. Quita el registro del panel; no lo borra de la base de datos.
export function BotonQuitar({ tipo, nombre, alConfirmar }) {
  const dialogo = useRef(null)
  const id = useId()

  function confirmar() {
    dialogo.current?.close()
    alConfirmar()
  }

  return (
    <>
      <button type="button" className="quitar-boton" onClick={() => dialogo.current?.showModal()}>
        Quitar del panel
      </button>
      <dialog
        ref={dialogo}
        className="quitar-dialogo"
        aria-labelledby={`${id}-t`}
        aria-describedby={`${id}-d`}
        onClick={(e) => { if (e.target === dialogo.current) dialogo.current.close() }}
      >
        <h2 id={`${id}-t`}>¿Quitar {ARTICULO[tipo]} del panel?</h2>
        {nombre && <p className="quitar-nombre">{nombre}</p>}
        <p id={`${id}-d`}>
          No se borra de la base de datos: sigue en el historial y en los cálculos. Solo deja de mostrarse en este
          navegador, y puedes volver a mostrarlo cuando quieras.
        </p>
        <div className="quitar-acciones">
          <button type="button" className="quitar-cancelar" onClick={() => dialogo.current?.close()}>Cancelar</button>
          <button type="button" className="quitar-confirmar" onClick={confirmar}>Quitar del panel</button>
        </div>
      </dialog>
    </>
  )
}

// Aviso con la cuenta de lo quitado y la forma de volver a mostrarlo.
export function BarraQuitados({ cantidad, unidad, plural, nota, alMostrar }) {
  if (cantidad <= 0) return null
  return (
    <p className="quitados-barra" role="status">
      <span>
        {cantidad} {cantidad === 1 ? unidad : plural} {cantidad === 1 ? 'quitado' : 'quitados'} de este panel.
        {nota ? ` ${nota}` : ''}
      </span>
      <button type="button" onClick={alMostrar}>Mostrar de nuevo</button>
    </p>
  )
}
