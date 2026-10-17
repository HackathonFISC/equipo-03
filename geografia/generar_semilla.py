"""Genera semilla y smoke de geografía desde puntos.csv, sin conectarse a la BD."""
import csv
import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path
from uuid import UUID

RAIZ = Path(__file__).resolve().parents[1]


def literal(valor):
    return "'" + str(valor).replace("'", "''") + "'"


def normalizar(valor):
    texto=''.join(c for c in unicodedata.normalize('NFD',valor.casefold()) if unicodedata.category(c)!='Mn')
    return ' '.join(re.findall(r'[^\W_]+',texto))


def leer_catalogo(raiz=RAIZ):
    ruta = Path(raiz) / 'datos/geografia/puntos.csv'
    with ruta.open(encoding='utf-8', newline='') as f:
        filas = list(csv.DictReader(f))
    if len(filas) != 6 or Counter(r['distrito'] for r in filas) != {'Arraiján': 3, 'La Chorrera': 3}:
        raise ValueError('El catálogo acordado requiere seis puntos: tres por distrito.')
    for columna in ('punto_atencion_id', 'sector_id', 'fuente_registro_id'):
        if len({r[columna] for r in filas}) != 6:
            raise ValueError(f'El catálogo inicial requiere {columna} únicos.')
    for r in filas:
        UUID(r['punto_atencion_id']); UUID(r['sector_id'])
        if not -90 <= float(r['latitud']) <= 90 or not -180 <= float(r['longitud']) <= 180:
            raise ValueError('Coordenadas fuera de rango.')
        if not re.fullmatch(r'-?\d+(?:\.\d+)?', r['latitud']) or not re.fullmatch(r'-?\d+(?:\.\d+)?', r['longitud']):
            raise ValueError('Las coordenadas deben ser decimales finitos.')
        if any(not r[k].strip() for k in ('nombre', 'nombre_sector', 'corregimiento', 'fuente_url', 'fuente_pagina', 'catalogo_version')):
            raise ValueError('Falta identidad o procedencia del catálogo.')
        if (r['provincia'], r['origen'], r['fuente_ubicacion'], r['estado_validacion'], r['activo']) != (
                'Panamá Oeste', 'real', 'catalogo', 'pendiente', 'true'):
            raise ValueError('No alterar el origen de referencia ni presentar candidatos como validados.')
        if any(r[k] for k in ('precision_metros', 'representa_punto_atencion', 'capacidad_recepcion_litros')):
            raise ValueError('Recepción, precisión y punto operativo siguen sin confirmar.')
    return filas


