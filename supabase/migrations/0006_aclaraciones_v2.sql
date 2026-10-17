-- Emilia V2. Requiere 0001, 0004 y 0005. No envía mensajes ni procesa reportes.
BEGIN;
ALTER TABLE public.reportes ADD COLUMN destino_origen_id uuid REFERENCES public.destinos ON DELETE RESTRICT;
CREATE INDEX reportes_destino_origen_idx ON public.reportes(destino_origen_id);
ALTER TABLE public.aclaraciones
 ADD COLUMN trabajador_id text,
 ADD COLUMN reservada_en timestamptz,
 ADD COLUMN reserva_hasta timestamptz,
 ADD COLUMN respuesta_externo_id text,
 ADD COLUMN respuesta_remitente_ref uuid REFERENCES public.remitentes ON DELETE RESTRICT,
 ADD COLUMN plazo_respuesta_segundos integer NOT NULL DEFAULT 1800 CHECK(plazo_respuesta_segundos BETWEEN 1 AND 86400),
 ADD COLUMN vence_en timestamptz,
 ADD COLUMN cerrada_en timestamptz,
 ADD COLUMN motivo_cierre text,
 ADD CONSTRAINT aclaracion_respuesta_texto CHECK(respuesta_texto IS NULL OR length(btrim(respuesta_texto)) BETWEEN 1 AND 4000);
-- No se reconstruyen chats de reportes antiguos ni se elige entre aclaraciones previas.
CREATE UNIQUE INDEX aclaracion_activa_ejecucion ON public.aclaraciones(ejecucion_id)
 WHERE respondida_en IS NULL AND cerrada_en IS NULL;
CREATE UNIQUE INDEX aclaracion_respuesta_externa ON public.aclaraciones(respuesta_externo_id) WHERE respuesta_externo_id IS NOT NULL;
CREATE UNIQUE INDEX aclaracion_pregunta_destino ON public.aclaraciones(destino_id,proveedor_mensaje_id) WHERE proveedor_mensaje_id IS NOT NULL;

CREATE FUNCTION public.ra_traza_aclaracion(p_ejecucion_id uuid,p_decision text,p_detalles jsonb DEFAULT '{}')
RETURNS void LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
 SELECT ejecucion_id,'sistema',p_decision,p_decision,0,estado,p_detalles,origen
 FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id;
$$;

