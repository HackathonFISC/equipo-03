-- Emilia V2. Requiere 0006. No llama Gemini, bot ni herramientas de cálculo.
BEGIN;
ALTER TABLE public.incidentes
 ADD COLUMN tipo_problema text NOT NULL DEFAULT 'desconocido' CHECK(tipo_problema IN ('sin_suministro','intermitencia','otro','desconocido')),
 ADD COLUMN episodio_establecido boolean NOT NULL DEFAULT false,
 ADD COLUMN evaluacion_necesidad jsonb,
 ADD COLUMN pendientes_calculo text[] NOT NULL DEFAULT ARRAY['Sin evaluación de necesidad'];
ALTER TABLE public.ejecuciones ADD COLUMN entrada_priorizacion jsonb;

CREATE FUNCTION public.ra_evento_v2(p_ejecucion_id uuid,p_agente public.ra_agente,p_decision text,p_detalles jsonb DEFAULT '{}')
RETURNS void LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
 INSERT INTO public.eventos(ejecucion_id,agente,actor_tipo,decision,herramienta,resultado,duracion_ms,siguiente_estado,detalles,origen)
 SELECT ejecucion_id,p_agente,'agente',p_decision,'herramientas_v2',p_decision,0,estado,p_detalles,origen FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id;
$$;

CREATE FUNCTION public.ra_catalogo_v2()
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.punto_atencion_id),'[]') FROM (
  SELECT p.*,s.distrito,s.corregimiento FROM public.puntos_atencion p JOIN public.sectores s USING(sector_id) WHERE p.activo
 ) c;
$$;
CREATE FUNCTION public.ra_incidentes_snapshot_v2()
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT coalesce(jsonb_agg(to_jsonb(i) ORDER BY i.incidente_id),'[]') FROM public.incidentes i
 WHERE EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i.incidente_id AND v.desvinculado_en IS NULL);
$$;

CREATE FUNCTION public.ra_tomar_etapa_v2(p_ejecucion_id uuid,p_trabajador_id text,p_etapa text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE;
BEGIN
 IF p_etapa IS NULL OR p_etapa NOT IN ('territorial','priorizacion') OR p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN
  RAISE EXCEPTION 'Etapa o trabajador inválido' USING ERRCODE='22023'; END IF;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'pendiente' OR e.etapa<>p_etapa THEN RETURN NULL; END IF;
 SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id FOR SHARE;
 IF NOT FOUND OR r.interpretacion IS NULL THEN RAISE EXCEPTION 'Falta interpretación' USING ERRCODE='55000'; END IF;
 UPDATE public.ejecuciones SET estado='ejecutando',trabajador_id=p_trabajador_id,bloqueada_hasta=clock_timestamp()+interval '180 seconds',intentos=intentos+1,ultimo_error=NULL
 WHERE ejecucion_id=e.ejecucion_id RETURNING * INTO e;
 RETURN jsonb_build_object('ejecucion',to_jsonb(e),'reporte',to_jsonb(r),
  'catalogo',public.ra_catalogo_v2(),
  'aclaraciones',coalesce((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.respondida_en,a.aclaracion_id) FROM public.aclaraciones a WHERE a.ejecucion_id=e.ejecucion_id AND a.respondida_en IS NOT NULL),'[]'),
  'incidentes',public.ra_incidentes_snapshot_v2(),'lote_calculo',e.entrada_priorizacion);
END $$;

