-- Emilia A1. Requiere 0015 y 0012; conserva firmas de aprobación/planificación.
-- No crea usuarios, activa políticas, aprueba ni envía. Instalar completo una vez.
BEGIN;
ALTER TABLE public.escenarios_planificacion_v3 ADD COLUMN fuente_necesidades jsonb,
 ADD COLUMN modo text CHECK(modo IS NULL OR modo='ensayo');
CREATE TABLE public.puentes_necesidades_v3 (
 ejecucion_id uuid PRIMARY KEY REFERENCES public.ejecuciones ON DELETE RESTRICT,
 estado text NOT NULL DEFAULT 'pendiente' CHECK(estado IN ('pendiente','registrado','revision')),
 motivo text, creado_en timestamptz NOT NULL DEFAULT now(), actualizado_en timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.puentes_necesidades_v3 ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.puentes_necesidades_v3 FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.puentes_necesidades_v3 TO service_role;
CREATE INDEX puentes_pendientes_v3_idx ON public.puentes_necesidades_v3(creado_en) WHERE estado='pendiente';

-- La revisión conserva procedencia: no mezclar episodios reales con fixtures.
CREATE OR REPLACE FUNCTION public.ra_incidentes_contexto_v2(p_ejecucion_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT coalesce(jsonb_agg(to_jsonb(i) ORDER BY i.incidente_id),'[]')
 FROM public.ejecuciones e JOIN public.incidentes i
 ON i.ensayo_priorizacion_id IS NOT DISTINCT FROM e.ensayo_priorizacion_id AND i.origen=e.origen
 WHERE e.ejecucion_id=p_ejecucion_id AND (e.ensayo_priorizacion_id IS NOT NULL
 OR EXISTS(SELECT 1 FROM public.vinculos_reportes v WHERE v.incidente_id=i.incidente_id AND v.desvinculado_en IS NULL));
$$;

CREATE FUNCTION public.ra_evaluacion_persistida_v3(n public.necesidades)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT (to_jsonb(n)-ARRAY['necesidad_id','entrada_demanda','resultado_demanda','creado_por','motivo','ventana_inicio','ventana_fin'])
 ||jsonb_build_object('esquema_version','1.0','ventana_atencion',
 CASE WHEN n.ventana_inicio IS NULL THEN NULL ELSE jsonb_build_object('inicio',n.ventana_inicio,'fin',n.ventana_fin) END);
$$;
CREATE FUNCTION public.ra_fuente_necesidades_v3(p_ejecucion_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT jsonb_build_object('datos_version',e.datos_version,'lote',e.entrada_priorizacion,
 'incidentes',public.ra_incidentes_contexto_v2(e.ejecucion_id),
 'necesidades',(SELECT coalesce(jsonb_agg(to_jsonb(n) ORDER BY n.incidente_id),'[]') FROM public.necesidades n
 WHERE n.ejecucion_id=e.ejecucion_id AND n.datos_version=e.datos_version
 AND n.politica_version=e.entrada_priorizacion->'politica'->>'politica_version'))
 FROM public.ejecuciones e WHERE e.ejecucion_id=p_ejecucion_id;
$$;
CREATE FUNCTION public.ra_contexto_puente_v3(p_ejecucion_id uuid,p_infraestructura jsonb)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT jsonb_build_object('ejecucion',to_jsonb(e),'infraestructura',p_infraestructura,
 'fuente',public.ra_fuente_necesidades_v3(e.ejecucion_id),
 'incidentes',public.ra_incidentes_contexto_v2(e.ejecucion_id),
 'evaluaciones',(SELECT coalesce(jsonb_agg(public.ra_evaluacion_persistida_v3(n) ORDER BY n.incidente_id),'[]')
 FROM public.necesidades n WHERE n.ejecucion_id=e.ejecucion_id AND n.datos_version=e.datos_version
 AND n.politica_version=e.entrada_priorizacion->'politica'->>'politica_version'),
 'politica',(SELECT to_jsonb(p) FROM public.politicas_prioridad p WHERE p.politica_version=e.entrada_priorizacion->'politica'->>'politica_version'),
 'revision',(SELECT jsonb_build_object('evento_id',v.evento_id,'usuario_id',v.detalles->>'usuario_id','creado_en',v.creado_en)
 FROM public.eventos v WHERE v.ejecucion_id=e.ejecucion_id AND v.decision='Preparar lote de priorización'
 AND v.detalles->>'datos_version'=e.datos_version ORDER BY v.creado_en DESC,v.evento_id DESC LIMIT 1),
 'puntos',(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.punto_atencion_id),'[]') FROM public.puntos_atencion p
 WHERE p.punto_atencion_id IN (SELECT n.punto_atencion_id FROM public.necesidades n WHERE n.ejecucion_id=e.ejecucion_id
 AND n.datos_version=e.datos_version AND n.politica_version=e.entrada_priorizacion->'politica'->>'politica_version')),
 'deposito',(SELECT to_jsonb(d) FROM public.depositos d WHERE d.deposito_id=(p_infraestructura->'deposito'->>'deposito_id')::uuid),
 'vehiculos',(SELECT coalesce(jsonb_agg(to_jsonb(v) ORDER BY v.vehiculo_id),'[]') FROM public.vehiculos v
 WHERE v.vehiculo_id IN (SELECT (j->>'vehiculo_id')::uuid FROM jsonb_array_elements(p_infraestructura->'vehiculos') j)))
 FROM public.ejecuciones e WHERE e.ejecucion_id=p_ejecucion_id;
$$;

CREATE FUNCTION public.ra_encolar_puente_v3() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
 IF NEW.etapa='priorizacion' AND NEW.estado='espera_validacion' AND NEW.origen IN ('real','estimado','sintetico')
 AND NEW.reporte_id IS NOT NULL AND NEW.entrada_priorizacion IS NOT NULL
 AND EXISTS(SELECT 1 FROM public.necesidades n WHERE n.ejecucion_id=NEW.ejecucion_id AND n.datos_version=NEW.datos_version)
 THEN
  INSERT INTO public.puentes_necesidades_v3(ejecucion_id) VALUES(NEW.ejecucion_id)
  ON CONFLICT(ejecucion_id) DO UPDATE SET estado='pendiente',motivo=NULL,actualizado_en=clock_timestamp()
  WHERE public.puentes_necesidades_v3.estado<>'registrado';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ra_encolar_puente_v3 AFTER UPDATE ON public.ejecuciones FOR EACH ROW EXECUTE FUNCTION public.ra_encolar_puente_v3();
-- Recuperar cierres de priorización ya persistidos antes de instalar el puente.
INSERT INTO public.puentes_necesidades_v3(ejecucion_id)
SELECT e.ejecucion_id FROM public.ejecuciones e WHERE e.etapa='priorizacion' AND e.estado='espera_validacion'
AND e.origen IN ('real','estimado','sintetico') AND e.reporte_id IS NOT NULL AND e.entrada_priorizacion IS NOT NULL
AND EXISTS(SELECT 1 FROM public.necesidades n WHERE n.ejecucion_id=e.ejecucion_id AND n.datos_version=e.datos_version);
CREATE FUNCTION public.ra_puentes_pendientes_v3(p_limite integer DEFAULT 20)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') FROM (
 SELECT q.ejecucion_id FROM public.puentes_necesidades_v3 q JOIN public.ejecuciones e USING(ejecucion_id)
 WHERE q.estado='pendiente' AND e.etapa='priorizacion' AND e.estado='espera_validacion'
 ORDER BY q.creado_en,q.ejecucion_id LIMIT greatest(1,least(coalesce(p_limite,20),100))) x;
