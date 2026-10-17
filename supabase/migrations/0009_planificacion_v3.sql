-- Emilia V3. Requiere 0008. Ensayo aislado: no consume incidentes de Telegram.
-- Ejecutar completo una vez. No crea usuarios/roles ni aprueba planes.
BEGIN;
CREATE TABLE public.escenarios_planificacion_v3 (
 ejecucion_id uuid PRIMARY KEY REFERENCES public.ejecuciones ON DELETE RESTRICT,
 plan_id uuid NOT NULL,
 version integer NOT NULL CHECK(version>0),
 solicitud jsonb NOT NULL CHECK(jsonb_typeof(solicitud)='object'),
 usuario_revision uuid NOT NULL REFERENCES public.usuarios_operativos ON DELETE RESTRICT,
 motivo text NOT NULL CHECK(length(btrim(motivo)) BETWEEN 1 AND 4000),
 revisado_en timestamptz NOT NULL DEFAULT now(),
 resultado jsonb,
 cierre_trabajador text,
 cierre_snapshot jsonb,
 cierre_respuesta jsonb,
 UNIQUE(plan_id,version)
);
ALTER TABLE public.escenarios_planificacion_v3 ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.escenarios_planificacion_v3 FROM PUBLIC,anon,authenticated;
GRANT ALL ON public.escenarios_planificacion_v3 TO service_role;
ALTER TABLE public.planes ADD COLUMN propuesta jsonb CHECK(propuesta IS NULL OR jsonb_typeof(propuesta)='object');

