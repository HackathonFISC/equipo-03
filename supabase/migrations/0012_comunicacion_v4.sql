-- Emilia V4. Aplicar una vez, DESPUÉS de 0009/0010/0011 y 0003 de Noel.
-- Sin cuentas, aprobación automática ni llamadas a Telegram. No habilita destinos reales.
BEGIN;

-- Serialización conservadora para este MVP: autorización, lecturas y cambios de
-- entradas usan el mismo bloqueo transaccional. No se usa una huella como permiso.
CREATE FUNCTION public.ra_bloqueo_v4() RETURNS void
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path='' AS $$
 SELECT pg_advisory_xact_lock(740312004::bigint);
$$;

CREATE TABLE public.destinos_ensayo_v4 (
 destino_id uuid PRIMARY KEY REFERENCES public.destinos ON DELETE RESTRICT,
 usuario_id uuid NOT NULL REFERENCES public.usuarios_operativos ON DELETE RESTRICT,
 motivo text NOT NULL CHECK(length(btrim(motivo)) BETWEEN 1 AND 4000),
 habilitado boolean NOT NULL DEFAULT false,
 autorizado_en timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.planes_sector_v4 (
 sector_id uuid PRIMARY KEY REFERENCES public.sectores ON DELETE RESTRICT,
 plan_id uuid NOT NULL, version integer NOT NULL,
 usuario_id uuid NOT NULL REFERENCES public.usuarios_operativos ON DELETE RESTRICT,
 motivo text NOT NULL CHECK(length(btrim(motivo)) BETWEEN 1 AND 4000),
 seleccionado_en timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(plan_id,version) REFERENCES public.planes ON DELETE RESTRICT
);
CREATE TABLE public.cierres_comunicacion_v4 (
 ejecucion_id uuid PRIMARY KEY REFERENCES public.ejecuciones ON DELETE RESTRICT,
 plan_id uuid NOT NULL, version integer NOT NULL,
 respuesta jsonb NOT NULL, creado_en timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(plan_id,version) REFERENCES public.planes ON DELETE RESTRICT
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['destinos_ensayo_v4','planes_sector_v4','cierres_comunicacion_v4'] LOOP
 EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,anon,authenticated',t);
 EXECUTE format('GRANT ALL ON public.%I TO service_role',t);
 END LOOP;
END $$;

-- No infiere vigencia por número o fecha: exige selección humana por sector.
CREATE FUNCTION public.ra_plan_valido_v4(p_plan_id uuid,p_version integer)
RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path='' AS $$
DECLARE p public.planes%ROWTYPE; x public.escenarios_planificacion_v3%ROWTYPE;
BEGIN
 PERFORM public.ra_bloqueo_v4();
 SELECT * INTO p FROM public.planes WHERE plan_id=p_plan_id AND version=p_version;
 IF NOT FOUND OR p.estado<>'aprobado' OR NOT p.verificado OR p.estado_solver<>'factible'
 OR p.verificacion->>'valido' IS DISTINCT FROM 'true'
 OR jsonb_array_length(coalesce(p.verificacion->'violaciones','[]'))<>0
 OR cardinality(p.bloqueos_publicacion)<>0
 OR jsonb_path_exists(p.no_atendidos,'$[*] ? (@.clase_prioridad == "critico")')
 OR EXISTS(SELECT 1 FROM public.planes z WHERE z.plan_id=p.plan_id AND z.version>p.version)
 OR NOT EXISTS(SELECT 1 FROM public.politicas_prioridad q WHERE q.politica_version=p.politica_version AND q.estado='activa')
 OR NOT EXISTS(SELECT 1 FROM public.aprobaciones a JOIN public.usuarios_operativos u ON u.usuario_id=a.usuario_id
 WHERE a.aprobacion_id=p.aprobacion_id AND a.plan_id=p.plan_id AND a.version=p.version
 AND a.datos_version=p.datos_version AND a.politica_version=p.politica_version AND u.rol='coordinador' AND u.activo)
 THEN RETURN false; END IF;
 SELECT * INTO x FROM public.escenarios_planificacion_v3 WHERE ejecucion_id=p.ejecucion_id AND plan_id=p.plan_id AND version=p.version;
 RETURN FOUND AND x.cierre_snapshot IS NOT NULL
 AND public.ra_snapshot_planificacion_v3(p.ejecucion_id) IS NOT DISTINCT FROM x.cierre_snapshot;
END $$;

-- Registro administrativo del chat de ensayo. UID debe venir del token verificado
-- en la API o de operación administrativa revisada; nunca del cuerpo del navegador.
CREATE FUNCTION public.ra_configurar_destino_ensayo_v4(p_usuario_id uuid,p_destino_id uuid,p_habilitado boolean,p_motivo text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
 PERFORM public.ra_bloqueo_v4();
 IF p_habilitado IS NULL OR p_motivo IS NULL OR length(btrim(p_motivo)) NOT BETWEEN 1 AND 4000 THEN
 RAISE EXCEPTION 'contrato_invalido: motivo y habilitado explícitos requeridos' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND activo AND rol='coordinador' FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'sin_permiso: coordinador activo requerido' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM public.destinos WHERE destino_id=p_destino_id AND canal='telegram' AND autorizado FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'sin_permiso: destino Telegram autorizado requerido' USING ERRCODE='42501'; END IF;
 INSERT INTO public.destinos_ensayo_v4(destino_id,usuario_id,motivo,habilitado)
 VALUES(p_destino_id,p_usuario_id,p_motivo,p_habilitado)
 ON CONFLICT(destino_id) DO UPDATE SET usuario_id=excluded.usuario_id,motivo=excluded.motivo,
 habilitado=excluded.habilitado,autorizado_en=clock_timestamp();
 IF p_habilitado THEN
 UPDATE public.ejecuciones e SET estado='pendiente',ultimo_error=NULL
 WHERE e.etapa='comunicacion' AND e.estado='espera_validacion'
 AND e.ultimo_error->>'codigo'='destino_autorizado_pendiente'
 AND EXISTS(SELECT 1 FROM public.planes pl JOIN public.planes_sector_v4 v USING(plan_id,version)
 JOIN public.suscripciones_sector su ON su.sector_id=v.sector_id AND su.activa
 WHERE pl.ejecucion_id=e.ejecucion_id AND su.destino_id=p_destino_id);
 END IF;
 RETURN jsonb_build_object('destino_id',p_destino_id,'habilitado',p_habilitado);
END $$;

CREATE FUNCTION public.ra_seleccionar_plan_sector_v4(p_usuario_id uuid,p_sector_id uuid,p_plan_id uuid,p_version integer,p_motivo text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e uuid; anterior public.planes_sector_v4%ROWTYPE;
BEGIN
 PERFORM public.ra_bloqueo_v4();
 IF p_motivo IS NULL OR length(btrim(p_motivo)) NOT BETWEEN 1 AND 4000 THEN
 RAISE EXCEPTION 'contrato_invalido: motivo requerido' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=p_usuario_id AND activo AND rol='coordinador' FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'sin_permiso: coordinador activo requerido' USING ERRCODE='42501'; END IF;
 IF NOT public.ra_plan_valido_v4(p_plan_id,p_version) THEN
 RAISE EXCEPTION 'version_obsoleta: plan sin aprobación vigente o entradas cambiadas' USING ERRCODE='40001'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.puntos_atencion pu WHERE pu.sector_id=p_sector_id AND pu.activo
 AND (EXISTS(SELECT 1 FROM public.paradas pa WHERE pa.plan_id=p_plan_id AND pa.version=p_version AND pa.punto_atencion_id=pu.punto_atencion_id)
 OR EXISTS(SELECT 1 FROM public.planes pl,jsonb_array_elements(pl.no_atendidos) n
 WHERE pl.plan_id=p_plan_id AND pl.version=p_version AND n->>'punto_atencion_id'=pu.punto_atencion_id::text))) THEN
 RAISE EXCEPTION 'contrato_invalido: sector ajeno al plan' USING ERRCODE='22023'; END IF;
 SELECT * INTO anterior FROM public.planes_sector_v4 WHERE sector_id=p_sector_id;
 IF FOUND AND anterior.plan_id=p_plan_id AND anterior.version=p_version THEN
 RETURN jsonb_build_object('sector_id',p_sector_id,'repetido',true); END IF;
 INSERT INTO public.planes_sector_v4(sector_id,plan_id,version,usuario_id,motivo)
 VALUES(p_sector_id,p_plan_id,p_version,p_usuario_id,p_motivo)
 ON CONFLICT(sector_id) DO UPDATE SET plan_id=excluded.plan_id,version=excluded.version,
 usuario_id=excluded.usuario_id,motivo=excluded.motivo,seleccionado_en=clock_timestamp();
 SELECT ejecucion_id INTO e FROM public.planes WHERE plan_id=p_plan_id AND version=p_version;
 -- Seleccionar reanuda Comunicación si estaba esperando selección de sectores/destinos.
 UPDATE public.ejecuciones SET estado='pendiente',etapa='comunicacion',ultimo_error=NULL
 WHERE ejecucion_id=e AND estado='espera_validacion' AND etapa='comunicacion';
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,usuario_id,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
 SELECT e,'coordinador',p_usuario_id,'Seleccionar plan vigente para sector','seleccionado',0,ej.estado,
 jsonb_build_object('sector_id',p_sector_id,'plan_id',p_plan_id,'version',p_version),ej.origen FROM public.ejecuciones ej WHERE ej.ejecucion_id=e;
 RETURN jsonb_build_object('sector_id',p_sector_id,'plan_id',p_plan_id,'version',p_version,'repetido',false);
END $$;

-- Herramienta del agente: una transacción, una fila por punto/destino/tipo y
-- un cierre único. Sin reservar operaciones externas ni enviar mensajes aquí.
CREATE FUNCTION public.ra_comunicar_plan_v4(p_ejecucion_id uuid,p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; p public.planes%ROWTYPE; f record;
 res jsonb; n integer:=0; t text; seleccionados integer; sectores integer;
BEGIN
 PERFORM public.ra_bloqueo_v4();
 IF p_trabajador_id IS NULL OR length(btrim(p_trabajador_id)) NOT BETWEEN 1 AND 200 THEN
 RAISE EXCEPTION 'contrato_invalido: trabajador requerido' USING ERRCODE='22023'; END IF;
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('estado','no_tomada'); END IF;
 SELECT respuesta INTO res FROM public.cierres_comunicacion_v4 WHERE ejecucion_id=e.ejecucion_id;
 IF FOUND THEN RETURN res||jsonb_build_object('repetido',true); END IF;
 IF e.estado<>'pendiente' OR e.etapa<>'comunicacion' THEN RETURN jsonb_build_object('estado','no_tomada'); END IF;
 IF (SELECT count(*) FROM public.planes WHERE ejecucion_id=e.ejecucion_id AND estado='aprobado')<>1 THEN
 RAISE EXCEPTION 'plan_no_verificado: se requiere un único plan aprobado de la ejecución' USING ERRCODE='55000'; END IF;
 SELECT * INTO p FROM public.planes WHERE ejecucion_id=e.ejecucion_id AND estado='aprobado';
 IF NOT public.ra_plan_valido_v4(p.plan_id,p.version) THEN
 UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo','version_obsoleta') WHERE ejecucion_id=e.ejecucion_id;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,agente,decision,herramienta,resultado,duracion_ms,siguiente_estado,origen)
 VALUES(e.ejecucion_id,'agente','comunicacion','No crear avisos de plan obsoleto','ra_comunicar_plan_v4','version_obsoleta',0,'espera_revision',e.origen);
 RETURN jsonb_build_object('estado','espera_revision','codigo','version_obsoleta'); END IF;
 SELECT count(DISTINCT pu.sector_id) INTO sectores FROM public.paradas pa JOIN public.puntos_atencion pu USING(punto_atencion_id)
 WHERE pa.plan_id=p.plan_id AND pa.version=p.version;
 SELECT count(*) INTO seleccionados FROM public.planes_sector_v4 s WHERE s.plan_id=p.plan_id AND s.version=p.version;
 IF sectores=0 OR EXISTS(SELECT 1 FROM public.paradas pa JOIN public.puntos_atencion pu USING(punto_atencion_id) WHERE pa.plan_id=p.plan_id AND pa.version=p.version AND NOT EXISTS(SELECT 1 FROM public.planes_sector_v4 vs WHERE vs.sector_id=pu.sector_id AND vs.plan_id=p.plan_id AND vs.version=p.version)) THEN
 UPDATE public.ejecuciones SET estado='espera_validacion',ultimo_error=jsonb_build_object('codigo','seleccion_sector_pendiente') WHERE ejecucion_id=e.ejecucion_id;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,agente,decision,herramienta,resultado,duracion_ms,siguiente_estado,origen)
 VALUES(e.ejecucion_id,'agente','comunicacion','Esperar revisión antes de crear avisos','ra_comunicar_plan_v4','seleccion_sector_pendiente',0,'espera_validacion',e.origen);
 RETURN jsonb_build_object('estado','espera_validacion','codigo','seleccion_sector_pendiente'); END IF;
 IF EXISTS(SELECT 1 FROM public.paradas pa JOIN public.puntos_atencion pu USING(punto_atencion_id)
 WHERE pa.plan_id=p.plan_id AND pa.version=p.version AND NOT EXISTS(
 SELECT 1 FROM public.suscripciones_sector su JOIN public.destinos de USING(destino_id)
 JOIN public.usuarios_operativos du ON du.usuario_id=de.autorizado_por AND du.activo AND du.rol='coordinador'
 WHERE su.sector_id=pu.sector_id AND su.activa AND de.autorizado AND de.canal='telegram'
 AND (p.origen<>'sintetico' OR EXISTS(SELECT 1 FROM public.destinos_ensayo_v4 test JOIN public.usuarios_operativos tu ON tu.usuario_id=test.usuario_id AND tu.activo AND tu.rol='coordinador' WHERE test.destino_id=de.destino_id AND test.habilitado)))) THEN
 UPDATE public.ejecuciones SET estado='espera_validacion',ultimo_error=jsonb_build_object('codigo','destino_autorizado_pendiente') WHERE ejecucion_id=e.ejecucion_id;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,agente,decision,herramienta,resultado,duracion_ms,siguiente_estado,origen)
 VALUES(e.ejecucion_id,'agente','comunicacion','Esperar revisión antes de crear avisos','ra_comunicar_plan_v4','destino_autorizado_pendiente',0,'espera_validacion',e.origen);
 RETURN jsonb_build_object('estado','espera_validacion','codigo','destino_autorizado_pendiente'); END IF;
 FOR f IN SELECT pa.*,pu.sector_id,pu.nombre,d.destino_id FROM public.paradas pa
 JOIN public.puntos_atencion pu USING(punto_atencion_id)
 JOIN public.planes_sector_v4 vigente ON vigente.sector_id=pu.sector_id AND vigente.plan_id=pa.plan_id AND vigente.version=pa.version
 JOIN public.suscripciones_sector s ON s.sector_id=pu.sector_id AND s.activa
 JOIN public.destinos d ON d.destino_id=s.destino_id AND d.autorizado AND d.canal='telegram'
 JOIN public.usuarios_operativos u ON u.usuario_id=d.autorizado_por AND u.activo AND u.rol='coordinador'
 WHERE pa.plan_id=p.plan_id AND pa.version=p.version AND pu.activo
 AND (p.origen<>'sintetico' OR EXISTS(SELECT 1 FROM public.destinos_ensayo_v4 de JOIN public.usuarios_operativos du ON du.usuario_id=de.usuario_id
 WHERE de.destino_id=d.destino_id AND de.habilitado AND du.activo AND du.rol='coordinador'))
 ORDER BY pu.sector_id,pa.punto_atencion_id,d.destino_id LOOP
 t:=CASE WHEN p.origen='sintetico' THEN 'ENSAYO SINTÉTICO. No es una entrega real. ' ELSE '' END
 ||'Plan '||p.plan_id||' versión '||p.version||'. Punto: '||f.nombre||'. Litros asignados: '||f.litros_asignados
 ||'. Ventana estimada (Panamá): '||to_char(f.inicio_descarga AT TIME ZONE 'America/Panama','YYYY-MM-DD HH24:MI')
 ||'–'||to_char(f.fin_descarga AT TIME ZONE 'America/Panama','YYYY-MM-DD HH24:MI')||'. Aviso de programación; no confirma entrega.';
 INSERT INTO public.avisos(ejecucion_id,aprobacion_id,plan_id,version,sector_id,punto_atencion_id,destino_id,tipo,
 ventana_inicio,ventana_fin,litros_asignados,texto,origen)
 VALUES(e.ejecucion_id,p.aprobacion_id,p.plan_id,p.version,f.sector_id,f.punto_atencion_id,f.destino_id,'distribucion',
 f.inicio_descarga,f.fin_descarga,f.litros_asignados,t,p.origen)
 ON CONFLICT(plan_id,version,sector_id,punto_atencion_id,destino_id,tipo) DO NOTHING;
 IF FOUND THEN n:=n+1; END IF;
 END LOOP;
 IF n=0 AND NOT EXISTS(SELECT 1 FROM public.avisos WHERE plan_id=p.plan_id AND version=p.version) THEN
 UPDATE public.ejecuciones SET estado='espera_validacion',ultimo_error=jsonb_build_object('codigo','destino_autorizado_pendiente') WHERE ejecucion_id=e.ejecucion_id;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,agente,decision,herramienta,resultado,duracion_ms,siguiente_estado,origen)
 VALUES(e.ejecucion_id,'agente','comunicacion','Esperar revisión antes de crear avisos','ra_comunicar_plan_v4','destino_autorizado_pendiente',0,'espera_validacion',e.origen);
 RETURN jsonb_build_object('estado','espera_validacion','codigo','destino_autorizado_pendiente'); END IF;
 res:=jsonb_build_object('estado','completada','etapa','terminada','avisos_creados',n,'plan_id',p.plan_id,'version',p.version,'repetido',false);
 INSERT INTO public.cierres_comunicacion_v4(ejecucion_id,plan_id,version,respuesta) VALUES(e.ejecucion_id,p.plan_id,p.version,res);
 UPDATE public.ejecuciones SET estado='completada',etapa='terminada',trabajador_id=NULL,bloqueada_hasta=NULL,ultimo_error=NULL WHERE ejecucion_id=e.ejecucion_id;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,agente,decision,herramienta,resultado,duracion_ms,siguiente_estado,detalles,origen)
 VALUES(e.ejecucion_id,'agente','comunicacion','Crear avisos por punto de plan aprobado','ra_comunicar_plan_v4','avisos_pendientes_de_envio',0,'completada',res,e.origen);
 RETURN res;