$$;
CREATE FUNCTION public.ra_revisar_puente_v3(p_ejecucion_id uuid,p_snapshot jsonb,p_motivo text)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
 PERFORM public.ra_bloqueo_v4();
 PERFORM 1 FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF p_motivo IS NULL OR length(btrim(p_motivo)) NOT BETWEEN 1 AND 4000 THEN RAISE EXCEPTION 'Motivo requerido' USING ERRCODE='22023'; END IF;
 IF public.ra_contexto_puente_v3(p_ejecucion_id,p_snapshot->'infraestructura') IS DISTINCT FROM p_snapshot THEN
 RAISE EXCEPTION 'Contexto cambió; no marcar revisión de otro lote' USING ERRCODE='40001'; END IF;
 UPDATE public.puentes_necesidades_v3 SET estado='revision',motivo=p_motivo,actualizado_en=clock_timestamp()
 WHERE ejecucion_id=p_ejecucion_id AND estado='pendiente';
 IF FOUND THEN
  UPDATE public.ejecuciones SET estado='espera_revision',ultimo_error=jsonb_build_object('codigo','puente_requiere_revision','mensaje',p_motivo)
  WHERE ejecucion_id=p_ejecucion_id AND etapa='priorizacion' AND estado='espera_validacion';
  PERFORM public.ra_evento_v2(p_ejecucion_id,'planificacion','Revisar puente sin sustituir necesidades',jsonb_build_object('motivo',p_motivo));
 END IF;
 RETURN jsonb_build_object('ejecucion_id',p_ejecucion_id,'estado','espera_revision','etapa','priorizacion');
