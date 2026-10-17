-- Generado desde datos/geografia/puntos.csv con python -m geografia.generar_semilla.
-- Catálogo oeste-1.0 aprobado: seis candidatos, tres por distrito.
-- SHA256 del CSV: 876dc342748084edd6bbda17a8b074243701ff0f5dc628e1da0cc130d0fe70a2
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
  ('e4cefc0a-7132-5fbe-809b-4a4964b10388', 'Juan Demóstenes Arosemena', 'Arraiján', 'Juan Demóstenes Arosemena', '920f8af3-1bfe-5ab6-a4f2-7fbcb323825e', 'Junta Comunal Nuevo Arraiján', 8.92561, -79.71959, 'AIG RNI enero 2022; PA 1257; página 27; https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf'),
  ('9bdee025-4b8b-56fc-8464-4ef9a162d003', 'Vista Alegre', 'Arraiján', 'Vista Alegre', '1e35ede2-8fc7-51b0-8830-6eec337f6a24', 'Junta Comunal de Vista Alegre', 8.92695, -79.70745, 'AIG RNI enero 2022; PA 1265; página 27; https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf'),
  ('8fa71373-37be-5929-9b54-f05fc04fb5d6', 'Burunga', 'Arraiján', 'Burunga', '66597297-f57e-54ac-b7f1-7a66cc35253f', 'C.E.B.G. Burunga', 8.96713, -79.67437, 'AIG RNI enero 2022; PA 1244; página 27; https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf'),
  ('f237d7cb-97d3-5972-8b8b-47ac38703b2e', 'El Coco', 'La Chorrera', 'El Coco', '9459ff87-0377-5622-8255-caaf79dc9898', 'Escuela El Coco', 8.86672, -79.81024, 'AIG RNI enero 2022; PA 1331; página 28; https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf'),
  ('076c136c-b638-5a90-a717-e331206be19a', 'Guadalupe', 'La Chorrera', 'Guadalupe', '4b89af3e-444a-5103-880c-fe1c886530ed', 'C.E. Virgen de Guadalupe', 8.85693, -79.82341, 'AIG RNI enero 2022; PA 1332; página 28; https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf'),
  ('b97abad5-0e4a-5748-90d0-030aaf55ca37', 'Playa Leona', 'La Chorrera', 'Playa Leona', 'b2478919-28e8-592d-ae1f-c450057cb229', 'Centro Educativo Guillermo Endara', 8.86130, -79.78450, 'AIG RNI enero 2022; PA 1398; página 30; https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf');

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
SELECT punto_atencion_id,sector_id,nombre,ARRAY(
    SELECT a.alias FROM (VALUES
      ('920f8af3-1bfe-5ab6-a4f2-7fbcb323825e'::uuid, 'Junta Comunal Nuevo Arraiján'),
      ('920f8af3-1bfe-5ab6-a4f2-7fbcb323825e'::uuid, 'Junta Comunal Nuevo Arraijan'),
      ('1e35ede2-8fc7-51b0-8830-6eec337f6a24'::uuid, 'Junta Comunal de Vista Alegre'),
      ('1e35ede2-8fc7-51b0-8830-6eec337f6a24'::uuid, 'Junta Comunal Vista Alegre'),
      ('66597297-f57e-54ac-b7f1-7a66cc35253f'::uuid, 'C.E.B.G. Burunga'),
      ('66597297-f57e-54ac-b7f1-7a66cc35253f'::uuid, 'CEBG Burunga'),
      ('66597297-f57e-54ac-b7f1-7a66cc35253f'::uuid, 'C E B G Burunga'),
      ('9459ff87-0377-5622-8255-caaf79dc9898'::uuid, 'Escuela El Coco'),
      ('9459ff87-0377-5622-8255-caaf79dc9898'::uuid, 'Primaria-Escuela El Coco'),
      ('4b89af3e-444a-5103-880c-fe1c886530ed'::uuid, 'C.E. Virgen de Guadalupe'),
      ('4b89af3e-444a-5103-880c-fe1c886530ed'::uuid, 'CE Virgen de Guadalupe'),
      ('4b89af3e-444a-5103-880c-fe1c886530ed'::uuid, 'C E Virgen de Guadalupe'),
      ('b2478919-28e8-592d-ae1f-c450057cb229'::uuid, 'Centro Educativo Guillermo Endara')
    ) AS a(punto_id,alias) WHERE a.punto_id=ra_catalogo_oeste.punto_atencion_id
  ),latitud,longitud,
  NULL,'catalogo',NULL,'pendiente',NULL,'real',fuente,true,
  'Referencia AIG 2022: pendiente acceso, autorización, descarga y recepción; no es sitio de entrega confirmado.'
FROM ra_catalogo_oeste ON CONFLICT(punto_atencion_id) DO NOTHING;
DROP TABLE pg_temp.ra_catalogo_oeste;
END $catalogo$;
