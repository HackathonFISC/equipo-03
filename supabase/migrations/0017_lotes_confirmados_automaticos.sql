-- Requiere 0016. Reutiliza revisiones humanas; no confirma, activa ni aprueba.
BEGIN;
CREATE TABLE public.revisiones_lote_v2 (
 evento_id uuid PRIMARY KEY REFERENCES public.eventos ON DELETE RESTRICT,
 ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
 usuario_id uuid NOT NULL REFERENCES public.usuarios_operativos ON DELETE RESTRICT,
 datos_version text NOT NULL,
 lote jsonb NOT NULL,
 ambito jsonb NOT NULL,
 creado_en timestamptz NOT NULL
);
ALTER TABLE public.revisiones_lote_v2 ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.revisiones_lote_v2 FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public.revisiones_lote_v2 TO service_role;

-- Excluir únicamente resultados derivados del cálculo y marcas de actualización.
-- Los reportes se comparan mediante huella, sin duplicar texto ciudadano.
CREATE FUNCTION public.ra_ambito_confirmaciones_v2(p_ejecucion_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT jsonb_build_object('origen',e.origen,'ensayo_id',e.ensayo_priorizacion_id,
 'puntos',(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.punto_atencion_id),'[]') FROM public.puntos_atencion p
 WHERE EXISTS(SELECT 1 FROM jsonb_array_elements(public.ra_incidentes_contexto_v2(e.ejecucion_id)) j WHERE j->>'punto_atencion_id'=p.punto_atencion_id::text)),
 'incidentes',(SELECT coalesce(jsonb_agg(j-ARRAY['evaluacion_necesidad','pendientes_calculo','actualizado_en'] ORDER BY j->>'incidente_id'),'[]')
 FROM jsonb_array_elements(public.ra_incidentes_contexto_v2(e.ejecucion_id)) j),
 'reportes',(SELECT coalesce(jsonb_agg(jsonb_build_object('incidente_id',v.incidente_id,'vinculo_id',v.vinculo_id,
 'reporte_id',r.reporte_id,'huella',md5((to_jsonb(r)-'actualizado_en')::text)) ORDER BY v.vinculo_id),'[]')
 FROM public.vinculos_reportes v JOIN public.reportes r USING(reporte_id)
 WHERE v.desvinculado_en IS NULL AND EXISTS(SELECT 1 FROM jsonb_array_elements(public.ra_incidentes_contexto_v2(e.ejecucion_id)) j
 WHERE j->>'incidente_id'=v.incidente_id::text)))
 FROM public.ejecuciones e WHERE e.ejecucion_id=p_ejecucion_id;
$$;
CREATE FUNCTION public.ra_guardar_revision_lote_v2() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE;
BEGIN
 IF NEW.decision<>'Preparar lote de priorización' OR NEW.detalles ? 'preparacion' THEN RETURN NEW; END IF;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=NEW.ejecucion_id;
 IF e.entrada_priorizacion IS NULL OR NEW.detalles->>'datos_version' IS DISTINCT FROM e.datos_version
 OR NOT EXISTS(SELECT 1 FROM public.usuarios_operativos u WHERE u.usuario_id::text=NEW.detalles->>'usuario_id' AND u.activo AND u.rol='coordinador')
 THEN RETURN NEW; END IF;
 INSERT INTO public.revisiones_lote_v2(evento_id,ejecucion_id,usuario_id,datos_version,lote,ambito,creado_en)
 VALUES(NEW.evento_id,e.ejecucion_id,(NEW.detalles->>'usuario_id')::uuid,e.datos_version,e.entrada_priorizacion,
 public.ra_ambito_confirmaciones_v2(e.ejecucion_id),clock_timestamp());
 -- Una revisión nueva permite volver a comprobar ejecuciones que esperaban datos.
 UPDATE public.ejecuciones x SET estado='pendiente',ultimo_error=NULL
 WHERE x.ejecucion_id<>e.ejecucion_id AND x.etapa='priorizacion' AND x.estado='espera_revision'
 AND x.entrada_priorizacion IS NULL AND x.ultimo_error->>'codigo'='lote_confirmaciones_pendientes'
 AND x.origen=e.origen AND x.ensayo_priorizacion_id IS NOT DISTINCT FROM e.ensayo_priorizacion_id;
 RETURN NEW;