END $$;

CREATE FUNCTION public.ra_estado_sector_v4(p_sector_id uuid)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path='' AS $$
DECLARE s public.sectores%ROWTYPE; p public.planes%ROWTYPE; a public.aprobaciones%ROWTYPE;
 puntos jsonb; plan jsonb:=NULL; ori public.ra_origen; ahora timestamptz;
BEGIN
 PERFORM public.ra_bloqueo_v4(); ahora:=clock_timestamp();
 SELECT * INTO s FROM public.sectores WHERE sector_id=p_sector_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'contrato_invalido: sector inexistente' USING ERRCODE='22023'; END IF;
 SELECT pl.* INTO p FROM public.planes pl JOIN public.planes_sector_v4 v USING(plan_id,version) WHERE v.sector_id=p_sector_id;
 IF FOUND AND public.ra_plan_valido_v4(p.plan_id,p.version) THEN
 SELECT * INTO a FROM public.aprobaciones WHERE aprobacion_id=p.aprobacion_id;
 plan:=jsonb_build_object('plan_id',p.plan_id,'version',p.version,'ejecucion_id',p.ejecucion_id,
 'datos_version',p.datos_version,'politica_version',p.politica_version,'origen',p.origen,'estado','aprobado',
 'verificado',true,'aprobacion_id',p.aprobacion_id,'aprobado_en',a.confirmado_en);
 END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('punto_atencion_id',pu.punto_atencion_id,'sector_id',pu.sector_id,
 'nombre',pu.nombre,'origen',CASE WHEN pu.origen='sintetico' OR (pa.parada_id IS NOT NULL AND p.origen='sintetico') THEN 'sintetico'
 WHEN pu.origen='estimado' OR (pa.parada_id IS NOT NULL AND p.origen='estimado') THEN 'estimado' ELSE 'real' END,
 'estado',CASE WHEN pa.parada_id IS NULL THEN 'sin_asignacion' ELSE pa.estado::text END,
 'parada_id',pa.parada_id,'litros_asignados',pa.litros_asignados,
 'ventana_estimada',CASE WHEN pa.parada_id IS NOT NULL THEN jsonb_build_object('inicio',pa.inicio_descarga,'fin',pa.fin_descarga) ELSE NULL END,
 'motivo_sin_asignacion',CASE WHEN pa.parada_id IS NOT NULL THEN NULL WHEN plan IS NULL THEN 'Sin plan vigente aprobado y válido.'
 ELSE coalesce((SELECT n->>'motivo' FROM jsonb_array_elements(p.no_atendidos) n WHERE n->>'punto_atencion_id'=pu.punto_atencion_id::text LIMIT 1),'Punto sin asignación en el plan vigente.') END
 ) ORDER BY pu.punto_atencion_id),'[]') INTO puntos
 FROM public.puntos_atencion pu LEFT JOIN public.paradas pa ON plan IS NOT NULL AND pa.plan_id=p.plan_id AND pa.version=p.version AND pa.punto_atencion_id=pu.punto_atencion_id
 WHERE pu.sector_id=p_sector_id AND pu.activo;
 ori:=CASE WHEN s.origen='sintetico' OR plan->>'origen'='sintetico' OR EXISTS(SELECT 1 FROM jsonb_array_elements(puntos) j WHERE j->>'origen'='sintetico') THEN 'sintetico'::public.ra_origen
 WHEN s.origen='estimado' OR plan->>'origen'='estimado' OR EXISTS(SELECT 1 FROM jsonb_array_elements(puntos) j WHERE j->>'origen'='estimado') THEN 'estimado'::public.ra_origen ELSE 'real'::public.ra_origen END;
 RETURN jsonb_build_object('esquema_version','1.0','consultado_en',ahora,'origen',ori,
 'sector',jsonb_build_object('sector_id',s.sector_id,'nombre',s.nombre,'distrito',s.distrito,'corregimiento',s.corregimiento,'origen',s.origen,'estado_informacion',s.estado_informacion),
 'estado',CASE WHEN plan IS NULL THEN 'sin_plan_vigente' ELSE 'con_plan_vigente' END,'plan_vigente',plan,'puntos',puntos);