CREATE FUNCTION public.ra_crear_aclaracion(p_ejecucion_id uuid,p_campos text[],p_pregunta text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE; d public.destinos%ROWTYPE; a public.aclaraciones%ROWTYPE;
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
 INSERT INTO public.aclaraciones(ejecucion_id,reporte_id,destino_id,campos_solicitados,pregunta,origen)
 VALUES(e.ejecucion_id,r.reporte_id,d.destino_id,p_campos,p_pregunta,r.origen) RETURNING * INTO a;
 PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Crear aclaración',jsonb_build_object('aclaracion_id',a.aclaracion_id));
 RETURN to_jsonb(a);
END $$;

CREATE FUNCTION public.ra_revisar_aclaraciones()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x record; a public.aclaraciones%ROWTYPE; n integer:=0; motivo text;
BEGIN
 FOR x IN SELECT e.ejecucion_id FROM public.ejecuciones e WHERE e.estado='espera_aclaracion' ORDER BY e.ejecucion_id FOR UPDATE SKIP LOCKED LOOP
  SELECT * INTO a FROM public.aclaraciones WHERE ejecucion_id=x.ejecucion_id AND respondida_en IS NULL AND cerrada_en IS NULL FOR UPDATE;
  IF NOT FOUND THEN CONTINUE; END IF;
  motivo:=NULL;
  IF a.estado_envio='enviado' AND a.vence_en<=clock_timestamp() THEN motivo:='aclaracion_vencida';
  ELSIF a.estado_envio IN ('incierto','fallido') THEN motivo:='envio_'||a.estado_envio::text;
  ELSIF a.reservada_en IS NOT NULL AND a.estado_envio='pendiente' AND a.reserva_hasta<=clock_timestamp() THEN motivo:='reserva_vencida'; END IF;
  IF motivo IS NOT NULL THEN
   UPDATE public.aclaraciones SET cerrada_en=clock_timestamp(),motivo_cierre=motivo WHERE aclaracion_id=a.aclaracion_id;
   UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo',motivo,'mensaje','Aclaración requiere revisión; sin reenvío automático') WHERE ejecucion_id=x.ejecucion_id;
   PERFORM public.ra_traza_aclaracion(x.ejecucion_id,'Revisar aclaración',jsonb_build_object('motivo',motivo,'aclaracion_id',a.aclaracion_id)); n:=n+1;
  END IF;
 END LOOP;
 RETURN n;
END $$;

CREATE FUNCTION public.ra_reservar_aclaracion(p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; a public.aclaraciones%ROWTYPE;
BEGIN
 IF p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN RAISE EXCEPTION 'trabajador_id inválido' USING ERRCODE='22023'; END IF;
 PERFORM public.ra_revisar_aclaraciones();
 SELECT e0.* INTO e FROM public.ejecuciones e0 WHERE e0.estado='espera_aclaracion' AND EXISTS(
  SELECT 1 FROM public.aclaraciones a0 WHERE a0.ejecucion_id=e0.ejecucion_id AND a0.estado_envio='pendiente' AND a0.reservada_en IS NULL AND a0.cerrada_en IS NULL AND a0.respondida_en IS NULL)
 ORDER BY e0.creado_en,e0.ejecucion_id LIMIT 1 FOR UPDATE SKIP LOCKED;
 IF NOT FOUND THEN RETURN NULL; END IF;
 UPDATE public.aclaraciones SET trabajador_id=p_trabajador_id,reservada_en=clock_timestamp(),reserva_hasta=clock_timestamp()+interval '60 seconds'
 WHERE ejecucion_id=e.ejecucion_id AND cerrada_en IS NULL AND respondida_en IS NULL RETURNING * INTO a;
 RETURN to_jsonb(a)||jsonb_build_object('chat_id',(SELECT identificador_externo FROM public.destinos WHERE destino_id=a.destino_id),
  'mensaje_externo_id',(SELECT mensaje_externo_id FROM public.reportes WHERE reporte_id=a.reporte_id));
END $$;

CREATE FUNCTION public.ra_registrar_envio_aclaracion(p_aclaracion_id uuid,p_trabajador_id text,p_estado text,p_proveedor_mensaje_id text,p_error text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE a public.aclaraciones%ROWTYPE; eid uuid; e public.ejecuciones%ROWTYPE;
BEGIN
 SELECT ejecucion_id INTO eid FROM public.aclaraciones WHERE aclaracion_id=p_aclaracion_id;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=eid FOR UPDATE;
 SELECT * INTO a FROM public.aclaraciones WHERE aclaracion_id=p_aclaracion_id FOR UPDATE;
 IF NOT FOUND OR a.trabajador_id IS DISTINCT FROM p_trabajador_id OR a.reservada_en IS NULL THEN RAISE EXCEPTION 'Reserva ajena o inexistente' USING ERRCODE='55000'; END IF;
 IF p_estado IS NULL OR p_estado NOT IN ('enviado','fallido','incierto')
  OR (p_estado='enviado' AND (p_proveedor_mensaje_id IS NULL OR p_proveedor_mensaje_id !~ '^[0-9]+$' OR p_error IS NOT NULL))
  OR (p_estado<>'enviado' AND (p_proveedor_mensaje_id IS NOT NULL OR p_error IS NULL OR length(btrim(p_error))=0)) THEN
  RAISE EXCEPTION 'Resultado de envío inválido' USING ERRCODE='22023'; END IF;
 IF a.estado_envio<>'pendiente' THEN
  IF a.estado_envio::text=p_estado AND a.proveedor_mensaje_id IS NOT DISTINCT FROM p_proveedor_mensaje_id AND a.ultimo_error IS NOT DISTINCT FROM p_error THEN RETURN to_jsonb(a); END IF;
  RAISE EXCEPTION 'Envío ya registrado con otro resultado' USING ERRCODE='55000'; END IF;
 -- Un acuse tardío puede conservar el ID real para reconocer replies, pero no reabre la ejecución.
 UPDATE public.aclaraciones SET estado_envio=p_estado::public.ra_estado_aviso,proveedor_mensaje_id=p_proveedor_mensaje_id,
  enviado_en=CASE WHEN p_estado='enviado' THEN clock_timestamp() END,
  vence_en=CASE WHEN p_estado='enviado' THEN clock_timestamp()+make_interval(secs=>plazo_respuesta_segundos) END,ultimo_error=p_error,
  cerrada_en=CASE WHEN p_estado<>'enviado' OR reserva_hasta<=clock_timestamp() THEN coalesce(cerrada_en,clock_timestamp()) ELSE cerrada_en END,
  motivo_cierre=CASE WHEN reserva_hasta<=clock_timestamp() THEN 'reserva_vencida' WHEN p_estado<>'enviado' THEN 'envio_'||p_estado ELSE motivo_cierre END
 WHERE aclaracion_id=a.aclaracion_id RETURNING * INTO a;
 IF a.cerrada_en IS NOT NULL THEN
  UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo',a.motivo_cierre,'mensaje','Envío requiere revisión') WHERE ejecucion_id=eid;
 END IF;
 PERFORM public.ra_traza_aclaracion(eid,'Registrar envío de aclaración',jsonb_build_object('aclaracion_id',a.aclaracion_id,'estado_envio',p_estado));
 RETURN to_jsonb(a);
END $$;

CREATE FUNCTION public.ra_aceptar_respuesta_aclaracion(p_chat_id text,p_pregunta_mensaje_id text,p_respuesta_externo_id text,p_remitente_ref uuid,p_texto text,p_ubicacion jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE a public.aclaraciones%ROWTYPE; e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE; aid uuid;
BEGIN
 SELECT a0.aclaracion_id INTO aid FROM public.aclaraciones a0 JOIN public.destinos d USING(destino_id)
 WHERE d.canal='telegram' AND d.identificador_externo=p_chat_id AND a0.proveedor_mensaje_id=p_pregunta_mensaje_id;
 IF NOT FOUND THEN RETURN jsonb_build_object('resultado','no_encontrada'); END IF;
 SELECT e0.* INTO e FROM public.ejecuciones e0 JOIN public.aclaraciones a0 USING(ejecucion_id) WHERE a0.aclaracion_id=aid FOR UPDATE OF e0;
 SELECT * INTO a FROM public.aclaraciones WHERE aclaracion_id=aid FOR UPDATE;
 SELECT * INTO r FROM public.reportes WHERE reporte_id=a.reporte_id;
 IF r.remitente_ref IS DISTINCT FROM p_remitente_ref THEN RETURN jsonb_build_object('resultado','autor_distinto'); END IF;
 IF r.destino_origen_id IS DISTINCT FROM a.destino_id OR r.canal<>'telegram' OR split_part(r.mensaje_externo_id,':',1) IS DISTINCT FROM p_chat_id THEN RETURN jsonb_build_object('resultado','no_encontrada'); END IF;
 IF a.respuesta_externo_id=p_respuesta_externo_id THEN RETURN jsonb_build_object('resultado','repetida','ejecucion_id',e.ejecucion_id); END IF;
 IF a.respondida_en IS NOT NULL THEN RETURN jsonb_build_object('resultado','ya_respondida','ejecucion_id',e.ejecucion_id); END IF;
 IF a.cerrada_en IS NOT NULL OR (a.vence_en IS NOT NULL AND a.vence_en<=clock_timestamp()) THEN
  IF a.cerrada_en IS NULL THEN
   UPDATE public.aclaraciones SET cerrada_en=clock_timestamp(),motivo_cierre='aclaracion_vencida' WHERE aclaracion_id=aid;
   UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo','aclaracion_vencida','mensaje','Aclaración vencida') WHERE ejecucion_id=e.ejecucion_id;
   PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Vencer aclaración');
  END IF;
  RETURN jsonb_build_object('resultado','vencida','ejecucion_id',e.ejecucion_id);
 END IF;
 IF a.estado_envio<>'enviado' OR e.estado<>'espera_aclaracion' THEN RETURN jsonb_build_object('resultado','no_encontrada'); END IF;
 IF p_respuesta_externo_id IS NULL OR p_respuesta_externo_id !~ '^-?[0-9]+:[0-9]+$' OR split_part(p_respuesta_externo_id,':',1)<>p_chat_id
  OR (p_texto IS NULL)=(p_ubicacion IS NULL) OR (p_texto IS NOT NULL AND length(btrim(p_texto)) NOT BETWEEN 1 AND 4000) THEN
  RAISE EXCEPTION 'Respuesta inválida' USING ERRCODE='22023'; END IF;
 IF p_ubicacion IS NOT NULL THEN
  IF jsonb_typeof(p_ubicacion) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'Ubicación inválida' USING ERRCODE='22023'; END IF;
  IF (p_ubicacion->>'fuente') IS DISTINCT FROM 'compartida'
   OR jsonb_typeof(p_ubicacion->'latitud') IS DISTINCT FROM 'number' OR jsonb_typeof(p_ubicacion->'longitud') IS DISTINCT FROM 'number'
   OR NOT ((p_ubicacion->>'latitud')::numeric BETWEEN -90 AND 90) OR NOT ((p_ubicacion->>'longitud')::numeric BETWEEN -180 AND 180)
   OR (p_ubicacion->'representa_punto_atencion' IS NOT NULL AND p_ubicacion->'representa_punto_atencion'<>'null'::jsonb)
   OR (p_ubicacion-'latitud'-'longitud'-'fuente'-'precision_metros'-'representa_punto_atencion')<>'{}'::jsonb THEN
   RAISE EXCEPTION 'Ubicación compartida inválida; sin aprobación de punto' USING ERRCODE='22023'; END IF;
  IF p_ubicacion ? 'precision_metros' AND p_ubicacion->'precision_metros'<>'null'::jsonb THEN
   IF jsonb_typeof(p_ubicacion->'precision_metros') IS DISTINCT FROM 'number' THEN RAISE EXCEPTION 'Precisión inválida' USING ERRCODE='22023'; END IF;
   IF (p_ubicacion->>'precision_metros')::numeric<0 THEN RAISE EXCEPTION 'Precisión inválida' USING ERRCODE='22023'; END IF;
  END IF;
 END IF;
 -- El índice global impide reutilizar el mismo reply en otra aclaración.
 UPDATE public.aclaraciones SET respuesta_texto=p_texto,respuesta_ubicacion=p_ubicacion,respuesta_externo_id=p_respuesta_externo_id,
  respuesta_remitente_ref=p_remitente_ref,respondida_en=clock_timestamp(),cerrada_en=clock_timestamp(),motivo_cierre='respondida' WHERE aclaracion_id=aid;
 UPDATE public.ejecuciones SET estado='pendiente',etapa='ingesta',trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=NULL WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Aceptar respuesta y reanudar Ingesta',jsonb_build_object('aclaracion_id',aid));
 RETURN jsonb_build_object('resultado','aceptada','ejecucion_id',e.ejecucion_id);
END $$;

-- RPC internas: acceso exclusivo del backend. RLS de las tablas permanece cerrado.
DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure AS firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' AND p.proname IN ('ra_traza_aclaracion','ra_crear_aclaracion','ra_revisar_aclaraciones','ra_reservar_aclaracion','ra_registrar_envio_aclaracion','ra_aceptar_respuesta_aclaracion') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated',f.firma);
  EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
 END LOOP;
END $$;
CREATE OR REPLACE FUNCTION public.ra_tomar_ingesta(p_ejecucion_id uuid, p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE;
BEGIN
  IF p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'trabajador_id inválido' USING ERRCODE='22023';
  END IF;
  SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
  IF NOT FOUND OR e.estado <> 'pendiente' OR e.etapa <> 'ingesta' THEN RETURN NULL; END IF;
  SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Ejecución sin reporte disponible' USING ERRCODE='23503'; END IF;
  UPDATE public.ejecuciones SET estado='ejecutando', trabajador_id=p_trabajador_id,
    bloqueada_hasta=clock_timestamp()+interval '180 seconds', intentos=intentos+1, ultimo_error=NULL
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
    estado_siguiente := 'fallida'; etapa_siguiente := 'ingesta';
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
    jsonb_build_object('ingesta_cierre_hash',cierre_hash,'trabajador_id',p_trabajador_id),
    r.origen,(p_evento->>'creado_en')::timestamptz);
  UPDATE public.ejecuciones SET estado=estado_siguiente, etapa=etapa_siguiente,
    ultimo_error=p_error, trabajador_id=NULL, bloqueada_hasta=NULL WHERE ejecucion_id=e.ejecucion_id;
  IF estado_siguiente='espera_aclaracion' THEN
    PERFORM public.ra_crear_aclaracion(e.ejecucion_id,
      ARRAY(SELECT jsonb_array_elements_text(extraccion->'faltantes')),
      'Para continuar, indica el nombre exacto de la instalación o una referencia, cuántas horas llevan sin agua y cuántas personas están afectadas. Si falta ubicar el lugar, puedes responder a esta pregunta con una ubicación estática.');
    SELECT estado,etapa INTO estado_siguiente,etapa_siguiente FROM public.ejecuciones WHERE ejecucion_id=e.ejecucion_id;
  END IF;
  RETURN jsonb_build_object('estado',estado_siguiente,'etapa',etapa_siguiente,
                           'ejecucion_id',e.ejecucion_id,'reintento',false);
END $$;


NOTIFY pgrst,'reload schema';
COMMIT;