END $$;
CREATE TRIGGER ra_guardar_revision_lote_v2 AFTER INSERT ON public.eventos
FOR EACH ROW EXECUTE FUNCTION public.ra_guardar_revision_lote_v2();

CREATE FUNCTION public.ra_contexto_lote_confirmado_v2(p_ejecucion_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT jsonb_build_object('ejecucion',to_jsonb(e),'ambito',public.ra_ambito_confirmaciones_v2(e.ejecucion_id),
 'revision',(SELECT to_jsonb(r) FROM public.revisiones_lote_v2 r
 WHERE r.ambito->>'origen'=e.origen::text
 AND r.ambito->'ensayo_id' IS NOT DISTINCT FROM coalesce(to_jsonb(e.ensayo_priorizacion_id),'null'::jsonb)
 AND (SELECT jsonb_agg(j->>'incidente_id' ORDER BY j->>'incidente_id') FROM jsonb_array_elements(r.ambito->'incidentes') j)
 IS NOT DISTINCT FROM (SELECT jsonb_agg(j->>'incidente_id' ORDER BY j->>'incidente_id') FROM jsonb_array_elements(public.ra_incidentes_contexto_v2(e.ejecucion_id)) j)
 ORDER BY r.creado_en DESC,r.evento_id DESC LIMIT 1),
 'politica',(SELECT to_jsonb(p)-ARRAY['creado_en','creado_por'] FROM public.politicas_prioridad p
 WHERE p.politica_version='oeste-prioridad-apoyo-pa-1'),
 'coordinadores',(SELECT coalesce(jsonb_agg(u.usuario_id ORDER BY u.usuario_id),'[]') FROM public.usuarios_operativos u WHERE activo AND rol='coordinador'))
 FROM public.ejecuciones e WHERE e.ejecucion_id=p_ejecucion_id;
$$;

CREATE FUNCTION public.ra_motivo_lote_confirmado_v2(s jsonb)
RETURNS text LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path='' AS $$
DECLARE f jsonb; n jsonb; d jsonb; c jsonb; i jsonb;
BEGIN
 IF s->'revision' IS NULL OR s->'revision'='null'::jsonb THEN RETURN 'Falta revisión humana registrada del ámbito completo.'; END IF;
 IF s->'ambito' IS DISTINCT FROM s->'revision'->'ambito' THEN RETURN 'Cambiaron incidentes, reportes, vínculos o versiones; revisar los datos.'; END IF;
 IF s->'politica'->>'estado' IS DISTINCT FROM 'activa'
 OR NOT (s->'politica' @> ((s->'revision'->'lote'->'politica')-'esquema_version'))
 THEN RETURN 'La política elegida no está activa o cambió desde la revisión.'; END IF;
 IF NOT (s->'coordinadores' @> jsonb_build_array(s->'revision'->>'usuario_id')) THEN RETURN 'El coordinador de la revisión ya no está activo.'; END IF;
 IF jsonb_array_length(s->'ambito'->'incidentes')=0
 OR jsonb_array_length(s->'ambito'->'incidentes')<>jsonb_array_length(s->'revision'->'lote'->'entradas')
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(s->'ambito'->'incidentes') j GROUP BY j->>'punto_atencion_id' HAVING count(*)>1)
 THEN RETURN 'Ámbito incompleto o varios incidentes por punto; requiere consolidación.'; END IF;
 FOR i IN SELECT value FROM jsonb_array_elements(s->'ambito'->'incidentes') LOOP
  IF i->>'estado_validacion' IS DISTINCT FROM 'validada' OR i->>'punto_atencion_id' IS NULL OR i->'conflictos'<>'[]'::jsonb OR i->'faltantes'<>'[]'::jsonb
  OR coalesce((i->>'requiere_revision_urgente')::boolean,false)
  THEN RETURN 'Hay ubicación pendiente, faltantes, conflictos o una revisión urgente.'; END IF;
  SELECT value INTO f FROM jsonb_array_elements(s->'revision'->'lote'->'entradas') j
  WHERE j->'solicitud_demanda'->>'incidente_id'=i->>'incidente_id';
  n:=f->'evaluacion';d:=f->'solicitud_demanda'->'demanda';
  IF f IS NULL OR f->>'version_incidente' IS DISTINCT FROM i->>'version'
  OR f->'solicitud_demanda'->>'punto_atencion_id' IS DISTINCT FROM i->>'punto_atencion_id'
  OR n->>'incidente_id' IS DISTINCT FROM i->>'incidente_id'
  OR n->>'punto_atencion_id' IS DISTINCT FROM i->>'punto_atencion_id'
  OR n->>'origen' IS DISTINCT FROM i->>'origen'
  OR n->>'politica_version' IS DISTINCT FROM s->'politica'->>'politica_version'
  OR f->'solicitud_demanda'->>'origen' IS DISTINCT FROM i->>'origen'
  OR (n->>'primera_deteccion_en')::timestamptz IS DISTINCT FROM (i->>'primera_deteccion_en')::timestamptz
  THEN RETURN 'La revisión no corresponde a la identidad o versión vigente.'; END IF;
  IF coalesce((n->>'requiere_revision_urgente')::boolean,false) OR n->>'clase_prioridad' IS NULL OR n->>'vulnerabilidad' IS NULL OR n->>'horas_sin_agua' IS NULL
  OR n->>'personas_atendidas' IS NULL OR f->'solicitud_demanda'->>'capacidad_recepcion_litros' IS NULL
  OR n->'ventana_atencion'->>'fin' IS NULL OR (n->'ventana_atencion'->>'fin')::timestamptz<=statement_timestamp()
  OR coalesce(jsonb_array_length(f->'pendientes'),0)>0
  OR (d->>'metodo'='directa' AND d->>'litros_declarados' IS NULL)
  OR (d->>'metodo'='formula' AND (d->>'personas_atendidas' IS NULL OR d->>'dotacion_litros_persona_dia' IS NULL OR d->>'dias_cobertura' IS NULL OR d->>'reserva_utilizable_litros' IS NULL))
  THEN RETURN 'Faltan datos confirmados o venció la ventana de atención.'; END IF;
  FOR c IN SELECT value FROM jsonb_array_elements(jsonb_build_array(s->'politica'->'confirmacion_activacion',d->'confirmacion',n->'confirmacion_demanda',n->'confirmacion_clase',n->'confirmacion_vulnerabilidad')) LOOP
   IF c IS NULL OR c='null'::jsonb OR c->>'usuario_id' IS NULL OR c->>'confirmado_en' IS NULL
   OR nullif(btrim(c->>'motivo'),'') IS NULL OR NOT(s->'coordinadores' @> jsonb_build_array(c->>'usuario_id'))
   OR (c->>'confirmado_en')::timestamptz>statement_timestamp()
   THEN RETURN 'Falta una confirmación vigente de coordinador activo.'; END IF;
  END LOOP;
 END LOOP;
 RETURN NULL;
