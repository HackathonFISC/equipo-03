import { useCallback, useState } from 'react'
import { guardarBorrador, leerBorrador } from './borradores.js'

// Igual que useState, pero el valor sobrevive a salir de la página. Si cambia la clave
// (por ejemplo, otro plan), se lee el borrador de esa clave.
export function useBorrador(clave, inicial) {
  const [estado, setEstado] = useState(() => ({ clave, valor: leerBorrador(clave, inicial) }))
  let valor = estado.valor
  if (estado.clave !== clave) {
    valor = leerBorrador(clave, inicial)
    setEstado({ clave, valor })
  }
  const poner = useCallback((nuevo) => {
    setEstado((previo) => {
      const base = previo.clave === clave ? previo.valor : leerBorrador(clave, inicial)
      const siguiente = typeof nuevo === 'function' ? nuevo(base) : nuevo
      guardarBorrador(clave, siguiente)
      return { clave, valor: siguiente }
    })
    // `inicial` es solo el valor de partida: no debe recrear el setter en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave])
  return [valor, poner]
}
