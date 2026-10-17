import test from 'node:test'
import assert from 'node:assert/strict'
import { datosDelToken, inicialesDe, minutosRestantes, nombreDe, perfilDe } from '../src/perfil.js'

const jwt = (carga) => `a.${Buffer.from(JSON.stringify(carga)).toString('base64url')}.c`

test('lee correo y vencimiento del token', () => {
  assert.deepEqual(datosDelToken(jwt({ email: 'a@b.pa', exp: 1000 })), { correo: 'a@b.pa', vence: 1000000 })
})

test('un token que no se puede leer no rompe nada', () => {
  assert.deepEqual(datosDelToken('abc.def.ghi'), { correo: null, vence: null })
  assert.deepEqual(datosDelToken(null), { correo: null, vence: null })
})

test('nombre e iniciales salen del correo', () => {
  assert.equal(nombreDe('noel.echer15@gmail.com'), 'Noel Echer')
  assert.equal(nombreDe('coordinacion@h2oeste.pa'), 'Coordinacion')
  assert.equal(nombreDe(null), 'Tu cuenta')
  assert.equal(inicialesDe('Noel Echer'), 'NE')
  assert.equal(inicialesDe('Coordinacion'), 'CO')
})

test('el coordinador activo puede aprobar; los demás no', () => {
  const t = { correo: 'a@b.pa', vence: null }
  const coord = perfilDe(t, { rol: 'coordinador', activo: true, es_coordinador: true })
  assert.equal(coord.rol, 'Coordinación')
  assert.equal(coord.permisos.length, 3)
  const inactivo = perfilDe(t, { rol: 'coordinador', activo: false, es_coordinador: false })
  assert.equal(inactivo.permisos.length, 0)
  assert.equal(inactivo.tono, 'aviso')
  const consulta = perfilDe(t, { rol: 'consulta', activo: true, es_coordinador: false })
  assert.equal(consulta.permisos.length, 1)
  assert.match(consulta.limites[0], /No puedes/)
  assert.equal(perfilDe(t, { rol: null, activo: false, es_coordinador: false }).rol, 'Sin rol asignado')
  assert.equal(perfilDe(t, null).rol, null)
  assert.equal(perfilDe(t, false).rol, 'Rol sin comprobar')
  assert.equal(perfilDe(t, false).permisos.length, 0)
})

test('minutos restantes nunca es negativo', () => {
  assert.equal(minutosRestantes(null), null)
  assert.equal(minutosRestantes(1000, 5000000), 0)
  assert.equal(minutosRestantes(61 * 60000, 0), 61)
})
