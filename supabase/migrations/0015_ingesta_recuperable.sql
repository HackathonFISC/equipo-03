-- Emilia A4. Requiere 0014 y las RPC de 0006/0007. Ejecutar completo una vez.
-- No modifica contratos ni reactiva errores históricos; no envía mensajes.
BEGIN;
ALTER TABLE public.ejecuciones
 ADD COLUMN reintentos_ingesta integer NOT NULL DEFAULT 0 CHECK(reintentos_ingesta BETWEEN 0 AND 2),
 ADD COLUMN proximo_intento_ingesta timestamptz;
CREATE INDEX ejecuciones_reintento_ingesta_idx ON public.ejecuciones(proximo_intento_ingesta)
 WHERE etapa='ingesta' AND estado='espera_validacion' AND proximo_intento_ingesta IS NOT NULL;

CREATE OR REPLACE FUNCTION public.ra_tomar_ingesta(p_ejecucion_id uuid, p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE;
BEGIN
  IF p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'trabajador_id inválido' USING ERRCODE='22023';
  END IF;
  SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
  IF NOT FOUND OR e.estado <> 'pendiente' OR e.etapa <> 'ingesta'
     OR e.proximo_intento_ingesta > clock_timestamp() THEN RETURN NULL; END IF;
  SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Ejecución sin reporte disponible' USING ERRCODE='23503'; END IF;
  UPDATE public.ejecuciones SET estado='ejecutando', trabajador_id=p_trabajador_id,
    bloqueada_hasta=clock_timestamp()+interval '180 seconds', intentos=intentos+1, ultimo_error=NULL, proximo_intento_ingesta=NULL
    WHERE ejecucion_id=e.ejecucion_id RETURNING * INTO e;
  RETURN jsonb_build_object('ejecucion',to_jsonb(e),'reporte',to_jsonb(r),'aclaraciones',coalesce((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.respondida_en,a.aclaracion_id) FROM public.aclaraciones a WHERE a.ejecucion_id=e.ejecucion_id AND a.respondida_en IS NOT NULL),'[]'::jsonb));
END $$;

