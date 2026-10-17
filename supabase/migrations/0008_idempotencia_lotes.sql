-- Corrección acotada de idempotencia. Requiere 0007. Ejecutar el archivo completo.
BEGIN;

-- Solo se omiten las fechas regeneradas al serializar. Se conservan actor,
-- motivo, cifras, versiones y todos los otros datos; no se altera la entrada guardada.
CREATE FUNCTION public.ra_lote_comparable_v2(p_lote jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path='' AS $$
DECLARE fila jsonb; solicitud jsonb; evaluacion jsonb; entradas jsonb:='[]'; campo text;
BEGIN
 IF p_lote IS NULL THEN RETURN NULL; END IF;
 IF jsonb_typeof(p_lote->'entradas') IS DISTINCT FROM 'array' THEN RETURN p_lote; END IF;
 FOR fila IN SELECT value FROM jsonb_array_elements(p_lote->'entradas')
  ORDER BY value->'solicitud_demanda'->>'incidente_id' LOOP
  solicitud:=(fila->'solicitud_demanda')-'creado_en';
  evaluacion:=(fila->'evaluacion')-'creado_en';
  IF jsonb_typeof(solicitud->'demanda'->'confirmacion')='object' THEN
   solicitud:=jsonb_set(solicitud,'{demanda,confirmacion}',(solicitud->'demanda'->'confirmacion')-'confirmado_en');
  END IF;
  FOREACH campo IN ARRAY ARRAY['confirmacion_demanda','confirmacion_clase','confirmacion_vulnerabilidad'] LOOP
   IF jsonb_typeof(evaluacion->campo)='object' THEN
    evaluacion:=jsonb_set(evaluacion,ARRAY[campo],(evaluacion->campo)-'confirmado_en');
   END IF;
  END LOOP;
  entradas:=entradas||jsonb_build_array(fila||jsonb_build_object('solicitud_demanda',solicitud,'evaluacion',evaluacion));
 END LOOP;
 RETURN jsonb_set(p_lote,'{entradas}',entradas);
END $$;
REVOKE ALL ON FUNCTION public.ra_lote_comparable_v2(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_lote_comparable_v2(jsonb) TO service_role;

CREATE OR REPLACE FUNCTION public.ra_preparar_priorizacion_v2(p_ejecucion_id uuid,p_usuario_id uuid,p_lote jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; fila jsonb; i public.incidentes%ROWTYPE; version_datos text; politica public.politicas_prioridad%ROWTYPE; repetido boolean;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo) THEN RAISE EXCEPTION 'Sin permiso de coordinador' USING ERRCODE='42501'; END IF;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.etapa<>'priorizacion' OR e.estado NOT IN ('pendiente','ejecutando','espera_validacion','espera_revision') THEN RAISE EXCEPTION 'Ejecución no disponible para preparar cálculo' USING ERRCODE='55000'; END IF;
 LOCK TABLE public.incidentes,public.vinculos_reportes IN SHARE ROW EXCLUSIVE MODE;
 IF jsonb_typeof(p_lote->'entradas') IS DISTINCT FROM 'array' OR jsonb_array_length(p_lote->'entradas')=0 THEN RAISE EXCEPTION 'Lote vacío' USING ERRCODE='22023'; END IF;
 SELECT * INTO politica FROM public.politicas_prioridad WHERE politica_version=p_lote->'politica'->>'politica_version' FOR SHARE;
 IF NOT FOUND OR politica.estado<>'activa' OR NOT (to_jsonb(politica) @> (p_lote->'politica')) THEN RAISE EXCEPTION 'Política sin activar o diferente de la registrada' USING ERRCODE='55000'; END IF;
 version_datos:=p_lote->'entradas'->0->'solicitud_demanda'->>'datos_version';
 IF version_datos IS NULL OR length(btrim(version_datos))=0 THEN RAISE EXCEPTION 'Falta datos_version' USING ERRCODE='22023'; END IF;
 repetido:=e.entrada_priorizacion IS NOT NULL AND public.ra_lote_comparable_v2(e.entrada_priorizacion)=public.ra_lote_comparable_v2(p_lote);
 IF e.estado='ejecutando' AND NOT repetido THEN RAISE EXCEPTION 'Hay un cálculo en curso; no se puede sustituir su lote' USING ERRCODE='55000'; END IF;
 IF e.entrada_priorizacion IS NOT NULL AND NOT repetido AND version_datos=e.entrada_priorizacion->'entradas'->0->'solicitud_demanda'->>'datos_version' THEN RAISE EXCEPTION 'Cambiar datos_version al modificar un lote' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_lote->'entradas') f GROUP BY f->'solicitud_demanda'->>'punto_atencion_id' HAVING count(*)>1)
  OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_lote->'entradas') f GROUP BY f->'solicitud_demanda'->>'incidente_id' HAVING count(*)>1) THEN RAISE EXCEPTION 'Consolidar un incidente por punto en el lote; sin omitir episodios pendientes' USING ERRCODE='22023'; END IF;
 FOR fila IN SELECT value FROM jsonb_array_elements(p_lote->'entradas') LOOP
  SELECT * INTO i FROM public.incidentes WHERE incidente_id=(fila->'solicitud_demanda'->>'incidente_id')::uuid;
  IF NOT FOUND OR i.origen<>e.origen OR i.punto_atencion_id::text IS DISTINCT FROM fila->'solicitud_demanda'->>'punto_atencion_id'
    OR i.version IS DISTINCT FROM (fila->>'version_incidente')::integer OR version_datos IS DISTINCT FROM fila->'solicitud_demanda'->>'datos_version'
    OR NOT EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i.incidente_id AND v.desvinculado_en IS NULL) THEN RAISE EXCEPTION 'Lote con identidad, versión u origen incompatible' USING ERRCODE='22023'; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM public.incidentes i0 WHERE EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i0.incidente_id AND v.desvinculado_en IS NULL)
   AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_lote->'entradas') f WHERE f->'solicitud_demanda'->>'incidente_id'=i0.incidente_id::text)) THEN RAISE EXCEPTION 'Faltan incidentes activos en el lote' USING ERRCODE='22023'; END IF;
 -- Las guardas anteriores siguen vigentes: una repetición obsoleta no elude validación.
 -- No tocar auditoría, errores, reserva ni estado, aunque todavía no haya necesidades.
 IF repetido THEN RETURN jsonb_build_object('estado',e.estado,'etapa',e.etapa,'ejecucion_id',e.ejecucion_id,'repetido',true); END IF;
 UPDATE public.ejecuciones SET entrada_priorizacion=p_lote,estado='pendiente',trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=NULL,datos_version=version_datos WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Preparar lote de priorización',jsonb_build_object('usuario_id',p_usuario_id,'datos_version',version_datos));
 RETURN jsonb_build_object('estado','pendiente','etapa','priorizacion','ejecucion_id',e.ejecucion_id);
END $$;

COMMIT;
