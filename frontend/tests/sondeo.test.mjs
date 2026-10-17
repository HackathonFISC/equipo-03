import test from 'node:test'
import assert from 'node:assert/strict'
import { iniciarSondeo } from '../src/api/sondeo.js'

const terminarPromesas = () => new Promise((resolve) => setImmediate(resolve))

test('no solapa consultas; actualiza después de la primera respuesta', async () => {
  let resolver
  const datos = []
  const tareas = []
  const parar = iniciarSondeo(() => new Promise((r) => { resolver = r }), {
    onDatos: (d) => datos.push(d), onError: assert.fail,
    programar: (f, ms) => { tareas.push({ f, ms }); return 1 }, cancelar: () => {},
  })
  assert.equal(tareas.length, 0)
  resolver('interpretado')
  await terminarPromesas()
  assert.deepEqual(datos, ['interpretado'])
  assert.equal(tareas[0].ms, 5000)
  parar()
})

test('cierre ignora una respuesta tardía y no deja otro temporizador', async () => {
  let resolver
  const parar = iniciarSondeo(() => new Promise((r) => { resolver = r }), {
    onDatos: assert.fail, onError: assert.fail, programar: assert.fail,
  })
  parar()
  resolver('tarde')
  await terminarPromesas()
})

test('cancela el temporizador pendiente al salir de la página', async () => {
  const cancelados = []
  const parar = iniciarSondeo(async () => [], {
    onDatos: () => {}, onError: assert.fail,
    programar: () => 17, cancelar: (id) => cancelados.push(id),
  })
  await terminarPromesas()
  parar()
  assert.deepEqual(cancelados, [17])
})

test('un error permite consultar de nuevo sin perder el ciclo', async () => {
  let siguiente
  let llamadas = 0
  const datos = [], errores = []
  const parar = iniciarSondeo(async () => {
    if (++llamadas === 1) throw new Error('sin conexión')
    return 'recuperado'
  }, { onDatos: (d) => datos.push(d), onError: (e) => errores.push(e.message),
    programar: (f) => { siguiente = f; return 1 }, cancelar: () => {} })
  await terminarPromesas()
  await siguiente()
  assert.deepEqual(errores, ['sin conexión'])
  assert.deepEqual(datos, ['recuperado'])
  parar()
})