CREATE FUNCTION public.ra_finalizar_territorial(p_ejecucion_id uuid,p_trabajador_id text,p_snapshot jsonb,p_resolucion jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; r public.reportes%ROWTYPE; p public.puntos_atencion%ROWTYPE;
 i public.incidentes%ROWTYPE; iid uuid; n integer; candidatos uuid[]; inicio timestamptz; fin timestamptz;
 horas numeric; establecido boolean; problema text; conflictos_nuevos text[]; estado text;
BEGIN
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'ejecutando' OR e.etapa<>'territorial' OR e.trabajador_id IS DISTINCT FROM p_trabajador_id OR e.bloqueada_hasta IS NULL OR e.bloqueada_hasta<=clock_timestamp() THEN
  RAISE EXCEPTION 'Reserva territorial inválida' USING ERRCODE='55000'; END IF;
 LOCK TABLE public.incidentes,public.vinculos_reportes IN SHARE ROW EXCLUSIVE MODE;
 LOCK TABLE public.puntos_atencion,public.sectores IN SHARE MODE;
 SELECT * INTO r FROM public.reportes WHERE reporte_id=e.reporte_id FOR UPDATE;
 IF to_jsonb(r) IS DISTINCT FROM p_snapshot->'reporte' OR public.ra_catalogo_v2() IS DISTINCT FROM p_snapshot->'catalogo' THEN
  RAISE EXCEPTION 'Reporte o catálogo cambió' USING ERRCODE='40001'; END IF;
 estado:=p_resolucion->>'estado';
 IF estado IN ('ambigua','desconocida') THEN
  UPDATE public.ejecuciones SET estado='espera_aclaracion',trabajador_id=NULL,bloqueada_hasta=NULL WHERE ejecucion_id=e.ejecucion_id;
  PERFORM public.ra_crear_aclaracion(e.ejecucion_id,ARRAY['ubicacion'],
   '¿A qué instalación o lugar exacto corresponde el reporte? Indica una referencia precisa o responde a este mensaje con una ubicación estática. No envíes ubicación en vivo.');
 ELSIF estado='revision' THEN
  UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
   ultimo_error=jsonb_build_object('codigo','ubicacion_pendiente_revision','mensaje',p_resolucion->>'motivo') WHERE ejecucion_id=e.ejecucion_id;
 ELSIF estado='resuelta' THEN
  SELECT * INTO p FROM public.puntos_atencion WHERE punto_atencion_id=(p_resolucion->>'punto_atencion_id')::uuid AND activo FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Punto no disponible' USING ERRCODE='22023'; END IF;
  -- Serializar consolidación por punto. No agrupar por cercanía ni por cantidad de mensajes.
  PERFORM pg_advisory_xact_lock(hashtextextended(p.punto_atencion_id::text,0));
  horas:=(r.interpretacion->'campos'->>'horas_sin_agua')::numeric;
  establecido:=horas IS NOT NULL;
  inicio:=r.creado_en-coalesce(horas,0)*interval '1 hour'; fin:=r.creado_en+interval '1 microsecond';
  problema:=r.interpretacion->'campos'->>'tipo_problema';
  SELECT incidente_id INTO iid FROM public.vinculos_reportes WHERE reporte_id=r.reporte_id AND desvinculado_en IS NULL;
  IF iid IS NULL THEN
   SELECT array_agg(i0.incidente_id) INTO candidatos FROM public.incidentes i0
   WHERE i0.punto_atencion_id=p.punto_atencion_id AND i0.origen=r.origen AND i0.tipo_problema=problema AND problema<>'desconocido'
    AND establecido AND i0.episodio_establecido AND i0.periodo_inicio<fin AND inicio<i0.periodo_fin
    AND EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i0.incidente_id AND v.desvinculado_en IS NULL)
    AND NOT EXISTS(SELECT 1 FROM public.confirmaciones_entrega c JOIN public.paradas pa USING(parada_id)
     WHERE pa.incidente_id=i0.incidente_id AND c.atendida_en>=i0.periodo_inicio AND c.atendida_en<=r.creado_en);
   IF cardinality(candidatos)=1 THEN iid:=candidatos[1];
   ELSE
    INSERT INTO public.incidentes(ejecucion_id,sector_id,punto_atencion_id,ubicacion,periodo_inicio,periodo_fin,primera_deteccion_en,origen,tipo_problema,episodio_establecido,conflictos,faltantes,motivo)
    VALUES(e.ejecucion_id,p.sector_id,p.punto_atencion_id,
     CASE WHEN p.latitud IS NULL THEN NULL ELSE jsonb_build_object('latitud',p.latitud,'longitud',p.longitud,'fuente',p.fuente_ubicacion,'precision_metros',p.precision_metros,'representa_punto_atencion',p.representa_punto_atencion) END,
     inicio,fin,r.creado_en,r.origen,problema,establecido,
     CASE WHEN cardinality(candidatos)>1 THEN ARRAY['Varios episodios compatibles; revisar asociación'] ELSE ARRAY[]::text[] END,
     ARRAY['Validación operativa del lugar y de la necesidad'], 'Asociación documental; no acredita descarga ni demanda') RETURNING incidente_id INTO iid;
   END IF;
   INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo) VALUES(iid,r.reporte_id,'Mismo punto, origen, tipo y solapamiento documentado; sin inferir cantidades');
  END IF;
  SELECT * INTO i FROM public.incidentes WHERE incidente_id=iid FOR UPDATE;
  IF i.punto_atencion_id<>p.punto_atencion_id THEN RAISE EXCEPTION 'Reporte ya vinculado a otro punto; corregir asociación' USING ERRCODE='55000'; END IF;
  SELECT count(DISTINCT rr.remitente_ref) INTO n FROM public.vinculos_reportes v JOIN public.reportes rr USING(reporte_id) WHERE v.incidente_id=iid AND v.desvinculado_en IS NULL;
  conflictos_nuevos:=i.conflictos;
  IF (SELECT count(DISTINCT rr.interpretacion->'campos'->>'personas_afectadas') FROM public.vinculos_reportes v JOIN public.reportes rr USING(reporte_id) WHERE v.incidente_id=iid AND v.desvinculado_en IS NULL)>1 THEN
   IF NOT ('Población declarada discrepante'=ANY(conflictos_nuevos)) THEN conflictos_nuevos:=array_append(conflictos_nuevos,'Población declarada discrepante'); END IF;
  END IF;
  UPDATE public.incidentes SET reportes_independientes=n,version=version+1,periodo_inicio=least(periodo_inicio,inicio),periodo_fin=greatest(periodo_fin,fin),
   primera_deteccion_en=least(primera_deteccion_en,r.creado_en),conflictos=conflictos_nuevos,
   evaluacion_necesidad=NULL,pendientes_calculo=ARRAY['Revisar entrada consolidada, confirmaciones y política'],
   requiere_revision_urgente=requiere_revision_urgente OR coalesce(r.interpretacion->'campos'->>'institucion_declarada','') ~* '(hospital|centro de salud)' WHERE incidente_id=iid;
  -- Invalidar rankings derivados: un lote nuevo exige recalcular, conservando la traza previa.
  UPDATE public.incidentes SET evaluacion_necesidad=NULL,pendientes_calculo=ARRAY['Lote cambió; recalcular prioridad'] WHERE evaluacion_necesidad IS NOT NULL;
  UPDATE public.necesidades SET estado_prioridad='pendiente',puntaje=NULL,componentes=NULL,posicion=NULL,pendientes=ARRAY['Lote cambió; recalcular prioridad'] WHERE estado_prioridad='calculada';
  UPDATE public.ejecuciones SET estado='pendiente',etapa='priorizacion',trabajador_id=NULL,bloqueada_hasta=NULL WHERE ejecucion_id=e.ejecucion_id;
 ELSE RAISE EXCEPTION 'Resolución inválida' USING ERRCODE='22023'; END IF;
 PERFORM public.ra_evento_v2(e.ejecucion_id,'territorial',coalesce(p_resolucion->>'motivo','Resolver ubicación'),p_resolucion||jsonb_build_object('incidente_id',iid));
 RETURN (SELECT jsonb_build_object('estado',e0.estado,'etapa',e0.etapa,'ejecucion_id',e0.ejecucion_id,'incidente_id',iid) FROM public.ejecuciones e0 WHERE e0.ejecucion_id=e.ejecucion_id);
