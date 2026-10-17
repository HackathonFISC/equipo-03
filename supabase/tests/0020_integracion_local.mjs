import { createRequire } from 'node:module'
import path from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'
import fs from 'node:fs/promises'
const require = createRequire(process.env.RA_PGLITE_PACKAGE ? path.resolve(process.env.RA_PGLITE_PACKAGE) : import.meta.url)
const { PGlite } = await import(pathToFileURL(path.join(path.dirname(require.resolve('@electric-sql/pglite')), 'index.js')).href)
const raiz = process.env.RA_REPO || fileURLToPath(new URL('../../', import.meta.url))
const db = new PGlite()
try {
  await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);')
  const archivos = ['0001_esquema.sql','0004_identidad_reportes.sql','0005_ingesta_transaccional.sql','0006_aclaraciones_v2.sql','0007_territorial_orquestador_v2.sql','0008_idempotencia_lotes.sql','0009_planificacion_v3.sql','0010_ensayos_priorizacion_v2.sql','0011_bandeja_salida.sql','0003_aprobacion.sql','0012_comunicacion_v4.sql','0013_feedback_aclaraciones.sql','0014_recuperacion_trabajador.sql','0015_ingesta_recuperable.sql','0016_puente_necesidades_v3.sql','0017_lotes_confirmados_automaticos.sql','0018_localizacion_automatica.sql','0018_validar_lugar.sql','0019_matriz_vial_planificacion.sql','0020_transcripciones_audio.sql']
  for (const archivo of archivos) await db.exec(await fs.readFile(path.join(raiz, 'supabase/migrations', archivo), 'utf8'))
  await db.exec(await fs.readFile(path.join(raiz, 'supabase/seed/01_sectores_puntos.sql'), 'utf8'))
  for (const archivo of ['0020_transcripciones_audio_smoke.sql','0006_aclaraciones_smoke.sql','0018_localizacion_automatica_smoke.sql','0013_feedback_aclaraciones_smoke.sql','0014_recuperacion_trabajador_smoke.sql']) {
    await db.exec(await fs.readFile(path.join(raiz, 'supabase/tests', archivo), 'utf8'))
    console.log(archivo + ': OK')
  }
} finally { await db.close() }
