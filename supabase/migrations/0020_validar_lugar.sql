-- Noel: validación humana del lugar de un incidente, con evidencia, versión y auditoría.
-- Requiere 0001, 0007 y 0012 (usa su bloqueo común) y la semilla 01 para probarla.
-- Territorial deja el incidente con estado_validacion='pendiente' y el faltante
-- «Validación operativa del lugar y de la necesidad». El formulario de cantidades no lo quita.
-- Esta RPC es la única acción que lo resuelve: la hace un coordinador activo y autenticado,
-- sobre una versión concreta del incidente, con evidencia escrita, y deja un evento de auditoría.
-- Quita SOLO ese faltante; no toca conflictos, otros faltantes, cantidades ni necesidades,
-- y no valida el punto del catálogo ni acredita entrega o recepción física.
-- Solo service_role ejecuta la RPC; la API pasa el usuario del token verificado, nunca uno del navegador.
-- Los errores empiezan por el código de dominio (como 0003).
-- No envía nada, no aprueba planes y no se llama desde texto de Telegram.
BEGIN;

CREATE OR REPLACE FUNCTION public.ra_validar_lugar_v1(
  p_usuario_id uuid, p_incidente_id uuid, p_version integer, p_evidencia text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE
  i public.incidentes%ROWTYPE; p public.puntos_atencion%ROWTYPE; ev text; nuevos text[]; estado_ej public.ra_estado_ejecucion;
  marcador CONSTANT text := 'Validación operativa del lugar y de la necesidad';
BEGIN
  -- Primera operación: serializa con quien cambie entradas (mismo orden que 0003 y 0012).
  PERFORM public.ra_bloqueo_v4();
  PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'sin_permiso: Solo un coordinador activo puede validar un lugar' USING ERRCODE='42501'; END IF;
  ev := btrim(coalesce(p_evidencia,''));
  IF length(ev) < 10 OR length(ev) > 2000 THEN
    RAISE EXCEPTION 'contrato_invalido: La evidencia debe tener entre 10 y 2000 caracteres' USING ERRCODE='22023';
  END IF;
  IF p_version IS NULL OR p_version < 1 THEN
    RAISE EXCEPTION 'contrato_invalido: Falta la versión del incidente' USING ERRCODE='22023';
  END IF;
  SELECT * INTO i FROM public.incidentes WHERE incidente_id=p_incidente_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'contrato_invalido: El incidente no existe' USING ERRCODE='22023'; END IF;
  IF i.version <> p_version THEN
    RAISE EXCEPTION 'version_obsoleta: El incidente cambió desde que lo revisó' USING ERRCODE='40001';
  END IF;
  IF i.estado_validacion <> 'pendiente' THEN
    RAISE EXCEPTION 'lugar_ya_resuelto: El lugar de este incidente ya está %', i.estado_validacion USING ERRCODE='55000';
  END IF;
  IF i.punto_atencion_id IS NULL OR i.sector_id IS NULL OR i.ubicacion IS NULL THEN
    RAISE EXCEPTION 'lugar_sin_punto: El incidente no tiene un punto de atención con ubicación para validar' USING ERRCODE='22023';
  END IF;
  SELECT * INTO p FROM public.puntos_atencion WHERE punto_atencion_id=i.punto_atencion_id AND sector_id=i.sector_id AND activo;
  IF NOT FOUND THEN RAISE EXCEPTION 'lugar_sin_punto: El punto de atención del incidente ya no está activo' USING ERRCODE='22023'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.vinculos_reportes WHERE incidente_id=i.incidente_id AND desvinculado_en IS NULL) THEN
    RAISE EXCEPTION 'lugar_sin_punto: El incidente no tiene reportes vinculados' USING ERRCODE='22023';
  END IF;

  nuevos := array_remove(i.faltantes, marcador);
  UPDATE public.incidentes
     SET estado_validacion='validada', faltantes=nuevos, version=version+1, actualizado_en=clock_timestamp()
   WHERE incidente_id=i.incidente_id;

  SELECT estado INTO estado_ej FROM public.ejecuciones WHERE ejecucion_id=i.ejecucion_id;
  INSERT INTO public.eventos(ejecucion_id,actor_tipo,usuario_id,decision,entrada_ids,salida_ids,resultado,duracion_ms,siguiente_estado,detalles,origen)
  VALUES (i.ejecucion_id,'coordinador',p_usuario_id,'Validar lugar del incidente',ARRAY[i.incidente_id],ARRAY[]::uuid[],'validada',0,estado_ej,
    jsonb_build_object('incidente_id',i.incidente_id,'version_anterior',i.version,'version_nueva',i.version+1,
      'punto_atencion_id',p.punto_atencion_id,'punto',p.nombre,'ubicacion',i.ubicacion,
      'evidencia',ev,'faltante_resuelto',marcador,'faltantes_restantes',to_jsonb(nuevos)),i.origen);

  RETURN jsonb_build_object('incidente_id',i.incidente_id,'version',i.version+1,'estado_validacion','validada',
    'faltantes',to_jsonb(nuevos));
END $$;

DO $$
DECLARE f record;
BEGIN
  FOR f IN SELECT p.oid::regprocedure::text AS firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname='ra_validar_lugar_v1' LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated',f.firma);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
  END LOOP;
END $$;

COMMIT;
