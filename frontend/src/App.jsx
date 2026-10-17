import { useCallback, useEffect, useRef, useState } from 'react'
import Acceso from './paginas/Acceso.jsx'
import { cerrarSesion, obtenerToken } from './api/sesion.js'
import Aprobacion from './paginas/Aprobacion.jsx'
import Necesidades from './paginas/Necesidades.jsx'
import Plan from './paginas/Plan.jsx'
import Reportes from './paginas/Reportes.jsx'
import logoCircular from './assets/h2oeste-circular.webp'
import './App.css'
import './design-system.css'
import './editorial.css'
import './transiciones.css'

const PAGINAS = [
  { id: 'reportes', nombre: 'Reportes', detalle: 'Escuchar a la comunidad', simbolo: '01', Componente: Reportes },
  { id: 'necesidades', nombre: 'Necesidades', detalle: 'Priorizar la atención', simbolo: '02', Componente: Necesidades },
  { id: 'plan', nombre: 'Plan de distribución', detalle: 'Revisar rutas y cobertura', simbolo: '03', Componente: Plan },
  { id: 'aprobacion', nombre: 'Aprobación', detalle: 'Autorizar una versión', simbolo: '04', Componente: Aprobacion },
]

function paginaDeLaDireccion() {
  const id = window.location.hash.slice(1)
  return id === 'acceso' || PAGINAS.some((p) => p.id === id) ? id : 'reportes'
}

function App() {
  const [activa, setActiva] = useState(paginaDeLaDireccion)
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [conSesion, setConSesion] = useState(() => Boolean(obtenerToken()))
  const [aviso, setAviso] = useState(null)
  const alExpirar = useCallback(() => {
    setConSesion(false)
    setAviso('Tu sesión venció. Inicia sesión de nuevo para continuar.')
  }, [])
  async function salir() {
    await cerrarSesion()
    setAviso(null)
    setConSesion(false)
  }
  // Tras iniciar sesión se abre la página que se pidió en la dirección, o Reportes si no hubo ninguna.
  function alEntrar() {
    const destino = paginaDeLaDireccion()
    const pagina = destino === 'acceso' ? 'reportes' : destino
    setAviso(null)
    setConSesion(true)
    setActiva(pagina)
    window.location.hash = pagina
  }
  const menuBoton = useRef(null)
  const contenido = useRef(null)
  useEffect(() => {
    const alCambiar = () => {
      setActiva(paginaDeLaDireccion())
      setMenuAbierto(false)
      contenido.current?.focus()
    }
    window.addEventListener('hashchange', alCambiar)
    return () => window.removeEventListener('hashchange', alCambiar)
  }, [])
  const { Componente, nombre } = activa === 'acceso'
    ? { Componente: Acceso, nombre: 'Mi cuenta' }
    : PAGINAS.find((p) => p.id === activa)
  useEffect(() => { document.title = `${conSesion ? nombre : 'Acceso'} · H2Oeste` }, [nombre, conSesion])

  function cerrarConEscape(evento) {
    if (evento.key === 'Escape' && menuAbierto) {
      setMenuAbierto(false)
      menuBoton.current?.focus()
    }
  }
  // La primera pantalla de quien no ha iniciado sesión es el acceso: el panel no se muestra sin sesión.
  if (!conSesion) {
    return (
      <main id="contenido" className="pantalla-acceso">
        <Acceso aviso={aviso} alEntrar={alEntrar} conSesion={false} />
      </main>
    )
  }
  return (
    <div className="app-shell" onKeyDown={cerrarConEscape}>
      <a className="saltar-contenido" href="#contenido" onClick={(e) => { e.preventDefault(); contenido.current?.focus() }}>Saltar al contenido</a>
      <aside className="sidebar">
        <a className="marca" href="#reportes" aria-label="H2Oeste, reportes">
          <img className="marca-logo" src={logoCircular} width="44" height="44" alt="" />
          <span>H2<strong>Oeste</strong><small>Coordinación de distribución</small></span>
        </a>
        <button ref={menuBoton} className="menu-boton" aria-expanded={menuAbierto} aria-controls="navegacion" onClick={() => setMenuAbierto(!menuAbierto)}>{menuAbierto ? 'Cerrar' : 'Menú'}<span aria-hidden="true">{menuAbierto ? '×' : '☰'}</span></button>
        <nav id="navegacion" className={`navegacion ${menuAbierto ? 'navegacion-abierta' : ''}`} aria-label="Secciones del panel">
          <p className="nav-etiqueta">CENTRO DE OPERACIONES</p>
          {PAGINAS.map((p) => (
            <a key={p.id} href={`#${p.id}`} className="nav-enlace" aria-current={p.id === activa ? 'page' : undefined} onClick={() => { setMenuAbierto(false); contenido.current?.focus() }}>
              <span className="nav-numero" aria-hidden="true">{p.simbolo}</span><span>{p.nombre}<small>{p.detalle}</small></span>
            </a>
          ))}
          <div className="sidebar-nota"><p>Cada decisión cuenta.<small>Información clara para coordinar la atención.</small></p></div>
        </nav>
      </aside>
      <div className="app-workspace">
        <header className="workspace-header"><span>{activa === 'acceso' ? 'Cuenta' : 'Operaciones'} <span aria-hidden="true">/</span> <strong>{nombre}</strong></span><a className="cuenta-enlace" href="#acceso" aria-current={activa === 'acceso' ? 'page' : undefined}><span className="cuenta-avatar" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.7"><circle cx="12" cy="8" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/></svg></span>Mi cuenta</a></header>
        <main id="contenido" ref={contenido} tabIndex={-1} className="app-main"><Componente conSesion={conSesion} alExpirar={alExpirar} alSalir={salir} alEntrar={alEntrar} /></main>
        <footer className="workspace-footer"><span>H2Oeste</span><span>Propuesta · Revisión humana · Comunicación</span></footer>
      </div>
    </div>
  )
}
export default App
