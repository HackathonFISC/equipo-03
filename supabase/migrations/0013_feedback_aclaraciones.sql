-- Emilia: feedback de ubicación y límite de repreguntas. Requiere 0006.
-- Aditiva, no depende de V4/0012. No cambia firmas ni migra reportes anteriores.
-- No reenvía ni modifica preguntas ya enviadas. Aplicar completa una vez.
BEGIN;
CREATE OR REPLACE FUNCTION public.ra_crear_aclaracion(p_ejecucion_id uuid,p_campos text[],p_pregunta text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE; d public.destinos%ROWTYPE; a public.aclaraciones%ROWTYPE; solo_ubicacion boolean; previas_ubicacion integer; pregunta text;
BEGIN
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'espera_aclaracion' THEN RAISE EXCEPTION 'Ejecución no espera aclaración' USING ERRCODE='55000'; END IF;
 SELECT * INTO a FROM public.aclaraciones WHERE ejecucion_id=e.ejecucion_id AND respondida_en IS NULL AND cerrada_en IS NULL;
 IF FOUND THEN RETURN to_jsonb(a); END IF;
 IF p_pregunta IS NULL OR length(btrim(p_pregunta)) NOT BETWEEN 1 AND 4000 OR coalesce(cardinality(p_campos),0)=0
    OR EXISTS(SELECT 1 FROM unnest(p_campos) c WHERE c IS NULL OR length(btrim(c))=0) THEN
  RAISE EXCEPTION 'Pregunta o campos inválidos' USING ERRCODE='22023'; END IF;
 SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id;
 SELECT * INTO d FROM public.destinos WHERE destino_id=r.destino_origen_id;
 IF NOT FOUND OR d.canal<>'telegram' OR r.canal<>'telegram'
    OR r.mensaje_externo_id !~ '^-?[0-9]+:[0-9]+$'
    OR split_part(r.mensaje_externo_id,':',1)<>d.identificador_externo THEN
  UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo','destino_origen_pendiente','mensaje','Falta chat de origen verificable') WHERE ejecucion_id=e.ejecucion_id;
  PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Revisar destino de aclaración'); RETURN NULL;
 END IF;
 -- Interpretar los nombres de faltantes con y sin tildes; no usar texto ciudadano
 -- para construir preguntas ni copiar respuestas privadas a la salida del bot.
 SELECT bool_and(translate(lower(c),'áéíóú','aeiou') ~ '(ubicaci|lugar|direcci|sector|punto)')
 INTO solo_ubicacion FROM unnest(p_campos) c;
 pregunta:=p_pregunta;
 IF solo_ubicacion THEN
  SELECT count(*) INTO previas_ubicacion FROM public.aclaraciones aa
  WHERE aa.ejecucion_id=e.ejecucion_id AND aa.respondida_en IS NOT NULL
  AND EXISTS(SELECT 1 FROM unnest(aa.campos_solicitados) c
    WHERE translate(lower(c),'áéíóú','aeiou') ~ '(ubicaci|lugar|direcci|sector|punto)');
  -- Dos respuestas a solicitudes de ubicación sin resolución son suficientes:
  -- conservar el reporte para revisión; no fabricar un punto ni otra pregunta.
  IF previas_ubicacion>=2 THEN
   UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
    ultimo_error=jsonb_build_object('codigo','ubicacion_sin_resolver_tras_aclaraciones',
    'mensaje','Recibimos las respuestas, pero no logramos identificar un único punto de atención. El reporte se conserva para revisión humana.')
   WHERE ejecucion_id=e.ejecucion_id;
   PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Detener preguntas repetidas de ubicación',
     jsonb_build_object('motivo','ubicacion_sin_resolver_tras_aclaraciones','respuestas_ubicacion',previas_ubicacion));
   RETURN NULL;
  END IF;
  pregunta:=CASE WHEN EXISTS(SELECT 1 FROM public.aclaraciones aa WHERE aa.ejecucion_id=e.ejecucion_id AND aa.respondida_en IS NOT NULL)
   THEN 'Recibimos tu respuesta, pero no encontramos una coincidencia única para el lugar indicado en nuestro catálogo. '
   ELSE 'Para ubicar tu reporte, necesitamos identificar el punto de atención. ' END
   ||'Indica su nombre completo (por ejemplo, una escuela o junta comunal) y el distrito. '
   ||'Si no conoces el nombre, responde a esta pregunta con una ubicación estática de referencia; no envíes ubicación en vivo. '
   ||'Esto no significa que el lugar esté fuera de cobertura. '
   ||CASE WHEN previas_ubicacion>=1 THEN 'Si con esta respuesta no podemos identificarlo, conservaremos tu reporte para revisión humana.' ELSE '' END;
 END IF;
 INSERT INTO public.aclaraciones(ejecucion_id,reporte_id,destino_id,campos_solicitados,pregunta,origen)
 VALUES(e.ejecucion_id,r.reporte_id,d.destino_id,p_campos,pregunta,r.origen) RETURNING * INTO a;
 PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Crear aclaración',jsonb_build_object('aclaracion_id',a.aclaracion_id,'seguimiento',coalesce(previas_ubicacion,0)>0));
 RETURN to_jsonb(a);
END $$;

REVOKE ALL ON FUNCTION public.ra_crear_aclaracion(uuid,text[],text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_crear_aclaracion(uuid,text[],text) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
