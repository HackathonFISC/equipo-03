-- Ubicación automática del reporte, independiente de la distribución.
-- Requiere 0017. No crea incidentes, vínculos, puntos ni cambia cálculos.
BEGIN;
ALTER TABLE public.reportes ADD COLUMN localizacion_resuelta jsonb
 CHECK(localizacion_resuelta IS NULL OR jsonb_typeof(localizacion_resuelta)='object');

CREATE FUNCTION public.ra_finalizar_localizacion(p_ejecucion_id uuid,p_trabajador_id text,p_snapshot jsonb,p_resolucion jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE; u jsonb; loc jsonb; fuente text;
BEGIN
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'ejecutando' OR e.etapa<>'territorial'
 OR e.trabajador_id IS DISTINCT FROM p_trabajador_id OR e.bloqueada_hasta IS NULL
 OR e.bloqueada_hasta<=clock_timestamp() THEN
  RAISE EXCEPTION 'Reserva territorial inválida' USING ERRCODE='55000';
 END IF;
 SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id FOR UPDATE;
 IF to_jsonb(r) IS DISTINCT FROM p_snapshot->'reporte' THEN
  RAISE EXCEPTION 'Reporte cambió durante localización' USING ERRCODE='40001';
 END IF;
 u:=p_resolucion->'ubicacion'; fuente:=u->>'fuente';
 IF p_resolucion->>'estado' IS DISTINCT FROM 'localizada' OR jsonb_typeof(u) IS DISTINCT FROM 'object'
 OR fuente IS NULL OR fuente NOT IN ('compartida','geocodificada')
 OR jsonb_typeof(u->'latitud') IS DISTINCT FROM 'number' OR jsonb_typeof(u->'longitud') IS DISTINCT FROM 'number'
 OR NOT ((u->>'latitud')::numeric BETWEEN -90 AND 90)
 OR NOT ((u->>'longitud')::numeric BETWEEN -180 AND 180)
 OR (u->'representa_punto_atencion' IS NOT NULL AND u->'representa_punto_atencion'<>'null'::jsonb)
 OR (fuente='geocodificada' AND coalesce(length(btrim(p_resolucion->>'place_id')),0)=0) THEN
  RAISE EXCEPTION 'Localización incompatible' USING ERRCODE='22023';
 END IF;
 IF u ? 'precision_metros' AND u->'precision_metros'<>'null'::jsonb THEN
  IF jsonb_typeof(u->'precision_metros') IS DISTINCT FROM 'number' OR (u->>'precision_metros')::numeric<0 THEN
   RAISE EXCEPTION 'Precisión inválida' USING ERRCODE='22023';
  END IF;
 END IF;
 -- Esta RPC solo localiza reportes fuera del circuito de un punto conocido.
 IF EXISTS(SELECT 1 FROM public.vinculos_reportes WHERE reporte_id=r.reporte_id AND desvinculado_en IS NULL) THEN
  RAISE EXCEPTION 'Reporte ya asociado; conservar circuito existente' USING ERRCODE='55000';
 END IF;
 loc:=jsonb_build_object('ubicacion',u,'resuelta_en',clock_timestamp(),
   'place_id',CASE WHEN fuente='geocodificada' THEN p_resolucion->>'place_id' END,
   'expira_en',CASE WHEN fuente='geocodificada' THEN clock_timestamp()+interval '29 days' END);
 UPDATE public.reportes SET localizacion_resuelta=loc WHERE reporte_id=r.reporte_id;
 -- Completada la localización, sin aprobar ni programar una distribución.
 UPDATE public.ejecuciones SET estado='completada',etapa='terminada',trabajador_id=NULL,
 bloqueada_hasta=NULL,ultimo_error=NULL WHERE ejecucion_id=e.ejecucion_id;
 -- La traza no duplica coordenadas ni contenido de Google.
 PERFORM public.ra_evento_v2(e.ejecucion_id,'territorial','Ubicación resuelta automáticamente',
   jsonb_build_object('fuente',fuente));
 RETURN jsonb_build_object('estado','completada','etapa','terminada','ejecucion_id',e.ejecucion_id);
END $$;
REVOKE ALL ON FUNCTION public.ra_finalizar_localizacion(uuid,text,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_finalizar_localizacion(uuid,text,jsonb,jsonb) TO service_role;

CREATE FUNCTION public.ra_limpiar_geocodificacion() RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE n integer;
BEGIN
 UPDATE public.reportes SET localizacion_resuelta=jsonb_set(localizacion_resuelta,'{ubicacion}','null'::jsonb)
 WHERE localizacion_resuelta->'ubicacion'->>'fuente'='geocodificada'
 AND (localizacion_resuelta->>'expira_en')::timestamptz<=clock_timestamp();
 GET DIAGNOSTICS n=ROW_COUNT;
 RETURN n;
END $$;
REVOKE ALL ON FUNCTION public.ra_limpiar_geocodificacion() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_limpiar_geocodificacion() TO service_role;
CREATE OR REPLACE FUNCTION public.ra_mantenimiento_v2()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x record; n integer; c integer:=0;
BEGIN
 PERFORM public.ra_limpiar_geocodificacion();
 n:=public.ra_revisar_aclaraciones();
 FOR x IN SELECT ejecucion_id FROM public.ejecuciones
 WHERE estado='ejecutando' AND etapa IN ('ingesta','territorial','priorizacion','planificacion','comunicacion')
 AND bloqueada_hasta<=clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
  UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
   ultimo_error=jsonb_build_object('codigo','reserva_trabajador_vencida','mensaje','Revisar resultado antes de reintentar')
   WHERE ejecucion_id=x.ejecucion_id;
  PERFORM public.ra_traza_aclaracion(x.ejecucion_id,'Revisar reserva de trabajador vencida'); c:=c+1;
 END LOOP;
 RETURN n+c;
END $$;


NOTIFY pgrst,'reload schema';
COMMIT;
