-- Noel V4: bandeja de salida de avisos. Requiere 0001 (y las RPC de 0006 solo como referencia de estilo).
-- No crea avisos (los crea Comunicación), no aprueba planes y no envía mensajes: reserva un aviso
-- pendiente para que el bot lo envíe y registra el resultado. Un envío incierto nunca se reenvía solo.
BEGIN;

ALTER TABLE public.avisos
  ADD COLUMN trabajador_id text,
  ADD COLUMN reservada_en timestamptz,
  ADD COLUMN reserva_hasta timestamptz;

COMMENT ON COLUMN public.avisos.reserva_hasta IS
  'Reserva del bot que va a enviar el aviso. Si vence sin resultado, el aviso pasa a incierto: pudo enviarse.';

-- Evento de traza sin agente: lo hace el sistema, no un agente ni una persona.
CREATE FUNCTION public.ra_traza_aviso(p_ejecucion_id uuid, p_decision text, p_detalles jsonb DEFAULT '{}')
RETURNS void LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
  INSERT INTO public.eventos(ejecucion_id,actor_tipo,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
  SELECT ejecucion_id,'sistema',p_decision,p_decision,0,estado,p_detalles,origen
  FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id;
$$;

-- Reservas vencidas: el bot pudo enviar y morir antes de registrar. No se reenvía; queda visible.
CREATE FUNCTION public.ra_revisar_avisos()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE a public.avisos%ROWTYPE; n integer:=0;
BEGIN
  FOR a IN SELECT * FROM public.avisos
           WHERE estado_envio='pendiente' AND reservada_en IS NOT NULL AND reserva_hasta<=clock_timestamp()
           ORDER BY aviso_id FOR UPDATE SKIP LOCKED LOOP
    UPDATE public.avisos
       SET estado_envio='incierto', actualizado_en=clock_timestamp(),
           ultimo_error='Reserva vencida sin resultado: el mensaje pudo enviarse; no se reenvía automáticamente.'
     WHERE aviso_id=a.aviso_id;
    PERFORM public.ra_traza_aviso(a.ejecucion_id,'Aviso incierto por reserva vencida',
      jsonb_build_object('aviso_id',a.aviso_id));
    n:=n+1;
  END LOOP;
  RETURN n;
END $$;

-- Reserva el siguiente aviso pendiente SI sigue vigente. Si dejó de serlo, lo cancela con motivo y sigue.
-- Devuelve null cuando no hay nada que enviar.
CREATE FUNCTION public.ra_reservar_aviso(p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE a public.avisos%ROWTYPE; p public.planes%ROWTYPE; motivo text; chat text; punto text;
BEGIN
  IF p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'trabajador_id inválido' USING ERRCODE='22023';
  END IF;
  PERFORM public.ra_revisar_avisos();
  LOOP
    SELECT av.* INTO a FROM public.avisos av
     WHERE av.estado_envio='pendiente' AND av.reservada_en IS NULL
     ORDER BY av.creado_en, av.aviso_id LIMIT 1 FOR UPDATE SKIP LOCKED;
    IF NOT FOUND THEN RETURN NULL; END IF;

    motivo:=NULL;
    SELECT * INTO p FROM public.planes WHERE plan_id=a.plan_id AND version=a.version;
    IF NOT FOUND OR p.estado<>'aprobado' OR p.aprobacion_id IS DISTINCT FROM a.aprobacion_id THEN
      motivo:='El plan ya no está aprobado o su aprobación cambió.';
    ELSIF EXISTS (SELECT 1 FROM public.planes p2 WHERE p2.plan_id=a.plan_id AND p2.version>a.version AND p2.estado='aprobado') THEN
      motivo:='Existe una versión más reciente aprobada del plan.';
    ELSIF NOT EXISTS (SELECT 1 FROM public.suscripciones_sector s
                       WHERE s.destino_id=a.destino_id AND s.sector_id=a.sector_id AND s.activa) THEN
      motivo:='La suscripción del destino a este sector ya no está activa.';
    ELSIF NOT EXISTS (SELECT 1 FROM public.destinos d
                       WHERE d.destino_id=a.destino_id AND d.autorizado AND d.canal='telegram') THEN
      motivo:='El destino no está autorizado o no es un chat de Telegram.';
    ELSIF NOT EXISTS (SELECT 1 FROM public.paradas pa
                       WHERE pa.plan_id=a.plan_id AND pa.version=a.version AND pa.punto_atencion_id=a.punto_atencion_id
                         AND pa.litros_asignados=a.litros_asignados
                         AND a.ventana_inicio>=pa.llegada_estimada AND a.ventana_fin<=pa.fin_descarga) THEN
      motivo:='Los litros o la ventana del aviso no coinciden con la parada aprobada.';
    END IF;

    IF motivo IS NOT NULL THEN
      UPDATE public.avisos SET estado_envio='cancelado', ultimo_error=motivo, actualizado_en=clock_timestamp()
       WHERE aviso_id=a.aviso_id;
      PERFORM public.ra_traza_aviso(a.ejecucion_id,'Aviso cancelado antes de enviar',
        jsonb_build_object('aviso_id',a.aviso_id,'motivo',motivo));
      CONTINUE;
    END IF;

    UPDATE public.avisos
       SET trabajador_id=p_trabajador_id, reservada_en=clock_timestamp(),
           reserva_hasta=clock_timestamp()+interval '60 seconds',
           intentos=intentos+1, actualizado_en=clock_timestamp()
     WHERE aviso_id=a.aviso_id RETURNING * INTO a;
    SELECT identificador_externo INTO chat FROM public.destinos WHERE destino_id=a.destino_id;
    SELECT nombre INTO punto FROM public.puntos_atencion WHERE punto_atencion_id=a.punto_atencion_id;
    -- Solo lo necesario para redactar el mensaje: el bot no recibe aprobaciones ni datos de personas.
    RETURN jsonb_build_object(
      'aviso_id',a.aviso_id,'chat_id',chat,'tipo',a.tipo,'version',a.version,
      'punto_nombre',punto,'litros_asignados',a.litros_asignados,
      'ventana_inicio',a.ventana_inicio,'ventana_fin',a.ventana_fin);
  END LOOP;
END $$;

-- Registra el resultado del envío. Repetir el mismo resultado es seguro; uno distinto se rechaza.
-- Un acuse tardío de quien envió puede resolver un incierto por reserva vencida (es evidencia real).
CREATE FUNCTION public.ra_registrar_envio_aviso(
  p_aviso_id uuid, p_trabajador_id text, p_estado text, p_proveedor_mensaje_id text, p_error text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE a public.avisos%ROWTYPE;
BEGIN
  SELECT * INTO a FROM public.avisos WHERE aviso_id=p_aviso_id FOR UPDATE;
  IF NOT FOUND OR a.trabajador_id IS DISTINCT FROM p_trabajador_id OR a.reservada_en IS NULL THEN
    RAISE EXCEPTION 'Reserva ajena o inexistente' USING ERRCODE='55000';
  END IF;
  IF p_estado IS NULL OR p_estado NOT IN ('enviado','fallido','incierto')
     OR (p_estado='enviado' AND (p_proveedor_mensaje_id IS NULL OR p_proveedor_mensaje_id !~ '^[0-9]+$' OR p_error IS NOT NULL))
     OR (p_estado<>'enviado' AND (p_proveedor_mensaje_id IS NOT NULL OR p_error IS NULL OR length(btrim(p_error))=0)) THEN
    RAISE EXCEPTION 'Resultado de envío inválido' USING ERRCODE='22023';
  END IF;
  IF a.estado_envio='pendiente' OR (a.estado_envio='incierto' AND a.ultimo_error LIKE 'Reserva vencida%') THEN
    UPDATE public.avisos
       SET estado_envio=p_estado::public.ra_estado_aviso, proveedor_mensaje_id=p_proveedor_mensaje_id,
           enviado_en=CASE WHEN p_estado='enviado' THEN clock_timestamp() END,
           ultimo_error=p_error, actualizado_en=clock_timestamp()
     WHERE aviso_id=a.aviso_id RETURNING * INTO a;
    PERFORM public.ra_traza_aviso(a.ejecucion_id,'Registrar envío de aviso',
      jsonb_build_object('aviso_id',a.aviso_id,'estado_envio',p_estado,'proveedor_mensaje_id',p_proveedor_mensaje_id));
    RETURN jsonb_build_object('aviso_id',a.aviso_id,'estado_envio',a.estado_envio);
  END IF;
  IF a.estado_envio::text=p_estado AND a.proveedor_mensaje_id IS NOT DISTINCT FROM p_proveedor_mensaje_id
     AND a.ultimo_error IS NOT DISTINCT FROM p_error THEN
    RETURN jsonb_build_object('aviso_id',a.aviso_id,'estado_envio',a.estado_envio);
  END IF;
  RAISE EXCEPTION 'Envío ya registrado con otro resultado' USING ERRCODE='55000';
END $$;

DO $$
DECLARE f record;
BEGIN
  FOR f IN SELECT p.oid::regprocedure::text AS firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN ('ra_traza_aviso','ra_revisar_avisos','ra_reservar_aviso','ra_registrar_envio_aviso') LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated',f.firma);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
  END LOOP;
END $$;

COMMIT;