END $$;

CREATE FUNCTION public.ra_finalizar_priorizacion_v2(p_ejecucion_id uuid,p_trabajador_id text,p_snapshot jsonb,p_resultado jsonb,p_pendientes text[],p_validaciones jsonb DEFAULT '{}')
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; ev jsonb; fila jsonb; validacion jsonb; i public.incidentes%ROWTYPE; politica public.politicas_prioridad%ROWTYPE; calculada boolean:=false;
BEGIN
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'ejecutando' OR e.etapa<>'priorizacion' OR e.trabajador_id IS DISTINCT FROM p_trabajador_id OR e.bloqueada_hasta IS NULL OR e.bloqueada_hasta<=clock_timestamp() THEN RAISE EXCEPTION 'Reserva de prioridad inválida' USING ERRCODE='55000'; END IF;
 -- Todas las mutaciones de lote comparten este bloqueo de tablas; snapshot no puede cambiar tras compararlo.
 LOCK TABLE public.incidentes,public.vinculos_reportes IN SHARE ROW EXCLUSIVE MODE;
 IF public.ra_incidentes_snapshot_v2() IS DISTINCT FROM p_snapshot->'incidentes' OR e.entrada_priorizacion IS DISTINCT FROM nullif(p_snapshot->'lote_calculo','null'::jsonb) THEN
  RAISE EXCEPTION 'Lote cambió durante cálculo' USING ERRCODE='40001'; END IF;
 IF p_resultado IS NULL THEN
  IF coalesce(cardinality(p_pendientes),0)=0 THEN RAISE EXCEPTION 'Pendiente necesita motivo' USING ERRCODE='22023'; END IF;
  UPDATE public.incidentes SET pendientes_calculo=p_pendientes WHERE incidente_id IN (SELECT incidente_id FROM public.vinculos_reportes WHERE reporte_id=e.reporte_id AND desvinculado_en IS NULL);
 ELSE
  IF p_resultado->>'ejecucion_id' IS DISTINCT FROM e.ejecucion_id::text OR p_resultado->>'origen' IS DISTINCT FROM e.origen::text OR jsonb_typeof(p_resultado->'evaluaciones') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Resultado incompatible' USING ERRCODE='22023'; END IF;
  SELECT * INTO politica FROM public.politicas_prioridad WHERE politica_version=p_resultado->>'politica_version' FOR SHARE;
  IF NOT FOUND OR politica.estado<>'activa' OR NOT (to_jsonb(politica) @> ((e.entrada_priorizacion->'politica')-'esquema_version')) THEN RAISE EXCEPTION 'Política no activa o modificada' USING ERRCODE='55000'; END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_resultado->'evaluaciones') v GROUP BY v->>'punto_atencion_id' HAVING count(*)>1) THEN RAISE EXCEPTION 'Puntos duplicados' USING ERRCODE='22023'; END IF;
  -- Exigir el lote completo, incluidos pendientes. No publicar posiciones calculadas de un subconjunto.
  IF EXISTS(SELECT 1 FROM public.incidentes i0 WHERE EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i0.incidente_id AND v.desvinculado_en IS NULL)
    AND NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_resultado->'evaluaciones') v WHERE v->>'incidente_id'=i0.incidente_id::text)) THEN RAISE EXCEPTION 'Ranking incompleto; faltan incidentes activos' USING ERRCODE='22023'; END IF;
  FOR ev IN SELECT value FROM jsonb_array_elements(p_resultado->'evaluaciones') LOOP
   SELECT * INTO i FROM public.incidentes WHERE incidente_id=(ev->>'incidente_id')::uuid;
   IF NOT FOUND OR i.punto_atencion_id::text IS DISTINCT FROM ev->>'punto_atencion_id' OR i.origen<>e.origen OR ev->>'datos_version' IS DISTINCT FROM p_resultado->>'datos_version' OR (ev->>'primera_deteccion_en')::timestamptz IS DISTINCT FROM i.primera_deteccion_en THEN RAISE EXCEPTION 'Identidad o versión de evaluación incompatible' USING ERRCODE='22023'; END IF;
   SELECT value INTO fila FROM jsonb_array_elements(e.entrada_priorizacion->'entradas') WHERE value->'solicitud_demanda'->>'incidente_id'=i.incidente_id::text;
   IF fila IS NULL OR (fila->>'version_incidente')::integer IS DISTINCT FROM i.version
     OR NOT EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i.incidente_id AND v.desvinculado_en IS NULL) THEN RAISE EXCEPTION 'Entrada de demanda ausente, inactiva o desactualizada' USING ERRCODE='22023'; END IF;
   validacion:=p_validaciones->i.incidente_id::text;
   IF validacion IS NULL OR validacion->>'incidente_id' IS DISTINCT FROM i.incidente_id::text
     OR validacion->>'ejecucion_id' IS DISTINCT FROM e.ejecucion_id::text OR validacion->>'origen' IS DISTINCT FROM e.origen::text
     OR validacion->>'punto_atencion_id' IS DISTINCT FROM i.punto_atencion_id::text
     OR validacion->>'datos_version' IS DISTINCT FROM ev->>'datos_version'
     OR validacion->>'estado' IS DISTINCT FROM ev->>'estado_demanda'
     OR validacion->'demanda_litros' IS DISTINCT FROM ev->'demanda_litros'
     OR validacion->>'metodo' IS DISTINCT FROM ev->>'metodo_demanda' THEN RAISE EXCEPTION 'Falta resultado original de validate_need o no coincide con evaluación' USING ERRCODE='22023'; END IF;
   UPDATE public.incidentes SET evaluacion_necesidad=ev,pendientes_calculo=ARRAY(SELECT jsonb_array_elements_text(ev->'pendientes')) WHERE incidente_id=i.incidente_id;
   INSERT INTO public.necesidades(ejecucion_id,incidente_id,punto_atencion_id,datos_version,politica_version,estado_demanda,demanda_litros,metodo_demanda,entrada_demanda,resultado_demanda,confirmacion_demanda,
    clase_prioridad,confirmacion_clase,ventana_inicio,ventana_fin,horas_sin_agua,personas_atendidas,vulnerabilidad,confirmacion_vulnerabilidad,ultima_atencion_confirmada_en,primera_deteccion_en,
    estado_prioridad,puntaje,componentes,posicion,pendientes,supuestos,requiere_revision_urgente,origen)
   VALUES(e.ejecucion_id,i.incidente_id,i.punto_atencion_id,p_resultado->>'datos_version',politica.politica_version,(ev->>'estado_demanda')::public.ra_validacion,(ev->>'demanda_litros')::numeric,ev->>'metodo_demanda',fila->'solicitud_demanda',validacion, nullif(ev->'confirmacion_demanda','null'),
    (ev->>'clase_prioridad')::public.ra_clase_prioridad,nullif(ev->'confirmacion_clase','null'),(ev->'ventana_atencion'->>'inicio')::timestamptz,(ev->'ventana_atencion'->>'fin')::timestamptz,
    (ev->>'horas_sin_agua')::numeric,(ev->>'personas_atendidas')::integer,(ev->>'vulnerabilidad')::public.ra_vulnerabilidad,nullif(ev->'confirmacion_vulnerabilidad','null'),(ev->>'ultima_atencion_confirmada_en')::timestamptz,(ev->>'primera_deteccion_en')::timestamptz,
    ev->>'estado_prioridad',(ev->>'puntaje')::numeric,nullif(ev->'componentes','null'),(ev->>'posicion')::integer,
    ARRAY(SELECT jsonb_array_elements_text(ev->'pendientes')),ARRAY(SELECT jsonb_array_elements_text(ev->'supuestos')),(ev->>'requiere_revision_urgente')::boolean,e.origen);
   calculada:=calculada OR ev->>'estado_prioridad'='calculada';
  END LOOP;
 END IF;
 UPDATE public.ejecuciones SET estado='espera_validacion',trabajador_id=NULL,bloqueada_hasta=NULL,
  ultimo_error=CASE WHEN p_resultado IS NULL THEN jsonb_build_object('codigo','datos_calculo_pendientes','mensaje',array_to_string(p_pendientes,'; ')) ELSE NULL END WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_evento_v2(e.ejecucion_id,'priorizacion','Registrar evaluación o faltantes de cálculo',jsonb_build_object('resultado',p_resultado,'pendientes',p_pendientes,'hay_prioridad_calculada',calculada));
 RETURN jsonb_build_object('estado','espera_validacion','etapa','priorizacion','ejecucion_id',e.ejecucion_id,'pendientes',p_pendientes);
