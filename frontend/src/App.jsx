import { useEffect, useRef, useState } from 'react'
import Aprobacion from './paginas/Aprobacion.jsx'
import Necesidades from './paginas/Necesidades.jsx'
import Plan from './paginas/Plan.jsx'
import Reportes from './paginas/Reportes.jsx'
import './App.css'
import './design-system.css'

const PAGINAS = [
  { id: 'reportes', nombre: 'Reportes', detalle: 'Escuchar a la comunidad', simbolo: '01', Componente: Reportes },
  { id: 'necesidades', nombre: 'Necesidades', detalle: 'Priorizar la atención', simbolo: '02', Componente: Necesidades },
  { id: 'plan', nombre: 'Plan de distribución', detalle: 'Revisar rutas y cobertura', simbolo: '03', Componente: Plan },
  { id: 'aprobacion', nombre: 'Aprobación', detalle: 'Autorizar una versión', simbolo: '04', Componente: Aprobacion },
]

function paginaDeLaDireccion() {
  const id = window.location.hash.slice(1)
  return PAGINAS.some((p) => p.id === id) ? id : 'reportes'
}

function App() {
  const [activa, setActiva] = useState(paginaDeLaDireccion)
  const [menuAbierto, setMenuAbierto] = useState(false)
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
  const { Componente, nombre } = PAGINAS.find((p) => p.id === activa)
  useEffect(() => { document.title = `${nombre} · RutaAgua Oeste` }, [nombre])

  function cerrarConEscape(evento) {
    if (evento.key === 'Escape' && menuAbierto) {
      setMenuAbierto(false)
      menuBoton.current?.focus()
    }
  }
  return (
    <div className="app-shell" onKeyDown={cerrarConEscape}>
      <a className="saltar-contenido" href="#contenido" onClick={(e) => { e.preventDefault(); contenido.current?.focus() }}>Saltar al contenido</a>
      <aside className="sidebar">
        <a className="marca" href="#reportes" aria-label="RutaAgua Oeste, reportes">
          <span className="marca-simbolo"><svg width="24" height="28" viewBox="0 0 24 28" fill="none" aria-hidden="true"><path d="M12 2S3 12 3 17a9 9 0 0 0 18 0C21 12 12 2 12 2Z" stroke="currentColor" strokeWidth="1.7"/><path d="M7 18a5 5 0 0 0 5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg></span>
          <span>RutaAgua <strong>Oeste</strong><small>Coordinación de distribución</small></span>
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
        <header className="workspace-header"><span>Operaciones <span aria-hidden="true">/</span> <strong>{nombre}</strong></span><span className="contexto-region">Panamá Oeste</span></header>
        <main id="contenido" ref={contenido} tabIndex={-1} className="app-main"><Componente /></main>
        <footer className="workspace-footer"><span>RutaAgua Oeste</span><span>Propuesta · Revisión humana · Comunicación</span></footer>
      </div>
    </div>
  )
}
export default App