CREATE FUNCTION public.ra_snapshot_planificacion_v3(p_ejecucion_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT jsonb_build_object('solicitud',x.solicitud,
  'revision',jsonb_build_object('usuario_id',x.usuario_revision,'motivo',x.motivo,'revisado_en',x.revisado_en),
  'deposito',(SELECT to_jsonb(d) FROM public.depositos d WHERE d.deposito_id=(x.solicitud->'deposito'->>'deposito_id')::uuid),
  'vehiculos',(SELECT coalesce(jsonb_agg(to_jsonb(v) ORDER BY v.vehiculo_id),'[]') FROM public.vehiculos v
    WHERE v.vehiculo_id IN(SELECT (j->>'vehiculo_id')::uuid FROM jsonb_array_elements(x.solicitud->'vehiculos') j)),
  'incidentes',(SELECT coalesce(jsonb_agg(to_jsonb(i) ORDER BY i.incidente_id),'[]') FROM public.incidentes i
    WHERE i.incidente_id IN(SELECT (j->>'incidente_id')::uuid FROM jsonb_array_elements(x.solicitud->'necesidades') j)),
  'puntos',(SELECT coalesce(jsonb_agg(to_jsonb(pu) ORDER BY pu.punto_atencion_id),'[]') FROM public.puntos_atencion pu
    WHERE pu.punto_atencion_id IN(SELECT (j->>'punto_atencion_id')::uuid FROM jsonb_array_elements(x.solicitud->'puntos') j)),
  'politica',(SELECT to_jsonb(p) FROM public.politicas_prioridad p WHERE p.politica_version=x.solicitud->'politica'->>'politica_version'))
 FROM public.escenarios_planificacion_v3 x WHERE x.ejecucion_id=p_ejecucion_id;
$$;

CREATE FUNCTION public.ra_preparar_ensayo_v3(p_usuario_id uuid,p_solicitud jsonb,p_motivo text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE eid uuid; pid uuid; ver integer; x public.escenarios_planificacion_v3%ROWTYPE;
 fila jsonb; politica jsonb; deposito jsonb; confirmacion jsonb; campo text;
BEGIN
 PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND rol='coordinador' AND activo FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'Coordinador activo requerido' USING ERRCODE='42501'; END IF;
 IF p_motivo IS NULL OR length(btrim(p_motivo)) NOT BETWEEN 1 AND 4000
 OR jsonb_typeof(p_solicitud) IS DISTINCT FROM 'object'
 OR p_solicitud->>'origen' IS DISTINCT FROM 'sintetico'
 OR p_solicitud->>'esquema_version' IS DISTINCT FROM '1.0'
 OR p_solicitud->>'recargas_permitidas' IS DISTINCT FROM 'false'
 OR p_solicitud->>'entregas_parciales_permitidas' IS DISTINCT FROM 'false'
 THEN RAISE EXCEPTION 'Se requiere solicitud de ensayo sintético y revisión explícita' USING ERRCODE='22023'; END IF;
 eid:=(p_solicitud->>'ejecucion_id')::uuid; pid:=(p_solicitud->>'plan_id')::uuid; ver:=(p_solicitud->>'version')::integer;
 IF eid IS NULL OR pid IS NULL OR ver IS NULL OR ver<1 OR coalesce(length(btrim(p_solicitud->>'datos_version')),0)=0
 OR coalesce((p_solicitud->>'limite_solver_segundos')::integer,0) NOT BETWEEN 1 AND 60
 THEN RAISE EXCEPTION 'Falta identidad, versión o límite del solver válido' USING ERRCODE='22023'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(pid::text,0));
 SELECT * INTO x FROM public.escenarios_planificacion_v3 WHERE ejecucion_id=eid FOR UPDATE;
 IF FOUND THEN
  IF x.solicitud=p_solicitud AND x.usuario_revision=p_usuario_id AND x.motivo=p_motivo THEN
   RETURN (SELECT jsonb_build_object('ejecucion_id',eid,'estado',e.estado,'etapa',e.etapa,'repetido',true) FROM public.ejecuciones e WHERE e.ejecucion_id=eid);
  END IF;
  RAISE EXCEPTION 'Identidad ya usada; generar una nueva versión de ensayo' USING ERRCODE='23505';
 END IF;
 IF EXISTS(SELECT 1 FROM public.ejecuciones WHERE ejecucion_id=eid)
 OR EXISTS(SELECT 1 FROM public.planes WHERE plan_id=pid AND version=ver)
 THEN RAISE EXCEPTION 'Identidad existente fuera de este ensayo' USING ERRCODE='23505'; END IF;
 IF jsonb_typeof(p_solicitud->'necesidades') IS DISTINCT FROM 'array'
 OR jsonb_typeof(p_solicitud->'puntos') IS DISTINCT FROM 'array'
 OR jsonb_typeof(p_solicitud->'vehiculos') IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Colecciones ausentes' USING ERRCODE='22023'; END IF;
 IF jsonb_array_length(p_solicitud->'necesidades') NOT BETWEEN 1 AND 6
 OR jsonb_array_length(p_solicitud->'necesidades')<>jsonb_array_length(p_solicitud->'puntos')
 OR jsonb_array_length(p_solicitud->'vehiculos')>2
 OR (SELECT count(DISTINCT j->>'incidente_id') FROM jsonb_array_elements(p_solicitud->'necesidades') j)<>jsonb_array_length(p_solicitud->'necesidades')
 OR (SELECT count(DISTINCT j->>'punto_atencion_id') FROM jsonb_array_elements(p_solicitud->'necesidades') j)<>jsonb_array_length(p_solicitud->'necesidades')
 THEN RAISE EXCEPTION 'Lote incompleto o identidades duplicadas' USING ERRCODE='22023'; END IF;
 politica:=p_solicitud->'politica'; deposito:=p_solicitud->'deposito';
 IF politica->>'estado' IS DISTINCT FROM 'activa' OR politica->>'origen' IS DISTINCT FROM 'sintetico'
 OR politica->'confirmacion_activacion'->>'usuario_id' IS DISTINCT FROM p_usuario_id::text
 OR deposito->>'origen' IS DISTINCT FROM 'sintetico'
 THEN RAISE EXCEPTION 'Política/depósito ajenos al ensayo o revisión sin identidad' USING ERRCODE='22023'; END IF;
 -- Las identidades de infraestructura y política deben ser exclusivas del escenario.
 INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
 VALUES(politica->>'politica_version','activa','sintetico',(politica->>'peso_duracion')::numeric,(politica->>'peso_vulnerabilidad')::numeric,
 (politica->>'peso_poblacion')::numeric,(politica->>'tope_horas')::numeric,(politica->>'tope_personas')::integer,
 (politica->>'vulnerabilidad_moderada')::numeric,politica->>'fundamento',politica->'confirmacion_activacion');
 IF NOT (SELECT to_jsonb(p) @> politica FROM public.politicas_prioridad p WHERE p.politica_version=politica->>'politica_version')
 THEN RAISE EXCEPTION 'Política incompatible con el registro' USING ERRCODE='22023'; END IF;
 INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,origen,fuente,creado_por,motivo)
 VALUES((deposito->>'deposito_id')::uuid,deposito->>'nombre',(deposito->'ubicacion'->>'latitud')::numeric,
 (deposito->'ubicacion'->>'longitud')::numeric,'escenario','sintetico','Depósito ficticio exclusivo de V3',p_usuario_id,p_motivo);
 FOR fila IN SELECT value FROM jsonb_array_elements(p_solicitud->'vehiculos') LOOP
  IF fila->>'origen' IS DISTINCT FROM 'sintetico' THEN RAISE EXCEPTION 'Vehículo no sintético' USING ERRCODE='22023'; END IF;
  INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,disponible,turno_inicio,turno_fin,deposito_id,origen,creado_por,motivo)
  VALUES((fila->>'vehiculo_id')::uuid,'Cisterna ficticia V3',(fila->>'capacidad_litros')::numeric,(fila->>'disponible')::boolean,
   (fila->'turno'->>'inicio')::timestamptz,(fila->'turno'->>'fin')::timestamptz,(deposito->>'deposito_id')::uuid,'sintetico',p_usuario_id,p_motivo);
 END LOOP;
 INSERT INTO public.ejecuciones(ejecucion_id,origen,etapa,datos_version,clave_idempotencia)
 VALUES(eid,'sintetico','planificacion',p_solicitud->>'datos_version','planificacion-v3:'||pid||':'||ver);
 FOR fila IN SELECT value FROM jsonb_array_elements(p_solicitud->'necesidades') LOOP
  IF fila->>'origen' IS DISTINCT FROM 'sintetico' OR fila->>'ejecucion_id' IS DISTINCT FROM eid::text
   OR fila->>'datos_version' IS DISTINCT FROM p_solicitud->>'datos_version'
   OR fila->>'politica_version' IS DISTINCT FROM politica->>'politica_version'
  THEN RAISE EXCEPTION 'Necesidad de otro contexto' USING ERRCODE='22023'; END IF;
  FOREACH campo IN ARRAY ARRAY['confirmacion_demanda','confirmacion_clase','confirmacion_vulnerabilidad'] LOOP
   confirmacion:=nullif(fila->campo,'null');
   IF confirmacion IS NOT NULL AND confirmacion->>'usuario_id' IS DISTINCT FROM p_usuario_id::text THEN
    RAISE EXCEPTION 'Confirmación sin coordinador de revisión' USING ERRCODE='22023'; END IF;
  END LOOP;
  IF NOT EXISTS(SELECT 1 FROM public.puntos_atencion p JOIN jsonb_array_elements(p_solicitud->'puntos') q
   ON p.punto_atencion_id=(q->>'punto_atencion_id')::uuid AND p.sector_id=(q->>'sector_id')::uuid
   WHERE p.punto_atencion_id=(fila->>'punto_atencion_id')::uuid AND p.activo)
  THEN RAISE EXCEPTION 'Punto sin correspondencia en catálogo' USING ERRCODE='22023'; END IF;
  -- No se crean vínculos a reportes: este grupo ficticio no entra en el snapshot V2.
  INSERT INTO public.incidentes(incidente_id,ejecucion_id,punto_atencion_id,sector_id,primera_deteccion_en,periodo_inicio,periodo_fin,origen,evaluacion_necesidad,creado_por,motivo)
  SELECT (fila->>'incidente_id')::uuid,eid,p.punto_atencion_id,p.sector_id,(fila->>'primera_deteccion_en')::timestamptz,
   (fila->>'primera_deteccion_en')::timestamptz,(fila->>'primera_deteccion_en')::timestamptz+interval '1 microsecond',
   'sintetico',fila,p_usuario_id,p_motivo FROM public.puntos_atencion p WHERE p.punto_atencion_id=(fila->>'punto_atencion_id')::uuid;
 END LOOP;
 INSERT INTO public.escenarios_planificacion_v3(ejecucion_id,plan_id,version,solicitud,usuario_revision,motivo)
 VALUES(eid,pid,ver,p_solicitud,p_usuario_id,p_motivo);
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,usuario_id,decision,herramienta,resultado,duracion_ms,siguiente_estado,detalles,origen)
 VALUES(eid,'coordinador',p_usuario_id,'Coordinador revisó escenario sintético separado','ra_preparar_ensayo_v3',
 'Preparado para Planificación; no es aprobación de plan',0,'pendiente',jsonb_build_object('motivo',p_motivo),'sintetico');
 RETURN jsonb_build_object('ejecucion_id',eid,'estado','pendiente','etapa','planificacion','repetido',false);
