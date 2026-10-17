// Comprobación del lugar de cada punto antes de enviar la revisión.
// Repite lo que la API exige al calcular (_comprobar_ambito): todos los incidentes del ámbito deben tener
// un punto de atención y no puede haber dos incidentes en el mismo punto. Así se avisa antes de enviar
// en vez de recibir el rechazo después. La API sigue siendo quien decide.

export const SIN_LUGAR = 'sin_lugar'
export const LUGAR_REPETIDO = 'lugar_repetido'

export function lugaresDelAmbito(items) {
  const lista = Array.isArray(items) ? items : []
  const sinLugar = lista.filter((i) => !i.punto_atencion_id)
  const porPunto = new Map()
  for (const i of lista) {
    if (!i.punto_atencion_id) continue
    porPunto.set(i.punto_atencion_id, [...(porPunto.get(i.punto_atencion_id) ?? []), i])
  }
  const repetidos = [...porPunto.values()].filter((grupo) => grupo.length > 1)
  const problemas = {}
  for (const i of sinLugar) problemas[i.incidente_id] = SIN_LUGAR
  for (const grupo of repetidos) for (const i of grupo) problemas[i.incidente_id] = LUGAR_REPETIDO
  return { sinLugar, repetidos, problemas, hayProblemas: sinLugar.length > 0 || repetidos.length > 0 }
}

// Frase para el motivo por el que no se puede enviar; null si el lugar está bien en todo el ámbito.
export function razonDeLugar({ sinLugar, repetidos }) {
  if (sinLugar.length > 0) {
    return sinLugar.length === 1
      ? 'Falta identificar el lugar de 1 reporte. Resuélvelo antes de enviar: no se omite.'
      : `Falta identificar el lugar de ${sinLugar.length} reportes. Resuélvelos antes de enviar: no se omiten.`
  }
  if (repetidos.length > 0) {
    return 'Hay más de un incidente en el mismo lugar. Consolida el episodio antes de enviar: no se suman ni se omiten.'
  }
  return null
}
