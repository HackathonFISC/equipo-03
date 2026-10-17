import test from 'node:test'
import assert from 'node:assert/strict'
import { lugaresDelAmbito, razonDeLugar, SIN_LUGAR, LUGAR_REPETIDO } from '../src/paginas/lugares.js'

const item = (incidente_id, punto_atencion_id) => ({ incidente_id, punto_atencion_id })

test('un ámbito con un punto distinto por incidente no tiene problemas', () => {
  const r = lugaresDelAmbito([item('a', 'p1'), item('b', 'p2')])
  assert.equal(r.hayProblemas, false)
  assert.equal(razonDeLugar(r), null)
})

test('un incidente sin punto bloquea aunque sea uno solo', () => {
  const r = lugaresDelAmbito([item('a', 'p1'), item('b', null)])
  assert.equal(r.problemas.b, SIN_LUGAR)
  assert.equal(r.problemas.a, undefined)
  assert.match(razonDeLugar(r), /1 reporte/)
})

test('varios sin punto se cuentan en plural', () => {
  const r = lugaresDelAmbito([item('a', null), item('b', undefined)])
  assert.match(razonDeLugar(r), /2 reportes/)
})

test('dos incidentes en el mismo punto se marcan como repetidos', () => {
  const r = lugaresDelAmbito([item('a', 'p1'), item('b', 'p1'), item('c', 'p2')])
  assert.equal(r.problemas.a, LUGAR_REPETIDO)
  assert.equal(r.problemas.b, LUGAR_REPETIDO)
  assert.equal(r.problemas.c, undefined)
  assert.match(razonDeLugar(r), /mismo lugar/)
})

test('sin lugar tiene prioridad en el mensaje sobre los repetidos', () => {
  const r = lugaresDelAmbito([item('a', 'p1'), item('b', 'p1'), item('c', null)])
  assert.match(razonDeLugar(r), /identificar el lugar/)
})

test('una lista vacía o inválida no rompe', () => {
  assert.equal(lugaresDelAmbito([]).hayProblemas, false)
  assert.equal(lugaresDelAmbito(undefined).hayProblemas, false)
})