END $$;

CREATE FUNCTION public.ra_tomar_planificacion_v3(p_ejecucion_id uuid,p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; snapshot jsonb;
BEGIN
 IF p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN RAISE EXCEPTION 'Trabajador inválido' USING ERRCODE='22023'; END IF;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND OR e.estado<>'pendiente' OR e.etapa<>'planificacion' THEN RETURN NULL; END IF;
 snapshot:=public.ra_snapshot_planificacion_v3(e.ejecucion_id);
 IF snapshot IS NULL THEN RAISE EXCEPTION 'Falta escenario revisado V3' USING ERRCODE='55000'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.escenarios_planificacion_v3 x JOIN public.usuarios_operativos u
 ON x.usuario_revision=u.usuario_id WHERE x.ejecucion_id=e.ejecucion_id AND u.rol='coordinador' AND u.activo)
 THEN RAISE EXCEPTION 'Revisión sin coordinador activo' USING ERRCODE='42501'; END IF;
 UPDATE public.ejecuciones SET estado='ejecutando',trabajador_id=p_trabajador_id,bloqueada_hasta=clock_timestamp()+interval '300 seconds',intentos=intentos+1,ultimo_error=NULL WHERE ejecucion_id=e.ejecucion_id;
 RETURN snapshot;
END $$;

