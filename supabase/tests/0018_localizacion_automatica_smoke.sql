-- Prueba local reversible: no servicios externos.
BEGIN;
DO $$
DECLARE u uuid:=gen_random_uuid(); rid uuid; eid uuid; snap jsonb; resultado jsonb;
 cantidad integer; loc jsonb; fuente text; otros integer;
BEGIN
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram','smoke-localizacion:'||u);
 SELECT count(*) INTO cantidad FROM public.incidentes;
 SELECT count(*) INTO otros FROM public.vinculos_reportes;
 FOREACH fuente IN ARRAY ARRAY['compartida','geocodificada'] LOOP
  INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen,interpretacion)
  VALUES(u,'telegram','smoke-localizacion:'||gen_random_uuid(),'texto','Sin agua en un lugar nuevo','sintetico',
   '{"campos":{"tipo_problema":"sin_suministro"}}') RETURNING reporte_id INTO rid;
  INSERT INTO public.ejecuciones(reporte_id,estado,etapa,origen)
  VALUES(rid,'pendiente','territorial','sintetico') RETURNING ejecucion_id INTO eid;
  snap:=public.ra_tomar_etapa_v2(eid,'smoke-localizacion','territorial');
  loc:=jsonb_build_object('estado','localizada','place_id','google-place-test',
    'ubicacion',jsonb_build_object('latitud',8.91,'longitud',-79.71,'fuente',fuente,'representa_punto_atencion',NULL));
  BEGIN
   PERFORM public.ra_finalizar_localizacion(eid,'otro',snap,loc);
   RAISE EXCEPTION 'Aceptó trabajador ajeno';
  EXCEPTION WHEN SQLSTATE '55000' THEN NULL; END;
  BEGIN
   PERFORM public.ra_finalizar_localizacion(eid,'smoke-localizacion',jsonb_set(snap,'{reporte,texto}','"cambió"'),loc);
   RAISE EXCEPTION 'Aceptó snapshot obsoleto';
  EXCEPTION WHEN SQLSTATE '40001' THEN NULL; END;
  BEGIN
   PERFORM public.ra_finalizar_localizacion(eid,'smoke-localizacion',snap,jsonb_set(loc,'{ubicacion,latitud}','999'));
   RAISE EXCEPTION 'Aceptó coordenadas inválidas';
  EXCEPTION WHEN SQLSTATE '22023' THEN NULL; END;
  resultado:=public.ra_finalizar_localizacion(eid,'smoke-localizacion',snap,loc);
  IF resultado->>'estado'<>'completada' OR resultado->>'etapa'<>'terminada' THEN RAISE EXCEPTION 'No completó localización'; END IF;
  IF (SELECT localizacion_resuelta->'ubicacion'->>'fuente' FROM public.reportes WHERE reporte_id=rid)<>fuente THEN RAISE EXCEPTION 'No persistió fuente'; END IF;
  IF EXISTS(SELECT 1 FROM public.aclaraciones WHERE reporte_id=rid) THEN RAISE EXCEPTION 'Pidió intervención'; END IF;
  IF EXISTS(SELECT 1 FROM public.eventos WHERE ejecucion_id=eid AND (detalles::text LIKE '%8.91%' OR detalles::text LIKE '%google-place-test%')) THEN RAISE EXCEPTION 'Duplicó contenido en traza'; END IF;
  BEGIN
   PERFORM public.ra_finalizar_localizacion(eid,'smoke-localizacion',snap,loc);
   RAISE EXCEPTION 'Duplicó cierre';
  EXCEPTION WHEN SQLSTATE '55000' THEN NULL; END;
  IF fuente='geocodificada' THEN
   UPDATE public.reportes SET localizacion_resuelta=jsonb_set(localizacion_resuelta,'{expira_en}',to_jsonb((clock_timestamp()-interval '1 second')::text)) WHERE reporte_id=rid;
  END IF;
 END LOOP;
 PERFORM public.ra_mantenimiento_v2();
 IF EXISTS(SELECT 1 FROM public.reportes WHERE remitente_ref=u AND localizacion_resuelta->'ubicacion'->>'fuente'='geocodificada') THEN RAISE EXCEPTION 'Retuvo coordenadas vencidas'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.reportes WHERE remitente_ref=u AND localizacion_resuelta->'ubicacion'->>'fuente'='compartida') THEN RAISE EXCEPTION 'Borró pin Telegram'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.reportes WHERE remitente_ref=u AND localizacion_resuelta->>'place_id'='google-place-test') THEN RAISE EXCEPTION 'Perdió place_id'; END IF;
 IF (SELECT count(*) FROM public.incidentes)<>cantidad OR (SELECT count(*) FROM public.vinculos_reportes)<>otros THEN RAISE EXCEPTION 'Modificó circuito de incidentes'; END IF;
 IF has_function_privilege('authenticated','public.ra_finalizar_localizacion(uuid,text,jsonb,jsonb)','EXECUTE')
 OR has_function_privilege('anon','public.ra_finalizar_localizacion(uuid,text,jsonb,jsonb)','EXECUTE') THEN RAISE EXCEPTION 'RPC expuesta'; END IF;
END $$;
ROLLBACK;
