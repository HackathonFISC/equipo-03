import { useEffect, useState } from 'react'
import Necesidades from './paginas/Necesidades.jsx'
import Plan from './paginas/Plan.jsx'
import Reportes from './paginas/Reportes.jsx'
import './App.css'

const PAGINAS = [
  { id: 'reportes', nombre: 'Reportes', Componente: Reportes },
  { id: 'necesidades', nombre: 'Necesidades', Componente: Necesidades },
  { id: 'plan', nombre: 'Plan', Componente: Plan },
]

// La página activa vive en la dirección (#reportes, #necesidades, #plan) para que recargar no la pierda.
function paginaDeLaDireccion() {
  const id = window.location.hash.replace('#', '')
  return PAGINAS.some((p) => p.id === id) ? id : 'reportes'
}

function App() {
  const [activa, setActiva] = useState(paginaDeLaDireccion)

  useEffect(() => {
    const alCambiar = () => setActiva(paginaDeLaDireccion())
    window.addEventListener('hashchange', alCambiar)
    return () => window.removeEventListener('hashchange', alCambiar)
  }, [])

  const { Componente } = PAGINAS.find((p) => p.id === activa)

  return (
    <>
      <header className="barra">
        <strong>RutaAgua Oeste</strong>
        <nav aria-label="Secciones del panel">
          {PAGINAS.map((p) => (
            <a
              key={p.id}
              href={`#${p.id}`}
              className="barra-enlace"
              aria-current={p.id === activa ? 'page' : undefined}
            >
              {p.nombre}
            </a>
          ))}
        </nav>
      </header>
      <main>
        <Componente />
      </main>
    </>
  )
}

export default App