CREATE FUNCTION public.ra_finalizar_planificacion_v3(p_ejecucion_id uuid,p_trabajador_id text,p_snapshot jsonb,p_resultado jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; x public.escenarios_planificacion_v3%ROWTYPE; s jsonb; p jsonb; inf jsonb;
 t jsonb; ruta jsonb; parada jsonb; rid uuid; valido boolean; respuesta jsonb;
BEGIN
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 SELECT * INTO x FROM public.escenarios_planificacion_v3 WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Escenario no registrado' USING ERRCODE='22023'; END IF;
 IF x.resultado IS NOT NULL THEN
  IF x.resultado=p_resultado AND x.cierre_trabajador=p_trabajador_id AND x.cierre_snapshot=p_snapshot THEN
   RETURN x.cierre_respuesta||jsonb_build_object('repetido',true); END IF;
  RAISE EXCEPTION 'Cierre diferente al registrado' USING ERRCODE='23505'; END IF;
 IF e.estado<>'ejecutando' OR e.etapa<>'planificacion' OR e.trabajador_id IS DISTINCT FROM p_trabajador_id
 OR e.bloqueada_hasta IS NULL OR e.bloqueada_hasta<=clock_timestamp()
 THEN RAISE EXCEPTION 'Reserva de Planificación inválida' USING ERRCODE='55000'; END IF;
 -- Cerrar con snapshot estable. No basta con que las etiquetas de versión coincidan.
 LOCK TABLE public.depositos,public.vehiculos,public.incidentes,public.puntos_atencion,public.politicas_prioridad IN SHARE MODE;
 IF public.ra_snapshot_planificacion_v3(e.ejecucion_id) IS DISTINCT FROM p_snapshot THEN
  RAISE EXCEPTION 'Escenario cambió; revisar y crear una nueva versión' USING ERRCODE='40001'; END IF;
 PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=x.usuario_revision AND rol='coordinador' AND activo FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Coordinador de revisión ya no activo' USING ERRCODE='42501'; END IF;
 IF p_resultado->>'estado' IS NULL OR p_resultado->>'estado' NOT IN ('espera_validacion','espera_revision')
 OR jsonb_typeof(p_resultado->'trazas') IS DISTINCT FROM 'array'
 THEN RAISE EXCEPTION 'Resultado V3 inválido' USING ERRCODE='22023'; END IF;
 IF jsonb_array_length(p_resultado->'trazas')=0 THEN RAISE EXCEPTION 'Falta traza' USING ERRCODE='22023'; END IF;
 s:=x.solicitud; p:=nullif(p_resultado->'propuesta','null'); inf:=nullif(p_resultado->'informe','null');
 IF p IS NULL THEN
  IF inf IS NOT NULL OR p_resultado->>'estado'<>'espera_revision' THEN RAISE EXCEPTION 'Falta propuesta verificable' USING ERRCODE='22023'; END IF;
 ELSE
  IF inf IS NULL OR p->>'ejecucion_id' IS DISTINCT FROM e.ejecucion_id::text
   OR p->>'plan_id' IS DISTINCT FROM x.plan_id::text OR (p->>'version')::integer IS DISTINCT FROM x.version
   OR p->>'datos_version' IS DISTINCT FROM s->>'datos_version' OR p->>'politica_version' IS DISTINCT FROM s->'politica'->>'politica_version'
   OR p->>'origen' IS DISTINCT FROM 'sintetico' OR p->>'estado' IS DISTINCT FROM 'pendiente_revision'
   OR nullif(p->'aprobacion','null') IS NOT NULL OR p->'verificacion' IS DISTINCT FROM inf
   OR jsonb_typeof(p->'rutas') IS DISTINCT FROM 'array' OR jsonb_typeof(p->'no_atendidos') IS DISTINCT FROM 'array'
   OR jsonb_typeof(p->'bloqueos_publicacion') IS DISTINCT FROM 'array'
  THEN RAISE EXCEPTION 'Propuesta incompatible o aprobación no permitida en V3' USING ERRCODE='22023'; END IF;
  IF inf->>'ejecucion_id' IS DISTINCT FROM e.ejecucion_id::text OR inf->>'plan_id' IS DISTINCT FROM x.plan_id::text
   OR (inf->>'version')::integer IS DISTINCT FROM x.version OR inf->>'datos_version' IS DISTINCT FROM s->>'datos_version'
   OR inf->>'politica_version' IS DISTINCT FROM s->'politica'->>'politica_version' OR inf->>'origen' IS DISTINCT FROM 'sintetico'
   OR jsonb_typeof(inf->'valido') IS DISTINCT FROM 'boolean'
  THEN RAISE EXCEPTION 'Informe de otro contexto' USING ERRCODE='22023'; END IF;
  IF jsonb_typeof(inf->'violaciones') IS DISTINCT FROM 'array' OR jsonb_typeof(inf->'comprobaciones') IS DISTINCT FROM 'array' THEN
   RAISE EXCEPTION 'Informe incompleto' USING ERRCODE='22023'; END IF;
  valido:=(inf->>'valido')::boolean;
  IF (valido AND (jsonb_array_length(inf->'violaciones')<>0 OR NOT(inf->'comprobaciones' @> '["capacidad","horarios","ventanas","retorno","asignacion_unica","demanda_completa","version_entradas","cobertura_critica"]')))
   OR (NOT valido AND jsonb_array_length(inf->'violaciones')=0) THEN
   RAISE EXCEPTION 'Informe incoherente o verificaciones incompletas' USING ERRCODE='22023'; END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(p->'rutas') r WHERE r->>'deposito_id' IS DISTINCT FROM s->'deposito'->>'deposito_id'
    OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s->'vehiculos') v WHERE v->>'vehiculo_id'=r->>'vehiculo_id'))
   OR EXISTS(SELECT 1 FROM jsonb_array_elements(p->'rutas') r CROSS JOIN LATERAL jsonb_array_elements(r->'paradas') pa
    WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(s->'necesidades') n WHERE n->>'incidente_id'=pa->>'incidente_id' AND n->>'punto_atencion_id'=pa->>'punto_atencion_id'))
   THEN RAISE EXCEPTION 'Ruta con identidades ajenas al escenario' USING ERRCODE='22023'; END IF;
  IF p_resultado->>'estado'='espera_validacion' AND (NOT valido OR p->>'estado_solver' IS DISTINCT FROM 'factible')
  THEN RAISE EXCEPTION 'Verificación o solución no válidas' USING ERRCODE='22023'; END IF;
  IF NOT(p->'bloqueos_publicacion' ? 'ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.') THEN
   RAISE EXCEPTION 'Falta bloqueo de ensayo' USING ERRCODE='22023'; END IF;
  INSERT INTO public.planes(plan_id,version,ejecucion_id,datos_version,politica_version,estado,estado_solver,deposito_id,solicitud_snapshot,no_atendidos,supuestos,bloqueos_publicacion,verificado,verificacion,origen,creado_por,motivo,propuesta)
  VALUES(x.plan_id,x.version,e.ejecucion_id,s->>'datos_version',s->'politica'->>'politica_version','pendiente_revision',
   (p->>'estado_solver')::public.ra_estado_solver,(s->'deposito'->>'deposito_id')::uuid,s,p->'no_atendidos',
   ARRAY(SELECT jsonb_array_elements_text(p->'supuestos')),ARRAY(SELECT jsonb_array_elements_text(p->'bloqueos_publicacion')),
   valido,inf,'sintetico',x.usuario_revision,x.motivo,p);
  FOR ruta IN SELECT value FROM jsonb_array_elements(p->'rutas') LOOP
   INSERT INTO public.rutas(plan_id,version,vehiculo_id,deposito_id,salida_estimada,retorno_estimado)
   VALUES(x.plan_id,x.version,(ruta->>'vehiculo_id')::uuid,(ruta->>'deposito_id')::uuid,
    (ruta->>'salida_estimada')::timestamptz,(ruta->>'retorno_estimado')::timestamptz) RETURNING ruta_id INTO rid;
   FOR parada IN SELECT value FROM jsonb_array_elements(ruta->'paradas') LOOP
    INSERT INTO public.paradas(parada_id,ruta_id,plan_id,version,incidente_id,punto_atencion_id,orden,litros_asignados,llegada_estimada,inicio_descarga,fin_descarga)
    VALUES((parada->>'parada_id')::uuid,rid,x.plan_id,x.version,(parada->>'incidente_id')::uuid,(parada->>'punto_atencion_id')::uuid,
     (parada->>'orden')::integer,(parada->>'litros_asignados')::numeric,(parada->>'llegada_estimada')::timestamptz,
     (parada->>'inicio_descarga')::timestamptz,(parada->>'fin_descarga')::timestamptz);
   END LOOP;
  END LOOP;
 END IF;
 UPDATE public.ejecuciones SET estado=(p_resultado->>'estado')::public.ra_estado_ejecucion,
 trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=CASE WHEN p_resultado->>'estado'='espera_revision'
 THEN jsonb_build_object('codigo','planificacion_requiere_revision','mensaje','Revisar traza e informe; no reintentar automáticamente.') ELSE NULL END WHERE ejecucion_id=e.ejecucion_id;
 FOR t IN SELECT value FROM jsonb_array_elements(p_resultado->'trazas') LOOP
  IF t->>'agente' IS DISTINCT FROM 'planificacion' THEN RAISE EXCEPTION 'Traza de otro agente' USING ERRCODE='22023'; END IF;
  INSERT INTO public.eventos(ejecucion_id,agente,actor_tipo,decision,herramienta,resultado,duracion_ms,siguiente_estado,detalles,origen)
  VALUES(e.ejecucion_id,'planificacion','agente',coalesce(t->>'decision','Decisión de planificación'),t->>'herramienta',
   coalesce(t->>'decision','Decisión de planificación'),coalesce((t->>'duracion_ms')::integer,0),
   (p_resultado->>'estado')::public.ra_estado_ejecucion,t,'sintetico');
 END LOOP;
 respuesta:=jsonb_build_object('ejecucion_id',e.ejecucion_id,'estado',p_resultado->>'estado','etapa','planificacion',
  'plan_id',CASE WHEN p IS NULL THEN NULL ELSE x.plan_id END,'version',x.version,'repetido',false);
 UPDATE public.escenarios_planificacion_v3 SET resultado=p_resultado,cierre_trabajador=p_trabajador_id,
 cierre_snapshot=p_snapshot,cierre_respuesta=respuesta WHERE ejecucion_id=e.ejecucion_id;
 RETURN respuesta;
