import test from 'node:test'
import assert from 'node:assert/strict'

const datos = new Map()
globalThis.window = {
  localStorage: {
    getItem: (k) => (datos.has(k) ? datos.get(k) : null),
    setItem: (k, v) => { datos.set(k, String(v)) },
  },
}
const q = await import('../src/quitados.js')

test('al inicio no hay nada quitado', () => {
  for (const t of q.TIPOS) assert.equal(q.quitadosDe(t).size, 0)
})

test('quitar guarda el id, avisa a los oyentes y cambia la referencia', () => {
  let avisos = 0
  const baja = q.suscribirQuitados(() => { avisos += 1 })
  const antes = q.quitadosDe('reporte')
  q.quitar('reporte', 'r1')
  assert.ok(q.quitadosDe('reporte').has('r1'))
  assert.notEqual(q.quitadosDe('reporte'), antes)
  assert.equal(avisos, 1)
  baja()
})

test('quitar dos veces lo mismo no notifica de nuevo', () => {
  let avisos = 0
  const baja = q.suscribirQuitados(() => { avisos += 1 })
  q.quitar('reporte', 'r1')
  assert.equal(avisos, 0)
  baja()
})

test('los tipos son independientes', () => {
  q.quitar('plan', 'p1:2')
  assert.ok(q.quitadosDe('plan').has('p1:2'))
  assert.equal(q.quitadosDe('incidente').size, 0)
})

test('se persiste en localStorage', () => {
  const guardado = JSON.parse(datos.get('h2oeste.quitados'))
  assert.deepEqual(guardado.reporte, ['r1'])
  assert.deepEqual(guardado.plan, ['p1:2'])
})

test('restaurar y restaurar todos', () => {
  q.quitar('reporte', 'r2')
  q.restaurar('reporte', 'r1')
  assert.deepEqual([...q.quitadosDe('reporte')], ['r2'])
  q.restaurarTodos('reporte')
  assert.equal(q.quitadosDe('reporte').size, 0)
})

test('un tipo desconocido se rechaza', () => {
  assert.throws(() => q.quitar('otro', 'x'))
})