END $$;

CREATE FUNCTION public.ra_preparar_priorizacion_v2(p_ejecucion_id uuid,p_usuario_id uuid,p_lote jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; fila jsonb; i public.incidentes%ROWTYPE; version_datos text; politica public.politicas_prioridad%ROWTYPE;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo) THEN RAISE EXCEPTION 'Sin permiso de coordinador' USING ERRCODE='42501'; END IF;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.etapa<>'priorizacion' OR e.estado NOT IN ('pendiente','espera_validacion','espera_revision') THEN RAISE EXCEPTION 'Ejecución no disponible para preparar cálculo' USING ERRCODE='55000'; END IF;
 LOCK TABLE public.incidentes,public.vinculos_reportes IN SHARE ROW EXCLUSIVE MODE;
 IF jsonb_typeof(p_lote->'entradas') IS DISTINCT FROM 'array' OR jsonb_array_length(p_lote->'entradas')=0 THEN RAISE EXCEPTION 'Lote vacío' USING ERRCODE='22023'; END IF;
 SELECT * INTO politica FROM public.politicas_prioridad WHERE politica_version=p_lote->'politica'->>'politica_version' FOR SHARE;
 IF NOT FOUND OR politica.estado<>'activa' OR NOT (to_jsonb(politica) @> (p_lote->'politica')) THEN RAISE EXCEPTION 'Política sin activar o diferente de la registrada' USING ERRCODE='55000'; END IF;
 version_datos:=p_lote->'entradas'->0->'solicitud_demanda'->>'datos_version';
 IF version_datos IS NULL OR length(btrim(version_datos))=0 THEN RAISE EXCEPTION 'Falta datos_version' USING ERRCODE='22023'; END IF;
 IF e.entrada_priorizacion IS NOT NULL AND e.entrada_priorizacion IS DISTINCT FROM p_lote AND version_datos=e.entrada_priorizacion->'entradas'->0->'solicitud_demanda'->>'datos_version' THEN RAISE EXCEPTION 'Cambiar datos_version al modificar un lote' USING ERRCODE='22023'; END IF;
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
 IF e.entrada_priorizacion=p_lote AND EXISTS(SELECT 1 FROM public.necesidades WHERE ejecucion_id=e.ejecucion_id AND datos_version=version_datos) THEN RETURN jsonb_build_object('estado',e.estado,'repetido',true); END IF;
 UPDATE public.ejecuciones SET entrada_priorizacion=p_lote,estado='pendiente',trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=NULL,datos_version=version_datos WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_traza_aclaracion(e.ejecucion_id,'Preparar lote de priorización',jsonb_build_object('usuario_id',p_usuario_id,'datos_version',version_datos));
 RETURN jsonb_build_object('estado','pendiente','etapa','priorizacion','ejecucion_id',e.ejecucion_id);