def generar(raiz=RAIZ):
    raiz = Path(raiz)
    filas = leer_catalogo(raiz)
    csv_path = raiz / 'datos/geografia/puntos.csv'
    huella = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    valores = []
    for r in filas:
        fuente = f"AIG RNI enero 2022; PA {r['fuente_registro_id']}; página {r['fuente_pagina']}; {r['fuente_url']}"
        datos = [r[k] for k in ('sector_id','nombre_sector','distrito','corregimiento','punto_atencion_id','nombre')]
        valores.append('  (' + ', '.join(literal(v) for v in datos)
                       + f", {r['latitud']}, {r['longitud']}, {literal(fuente)})")
    sql = f'''-- Generado desde datos/geografia/puntos.csv con python -m geografia.generar_semilla.
-- Catálogo oeste-1.0 aprobado: seis candidatos, tres por distrito.
-- SHA256 del CSV: {huella}
-- Requiere 0001. Referencias geográficas reales; entrega/recepción NO validadas.
-- Reejecutable: inserta ausentes y conserva todas las correcciones de filas existentes.
-- Ejecutar el bloque DO completo, sin seleccionar fragmentos.
DO $catalogo$
BEGIN
LOCK TABLE public.sectores, public.puntos_atencion IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE ra_catalogo_oeste (
  sector_id uuid PRIMARY KEY, nombre_sector text NOT NULL, distrito text NOT NULL,
  corregimiento text NOT NULL, punto_atencion_id uuid UNIQUE NOT NULL,
  nombre text NOT NULL, latitud numeric NOT NULL, longitud numeric NOT NULL, fuente text NOT NULL
) ON COMMIT DROP;
INSERT INTO ra_catalogo_oeste VALUES
''' + ',\n'.join(valores) + ''';

-- No reutilizar una identidad existente ni duplicar un lugar con otro UUID.
  IF EXISTS (
    SELECT 1 FROM public.sectores s JOIN ra_catalogo_oeste c USING(sector_id)
    WHERE s.distrito IS DISTINCT FROM c.distrito OR s.corregimiento IS DISTINCT FROM c.corregimiento
  ) THEN RAISE EXCEPTION 'Catálogo: UUID de sector existente con otra división territorial; revisar antes de cargar'; END IF;
  IF EXISTS (
    SELECT 1 FROM public.sectores s JOIN ra_catalogo_oeste c
    ON lower(btrim(s.nombre))=lower(btrim(c.nombre_sector))
      AND s.distrito=c.distrito AND s.corregimiento=c.corregimiento
    WHERE s.sector_id<>c.sector_id
  ) THEN RAISE EXCEPTION 'Catálogo: ya existe un sector equivalente con otro UUID; coordinar correspondencia'; END IF;
  IF EXISTS (
    SELECT 1 FROM public.puntos_atencion p JOIN ra_catalogo_oeste c USING(punto_atencion_id)
    WHERE p.sector_id<>c.sector_id
  ) THEN RAISE EXCEPTION 'Catálogo: UUID de punto existente vinculado a otro sector'; END IF;
  IF EXISTS (
    SELECT 1 FROM public.puntos_atencion p JOIN ra_catalogo_oeste c
    ON p.sector_id=c.sector_id AND lower(btrim(p.nombre))=lower(btrim(c.nombre))
    WHERE p.punto_atencion_id<>c.punto_atencion_id
  ) THEN RAISE EXCEPTION 'Catálogo: ya existe el punto con otro UUID; coordinar correspondencia'; END IF;
INSERT INTO public.sectores(sector_id,nombre,distrito,corregimiento,origen,fuente,estado_informacion,motivo)
SELECT sector_id,nombre_sector,distrito,corregimiento,'real',fuente,'pendiente_verificar',
  'Catálogo oeste-1.0: zona candidata; sin acreditar desabastecimiento actual ni criticidad.'
FROM ra_catalogo_oeste ON CONFLICT(sector_id) DO NOTHING;
INSERT INTO public.puntos_atencion(punto_atencion_id,sector_id,nombre,alias,latitud,longitud,
  precision_metros,fuente_ubicacion,representa_punto_atencion,estado_validacion,
  capacidad_recepcion_litros,origen,fuente,activo,motivo)
SELECT punto_atencion_id,sector_id,nombre,ARRAY[]::text[],latitud,longitud,
  NULL,'catalogo',NULL,'pendiente',NULL,'real',fuente,true,
  'Referencia AIG 2022: pendiente acceso, autorización, descarga y recepción; no es sitio de entrega confirmado.'
FROM ra_catalogo_oeste ON CONFLICT(punto_atencion_id) DO NOTHING;
'''
    with (raiz / 'datos/geografia/alias.csv').open(encoding='utf-8', newline='') as f:
        alias = list(csv.DictReader(f))
    puntos = {r['punto_atencion_id'] for r in filas}
    if not alias or any(a['punto_atencion_id'] not in puntos for a in alias):
        raise ValueError('Alias sin referencia en el catálogo.')
    zonas={normalizar(r[k]) for r in filas for k in ('distrito','corregimiento','provincia')}
    if any(not a['alias'].strip() or normalizar(a['alias']) in zonas for a in alias):
        raise ValueError('Un nombre de zona no es alias de una instalación concreta.')
    if len({(a['punto_atencion_id'],a['alias']) for a in alias})!=len(alias):
        raise ValueError('Alias repetidos para el mismo punto.')
    # Solo inicializa alias de puntos nuevos: no reescribe los revisados por humanos.
    # Los alias también se cargan dentro del INSERT, antes de ON CONFLICT.
    sql = sql.replace("nombre,ARRAY[]::text[],latitud,longitud,", "nombre," + '''ARRAY(
    SELECT a.alias FROM (VALUES
''' + ',\n'.join(f"      ({literal(a['punto_atencion_id'])}::uuid, {literal(a['alias'])})" for a in alias)
        + '''
    ) AS a(punto_id,alias) WHERE a.punto_id=ra_catalogo_oeste.punto_atencion_id
  ),latitud,longitud,''')
    sql += 'DROP TABLE pg_temp.ra_catalogo_oeste;\nEND $catalogo$;\n'
    seed_path = raiz / 'supabase/seed/01_sectores_puntos.sql'
    seed_path.write_text(sql, encoding='utf-8')
    ids = ','.join(literal(r['punto_atencion_id'])+'::uuid' for r in filas)
    pares = ',\n'.join('    ('+','.join(literal(r[k]) for k in ('punto_atencion_id','sector_id','distrito','corregimiento'))+')' for r in filas)
    smoke = f'''-- Después de 0001 y la semilla 01. No borra ni valida operativamente lugares.
BEGIN;
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM public.puntos_atencion WHERE punto_atencion_id IN ({ids});
  IF n<>6 THEN RAISE EXCEPTION 'Faltan puntos del catálogo oeste-1.0'; END IF;
  IF EXISTS (
    SELECT 1 FROM (VALUES
{pares}
    ) AS c(punto_id,sector_id,distrito,corregimiento)
    LEFT JOIN public.puntos_atencion p ON p.punto_atencion_id=c.punto_id::uuid
    LEFT JOIN public.sectores s ON s.sector_id=p.sector_id
    WHERE p.sector_id IS DISTINCT FROM c.sector_id::uuid
       OR s.distrito IS DISTINCT FROM c.distrito OR s.corregimiento IS DISTINCT FROM c.corregimiento
       OR p.latitud IS NULL OR p.longitud IS NULL OR length(btrim(p.fuente))=0
  ) THEN RAISE EXCEPTION 'Catálogo con referencias o procedencia incompatibles'; END IF;
  RAISE NOTICE 'OK: seis puntos del catálogo, tres por distrito, con sector, coordenadas y fuente. No acredita descarga ni necesidad de agua.';
END $$;
ROLLBACK;
'''
    (raiz / 'supabase/tests/01_sectores_puntos_smoke.sql').write_text(smoke, encoding='utf-8')
    return seed_path


if __name__ == '__main__':
    print(generar())
