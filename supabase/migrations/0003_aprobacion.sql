-- Noel V4: aprobación atómica de planes. Requiere 0001 y 0009 (escenarios_planificacion_v3 y su snapshot).
-- Se aplica DESPUÉS de las demás aunque se llame 0003: el número estaba reservado a Noel desde 0001.
-- No crea cuentas ni roles, no envía nada y no crea avisos (los crea Comunicación después de aprobar).
-- Solo service_role ejecuta las RPC; la API debe pasar el usuario tomado del token verificado,
-- nunca uno enviado por el navegador. Los errores empiezan por el código de dominio de D003.
-- Además bloquea las tablas de entradas al aprobar e invalida el plan aprobado si luego cambian.
BEGIN;

-- Aprobar un plan. Una sola transacción: coordinador activo, versión vigente, política activa,
-- entradas sin cambios desde el cálculo, verificación válida y bloqueos reconocidos por la persona.
CREATE FUNCTION public.ra_aprobar_plan(
  p_usuario_id uuid, p_plan_id uuid, p_version integer, p_datos_version text, p_politica_version text,
  p_motivo text, p_bloqueos_reconocidos text[])
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  pl public.planes%ROWTYPE; ap public.aprobaciones%ROWTYPE; ej public.ejecuciones%ROWTYPE;
  esc public.escenarios_planificacion_v3%ROWTYPE; nuevo uuid; ajenos text[]; faltan text[];
  -- Bloqueos que la aprobación humana puede reconocer y levantar. Cualquier otro (cobertura crítica,
  -- solver sin solución, verificación inválida) impide aprobar: no se levanta con una confirmación.
  reconocibles CONSTANT text[] := ARRAY[
    'Sin verificación independiente ni aprobación autorizada de esta versión.',
    'Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.',
    'ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.'];