CREATE OR REPLACE FUNCTION public.ra_finalizar_ingesta(
  p_ejecucion_id uuid, p_trabajador_id text, p_reporte_snapshot jsonb,
  p_resultado jsonb, p_evento jsonb, p_error jsonb
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
  e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE; anterior public.eventos%ROWTYPE;
  estado_siguiente public.ra_estado_ejecucion; etapa_siguiente text; extraccion jsonb;
  reintento_programado timestamptz; cantidad_reintentos integer;
  cierre_hash text; evento_id_nuevo uuid;
  ignoradas text[] := ARRAY['interpretacion','evidencias','requiere_aclaracion','fuera_de_alcance','actualizado_en'];
BEGIN
  IF (p_resultado IS NULL) = (p_error IS NULL) OR p_evento IS NULL OR p_reporte_snapshot IS NULL THEN
    RAISE EXCEPTION 'Se requiere resultado o error y una traza con snapshot' USING ERRCODE='22023';
  END IF;
  cierre_hash := md5(jsonb_build_object('trabajador',p_trabajador_id,'snapshot',p_reporte_snapshot,
                    'resultado',p_resultado,'evento',p_evento,'error',p_error)::text);
  evento_id_nuevo := (p_evento->>'evento_id')::uuid;
  SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Ejecución no disponible' USING ERRCODE='22023'; END IF;
  SELECT * INTO anterior FROM public.eventos WHERE evento_id=evento_id_nuevo;
  IF FOUND THEN
    IF anterior.ejecucion_id=e.ejecucion_id AND anterior.detalles->>'ingesta_cierre_hash'=cierre_hash THEN
      RETURN jsonb_build_object('estado',e.estado,'etapa',e.etapa,'ejecucion_id',e.ejecucion_id,'reintento',true);
    END IF;
    RAISE EXCEPTION 'ID de evento ya usado por otro cierre' USING ERRCODE='23505';
  END IF;
  IF e.estado <> 'ejecutando' OR e.etapa <> 'ingesta'
     OR e.trabajador_id IS DISTINCT FROM p_trabajador_id
     OR e.bloqueada_hasta IS NULL OR e.bloqueada_hasta <= clock_timestamp() THEN
    RAISE EXCEPTION 'Reserva de Ingesta ausente, vencida o de otro trabajador' USING ERRCODE='55000';
  END IF;
  SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id FOR UPDATE;
  IF NOT FOUND OR (to_jsonb(r)-ignoradas) IS DISTINCT FROM (p_reporte_snapshot-ignoradas) THEN
    RAISE EXCEPTION 'El reporte cambió durante Ingesta' USING ERRCODE='40001';
  END IF;
  IF (p_evento->>'ejecucion_id') IS DISTINCT FROM e.ejecucion_id::text
     OR (p_evento->>'agente') IS DISTINCT FROM 'ingesta'
     OR (p_evento->>'origen') IS DISTINCT FROM r.origen::text
     OR (p_evento->>'esquema_version') IS DISTINCT FROM '1.0' THEN
    RAISE EXCEPTION 'Traza incompatible con la ejecución' USING ERRCODE='22023';
  END IF;
  IF p_error IS NULL THEN
    IF (p_resultado->>'reporte_id') IS DISTINCT FROM r.reporte_id::text
       OR (p_resultado->>'ejecucion_id') IS DISTINCT FROM e.ejecucion_id::text
       OR (p_resultado->>'origen') IS DISTINCT FROM r.origen::text
       OR (p_resultado->>'modalidad') IS DISTINCT FROM 'texto'
       OR r.modalidad <> 'texto'
       OR jsonb_typeof(p_resultado->'interpretacion') IS DISTINCT FROM 'object'
       OR jsonb_typeof(p_resultado->'evidencias') IS DISTINCT FROM 'array' THEN
      RAISE EXCEPTION 'Interpretación incompatible con el reporte' USING ERRCODE='22023';
    END IF;
    IF jsonb_array_length(p_resultado->'evidencias') < 1 OR EXISTS (
      SELECT 1 FROM jsonb_array_elements(p_resultado->'evidencias') AS ev
      WHERE (ev->>'reporte_id') IS DISTINCT FROM r.reporte_id::text
    ) THEN RAISE EXCEPTION 'Evidencias sin referencia válida' USING ERRCODE='22023'; END IF;
    extraccion := p_resultado->'interpretacion';
    IF jsonb_typeof(extraccion->'requiere_aclaracion') IS DISTINCT FROM 'boolean'
       OR jsonb_typeof(extraccion->'fuera_de_alcance') IS DISTINCT FROM 'boolean' THEN
      RAISE EXCEPTION 'Faltan banderas de interpretación' USING ERRCODE='22023';
    END IF;
    IF (extraccion->>'fuera_de_alcance')::boolean THEN
      IF (extraccion->>'requiere_aclaracion')::boolean THEN
        RAISE EXCEPTION 'Fuera de alcance no debe pedir aclaración' USING ERRCODE='22023';
      END IF;
      estado_siguiente := 'completada'; etapa_siguiente := 'terminada';
    ELSIF (extraccion->>'requiere_aclaracion')::boolean THEN
      estado_siguiente := 'espera_aclaracion'; etapa_siguiente := 'ingesta';
    ELSE estado_siguiente := 'pendiente'; etapa_siguiente := 'territorial';
    END IF;
    UPDATE public.reportes SET interpretacion=extraccion, evidencias=p_resultado->'evidencias',
      requiere_aclaracion=(extraccion->>'requiere_aclaracion')::boolean,
      fuera_de_alcance=(extraccion->>'fuera_de_alcance')::boolean WHERE reporte_id=r.reporte_id;
  ELSE
    IF (p_error->>'ejecucion_id') IS DISTINCT FROM e.ejecucion_id::text
       OR (p_error->>'origen') IS DISTINCT FROM r.origen::text
       OR jsonb_typeof(p_error->'mensaje') IS DISTINCT FROM 'string'
       OR jsonb_typeof(p_error->'codigo') IS DISTINCT FROM 'string' THEN
      RAISE EXCEPTION 'Error incompatible con ejecución' USING ERRCODE='22023';
    END IF;
    etapa_siguiente := 'ingesta';
    IF jsonb_typeof(p_error->'recuperable') IS DISTINCT FROM 'boolean' THEN
      RAISE EXCEPTION 'Error sin indicador recuperable' USING ERRCODE='22023';
    END IF;
    IF (p_error->>'recuperable')::boolean THEN
      IF coalesce(p_error->'campos' @> '["configuracion_gemini"]'::jsonb,false)
         OR e.reintentos_ingesta>=2 THEN
        estado_siguiente := 'espera_revision';
      ELSE
        estado_siguiente := 'espera_validacion';
        cantidad_reintentos := e.reintentos_ingesta+1;
        reintento_programado := clock_timestamp() + make_interval(secs => 5 * (2 ^ e.reintentos_ingesta)::integer);
      END IF;
    ELSE
      estado_siguiente := 'fallida';
    END IF;
  END IF;
  IF (p_evento->>'siguiente_estado') IS DISTINCT FROM estado_siguiente::text THEN
    RAISE EXCEPTION 'Transición de traza incompatible' USING ERRCODE='22023';
  END IF;
  INSERT INTO public.eventos(evento_id,ejecucion_id,agente,actor_tipo,decision,herramienta,
    entrada_ids,salida_ids,resultado,duracion_ms,siguiente_estado,detalles,origen,creado_en)
  VALUES(evento_id_nuevo,e.ejecucion_id,'ingesta','agente',p_evento->>'decision',p_evento->>'herramienta',
    ARRAY(SELECT jsonb_array_elements_text(p_evento->'entrada_ids')::uuid),
    ARRAY(SELECT jsonb_array_elements_text(p_evento->'salida_ids')::uuid),
    p_evento->>'resultado',(p_evento->>'duracion_ms')::integer,estado_siguiente,
    jsonb_build_object('ingesta_cierre_hash',cierre_hash,'trabajador_id',p_trabajador_id,
      'reintentos_ingesta',coalesce(cantidad_reintentos,e.reintentos_ingesta),
      'proximo_intento_ingesta',reintento_programado),
    r.origen,(p_evento->>'creado_en')::timestamptz);
  UPDATE public.ejecuciones SET estado=estado_siguiente, etapa=etapa_siguiente,
    ultimo_error=p_error, trabajador_id=NULL, bloqueada_hasta=NULL,
    reintentos_ingesta=coalesce(cantidad_reintentos,e.reintentos_ingesta),
    proximo_intento_ingesta=reintento_programado WHERE ejecucion_id=e.ejecucion_id;
  IF estado_siguiente='espera_aclaracion' THEN
    PERFORM public.ra_crear_aclaracion(e.ejecucion_id,
      ARRAY(SELECT jsonb_array_elements_text(extraccion->'faltantes')),
      'Para continuar, indica el nombre exacto de la instalación o una referencia, cuántas horas llevan sin agua y cuántas personas están afectadas. Si falta ubicar el lugar, puedes responder a esta pregunta con una ubicación estática.');
    SELECT estado,etapa INTO estado_siguiente,etapa_siguiente FROM public.ejecuciones WHERE ejecucion_id=e.ejecucion_id;
  END IF;
  RETURN jsonb_build_object('estado',estado_siguiente,'etapa',etapa_siguiente,
                           'ejecucion_id',e.ejecucion_id,'reintento',false);
END $$;


CREATE OR REPLACE FUNCTION public.ra_mantenimiento_v2()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x record; n integer; c integer:=0;
BEGIN
 n:=public.ra_revisar_aclaraciones();
 FOR x IN SELECT ejecucion_id FROM public.ejecuciones
 WHERE estado='ejecutando' AND etapa IN ('ingesta','territorial','priorizacion','planificacion','comunicacion')
 AND bloqueada_hasta<=clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
  UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
   ultimo_error=jsonb_build_object('codigo','reserva_trabajador_vencida','mensaje','Revisar resultado antes de reintentar')
   WHERE ejecucion_id=x.ejecucion_id;
  PERFORM public.ra_traza_aclaracion(x.ejecucion_id,'Revisar reserva de trabajador vencida'); c:=c+1;
 END LOOP;
 -- Solo reanudar errores cuyo cierre quedó confirmado y programado en BD.
 -- Reserva vencida, resultado incierto y configuración no tienen fecha de reintento.
 FOR x IN SELECT ejecucion_id FROM public.ejecuciones
 WHERE etapa='ingesta' AND estado='espera_validacion'
 AND proximo_intento_ingesta<=clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
  UPDATE public.ejecuciones SET estado='pendiente',proximo_intento_ingesta=NULL
   WHERE ejecucion_id=x.ejecucion_id;
  PERFORM public.ra_evento_v2(x.ejecucion_id,'ingesta','Reanudar extracción tras error recuperable confirmado',
    jsonb_build_object('motivo','reintento_ingesta_programado'));
  c:=c+1;
 END LOOP;
 RETURN n+c;
END $$;

REVOKE ALL ON FUNCTION public.ra_tomar_ingesta(uuid,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.ra_finalizar_ingesta(uuid,text,jsonb,jsonb,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.ra_mantenimiento_v2() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_tomar_ingesta(uuid,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.ra_finalizar_ingesta(uuid,text,jsonb,jsonb,jsonb,jsonb) TO service_role;
GRANT EXECUTE ON FUNCTION public.ra_mantenimiento_v2() TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
