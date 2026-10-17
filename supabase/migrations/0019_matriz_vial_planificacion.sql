-- Requiere 0018. Solo actualiza la matriz antes de calcular una planificación reservada.
-- No cambia destinos, capacidad, demanda, revisiones ni planes ya calculados.
BEGIN;
CREATE FUNCTION public.ra_actualizar_matriz_planificacion(p_ejecucion_id uuid,p_trabajador_id text,p_snapshot jsonb,p_matriz jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; x public.escenarios_planificacion_v3%ROWTYPE;
 n integer; a integer; b integer; celda jsonb; ids jsonb;
BEGIN
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'ejecutando' OR e.etapa<>'planificacion'
 OR e.trabajador_id IS DISTINCT FROM p_trabajador_id OR e.bloqueada_hasta IS NULL
 OR e.bloqueada_hasta<=clock_timestamp() THEN
  RAISE EXCEPTION 'Reserva de planificación inválida' USING ERRCODE='55000';
 END IF;
 SELECT * INTO x FROM public.escenarios_planificacion_v3 WHERE ejecucion_id=e.ejecucion_id FOR UPDATE;
 IF NOT FOUND OR x.resultado IS NOT NULL THEN
  RAISE EXCEPTION 'Escenario ausente o ya calculado' USING ERRCODE='55000';
 END IF;
 LOCK TABLE public.depositos,public.vehiculos,public.incidentes,public.puntos_atencion,public.politicas_prioridad IN SHARE MODE;
 IF public.ra_snapshot_planificacion_v3(e.ejecucion_id) IS DISTINCT FROM p_snapshot THEN
  RAISE EXCEPTION 'Escenario cambió durante consulta vial' USING ERRCODE='40001';
 END IF;
 ids:=p_matriz->'nodos_ids';
 IF jsonb_typeof(p_matriz) IS DISTINCT FROM 'object' OR p_matriz->>'origen' IS DISTINCT FROM 'estimado'
 OR coalesce(p_matriz->>'matriz_version','') NOT LIKE 'google-routes-%'
 OR coalesce(length(btrim(p_matriz->>'descripcion')),0)=0
 OR (p_matriz-ARRAY['matriz_version','origen','nodos_ids','minutos','descripcion'])<>'{}'::jsonb
 OR jsonb_typeof(ids) IS DISTINCT FROM 'array' OR jsonb_typeof(p_matriz->'minutos') IS DISTINCT FROM 'array'
 THEN RAISE EXCEPTION 'Matriz vial inválida' USING ERRCODE='22023'; END IF;
 n:=jsonb_array_length(ids);
 IF n NOT BETWEEN 2 AND 7 OR (SELECT count(DISTINCT value) FROM jsonb_array_elements(ids))<>n
 OR n<>jsonb_array_length(x.solicitud->'matriz'->'nodos_ids')
 OR NOT(ids @> (x.solicitud->'matriz'->'nodos_ids'))
 OR jsonb_array_length(p_matriz->'minutos')<>n THEN
  RAISE EXCEPTION 'Nodos de matriz incompatibles' USING ERRCODE='22023';
 END IF;
 FOR a IN 0..n-1 LOOP
  IF jsonb_typeof(p_matriz->'minutos'->a) IS DISTINCT FROM 'array'
  OR jsonb_array_length(p_matriz->'minutos'->a)<>n THEN
   RAISE EXCEPTION 'Matriz no cuadrada' USING ERRCODE='22023';
  END IF;
  FOR b IN 0..n-1 LOOP
   celda:=p_matriz->'minutos'->a->b;
   IF (a=b AND celda IS DISTINCT FROM '0'::jsonb)
   OR (celda<>'null'::jsonb AND (jsonb_typeof(celda)<>'number' OR celda::text !~ '^[0-9]+$')) THEN
    RAISE EXCEPTION 'Tiempo de matriz inválido' USING ERRCODE='22023';
   END IF;
  END LOOP;
 END LOOP;
 UPDATE public.escenarios_planificacion_v3 SET solicitud=jsonb_set(solicitud,'{matriz}',p_matriz)
 WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_evento_v2(e.ejecucion_id,'planificacion','Incorporar tiempos viales de Google Maps',
   jsonb_build_object('matriz_version',p_matriz->>'matriz_version','nodos',n));
 RETURN public.ra_snapshot_planificacion_v3(e.ejecucion_id);
END $$;
REVOKE ALL ON FUNCTION public.ra_actualizar_matriz_planificacion(uuid,text,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_actualizar_matriz_planificacion(uuid,text,jsonb,jsonb) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