END $$;

-- Serializar también escrituras a las entradas, planes y autorizaciones. El
-- bloqueo se toma ANTES de escribir, no después de leer una aprobación vieja.
CREATE FUNCTION public.ra_serializar_cambios_v4() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN PERFORM public.ra_bloqueo_v4(); RETURN NULL; END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['planes','depositos','vehiculos','incidentes','puntos_atencion','sectores','politicas_prioridad',
 'escenarios_planificacion_v3','usuarios_operativos','destinos','suscripciones_sector','destinos_ensayo_v4','planes_sector_v4','paradas','rutas'] LOOP
 EXECUTE format('CREATE TRIGGER ra_serializar_v4 BEFORE INSERT OR UPDATE OR DELETE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.ra_serializar_cambios_v4()',t);
 END LOOP;
END $$;

-- Cuando cambian las entradas, conservar historia e invalidar planes aprobados;
-- la consulta y la reserva comprueban además el snapshot, incluso si ya era inválido.
CREATE FUNCTION public.ra_invalidar_planes_v4() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE p record;
BEGIN
 FOR p IN SELECT pl.plan_id,pl.version,pl.ejecucion_id FROM public.planes pl
 JOIN public.escenarios_planificacion_v3 x USING(ejecucion_id)
 WHERE pl.estado='aprobado' AND (x.cierre_snapshot IS NULL OR public.ra_snapshot_planificacion_v3(pl.ejecucion_id) IS DISTINCT FROM x.cierre_snapshot) LOOP
 UPDATE public.planes SET estado='invalidado' WHERE plan_id=p.plan_id AND version=p.version;
 UPDATE public.avisos SET estado_envio='cancelado',ultimo_error='Plan invalidado por cambios de entradas.',actualizado_en=clock_timestamp()
 WHERE plan_id=p.plan_id AND version=p.version AND estado_envio='pendiente' AND reservada_en IS NULL;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
 SELECT p.ejecucion_id,'sistema','Invalidar plan por cambio de entradas','invalidado',0,e.estado,
 jsonb_build_object('plan_id',p.plan_id,'version',p.version),e.origen FROM public.ejecuciones e WHERE e.ejecucion_id=p.ejecucion_id;
 END LOOP;
 RETURN NULL;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['depositos','vehiculos','incidentes','puntos_atencion','politicas_prioridad','escenarios_planificacion_v3'] LOOP
 EXECUTE format('CREATE TRIGGER ra_invalidar_v4 AFTER UPDATE OR DELETE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.ra_invalidar_planes_v4()',t);
 END LOOP;