BEGIN
  IF p_usuario_id IS NULL OR p_plan_id IS NULL OR p_version IS NULL OR p_version<1
     OR p_datos_version IS NULL OR p_politica_version IS NULL OR p_bloqueos_reconocidos IS NULL
     OR p_motivo IS NULL OR length(btrim(p_motivo)) NOT BETWEEN 1 AND 4000 THEN
    RAISE EXCEPTION 'contrato_invalido: faltan datos de la aprobación o el motivo no es válido' USING ERRCODE='22023';
  END IF;

  PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'sin_permiso: solo un coordinador activo puede aprobar planes' USING ERRCODE='42501';
  END IF;

  -- Entradas estables hasta el commit: quien las modifique espera a que esta aprobación termine y, si
  -- el plan ya quedó aprobado, el disparador de abajo lo invalida. Se bloquea ANTES de la fila del plan
  -- (mismo orden que el disparador) para que ambos lados no se esperen entre sí.
  LOCK TABLE public.depositos,public.vehiculos,public.incidentes,public.puntos_atencion,public.politicas_prioridad IN SHARE MODE;

  SELECT * INTO pl FROM public.planes WHERE plan_id=p_plan_id AND version=p_version FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'contrato_invalido: el plan no existe' USING ERRCODE='22023';
  END IF;

  -- Repetir la misma aprobación devuelve el acuse anterior; otra distinta se rechaza.
  IF pl.estado='aprobado' THEN
    SELECT * INTO ap FROM public.aprobaciones WHERE aprobacion_id=pl.aprobacion_id;
    IF ap.usuario_id=p_usuario_id AND ap.motivo=p_motivo AND ap.datos_version=p_datos_version
       AND ap.politica_version=p_politica_version THEN
      RETURN jsonb_build_object('plan_id',pl.plan_id,'version',pl.version,'aprobacion_id',ap.aprobacion_id,
        'estado','aprobado','ejecucion_id',pl.ejecucion_id,'repetido',true);
    END IF;
    RAISE EXCEPTION 'plan_ya_resuelto: el plan ya fue aprobado con otra confirmación' USING ERRCODE='55000';
  END IF;
  IF pl.estado<>'pendiente_revision' THEN
    RAISE EXCEPTION 'plan_ya_resuelto: el plan está en estado %', pl.estado USING ERRCODE='55000';
  END IF;

  IF pl.datos_version IS DISTINCT FROM p_datos_version OR pl.politica_version IS DISTINCT FROM p_politica_version THEN
    RAISE EXCEPTION 'version_obsoleta: los datos o la política que revisó ya no son los del plan' USING ERRCODE='40001';
  END IF;
  IF EXISTS (SELECT 1 FROM public.planes p2 WHERE p2.plan_id=pl.plan_id AND p2.version>pl.version) THEN
    RAISE EXCEPTION 'version_obsoleta: existe una versión más reciente de este plan' USING ERRCODE='40001';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.politicas_prioridad WHERE politica_version=pl.politica_version AND estado='activa') THEN
    RAISE EXCEPTION 'politica_no_activa: la política del plan no está activa' USING ERRCODE='55000';
  END IF;

  -- Las entradas (depósito, flota, incidentes, puntos, política) deben ser las del cálculo.
  SELECT * INTO esc FROM public.escenarios_planificacion_v3
   WHERE ejecucion_id=pl.ejecucion_id AND plan_id=pl.plan_id AND version=pl.version;
  IF NOT FOUND OR esc.cierre_snapshot IS NULL THEN
    RAISE EXCEPTION 'plan_no_verificado: no hay snapshot de entradas con el que comprobar la vigencia' USING ERRCODE='55000';
  END IF;
  IF public.ra_snapshot_planificacion_v3(pl.ejecucion_id) IS DISTINCT FROM esc.cierre_snapshot THEN
    RAISE EXCEPTION 'version_obsoleta: las entradas cambiaron desde el cálculo del plan' USING ERRCODE='40001';
  END IF;

  SELECT * INTO ej FROM public.ejecuciones WHERE ejecucion_id=pl.ejecucion_id FOR UPDATE;
  IF ej.estado<>'espera_validacion' OR ej.etapa<>'planificacion' THEN
    RAISE EXCEPTION 'plan_no_verificado: la ejecución no está esperando validación' USING ERRCODE='55000';
  END IF;

  IF NOT pl.verificado OR pl.estado_solver IS DISTINCT FROM 'factible' OR (pl.verificacion->>'valido') IS DISTINCT FROM 'true'
     OR jsonb_array_length(coalesce(pl.verificacion->'violaciones','[]'::jsonb))<>0 THEN
    RAISE EXCEPTION 'plan_no_verificado: el plan no tiene una verificación independiente válida' USING ERRCODE='55000';
  END IF;
  IF jsonb_path_exists(pl.no_atendidos,'$[*] ? (@.clase_prioridad == "critico")')
     OR EXISTS (SELECT 1 FROM unnest(pl.bloqueos_publicacion) b WHERE b LIKE 'Cobertura crítica%') THEN
    RAISE EXCEPTION 'cobertura_critica_pendiente: hay puntos críticos sin atender' USING ERRCODE='55000';
  END IF;

  ajenos:=ARRAY(SELECT b FROM unnest(pl.bloqueos_publicacion) b WHERE NOT (b = ANY(reconocibles)));
  IF cardinality(ajenos)>0 THEN
    RAISE EXCEPTION 'plan_no_verificado: bloqueos que una aprobación no puede levantar: %', array_to_string(ajenos,' | ') USING ERRCODE='55000';
  END IF;
  faltan:=ARRAY(SELECT b FROM unnest(pl.bloqueos_publicacion) b WHERE NOT (b = ANY(p_bloqueos_reconocidos)));
  IF cardinality(faltan)>0 THEN
    RAISE EXCEPTION 'bloqueos_sin_reconocer: falta reconocer: %', array_to_string(faltan,' | ') USING ERRCODE='22023';
  END IF;

  INSERT INTO public.aprobaciones(plan_id,version,datos_version,politica_version,usuario_id,motivo)
  VALUES (pl.plan_id,pl.version,pl.datos_version,pl.politica_version,p_usuario_id,p_motivo)
  RETURNING aprobacion_id INTO nuevo;
  -- 0001 exige cero bloqueos en un plan aprobado. Los reconocidos quedan en el evento y en planes.propuesta.
  UPDATE public.planes SET estado='aprobado', aprobacion_id=nuevo, bloqueos_publicacion='{}'
   WHERE plan_id=pl.plan_id AND version=pl.version;
  -- Entrega a Comunicación: esa etapa crea los avisos del plan aprobado.
  UPDATE public.ejecuciones SET estado='pendiente', etapa='comunicacion', trabajador_id=NULL,
         bloqueada_hasta=NULL, ultimo_error=NULL WHERE ejecucion_id=ej.ejecucion_id;
  INSERT INTO public.eventos(ejecucion_id,actor_tipo,usuario_id,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
  VALUES (ej.ejecucion_id,'coordinador',p_usuario_id,'Aprobar plan','aprobado',0,'pendiente',
    jsonb_build_object('plan_id',pl.plan_id,'version',pl.version,'aprobacion_id',nuevo,'motivo',p_motivo,
      'bloqueos_reconocidos',to_jsonb(pl.bloqueos_publicacion)),ej.origen);
  RETURN jsonb_build_object('plan_id',pl.plan_id,'version',pl.version,'aprobacion_id',nuevo,
    'estado','aprobado','ejecucion_id',pl.ejecucion_id,'repetido',false);
END $$;

-- Rechazar un plan pendiente. No crea aprobación ni avisos y deja la ejecución en revisión.
CREATE FUNCTION public.ra_rechazar_plan(p_usuario_id uuid, p_plan_id uuid, p_version integer, p_motivo text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE pl public.planes%ROWTYPE; ej public.ejecuciones%ROWTYPE;
BEGIN
  IF p_usuario_id IS NULL OR p_plan_id IS NULL OR p_version IS NULL OR p_version<1
     OR p_motivo IS NULL OR length(btrim(p_motivo)) NOT BETWEEN 1 AND 4000 THEN
    RAISE EXCEPTION 'contrato_invalido: faltan datos del rechazo o el motivo no es válido' USING ERRCODE='22023';
  END IF;
  PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'sin_permiso: solo un coordinador activo puede rechazar planes' USING ERRCODE='42501';
  END IF;
  SELECT * INTO pl FROM public.planes WHERE plan_id=p_plan_id AND version=p_version FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'contrato_invalido: el plan no existe' USING ERRCODE='22023';
  END IF;
  IF pl.estado='rechazado' THEN
    RETURN jsonb_build_object('plan_id',pl.plan_id,'version',pl.version,'estado','rechazado','repetido',true);
  END IF;
  IF pl.estado<>'pendiente_revision' THEN
    RAISE EXCEPTION 'plan_ya_resuelto: el plan está en estado %', pl.estado USING ERRCODE='55000';
  END IF;
  SELECT * INTO ej FROM public.ejecuciones WHERE ejecucion_id=pl.ejecucion_id FOR UPDATE;
  UPDATE public.planes SET estado='rechazado' WHERE plan_id=pl.plan_id AND version=pl.version;
  UPDATE public.ejecuciones SET estado='espera_revision', trabajador_id=NULL, bloqueada_hasta=NULL,
         ultimo_error=jsonb_build_object('codigo','plan_rechazado','mensaje','Un coordinador rechazó el plan; revisar el motivo en la traza.')
   WHERE ejecucion_id=ej.ejecucion_id AND estado='espera_validacion';
  INSERT INTO public.eventos(ejecucion_id,actor_tipo,usuario_id,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
  VALUES (ej.ejecucion_id,'coordinador',p_usuario_id,'Rechazar plan','rechazado',0,
    (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=ej.ejecucion_id),
    jsonb_build_object('plan_id',pl.plan_id,'version',pl.version,'motivo',p_motivo),ej.origen);
  RETURN jsonb_build_object('plan_id',pl.plan_id,'version',pl.version,'estado','rechazado','repetido',false);
END $$;

-- Vigencia posterior: si cambia una entrada de un plan ya aprobado (depósito, flota, incidente, punto
-- o política que usó el cálculo), el plan pasa a 'invalidado'. Los avisos pendientes los cancela
-- ra_reservar_aviso al ver que el plan ya no está aprobado. Solo mira planes aprobados, que son pocos.
-- SECURITY DEFINER: lo dispara quien escriba la tabla de entradas y debe poder invalidar el plan.
CREATE FUNCTION public.ra_invalidar_planes_obsoletos()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT pl.plan_id, pl.version, pl.ejecucion_id, e.origen
      FROM public.planes pl
      JOIN public.escenarios_planificacion_v3 x
        ON x.ejecucion_id=pl.ejecucion_id AND x.plan_id=pl.plan_id AND x.version=pl.version
      JOIN public.ejecuciones e ON e.ejecucion_id=pl.ejecucion_id
     WHERE pl.estado='aprobado'
       AND public.ra_snapshot_planificacion_v3(pl.ejecucion_id) IS DISTINCT FROM x.cierre_snapshot
     ORDER BY pl.plan_id, pl.version
       FOR UPDATE OF pl
  LOOP
    UPDATE public.planes SET estado='invalidado' WHERE plan_id=r.plan_id AND version=r.version;
    INSERT INTO public.eventos(ejecucion_id,actor_tipo,decision,resultado,duracion_ms,detalles,origen)
    VALUES (r.ejecucion_id,'sistema','Invalidar plan aprobado','invalidado',0,
      jsonb_build_object('plan_id',r.plan_id,'version',r.version,
        'motivo','Cambió una entrada del cálculo después de la aprobación.',
        'tabla',TG_TABLE_NAME),r.origen);
  END LOOP;
  RETURN NULL;
END $$;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['depositos','vehiculos','incidentes','puntos_atencion','politicas_prioridad'] LOOP
    EXECUTE format('CREATE TRIGGER ra_invalidar_planes AFTER INSERT OR UPDATE OR DELETE ON public.%I
                    FOR EACH STATEMENT EXECUTE FUNCTION public.ra_invalidar_planes_obsoletos()',t);
  END LOOP;
END $$;

DO $$
DECLARE f record;
BEGIN
  FOR f IN SELECT p.oid::regprocedure::text AS firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN ('ra_aprobar_plan','ra_rechazar_plan','ra_invalidar_planes_obsoletos') LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated',f.firma);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
  END LOOP;
END $$;

COMMIT;
