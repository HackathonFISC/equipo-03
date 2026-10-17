import test from 'node:test'
import assert from 'node:assert/strict'

function almacenFalso() {
  const datos = new Map()
  return {
    get length() { return datos.size },
    key: (i) => [...datos.keys()][i] ?? null,
    getItem: (k) => (datos.has(k) ? datos.get(k) : null),
    setItem: (k, v) => { datos.set(k, String(v)) },
    removeItem: (k) => { datos.delete(k) },
  }
}

globalThis.window = { sessionStorage: almacenFalso() }
const { leerBorrador, guardarBorrador, descartarBorradores } = await import('../src/borradores.js')

test('sin borrador devuelve el valor inicial', () => {
  assert.equal(leerBorrador('x', 'vacío'), 'vacío')
})

test('lo guardado se lee de vuelta, también objetos', () => {
  guardarBorrador('motivo', 'confirmado por llamada')
  guardarBorrador('filas', { a: { litros: '500' } })
  assert.equal(leerBorrador('motivo', ''), 'confirmado por llamada')
  assert.deepEqual(leerBorrador('filas', {}), { a: { litros: '500' } })
})

test('sobrevive a perder la memoria si sessionStorage lo conserva', () => {
  guardarBorrador('persistente', [1, 2])
  // Simula recargar la página: se vacía solo la memoria, no el almacén.
  window.sessionStorage.setItem('h2oeste.borrador.recargado', JSON.stringify('sigue aquí'))
  assert.equal(leerBorrador('recargado', ''), 'sigue aquí')
})

test('descartar borra todo lo del panel y deja lo ajeno', () => {
  window.sessionStorage.setItem('otra.cosa', 'intacta')
  guardarBorrador('motivo', 'algo')
  descartarBorradores()
  assert.equal(leerBorrador('motivo', 'inicial'), 'inicial')
  assert.equal(window.sessionStorage.getItem('otra.cosa'), 'intacta')
  assert.equal(window.sessionStorage.length, 1)
})

test('un dato ilegible no rompe: se usa el inicial', () => {
  window.sessionStorage.setItem('h2oeste.borrador.roto', '{no es json')
  assert.equal(leerBorrador('roto', 'ok'), 'ok')
})

test('si el almacenamiento lanza errores, sigue funcionando en memoria', () => {
  descartarBorradores()
  globalThis.window = { get sessionStorage() { throw new Error('bloqueado') } }
  guardarBorrador('solo-memoria', 'v')
  assert.equal(leerBorrador('solo-memoria', ''), 'v')
  descartarBorradores()
})