END $$;

CREATE FUNCTION public.ra_registrar_lote_confirmado_v2(p_ejecucion_id uuid,p_snapshot jsonb,p_lote jsonb,p_motivo text DEFAULT NULL)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; s jsonb; motivo text; esperado jsonb; entradas jsonb; dv text;
BEGIN
 PERFORM public.ra_bloqueo_v4();
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.etapa<>'priorizacion' OR e.estado NOT IN ('pendiente','espera_revision','espera_validacion')
 THEN RETURN jsonb_build_object('estado','no_disponible'); END IF;
 -- Una repetición no modifica reserva, auditoría ni resultados.
 IF e.entrada_priorizacion IS NOT NULL THEN RETURN jsonb_build_object('estado','existente'); END IF;
 LOCK TABLE public.incidentes,public.vinculos_reportes,public.reportes IN SHARE ROW EXCLUSIVE MODE;
 LOCK TABLE public.usuarios_operativos,public.politicas_prioridad IN SHARE MODE;
 s:=public.ra_contexto_lote_confirmado_v2(e.ejecucion_id);
 IF s IS DISTINCT FROM p_snapshot THEN RAISE EXCEPTION 'Contexto cambió durante preparación automática' USING ERRCODE='40001'; END IF;
 motivo:=coalesce(public.ra_motivo_lote_confirmado_v2(s),p_motivo);
 IF motivo IS NOT NULL THEN
  UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo','lote_confirmaciones_pendientes','mensaje',motivo)
  WHERE ejecucion_id=e.ejecucion_id;
  PERFORM public.ra_evento_v2(e.ejecucion_id,'priorizacion','Solicitar revisión por faltantes o cambios',jsonb_build_object('motivo',motivo));
  RETURN jsonb_build_object('estado','requiere_revision','ejecucion_id',e.ejecucion_id,'motivo',motivo);
 END IF;
 dv:='auto-'||md5(e.ejecucion_id::text||(s->'revision'->>'evento_id'));
 SELECT jsonb_agg(jsonb_set(jsonb_set(f,'{solicitud_demanda}',(f->'solicitud_demanda')||jsonb_build_object('ejecucion_id',e.ejecucion_id,'datos_version',dv,'creado_en',e.creado_en)),
 '{evaluacion}',(f->'evaluacion')||jsonb_build_object('ejecucion_id',e.ejecucion_id,'datos_version',dv,'creado_en',e.creado_en)) ORDER BY ord)
 INTO entradas FROM jsonb_array_elements(s->'revision'->'lote'->'entradas') WITH ORDINALITY j(f,ord);
 esperado:=jsonb_set(s->'revision'->'lote','{entradas}',entradas);
 IF p_lote IS DISTINCT FROM esperado THEN RAISE EXCEPTION 'No sustituir datos ni confirmaciones revisadas' USING ERRCODE='22023'; END IF;
 UPDATE public.ejecuciones SET entrada_priorizacion=esperado,datos_version=dv,estado='pendiente',ultimo_error=NULL WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Preparar lote de priorización',jsonb_build_object('usuario_id',s->'revision'->>'usuario_id',
 'datos_version',dv,'preparacion','automatica','revision_evento_id',s->'revision'->>'evento_id','revision_ejecucion_id',s->'revision'->>'ejecucion_id',
 'nota','Reutilización de confirmaciones existentes; no es una nueva revisión ni aprobación humana.'));
 RETURN jsonb_build_object('estado','preparado','ejecucion_id',e.ejecucion_id,'datos_version',dv);
END $$;
-- Dar una vuelta al nuevo preparador en esperas antiguas sin lote.
UPDATE public.ejecuciones SET estado='pendiente' WHERE etapa='priorizacion' AND estado='espera_validacion'
AND entrada_priorizacion IS NULL AND ultimo_error->>'codigo'='datos_calculo_pendientes';
-- Las revisiones anteriores a 0017 requieren una nueva preparación humana para
-- capturar una instantánea confiable. No reconstruir ni inventar su vigencia.
REVOKE ALL ON FUNCTION public.ra_ambito_confirmaciones_v2(uuid),public.ra_guardar_revision_lote_v2(),public.ra_contexto_lote_confirmado_v2(uuid),public.ra_motivo_lote_confirmado_v2(jsonb),public.ra_registrar_lote_confirmado_v2(uuid,jsonb,jsonb,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_ambito_confirmaciones_v2(uuid),public.ra_guardar_revision_lote_v2(),public.ra_contexto_lote_confirmado_v2(uuid),public.ra_motivo_lote_confirmado_v2(jsonb),public.ra_registrar_lote_confirmado_v2(uuid,jsonb,jsonb,text) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
