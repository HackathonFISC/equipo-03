import { useEffect, useRef, useState } from 'react'
import Icono from './Iconos.jsx'

// Menú de la cuenta en el encabezado: quién eres y cerrar sesión desde cualquier página.
export default function MenuCuenta({ perfil, enCuenta, alSalir }) {
  const [abierto, setAbierto] = useState(false)
  const raiz = useRef(null)
  const boton = useRef(null)

  useEffect(() => {
    if (!abierto) return
    const fuera = (e) => { if (!raiz.current?.contains(e.target)) setAbierto(false) }
    const tecla = (e) => {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      setAbierto(false)
      boton.current?.focus()
    }
    document.addEventListener('pointerdown', fuera)
    document.addEventListener('keydown', tecla)
    return () => {
      document.removeEventListener('pointerdown', fuera)
      document.removeEventListener('keydown', tecla)
    }
  }, [abierto])

  return (
    <div className="cuenta-menu" ref={raiz}>
      <button
        ref={boton} type="button" className="cuenta-chip" aria-expanded={abierto} aria-controls="menu-cuenta"
        aria-current={enCuenta ? 'page' : undefined} onClick={() => setAbierto(!abierto)}
      >
        <span className="avatar" aria-hidden="true">{perfil.iniciales}</span>
        <span className="cuenta-chip-texto">
          <strong>{perfil.nombre}</strong>
          <small>{perfil.rol ?? 'Sesión iniciada'}</small>
        </span>
        <Icono nombre="chevron" tamano={18} />
      </button>
      {abierto && (
        <div id="menu-cuenta" className="cuenta-panel" role="group" aria-label="Cuenta">
          <div className="cuenta-panel-quien">
            <span className="avatar avatar-grande" aria-hidden="true">{perfil.iniciales}</span>
            <p><strong>{perfil.nombre}</strong><small>{perfil.correo ?? 'Sin correo visible'}</small></p>
          </div>
          <a className="cuenta-opcion" href="#acceso" onClick={() => setAbierto(false)}>
            <Icono nombre="cuenta" tamano={18} />Ver mi cuenta
          </a>
          <button type="button" className="cuenta-opcion cuenta-salir" onClick={() => { setAbierto(false); alSalir() }}>
            <Icono nombre="salir" tamano={18} />Cerrar sesión
          </button>
        </div>
      )}
    </div>
  )
}
