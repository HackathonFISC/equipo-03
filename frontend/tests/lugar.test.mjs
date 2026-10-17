import test from 'node:test'
import assert from 'node:assert/strict'
import { coordenadasDe, lugarPorValidar, enlaceMapa, urlMapaIncrustado, textoCoordenadas, evidenciaValida } from '../src/lugar.js'

test('coordenadas válidas del catálogo', () => {
  assert.deepEqual(coordenadasDe({ latitud: 8.86672, longitud: -79.81024 }), { latitud: 8.86672, longitud: -79.81024 })
  assert.deepEqual(coordenadasDe({ latitud: '8.9', longitud: '-79.8' }), { latitud: 8.9, longitud: -79.8 })
})

test('coordenadas ausentes o inválidas no se inventan', () => {
  for (const punto of [null, undefined, {}, { latitud: 8.9 }, { latitud: null, longitud: null }, { latitud: 'a', longitud: 1 },
    { latitud: 91, longitud: 0 }, { latitud: 0, longitud: 181 }, { latitud: NaN, longitud: 1 }]) {
    assert.equal(coordenadasDe(punto), null)
  }
})

test('solo un incidente pendiente con punto espera validación', () => {
  assert.equal(lugarPorValidar({ estado_validacion: 'pendiente', punto_atencion_id: 'p' }), true)
  assert.equal(lugarPorValidar({ estado_validacion: 'validada', punto_atencion_id: 'p' }), false)
  assert.equal(lugarPorValidar({ estado_validacion: 'rechazada', punto_atencion_id: 'p' }), false)
  assert.equal(lugarPorValidar({ estado_validacion: 'pendiente', punto_atencion_id: null }), false)
  assert.equal(lugarPorValidar(null), false)
})

test('el enlace a Google Maps no lleva clave', () => {
  const url = enlaceMapa({ latitud: 8.9, longitud: -79.8 })
  assert.equal(url, 'https://www.google.com/maps/search/?api=1&query=8.9%2C-79.8')
  assert.doesNotMatch(url, /key=/)
})

test('el mapa incrustado exige clave y coordenadas', () => {
  const c = { latitud: 8.9, longitud: -79.8 }
  assert.equal(urlMapaIncrustado(c, ''), null)
  assert.equal(urlMapaIncrustado(null, 'abc'), null)
  assert.equal(urlMapaIncrustado(c, 'abc'), 'https://www.google.com/maps/embed/v1/place?key=abc&q=8.9%2C-79.8&zoom=17')
})

test('la clave se codifica en la dirección', () => {
  assert.match(urlMapaIncrustado({ latitud: 1, longitud: 2 }, 'a b&c'), /key=a%20b%26c&/)
})

test('formato de coordenadas', () => {
  assert.equal(textoCoordenadas({ latitud: 8.86672, longitud: -79.81024 }), '8.86672, -79.81024')
})

test('la evidencia pide entre 10 y 2000 caracteres sin contar espacios de los bordes', () => {
  assert.equal(evidenciaValida('corta'), false)
  assert.equal(evidenciaValida('   corta   '), false)
  assert.equal(evidenciaValida('Llamé a la junta comunal'), true)
  assert.equal(evidenciaValida('x'.repeat(2000)), true)
  assert.equal(evidenciaValida('x'.repeat(2001)), false)
})