END $$;

CREATE FUNCTION public.ra_registrar_puente_v3(p_ejecucion_id uuid,p_snapshot jsonb,p_solicitud jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE e public.ejecuciones%ROWTYPE; x public.escenarios_planificacion_v3%ROWTYPE;
 infra jsonb; fila jsonb; p jsonb; d public.depositos%ROWTYPE; v public.vehiculos%ROWTYPE;
 uid uuid; iid uuid; indices integer[]; a integer; b integer; nodos jsonb; n integer;
BEGIN
 PERFORM public.ra_bloqueo_v4();
 SELECT * INTO e FROM public.ejecuciones WHERE ejecucion_id=p_ejecucion_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Ejecución ausente' USING ERRCODE='22023'; END IF;
 infra:=p_snapshot->'infraestructura';
 SELECT * INTO x FROM public.escenarios_planificacion_v3 WHERE ejecucion_id=e.ejecucion_id FOR UPDATE;
 IF FOUND THEN
  IF x.fuente_necesidades IS NOT NULL AND x.solicitud=p_solicitud
  AND x.fuente_necesidades=public.ra_fuente_necesidades_v3(e.ejecucion_id) THEN
   RETURN jsonb_build_object('ejecucion_id',e.ejecucion_id,'estado',e.estado,'etapa',e.etapa,'repetido',true);
  END IF;
  RAISE EXCEPTION 'Escenario ya registrado; preservar historial y preparar una nueva versión' USING ERRCODE='55000';
 END IF;
 IF e.estado<>'espera_validacion' OR e.etapa<>'priorizacion' OR e.reporte_id IS NULL
 THEN RAISE EXCEPTION 'Solo se admite priorización revisada de reportes para un plan de ensayo' USING ERRCODE='55000'; END IF;
 IF public.ra_contexto_puente_v3(e.ejecucion_id,infra) IS DISTINCT FROM p_snapshot
 THEN RAISE EXCEPTION 'Entradas cambiaron durante el puente' USING ERRCODE='40001'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.puentes_necesidades_v3 WHERE ejecucion_id=e.ejecucion_id AND estado='pendiente')
 THEN RAISE EXCEPTION 'Falta pendiente persistido del puente' USING ERRCODE='55000'; END IF;
 uid:=(p_snapshot->'revision'->>'usuario_id')::uuid;
 PERFORM 1 FROM public.usuarios_operativos WHERE usuario_id=uid AND activo AND rol='coordinador' FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Revisión sin coordinador activo' USING ERRCODE='42501'; END IF;
 n:=jsonb_array_length(p_snapshot->'evaluaciones');
 IF n NOT BETWEEN 1 AND 6 OR n<>jsonb_array_length(p_snapshot->'incidentes')
 OR p_solicitud->'necesidades' IS DISTINCT FROM p_snapshot->'evaluaciones'
 OR p_solicitud->>'ejecucion_id' IS DISTINCT FROM e.ejecucion_id::text
 OR p_solicitud->>'datos_version' IS DISTINCT FROM e.datos_version
 OR p_solicitud->>'origen' IS DISTINCT FROM 'sintetico' OR p_solicitud->>'esquema_version' IS DISTINCT FROM '1.0'
 OR p_solicitud->>'version' IS DISTINCT FROM '1'
 OR p_solicitud->>'recargas_permitidas' IS DISTINCT FROM 'false' OR p_solicitud->>'entregas_parciales_permitidas' IS DISTINCT FROM 'false'
 OR p_solicitud->'limite_solver_segundos' IS DISTINCT FROM infra->'limite_solver_segundos'
 OR coalesce((p_solicitud->>'limite_solver_segundos')::integer,0) NOT BETWEEN 1 AND 60
 THEN RAISE EXCEPTION 'Solicitud ajena a las necesidades persistidas' USING ERRCODE='22023'; END IF;
 IF p_snapshot->'politica'->>'estado' IS DISTINCT FROM 'activa'
 OR p_solicitud->'politica'->>'politica_version' IS DISTINCT FROM e.entrada_priorizacion->'politica'->>'politica_version'
 OR NOT (p_snapshot->'politica' @> ((p_solicitud->'politica')-'esquema_version'))
 THEN RAISE EXCEPTION 'Política modificada o no activa' USING ERRCODE='55000'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_snapshot->'evaluaciones') f GROUP BY f->>'punto_atencion_id' HAVING count(*)>1)
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_snapshot->'incidentes') i
 WHERE i->>'origen' IS DISTINCT FROM e.origen::text OR NOT EXISTS(
 SELECT 1 FROM jsonb_array_elements(e.entrada_priorizacion->'entradas') z
 WHERE z->'solicitud_demanda'->>'incidente_id'=i->>'incidente_id'
 AND z->>'version_incidente'=i->>'version'))
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_snapshot->'evaluaciones') z
 WHERE z->>'origen' IS DISTINCT FROM e.origen::text OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_snapshot->'incidentes') i
 WHERE i->>'incidente_id'=z->>'incidente_id' AND i->>'punto_atencion_id'=z->>'punto_atencion_id'))
 THEN RAISE EXCEPTION 'Ámbito incompleto, duplicado o desactualizado' USING ERRCODE='40001'; END IF;
 IF (SELECT count(DISTINCT z->>'punto_atencion_id') FROM jsonb_array_elements(p_solicitud->'puntos') z)<>n
 OR (SELECT count(DISTINCT z->>'punto_atencion_id') FROM jsonb_array_elements(p_solicitud->'servicios') z)<>n
 OR (SELECT count(DISTINCT z->>'vehiculo_id') FROM jsonb_array_elements(p_solicitud->'vehiculos') z)<>2
 OR jsonb_array_length(p_solicitud->'puntos')<>n OR jsonb_array_length(p_solicitud->'servicios')<>n
 OR jsonb_array_length(p_solicitud->'vehiculos')<>2 OR jsonb_array_length(infra->'vehiculos')<>2
 OR p_solicitud->'matriz'->>'origen' IS DISTINCT FROM 'sintetico'
 THEN RAISE EXCEPTION 'Infraestructura fuera del ensayo aprobado' USING ERRCODE='22023'; END IF;
 FOR fila IN SELECT value FROM jsonb_array_elements(p_solicitud->'puntos') LOOP
  IF NOT EXISTS(SELECT 1 FROM public.puntos_atencion pu WHERE pu.punto_atencion_id=(fila->>'punto_atencion_id')::uuid
   AND pu.activo AND pu.sector_id=(fila->>'sector_id')::uuid
   AND pu.nombre=fila->>'nombre' AND pu.origen::text=fila->>'origen'
   AND fila->'ubicacion'=jsonb_build_object('latitud',pu.latitud,'longitud',pu.longitud,
    'fuente',pu.fuente_ubicacion,'precision_metros',pu.precision_metros,'representa_punto_atencion',pu.representa_punto_atencion))
  OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(infra->'puntos') z WHERE z->>'punto_atencion_id'=fila->>'punto_atencion_id')
  OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_snapshot->'evaluaciones') z WHERE z->>'punto_atencion_id'=fila->>'punto_atencion_id')
  THEN RAISE EXCEPTION 'Punto ajeno al catálogo/ámbito/ensayo' USING ERRCODE='22023'; END IF;
 END LOOP;
 FOR fila IN SELECT value FROM jsonb_array_elements(p_solicitud->'servicios') LOOP
  IF NOT (infra->'servicios' @> jsonb_build_array(fila)) OR NOT EXISTS(
   SELECT 1 FROM jsonb_array_elements(p_solicitud->'puntos') z WHERE z->>'punto_atencion_id'=fila->>'punto_atencion_id')
  THEN RAISE EXCEPTION 'Servicio distinto del ensayo' USING ERRCODE='22023'; END IF;
 END LOOP;
 -- Registrar recursos sintéticos ausentes; nunca sobrescribir disponibilidad/capacidad existentes.
 p:=p_solicitud->'deposito';
 IF p->>'origen' IS DISTINCT FROM 'sintetico' OR p->>'deposito_id' IS DISTINCT FROM infra->'deposito'->>'deposito_id'
 THEN RAISE EXCEPTION 'Depósito de otro origen o escenario' USING ERRCODE='22023'; END IF;
 IF p_snapshot->'deposito'='null'::jsonb AND p IS DISTINCT FROM infra->'deposito'
 THEN RAISE EXCEPTION 'Depósito nuevo distinto del confirmado' USING ERRCODE='22023'; END IF;
 INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,precision_metros,origen,fuente,creado_por,motivo)
 VALUES((p->>'deposito_id')::uuid,p->>'nombre',(p->'ubicacion'->>'latitud')::numeric,(p->'ubicacion'->>'longitud')::numeric,
 p->'ubicacion'->>'fuente',(p->'ubicacion'->>'precision_metros')::numeric,'sintetico','Infraestructura del ensayo 3 confirmada; sin ubicación operativa',uid,'ENSAYO SINTÉTICO: puente de necesidades revisadas')
 ON CONFLICT(deposito_id) DO NOTHING;
 SELECT * INTO d FROM public.depositos WHERE deposito_id=(p->>'deposito_id')::uuid FOR SHARE;
 IF d.origen<>'sintetico' OR NOT d.activo OR d.nombre IS DISTINCT FROM p->>'nombre'
 OR d.latitud IS DISTINCT FROM (p->'ubicacion'->>'latitud')::numeric OR d.longitud IS DISTINCT FROM (p->'ubicacion'->>'longitud')::numeric
 THEN RAISE EXCEPTION 'Depósito cambió' USING ERRCODE='40001'; END IF;
 FOR fila IN SELECT value FROM jsonb_array_elements(p_solicitud->'vehiculos') LOOP
  IF fila->>'origen' IS DISTINCT FROM 'sintetico' OR NOT EXISTS(
   SELECT 1 FROM jsonb_array_elements(infra->'vehiculos') z WHERE z->>'vehiculo_id'=fila->>'vehiculo_id')
  THEN RAISE EXCEPTION 'Vehículo ajeno al ensayo' USING ERRCODE='22023'; END IF;
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_snapshot->'vehiculos') z WHERE z->>'vehiculo_id'=fila->>'vehiculo_id')
  AND NOT (infra->'vehiculos' @> jsonb_build_array(fila)) THEN RAISE EXCEPTION 'Vehículo nuevo distinto del confirmado' USING ERRCODE='22023'; END IF;
  INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,disponible,turno_inicio,turno_fin,deposito_id,origen,creado_por,motivo)
  VALUES((fila->>'vehiculo_id')::uuid,'Cisterna ficticia ensayo 3',(fila->>'capacidad_litros')::numeric,(fila->>'disponible')::boolean,
   (fila->'turno'->>'inicio')::timestamptz,(fila->'turno'->>'fin')::timestamptz,d.deposito_id,'sintetico',uid,'ENSAYO SINTÉTICO: puente de necesidades revisadas')
  ON CONFLICT(vehiculo_id) DO NOTHING;
  SELECT * INTO v FROM public.vehiculos WHERE vehiculo_id=(fila->>'vehiculo_id')::uuid FOR SHARE;
  IF v.origen<>'sintetico' OR v.deposito_id<>d.deposito_id OR v.capacidad_litros IS DISTINCT FROM (fila->>'capacidad_litros')::numeric
   OR v.disponible IS DISTINCT FROM (fila->>'disponible')::boolean OR v.turno_inicio IS DISTINCT FROM (fila->'turno'->>'inicio')::timestamptz
   OR v.turno_fin IS DISTINCT FROM (fila->'turno'->>'fin')::timestamptz THEN RAISE EXCEPTION 'Vehículo cambió' USING ERRCODE='40001'; END IF;
 END LOOP;
 -- La submatriz mantiene los tiempos manuales originales; solo selecciona nodos del ámbito.
 nodos:=p_solicitud->'matriz'->'nodos_ids';
 IF (SELECT count(DISTINCT value) FROM jsonb_array_elements_text(nodos))<>n+1
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_solicitud->'puntos') z WHERE NOT(nodos @> jsonb_build_array(z->>'punto_atencion_id')))
 OR jsonb_array_length(p_solicitud->'matriz'->'minutos')<>n+1
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_solicitud->'matriz'->'minutos') z WHERE jsonb_array_length(z)<>n+1)
 OR jsonb_array_length(nodos)<>n+1 OR NOT(nodos @> jsonb_build_array(d.deposito_id))
 OR ((p_solicitud->'matriz')-ARRAY['nodos_ids','minutos']) IS DISTINCT FROM ((infra->'matriz')-ARRAY['nodos_ids','minutos'])
 THEN RAISE EXCEPTION 'Matriz ajena al escenario' USING ERRCODE='22023'; END IF;
 indices:=ARRAY(SELECT (SELECT ordinality::integer-1 FROM jsonb_array_elements_text(infra->'matriz'->'nodos_ids') WITH ORDINALITY z
 WHERE z.value=j.value) FROM jsonb_array_elements_text(nodos) j);
 FOR a IN 0..n LOOP
  IF indices[a+1] IS NULL THEN RAISE EXCEPTION 'Nodo desconocido' USING ERRCODE='22023'; END IF;
  FOR b IN 0..n LOOP
   IF (p_solicitud->'matriz'->'minutos'->a->b) IS DISTINCT FROM (infra->'matriz'->'minutos'->(indices[a+1])->(indices[b+1]))
   THEN RAISE EXCEPTION 'Tiempo de matriz alterado' USING ERRCODE='22023'; END IF;
  END LOOP;
 END LOOP;
 INSERT INTO public.escenarios_planificacion_v3(ejecucion_id,plan_id,version,solicitud,usuario_revision,motivo,fuente_necesidades,modo)
 VALUES(e.ejecucion_id,(p_solicitud->>'plan_id')::uuid,1,p_solicitud,uid,
 'ENSAYO SINTÉTICO: necesidades revisadas e infraestructura confirmada; no es aprobación de plan',p_snapshot->'fuente','ensayo');
 UPDATE public.puentes_necesidades_v3 SET estado='registrado',motivo=NULL,actualizado_en=clock_timestamp() WHERE ejecucion_id=e.ejecucion_id;
 UPDATE public.ejecuciones SET etapa='planificacion',estado='pendiente',ultimo_error=NULL WHERE ejecucion_id=e.ejecucion_id;
 PERFORM public.ra_evento_v2(e.ejecucion_id,'planificacion','Recibir necesidades persistidas sin sustituir cantidades ni identidad',
 jsonb_build_object('incidentes',n,'datos_version',e.datos_version,'origen_reporte',e.origen,'origen_escenario','sintetico','modo','ensayo','sin_aprobacion',true));
 RETURN jsonb_build_object('ejecucion_id',e.ejecucion_id,'estado','pendiente','etapa','planificacion','repetido',false);
