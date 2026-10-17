-- Después de 0016 y semilla 01. Sintético, ámbito aislado, sin Gemini/Telegram.
-- Ejecutar completo; ROLLBACK revierte usuarios, reportes y escenarios de prueba.
BEGIN;
CREATE FUNCTION pg_temp.rechaza_puente_a1(cambio text,llamada text) RETURNS text LANGUAGE plpgsql AS $$
BEGIN
 IF cambio IS NOT NULL THEN EXECUTE cambio; END IF;
 EXECUTE llamada;
 RAISE EXCEPTION 'sin_rechazo' USING ERRCODE='XX999';
EXCEPTION WHEN OTHERS THEN RETURN SQLSTATE;
END $$;
CREATE FUNCTION pg_temp.caso_puente_a1(procedencia public.ra_origen) RETURNS void LANGUAGE plpgsql AS $$
DECLARE u uuid:=gen_random_uuid(); e uuid:=gen_random_uuid(); r uuid:=gen_random_uuid(); m uuid:=gen_random_uuid();
 i uuid:=gen_random_uuid(); ensayo uuid:=gen_random_uuid(); punto public.puntos_atencion%ROWTYPE;
 d uuid:=gen_random_uuid();v1 uuid:=gen_random_uuid();v2 uuid:=gen_random_uuid(); pol text:='smoke-a1-'||gen_random_uuid();
 marca jsonb; politica jsonb; infra jsonb; snapshot jsonb; solicitud jsonb; salida jsonb; toma jsonb; alterada jsonb;
 inicio timestamptz:='2026-10-17T08:00:00-05:00'; fin timestamptz:='2026-10-17T12:00:00-05:00'; antes integer;
