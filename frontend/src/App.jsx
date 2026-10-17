import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Acceso from './paginas/Acceso.jsx'
import Cuenta from './paginas/Cuenta.jsx'
import Icono from './Iconos.jsx'
import MenuCuenta from './MenuCuenta.jsx'
import { cerrarSesion, obtenerSesion, obtenerToken } from './api/sesion.js'
import { descartarBorradores } from './borradores.js'
import { datosDelToken, perfilDe } from './perfil.js'
import Aprobacion from './paginas/Aprobacion.jsx'
import Eventos from './paginas/Eventos.jsx'
import Necesidades from './paginas/Necesidades.jsx'
import Plan from './paginas/Plan.jsx'
import Reportes from './paginas/Reportes.jsx'
import logoCircular from './assets/h2oeste-circular.webp'
import './App.css'
import './design-system.css'
import './editorial.css'
import './transiciones.css'
import './Navegacion.css'

const PAGINAS = [
  { id: 'reportes', nombre: 'Reportes', detalle: 'Escuchar a la comunidad', grupo: 'flujo', Componente: Reportes },
  { id: 'necesidades', nombre: 'Necesidades', detalle: 'Priorizar la atención', grupo: 'flujo', Componente: Necesidades },
  { id: 'plan', nombre: 'Plan de distribución', detalle: 'Revisar rutas y cobertura', grupo: 'flujo', Componente: Plan },
  { id: 'aprobacion', nombre: 'Aprobación', detalle: 'Autorizar una versión', grupo: 'flujo', Componente: Aprobacion },
  { id: 'eventos', nombre: 'Eventos', detalle: 'Ver qué decidió cada agente', grupo: 'seguimiento', Componente: Eventos },
]
const FLUJO = PAGINAS.filter((p) => p.grupo === 'flujo')
const SEGUIMIENTO = PAGINAS.filter((p) => p.grupo === 'seguimiento')

function paginaDeLaDireccion() {
  const id = window.location.hash.slice(1)
  return id === 'acceso' || PAGINAS.some((p) => p.id === id) ? id : 'reportes'
}

function App() {
  const [activa, setActiva] = useState(paginaDeLaDireccion)
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [conSesion, setConSesion] = useState(() => Boolean(obtenerToken()))
  const [aviso, setAviso] = useState(null)
  // Rol que informa GET /sesion; hasta que llega (o si falla) el perfil muestra solo lo que dice el token.
  const [sesion, setSesion] = useState(null)
  const alExpirar = useCallback(() => {
    setConSesion(false)
    setAviso('Tu sesión venció. Inicia sesión de nuevo para continuar.')
  }, [])
  async function salir() {
    await cerrarSesion()
    descartarBorradores()
    setAviso(null)
    setSesion(null)
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
  useEffect(() => {
    if (!conSesion) return
    let cancelado = false
    obtenerSesion().then((datos) => { if (!cancelado) setSesion(datos) }).catch(() => { if (!cancelado) setSesion(false) })
    return () => { cancelado = true }
  }, [conSesion])
  const datosToken = useMemo(() => (conSesion ? datosDelToken(obtenerToken()) : { correo: null, vence: null }), [conSesion])
  const perfil = useMemo(() => perfilDe(datosToken, sesion), [datosToken, sesion])
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
    ? { Componente: Cuenta, nombre: 'Mi cuenta' }
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
        <Acceso aviso={aviso} alEntrar={alEntrar} />
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
          <p className="nav-grupo" id="nav-flujo">Flujo de trabajo</p>
          <ol className="nav-lista nav-pasos" aria-labelledby="nav-flujo">
            {FLUJO.map((p, i) => (
              <li key={p.id}>
                <a href={`#${p.id}`} className="nav-enlace" aria-current={p.id === activa ? 'page' : undefined} onClick={() => { setMenuAbierto(false); contenido.current?.focus() }}>
                  <span className="nav-paso" aria-hidden="true">{i + 1}</span><span>{p.nombre}<small>{p.detalle}</small></span>
                </a>
              </li>
            ))}
          </ol>
          <p className="nav-grupo" id="nav-seguimiento">Seguimiento</p>
          <ul className="nav-lista" aria-labelledby="nav-seguimiento">
            {SEGUIMIENTO.map((p) => (
              <li key={p.id}>
                <a href={`#${p.id}`} className="nav-enlace" aria-current={p.id === activa ? 'page' : undefined} onClick={() => { setMenuAbierto(false); contenido.current?.focus() }}>
                  <span className="nav-icono" aria-hidden="true"><Icono nombre={p.id} tamano={16} /></span><span>{p.nombre}<small>{p.detalle}</small></span>
                </a>
              </li>
            ))}
          </ul>
          <div className="sidebar-nota"><p>Cada decisión cuenta.<small>Información clara para coordinar la atención.</small></p></div>
        </nav>
      </aside>
      <div className="app-workspace">
        <header className="workspace-header"><span>{activa === 'acceso' ? 'Cuenta' : 'Operaciones'} <span aria-hidden="true">/</span> <strong>{nombre}</strong></span><MenuCuenta perfil={perfil} enCuenta={activa === 'acceso'} alSalir={salir} /></header>
        <main id="contenido" ref={contenido} tabIndex={-1} className="app-main"><Componente conSesion={conSesion} alExpirar={alExpirar} alSalir={salir} alEntrar={alEntrar} perfil={perfil} /></main>
        <footer className="workspace-footer"><span>H2Oeste</span><span>Propuesta · Revisión humana · Comunicación</span></footer>
      </div>
    </div>
  )
}
export default App