END $$;


CREATE OR REPLACE FUNCTION public.ra_snapshot_planificacion_v3(p_ejecucion_id uuid)
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
 ||CASE WHEN x.fuente_necesidades IS NULL THEN '{}'::jsonb ELSE
 jsonb_build_object('modo',x.modo,'fuente_revisada',x.fuente_necesidades,'fuente_necesidades',public.ra_fuente_necesidades_v3(x.ejecucion_id)) END
 FROM public.escenarios_planificacion_v3 x WHERE x.ejecucion_id=p_ejecucion_id;
$$;

CREATE OR REPLACE FUNCTION public.ra_finalizar_planificacion_v3(p_ejecucion_id uuid,p_trabajador_id text,p_snapshot jsonb,p_resultado jsonb)
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
   (p_resultado->>'estado')::public.ra_estado_ejecucion,t||jsonb_build_object('modo',coalesce(x.modo,'ensayo'),'origen_escenario','sintetico'),e.origen);
 END LOOP;
 respuesta:=jsonb_build_object('ejecucion_id',e.ejecucion_id,'estado',p_resultado->>'estado','etapa','planificacion',
  'plan_id',CASE WHEN p IS NULL THEN NULL ELSE x.plan_id END,'version',x.version,'repetido',false);
 UPDATE public.escenarios_planificacion_v3 SET resultado=p_resultado,cierre_trabajador=p_trabajador_id,
 cierre_snapshot=p_snapshot,cierre_respuesta=respuesta WHERE ejecucion_id=e.ejecucion_id;
 RETURN respuesta;
END $$;

-- Ampliar vigencia a cambios en necesidades, incluyendo nuevas versiones insertadas.
CREATE TRIGGER ra_serializar_v4 BEFORE INSERT OR UPDATE OR DELETE ON public.necesidades
 FOR EACH STATEMENT EXECUTE FUNCTION public.ra_serializar_cambios_v4();
CREATE TRIGGER ra_invalidar_necesidades_v3 AFTER INSERT OR UPDATE OR DELETE ON public.necesidades
 FOR EACH STATEMENT EXECUTE FUNCTION public.ra_invalidar_planes_v4();

DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT p.oid::regprocedure firma FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' AND p.proname IN ('ra_evaluacion_persistida_v3','ra_fuente_necesidades_v3',
 'ra_contexto_puente_v3','ra_encolar_puente_v3','ra_puentes_pendientes_v3','ra_revisar_puente_v3','ra_registrar_puente_v3',
 'ra_snapshot_planificacion_v3','ra_incidentes_contexto_v2','ra_finalizar_planificacion_v3') LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC,anon,authenticated',f.firma);
  EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role',f.firma);
 END LOOP;
END $$;
NOTIFY pgrst,'reload schema';
COMMIT;
