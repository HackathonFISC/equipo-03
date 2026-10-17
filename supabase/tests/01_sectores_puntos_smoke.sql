-- Después de 0001 y la semilla 01. No borra ni valida operativamente lugares.
BEGIN;
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n FROM public.puntos_atencion WHERE punto_atencion_id IN ('920f8af3-1bfe-5ab6-a4f2-7fbcb323825e'::uuid,'1e35ede2-8fc7-51b0-8830-6eec337f6a24'::uuid,'66597297-f57e-54ac-b7f1-7a66cc35253f'::uuid,'9459ff87-0377-5622-8255-caaf79dc9898'::uuid,'4b89af3e-444a-5103-880c-fe1c886530ed'::uuid,'b2478919-28e8-592d-ae1f-c450057cb229'::uuid);
  IF n<>6 THEN RAISE EXCEPTION 'Faltan puntos del catálogo oeste-1.0'; END IF;
  IF EXISTS (
    SELECT 1 FROM (VALUES
    ('920f8af3-1bfe-5ab6-a4f2-7fbcb323825e','e4cefc0a-7132-5fbe-809b-4a4964b10388','Arraiján','Juan Demóstenes Arosemena'),
    ('1e35ede2-8fc7-51b0-8830-6eec337f6a24','9bdee025-4b8b-56fc-8464-4ef9a162d003','Arraiján','Vista Alegre'),
    ('66597297-f57e-54ac-b7f1-7a66cc35253f','8fa71373-37be-5929-9b54-f05fc04fb5d6','Arraiján','Burunga'),
    ('9459ff87-0377-5622-8255-caaf79dc9898','f237d7cb-97d3-5972-8b8b-47ac38703b2e','La Chorrera','El Coco'),
    ('4b89af3e-444a-5103-880c-fe1c886530ed','076c136c-b638-5a90-a717-e331206be19a','La Chorrera','Guadalupe'),
    ('b2478919-28e8-592d-ae1f-c450057cb229','b97abad5-0e4a-5748-90d0-030aaf55ca37','La Chorrera','Playa Leona')
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