END $$;


CREATE FUNCTION public.ra_invalidar_asignacion_v4() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE pid uuid; ver integer; eid uuid;
BEGIN
 IF TG_OP='UPDATE' AND (to_jsonb(NEW)-'estado'-'actualizado_en') IS NOT DISTINCT FROM (to_jsonb(OLD)-'estado'-'actualizado_en') THEN RETURN NULL; END IF;
 IF TG_OP='INSERT' THEN pid:=NEW.plan_id;ver:=NEW.version; ELSE pid:=OLD.plan_id;ver:=OLD.version; END IF;
 UPDATE public.planes SET estado='invalidado' WHERE plan_id=pid AND version=ver AND estado='aprobado' RETURNING ejecucion_id INTO eid;
 IF FOUND THEN
 UPDATE public.avisos SET estado_envio='cancelado',ultimo_error='Cambió la asignación aprobada.',actualizado_en=clock_timestamp()
 WHERE plan_id=pid AND version=ver AND estado_envio='pendiente' AND reservada_en IS NULL;
 INSERT INTO public.eventos(ejecucion_id,actor_tipo,decision,resultado,duracion_ms,siguiente_estado,detalles,origen)
 SELECT eid,'sistema','Invalidar por cambio de rutas o cantidades','invalidado',0,e.estado,
 jsonb_build_object('plan_id',pid,'version',ver),e.origen FROM public.ejecuciones e WHERE e.ejecucion_id=eid;
 END IF;
 RETURN NULL;