BEGIN
 IF has_function_privilege('anon','public.ra_registrar_puente_v3(uuid,jsonb,jsonb)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_contexto_puente_v3(uuid,jsonb)','EXECUTE')
 OR NOT has_function_privilege('service_role','public.ra_registrar_puente_v3(uuid,jsonb,jsonb)','EXECUTE')
 THEN RAISE EXCEPTION 'Puente expuesto o sin permiso backend'; END IF;
 SELECT * INTO punto FROM public.puntos_atencion WHERE activo AND latitud IS NOT NULL ORDER BY punto_atencion_id LIMIT 1;
 IF NOT FOUND THEN RAISE EXCEPTION 'Aplicar semilla 01 antes del smoke'; END IF;
 INSERT INTO auth.users(id) VALUES(u);
 INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES(u,'coordinador',true,'Smoke sintético A1');
 marca:=jsonb_build_object('usuario_id',u,'confirmado_en',inicio,'motivo','FIXTURE SINTÉTICO: revisión de prueba A1');
 INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
 VALUES(pol,'activa','sintetico',.4,.4,.2,168,500,.5,'FIXTURE SINTÉTICO: política de prueba',marca);
 SELECT to_jsonb(p)-ARRAY['creado_en','creado_por'] INTO politica FROM public.politicas_prioridad p WHERE politica_version=pol;
 INSERT INTO public.ensayos_priorizacion_v2(ensayo_id,usuario_id,caso,paquete,motivo) VALUES(ensayo,u,'calculable','{}','Ámbito aislado del smoke');
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(m,'telegram','smoke-a1:'||m);
 INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
 VALUES(r,m,'telegram','smoke-a1:'||r,'texto','Reporte controlado para el puente',procedencia);
 INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,estado,etapa,origen,datos_version,ensayo_priorizacion_id,entrada_priorizacion)
 VALUES(e,r,'espera_validacion','priorizacion',procedencia,'smoke-a1-datos',ensayo,
 jsonb_build_object('politica',politica,'entradas',jsonb_build_array(jsonb_build_object('version_incidente',1,
 'solicitud_demanda',jsonb_build_object('incidente_id',i,'datos_version','smoke-a1-datos')))));
 INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,primera_deteccion_en,periodo_inicio,periodo_fin,origen,ensayo_priorizacion_id)
 VALUES(i,e,punto.sector_id,punto.punto_atencion_id,inicio,inicio,fin,procedencia,ensayo);
 INSERT INTO public.necesidades(ejecucion_id,incidente_id,punto_atencion_id,datos_version,politica_version,metodo_demanda,entrada_demanda,primera_deteccion_en,origen,pendientes)
 VALUES(e,i,punto.punto_atencion_id,'smoke-a1-datos',pol,'directa','{}',inicio,procedencia,ARRAY['capacidad_recepcion_litros']);
 PERFORM public.ra_traza_aclaracion(e,'Preparar lote de priorización',jsonb_build_object('usuario_id',u,'datos_version','smoke-a1-datos'));
 UPDATE public.ejecuciones SET estado='espera_validacion' WHERE ejecucion_id=e;
 IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(public.ra_puentes_pendientes_v3()) j WHERE j->>'ejecucion_id'=e::text)
 THEN RAISE EXCEPTION 'Cierre no dejó puente persistido'; END IF;
 infra:=jsonb_build_object('deposito',jsonb_build_object('deposito_id',d,'nombre','Depósito ficticio smoke','origen','sintetico',
 'ubicacion',jsonb_build_object('latitud',8.9,'longitud',-79.74,'fuente','escenario','precision_metros',NULL,'representa_punto_atencion',NULL)),
 'vehiculos',jsonb_build_array(
 jsonb_build_object('vehiculo_id',v1,'capacidad_litros',10000,'disponible',true,'turno',jsonb_build_object('inicio',inicio,'fin',fin),'origen','sintetico'),
 jsonb_build_object('vehiculo_id',v2,'capacidad_litros',10000,'disponible',true,'turno',jsonb_build_object('inicio',inicio,'fin',fin),'origen','sintetico')),
 'puntos',jsonb_build_array(jsonb_build_object('punto_atencion_id',punto.punto_atencion_id)),
 'servicios',jsonb_build_array(jsonb_build_object('punto_atencion_id',punto.punto_atencion_id,'descarga_minutos',5)),
 'matriz',jsonb_build_object('matriz_version','smoke-a1','origen','sintetico','nodos_ids',jsonb_build_array(d,punto.punto_atencion_id),
 'minutos','[[0,10],[10,0]]'::jsonb,'descripcion','Tiempos ficticios smoke'),'limite_solver_segundos',5);
 snapshot:=public.ra_contexto_puente_v3(e,infra);
 solicitud:=jsonb_build_object('esquema_version','1.0','ejecucion_id',e,'creado_en',inicio,'origen','sintetico','plan_id',gen_random_uuid(),
 'version',1,'datos_version','smoke-a1-datos','politica',politica,'deposito',infra->'deposito','vehiculos',infra->'vehiculos',
 'puntos',jsonb_build_array(jsonb_build_object('punto_atencion_id',punto.punto_atencion_id,'sector_id',punto.sector_id,'nombre',punto.nombre,'origen',punto.origen,
 'ubicacion',jsonb_build_object('latitud',punto.latitud,'longitud',punto.longitud,'fuente',punto.fuente_ubicacion,'precision_metros',punto.precision_metros,'representa_punto_atencion',punto.representa_punto_atencion))),
 'necesidades',snapshot->'evaluaciones','servicios',infra->'servicios','matriz',infra->'matriz','limite_solver_segundos',5,
 'recargas_permitidas',false,'entregas_parciales_permitidas',false);
 alterada:=jsonb_set(solicitud,'{origen}','"real"');
 IF pg_temp.rechaza_puente_a1(NULL,format('SELECT public.ra_registrar_puente_v3(%L,%L::jsonb,%L::jsonb)',e,snapshot,alterada))<>'22023'
 THEN RAISE EXCEPTION 'Permitió plan operativo fuera del modo ensayo'; END IF;
 alterada:=jsonb_set(solicitud,'{necesidades,0,demanda_litros}','99999');
 IF pg_temp.rechaza_puente_a1(NULL,format('SELECT public.ra_registrar_puente_v3(%L,%L::jsonb,%L::jsonb)',e,snapshot,alterada))<>'22023'
 THEN RAISE EXCEPTION 'Aceptó sustituir demanda'; END IF;
 IF pg_temp.rechaza_puente_a1(format('UPDATE public.necesidades SET motivo=''Cambio durante puente'' WHERE ejecucion_id=%L',e),
 format('SELECT public.ra_registrar_puente_v3(%L,%L::jsonb,%L::jsonb)',e,snapshot,solicitud))<>'40001'
 THEN RAISE EXCEPTION 'Aceptó snapshot obsoleto'; END IF;
 IF pg_temp.rechaza_puente_a1(format('UPDATE public.usuarios_operativos SET activo=false WHERE usuario_id=%L',u),
 format('SELECT public.ra_registrar_puente_v3(%L,%L::jsonb,%L::jsonb)',e,snapshot,solicitud))<>'42501'
 THEN RAISE EXCEPTION 'Aceptó revisión sin coordinador activo'; END IF;
 IF pg_temp.rechaza_puente_a1(format('UPDATE public.ejecuciones SET origen=%L WHERE ejecucion_id=%L',CASE WHEN procedencia='real' THEN 'sintetico' ELSE 'real' END,e),
 format('SELECT public.ra_registrar_puente_v3(%L,%L::jsonb,%L::jsonb)',e,snapshot,solicitud))<>'40001'
 THEN RAISE EXCEPTION 'Aceptó cambio de procedencia durante puente'; END IF;
 salida:=public.ra_registrar_puente_v3(e,snapshot,solicitud);
 IF (SELECT origen FROM public.ejecuciones WHERE ejecucion_id=e)<>procedencia
 OR (SELECT esc.solicitud->'necesidades'->0->>'origen' FROM public.escenarios_planificacion_v3 esc WHERE esc.ejecucion_id=e)<>procedencia::text
 OR (SELECT modo FROM public.escenarios_planificacion_v3 WHERE ejecucion_id=e)<>'ensayo'
 OR salida->>'etapa'<>'planificacion' OR salida->>'ejecucion_id'<>e::text
 OR (SELECT count(*) FROM public.necesidades WHERE ejecucion_id=e)<>1
 OR (SELECT count(*) FROM public.incidentes WHERE ensayo_priorizacion_id=ensayo)<>1
 OR EXISTS(SELECT 1 FROM public.planes WHERE ejecucion_id=e)
 THEN RAISE EXCEPTION 'Cambió historia, duplicó necesidades o creó plan sin tools'; END IF;
 SELECT count(*) INTO antes FROM public.eventos WHERE ejecucion_id=e;
 salida:=public.ra_registrar_puente_v3(e,snapshot,solicitud);
 IF NOT(salida->>'repetido')::boolean OR (SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)<>antes
 THEN RAISE EXCEPTION 'Reinicio/repetición duplicó el puente'; END IF;
 toma:=public.ra_tomar_planificacion_v3(e,'smoke-a1');
 IF toma->'solicitud'->'necesidades'->0->'demanda_litros'<>'null'::jsonb
 OR toma->'solicitud'->'necesidades'->0->'pendientes' IS DISTINCT FROM '["capacidad_recepcion_litros"]'::jsonb
 THEN RAISE EXCEPTION 'Perdió necesidad pendiente o inventó cantidad'; END IF;
 salida:=public.ra_finalizar_planificacion_v3(e,'smoke-a1',toma,jsonb_build_object('estado','espera_revision','propuesta',NULL,'informe',NULL,
 'trazas',jsonb_build_array(jsonb_build_object('agente','planificacion','decision','Revisar faltantes sintéticos sin aprobar','duracion_ms',0))));
 IF salida->>'estado'<>'espera_revision' OR EXISTS(SELECT 1 FROM public.aprobaciones a JOIN public.planes p USING(plan_id,version) WHERE p.ejecucion_id=e)
 OR EXISTS(SELECT 1 FROM public.avisos a JOIN public.planes p USING(plan_id,version) WHERE p.ejecucion_id=e)
 THEN RAISE EXCEPTION 'El puente aprobó o comunicó sin revisión'; END IF;
END $$;
SELECT pg_temp.caso_puente_a1('sintetico');
SELECT pg_temp.caso_puente_a1('real');
SELECT pg_temp.caso_puente_a1('estimado');
ROLLBACK;