END $$;

CREATE FUNCTION public.ra_mantenimiento_planificacion_v3(p_ejecucion_id uuid)
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE;
BEGIN
 SELECT e0.* INTO e FROM public.ejecuciones e0 JOIN public.escenarios_planificacion_v3 x USING(ejecucion_id)
 WHERE e0.ejecucion_id=p_ejecucion_id FOR UPDATE OF e0;
 IF NOT FOUND OR e.estado<>'ejecutando' OR e.etapa<>'planificacion' OR e.bloqueada_hasta IS NULL OR e.bloqueada_hasta>clock_timestamp() THEN RETURN 0; END IF;
 UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
 ultimo_error=jsonb_build_object('codigo','reserva_trabajador_vencida','mensaje','Revisar resultado antes de reintentar') WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_evento_v2(e.ejecucion_id,'planificacion','Revisar reserva de planificación vencida');
 RETURN 1;
END $$;

DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' AND p.proname IN('ra_snapshot_planificacion_v3','ra_preparar_ensayo_v3','ra_tomar_planificacion_v3','ra_finalizar_planificacion_v3','ra_mantenimiento_planificacion_v3') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,anon,authenticated',f.firma);
  EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION public.ra_mantenimiento_v2()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x record; n integer; c integer:=0;
BEGIN
 n:=public.ra_revisar_aclaraciones();
 FOR x IN SELECT ejecucion_id FROM public.ejecuciones WHERE estado='ejecutando' AND etapa IN ('ingesta','territorial','priorizacion','planificacion') AND bloqueada_hasta<=clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
  UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=jsonb_build_object('codigo','reserva_trabajador_vencida','mensaje','Revisar resultado antes de reintentar') WHERE ejecucion_id=x.ejecucion_id;
  PERFORM public.ra_traza_aclaracion(x.ejecucion_id,'Revisar reserva de trabajador vencida'); c:=c+1;
 END LOOP;
 RETURN n+c;
END $$;

NOTIFY pgrst,'reload schema';
COMMIT;