END $$;

CREATE FUNCTION public.ra_separar_reporte(p_reporte_id uuid,p_usuario_id uuid,p_motivo text)
RETURNS uuid LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE v public.vinculos_reportes%ROWTYPE; i public.incidentes%ROWTYPE; nuevo uuid;
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo) THEN RAISE EXCEPTION 'Sin permiso de coordinador' USING ERRCODE='42501'; END IF;
 IF p_motivo IS NULL OR length(btrim(p_motivo))=0 THEN RAISE EXCEPTION 'Corrección requiere motivo' USING ERRCODE='22023'; END IF;
 LOCK TABLE public.incidentes,public.vinculos_reportes IN SHARE ROW EXCLUSIVE MODE;
 SELECT * INTO v FROM public.vinculos_reportes WHERE reporte_id=p_reporte_id AND desvinculado_en IS NULL FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Reporte sin asociación activa' USING ERRCODE='22023'; END IF;
 SELECT * INTO i FROM public.incidentes WHERE incidente_id=v.incidente_id FOR UPDATE;
 UPDATE public.vinculos_reportes SET desvinculado_en=clock_timestamp(),desvinculado_por=p_usuario_id WHERE vinculo_id=v.vinculo_id;
 INSERT INTO public.incidentes(ejecucion_id,sector_id,punto_atencion_id,ubicacion,periodo_inicio,periodo_fin,primera_deteccion_en,origen,tipo_problema,episodio_establecido,creado_por,motivo,faltantes)
 SELECT i.ejecucion_id,i.sector_id,i.punto_atencion_id,i.ubicacion,r.creado_en-coalesce((r.interpretacion->'campos'->>'horas_sin_agua')::numeric,0)*interval '1 hour',r.creado_en+interval '1 microsecond',r.creado_en,i.origen,i.tipo_problema,false,p_usuario_id,p_motivo,ARRAY['Asociación separada por coordinador; revisar episodio y necesidad'] FROM public.reportes r WHERE r.reporte_id=p_reporte_id RETURNING incidente_id INTO nuevo;
 INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,vinculado_por,motivo) VALUES(nuevo,p_reporte_id,p_usuario_id,p_motivo);
 UPDATE public.incidentes i0 SET version=version+1,episodio_establecido=false,
  reportes_independientes=(SELECT count(DISTINCT r.remitente_ref) FROM public.vinculos_reportes v0 JOIN public.reportes r USING(reporte_id) WHERE v0.incidente_id=i0.incidente_id AND v0.desvinculado_en IS NULL),
  primera_deteccion_en=coalesce((SELECT min(r.creado_en) FROM public.vinculos_reportes v0 JOIN public.reportes r USING(reporte_id) WHERE v0.incidente_id=i0.incidente_id AND v0.desvinculado_en IS NULL),i0.primera_deteccion_en)
 WHERE i0.incidente_id IN(i.incidente_id,nuevo);
 UPDATE public.incidentes i0 SET
  periodo_inicio=coalesce((SELECT min(r.creado_en-coalesce((r.interpretacion->'campos'->>'horas_sin_agua')::numeric,0)*interval '1 hour') FROM public.vinculos_reportes v0 JOIN public.reportes r USING(reporte_id) WHERE v0.incidente_id=i0.incidente_id AND v0.desvinculado_en IS NULL),i0.periodo_inicio),
  periodo_fin=coalesce((SELECT max(r.creado_en+interval '1 microsecond') FROM public.vinculos_reportes v0 JOIN public.reportes r USING(reporte_id) WHERE v0.incidente_id=i0.incidente_id AND v0.desvinculado_en IS NULL),i0.periodo_fin)
 WHERE i0.incidente_id IN(i.incidente_id,nuevo);
 UPDATE public.necesidades SET estado_demanda='pendiente',demanda_litros=NULL,confirmacion_demanda=NULL,resultado_demanda=NULL,
  estado_prioridad='pendiente',puntaje=NULL,componentes=NULL,posicion=NULL,pendientes=ARRAY['Asociación corregida; validar de nuevo la necesidad'] WHERE incidente_id=i.incidente_id;
 UPDATE public.incidentes SET evaluacion_necesidad=NULL,pendientes_calculo=ARRAY['Asociación corregida; revisar lote y recalcular'];
 UPDATE public.necesidades SET estado_prioridad='pendiente',puntaje=NULL,componentes=NULL,posicion=NULL,pendientes=ARRAY['Asociación corregida; recalcular'] WHERE estado_prioridad='calculada';
 PERFORM public.ra_traza_aclaracion(i.ejecucion_id,'Separar asociación',jsonb_build_object('reporte_id',p_reporte_id,'incidente_anterior',i.incidente_id,'incidente_nuevo',nuevo,'usuario_id',p_usuario_id,'motivo',p_motivo));
 RETURN nuevo;
END $$;

CREATE FUNCTION public.ra_mantenimiento_v2()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x record; n integer; c integer:=0;
BEGIN
 n:=public.ra_revisar_aclaraciones();
 FOR x IN SELECT ejecucion_id FROM public.ejecuciones WHERE estado='ejecutando' AND etapa IN ('ingesta','territorial','priorizacion') AND bloqueada_hasta<=clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
  UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=jsonb_build_object('codigo','reserva_trabajador_vencida','mensaje','Revisar resultado antes de reintentar') WHERE ejecucion_id=x.ejecucion_id;
  PERFORM public.ra_traza_aclaracion(x.ejecucion_id,'Revisar reserva de trabajador vencida'); c:=c+1;
 END LOOP;
 RETURN n+c;
END $$;

DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure AS firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN
 ('ra_evento_v2','ra_catalogo_v2','ra_incidentes_snapshot_v2','ra_tomar_etapa_v2','ra_finalizar_territorial','ra_finalizar_priorizacion_v2','ra_preparar_priorizacion_v2','ra_separar_reporte','ra_mantenimiento_v2') LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated',f.firma);
 EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
 END LOOP;
END $$;
NOTIFY pgrst,'reload schema';
COMMIT;
