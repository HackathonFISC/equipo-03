// Consulta de nuevo después de terminar la petición anterior; nunca se solapan.
// El cierre ignora respuestas tardías y cancela la siguiente consulta.
export function iniciarSondeo(consultar, { onDatos, onError, intervalo = 5000,
  programar = setTimeout, cancelar = clearTimeout }) {
  let activo = true
  let temporizador
  async function consultarAhora() {
    try {
      const datos = await consultar()
      if (activo) onDatos(datos)
    } catch (error) {
      if (activo) onError(error)
    } finally {
      if (activo && intervalo !== null) temporizador = programar(consultarAhora, intervalo)
    }
  }
  consultarAhora()
  return () => {
    activo = false
    if (temporizador !== undefined) cancelar(temporizador)
  }
}
