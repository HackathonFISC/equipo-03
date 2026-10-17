// Íconos de trazo para la navegación y la cuenta. Decorativos: el texto siempre acompaña.
const FORMAS = {
  eventos: <><path d="M4 6h16M4 12h10M4 18h13" /><circle cx="19" cy="12" r="1.2" /></>,
  salir: <><path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" /><path d="M16 8l4 4-4 4M20 12H9" /></>,
  cuenta: <><circle cx="12" cy="8" r="3.5" /><path d="M5 21v-2a7 7 0 0 1 14 0v2" /></>,
  chevron: <path d="m7 10 5 5 5-5" />,
  ok: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  limite: <><circle cx="12" cy="12" r="8.5" /><path d="M8 12h8" /></>,
  reloj: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>,
  volver: <path d="M19 12H5M11 6l-6 6 6 6" />,
}

export default function Icono({ nombre, tamano = 20 }) {
  return (
    <svg className="icono" viewBox="0 0 24 24" width={tamano} height={tamano} aria-hidden="true" focusable="false"
      fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {FORMAS[nombre]}
    </svg>
  )
}