END $$;
CREATE TRIGGER ra_invalidar_asignacion_v4 AFTER INSERT OR UPDATE OR DELETE ON public.paradas FOR EACH ROW EXECUTE FUNCTION public.ra_invalidar_asignacion_v4();
CREATE TRIGGER ra_invalidar_asignacion_v4 AFTER INSERT OR UPDATE OR DELETE ON public.rutas FOR EACH ROW EXECUTE FUNCTION public.ra_invalidar_asignacion_v4();

-- Misma firma/forma de reserva de Noel; vuelve a validar antes de autorizar envío.
CREATE OR REPLACE FUNCTION public.ra_reservar_aviso(p_trabajador_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE a public.avisos%ROWTYPE; p public.planes%ROWTYPE; motivo text; chat text; punto text;
BEGIN
  PERFORM public.ra_bloqueo_v4();
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
    ELSIF NOT public.ra_plan_valido_v4(a.plan_id,a.version) THEN
      motivo:='El snapshot o la aprobación del plan dejaron de ser vigentes.';
    ELSIF NOT EXISTS(SELECT 1 FROM public.planes_sector_v4 v WHERE v.sector_id=a.sector_id AND v.plan_id=a.plan_id AND v.version=a.version) THEN
      motivo:='El sector tiene otro plan vigente.';
    ELSIF p.origen='sintetico' AND NOT EXISTS(SELECT 1 FROM public.destinos_ensayo_v4 de JOIN public.usuarios_operativos u ON u.usuario_id=de.usuario_id WHERE de.destino_id=a.destino_id AND de.habilitado AND u.activo AND u.rol='coordinador') THEN
      motivo:='Plan sintético limitado a destino de ensayo habilitado.';
    ELSIF NOT EXISTS(SELECT 1 FROM public.destinos d JOIN public.usuarios_operativos u ON u.usuario_id=d.autorizado_por WHERE d.destino_id=a.destino_id AND u.activo AND u.rol='coordinador') THEN
      motivo:='La autorización del destino ya no tiene coordinador activo.';
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
    IF p.origen='sintetico' THEN punto:='ENSAYO SINTÉTICO, SIN ENTREGA REAL — '||punto; END IF;
    -- Solo lo necesario para redactar el mensaje: el bot no recibe aprobaciones ni datos de personas.
    RETURN jsonb_build_object(
      'aviso_id',a.aviso_id,'chat_id',chat,'tipo',a.tipo,'version',a.version,
      'punto_nombre',punto,'litros_asignados',a.litros_asignados,
      'ventana_inicio',a.ventana_inicio,'ventana_fin',a.ventana_fin);
  END LOOP;
END $$;


DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure::text firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' AND (p.proname IN('ra_bloqueo_v4','ra_plan_valido_v4','ra_configurar_destino_ensayo_v4',
 'ra_seleccionar_plan_sector_v4','ra_comunicar_plan_v4','ra_estado_sector_v4','ra_serializar_cambios_v4','ra_invalidar_planes_v4',
 'ra_invalidar_asignacion_v4','ra_reservar_aviso')) LOOP
 EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,anon,authenticated',f.firma);
 EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
 END LOOP;
END $$;
COMMIT;
