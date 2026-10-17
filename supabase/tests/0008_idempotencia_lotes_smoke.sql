-- Resultado sintético de herramientas: prueba persistencia, no el algoritmo de José.
BEGIN;
DO $$
<<ensayo>>
DECLARE u uuid:=gen_random_uuid(); r uuid:=gen_random_uuid(); e uuid:=gen_random_uuid(); i uuid:=gen_random_uuid(); p uuid; s uuid;
 politica jsonb; confirmacion jsonb; ev jsonb; lote jsonb; toma jsonb; resultado jsonb; fecha timestamptz:=clock_timestamp(); rechazado boolean; respuesta jsonb; copia jsonb; antes jsonb; eventos_antes bigint;
BEGIN
 SELECT punto_atencion_id,sector_id INTO p,s FROM public.puntos_atencion ORDER BY punto_atencion_id LIMIT 1;
 confirmacion:=jsonb_build_object('usuario_id',u,'confirmado_en',fecha,'motivo','Confirmación ficticia exclusiva del smoke sintético');
 politica:=jsonb_build_object('politica_version','smoke-v2-'||e,'estado','activa','origen','sintetico','peso_duracion',0.5,'peso_vulnerabilidad',0.3,'peso_poblacion',0.2,'tope_horas',168,'tope_personas',500,'vulnerabilidad_moderada',0.5,'fundamento','Ensayo sintético de persistencia; no política operativa','confirmacion_activacion',confirmacion,'criticos_obligatorios',true,'faltantes_fuera_ranking',true,'orden_desempate','ultima_atencion_luego_incidente_luego_id');
 INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
 VALUES(politica->>'politica_version','activa','sintetico',0.5,0.3,0.2,168,500,0.5,politica->>'fundamento',confirmacion);
 INSERT INTO auth.users(id) VALUES(u);
 INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES(u,'coordinador',true,'Coordinador ficticio del smoke');
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram',u::text);
 INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen,interpretacion) VALUES(r,u,'telegram','smoke-prioridad:'||r,'texto','Reporte sintético','sintetico','{}');
 INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen,etapa) VALUES(e,r,'sintetico','priorizacion');
 INSERT INTO public.incidentes(incidente_id,ejecucion_id,punto_atencion_id,sector_id,periodo_inicio,periodo_fin,primera_deteccion_en,origen) VALUES(i,e,p,s,fecha-interval '1 hour',fecha,fecha,'sintetico');
 INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo) VALUES(i,r,'Prueba sintética');
 ev:=jsonb_build_object('esquema_version','1.0','ejecucion_id',e,'creado_en',fecha,'origen','sintetico','incidente_id',i,'punto_atencion_id',p,'datos_version','smoke-1','politica_version',politica->>'politica_version',
  'estado_demanda','pendiente','demanda_litros',NULL,'metodo_demanda','formula','confirmacion_demanda',NULL,'clase_prioridad',NULL,'confirmacion_clase',NULL,'ventana_atencion',NULL,
  'horas_sin_agua',NULL,'personas_atendidas',NULL,'vulnerabilidad',NULL,'confirmacion_vulnerabilidad',NULL,'ultima_atencion_confirmada_en',NULL,'primera_deteccion_en',fecha,
  'estado_prioridad','pendiente','puntaje',NULL,'componentes',NULL,'posicion',NULL,'pendientes',jsonb_build_array('Faltan datos validados'),'supuestos','[]'::jsonb,'requiere_revision_urgente',false);
 lote:=jsonb_build_object('politica',politica,'entradas',jsonb_build_array(jsonb_build_object('version_incidente',1,'solicitud_demanda',jsonb_build_object('incidente_id',i,'punto_atencion_id',p,'datos_version','smoke-1','demanda',jsonb_build_object('metodo','formula','fuente','Prueba sintética')),'evaluacion',ev)));
 PERFORM public.ra_preparar_priorizacion_v2(e,u,lote);
 SELECT to_jsonb(x) INTO antes FROM public.ejecuciones x WHERE ejecucion_id=e;
 SELECT count(*) INTO eventos_antes FROM public.eventos WHERE ejecucion_id=e;
 respuesta:=public.ra_preparar_priorizacion_v2(e,u,lote);
 IF respuesta->>'repetido' IS DISTINCT FROM 'true' OR
  antes IS DISTINCT FROM (SELECT to_jsonb(x) FROM public.ejecuciones x WHERE ejecucion_id=e) OR
  eventos_antes<>(SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)
 THEN RAISE EXCEPTION 'Repetición inicial modificó ejecución o eventos'; END IF;
 -- El servidor puede regenerar creado_en; conservar siempre el JSON original aceptado.
 copia:=jsonb_set(lote,'{entradas,0,evaluacion,creado_en}',to_jsonb(fecha+interval '1 minute'));
 IF public.ra_preparar_priorizacion_v2(e,u,copia)->>'repetido' IS DISTINCT FROM 'true' OR
  (SELECT entrada_priorizacion FROM public.ejecuciones WHERE ejecucion_id=e) IS DISTINCT FROM lote
 THEN RAISE EXCEPTION 'Las fechas regeneradas sobrescribieron el lote'; END IF;
 toma:=public.ra_tomar_etapa_v2(e,'smoke-sin-datos','priorizacion');
 SELECT to_jsonb(x) INTO antes FROM public.ejecuciones x WHERE ejecucion_id=e;
 SELECT count(*) INTO eventos_antes FROM public.eventos WHERE ejecucion_id=e;
 respuesta:=public.ra_preparar_priorizacion_v2(e,u,lote);
 IF respuesta->>'repetido' IS DISTINCT FROM 'true' OR respuesta->>'estado'<>'ejecutando' OR
  antes IS DISTINCT FROM (SELECT to_jsonb(x) FROM public.ejecuciones x WHERE ejecucion_id=e) OR
  eventos_antes<>(SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)
 THEN RAISE EXCEPTION 'Repetición quitó reserva o alteró cálculo en curso'; END IF;
 copia:=jsonb_set(lote,'{entradas,0,solicitud_demanda,datos_version}','"smoke-otra"');
 rechazado:=false;
 BEGIN PERFORM public.ra_preparar_priorizacion_v2(e,u,copia);
 EXCEPTION WHEN SQLSTATE '55000' THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Se sustituyó un lote en ejecución'; END IF;
 PERFORM public.ra_finalizar_priorizacion_v2(e,'smoke-sin-datos',toma,NULL,ARRAY['Faltan datos validados']);
 SELECT to_jsonb(x) INTO antes FROM public.ejecuciones x WHERE ejecucion_id=e;
 SELECT count(*) INTO eventos_antes FROM public.eventos WHERE ejecucion_id=e;
 respuesta:=public.ra_preparar_priorizacion_v2(e,u,lote);
 IF respuesta->>'repetido' IS DISTINCT FROM 'true' OR respuesta->>'estado'<>'espera_validacion' OR
  antes IS DISTINCT FROM (SELECT to_jsonb(x) FROM public.ejecuciones x WHERE ejecucion_id=e) OR
  eventos_antes<>(SELECT count(*) FROM public.eventos WHERE ejecucion_id=e) OR
  EXISTS(SELECT 1 FROM public.necesidades WHERE ejecucion_id=e)
 THEN RAISE EXCEPTION 'Repetición sin necesidades reactivó la ejecución'; END IF;
 -- Cambiar una entrada requiere datos_version nueva, incluso sin filas de necesidades.
 copia:=jsonb_set(lote,'{entradas,0,solicitud_demanda,demanda,fuente}','"Otra fuente"');
 rechazado:=false;
 BEGIN PERFORM public.ra_preparar_priorizacion_v2(e,u,copia);
 EXCEPTION WHEN SQLSTATE '22023' THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Se cambió la entrada sin nueva versión'; END IF;
 -- Una repetición no debe aceptar la versión obsoleta de un incidente.
 UPDATE public.incidentes SET version=version+1 WHERE incidente_id=i;
 rechazado:=false;
 BEGIN PERFORM public.ra_preparar_priorizacion_v2(e,u,lote);
 EXCEPTION WHEN SQLSTATE '22023' THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Repetición eludió control de versión de incidente'; END IF;
 UPDATE public.incidentes SET version=version-1 WHERE incidente_id=i;
 -- Recalcular es explícito: nueva versión. No usar el reintento para reactivar.
 lote:=jsonb_set(lote,'{entradas,0,solicitud_demanda,datos_version}','"smoke-1b"');
 ev:=ev||jsonb_build_object('datos_version','smoke-1b');
 lote:=jsonb_set(lote,'{entradas,0,evaluacion}',ev);
 PERFORM public.ra_preparar_priorizacion_v2(e,u,lote);
 toma:=public.ra_tomar_etapa_v2(e,'smoke-P','priorizacion');
 resultado:=jsonb_build_object('esquema_version','1.0','ejecucion_id',e,'creado_en',fecha,'origen','sintetico','datos_version','smoke-1b','politica_version',politica->>'politica_version','evaluaciones',jsonb_build_array(ev),'alertas_revision','[]'::jsonb);
 PERFORM public.ra_finalizar_priorizacion_v2(e,'smoke-P',toma,resultado,ARRAY[]::text[],jsonb_build_object(i::text,jsonb_build_object('incidente_id',i,'ejecucion_id',e,'origen','sintetico','punto_atencion_id',p,'datos_version',ev->>'datos_version','estado',ev->>'estado_demanda','demanda_litros',ev->'demanda_litros','metodo',ev->>'metodo_demanda')));
 IF (SELECT count(*) FROM public.necesidades WHERE ejecucion_id=e)<>1 OR (SELECT estado_prioridad FROM public.necesidades WHERE ejecucion_id=e)<>'pendiente' THEN RAISE EXCEPTION 'No se guardó necesidad pendiente'; END IF;
 IF (SELECT evaluacion_necesidad FROM public.incidentes WHERE incidente_id=i) IS DISTINCT FROM ev THEN RAISE EXCEPTION 'Se perdió contrato de evaluación'; END IF;
 -- Segunda versión: resultado calculado sintético; no se publica ni aprueba plan.
 ev:=ev||jsonb_build_object('datos_version','smoke-2','estado_demanda','validada','demanda_litros',1000,'metodo_demanda','directa','confirmacion_demanda',confirmacion,
  'clase_prioridad','general','confirmacion_clase',confirmacion,'horas_sin_agua',0,'personas_atendidas',0,'vulnerabilidad','sin_condicion_identificada','confirmacion_vulnerabilidad',confirmacion,
  'estado_prioridad','calculada','puntaje',0,'componentes',jsonb_build_object('duracion_normalizada',0,'vulnerabilidad_normalizada',0,'poblacion_normalizada',0,'aporte_duracion',0,'aporte_vulnerabilidad',0,'aporte_poblacion',0),'posicion',1,'pendientes','[]'::jsonb);
 lote:=jsonb_set(lote,'{entradas,0,evaluacion}',ev);
 lote:=jsonb_set(lote,'{entradas,0,solicitud_demanda,datos_version}','"smoke-2"');
 lote:=jsonb_set(lote,'{entradas,0,solicitud_demanda,demanda}',jsonb_build_object('metodo','directa','litros_declarados',1000,'fuente','Ensayo sintético','confirmacion',confirmacion));
 PERFORM public.ra_preparar_priorizacion_v2(e,u,lote);
 toma:=public.ra_tomar_etapa_v2(e,'smoke-P2','priorizacion');
 resultado:=resultado||jsonb_build_object('datos_version','smoke-2','evaluaciones',jsonb_build_array(ev));
 PERFORM public.ra_finalizar_priorizacion_v2(e,'smoke-P2',toma,resultado,ARRAY[]::text[],jsonb_build_object(i::text,jsonb_build_object('incidente_id',i,'ejecucion_id',e,'origen','sintetico','punto_atencion_id',p,'datos_version',ev->>'datos_version','estado',ev->>'estado_demanda','demanda_litros',ev->'demanda_litros','metodo',ev->>'metodo_demanda')));
 IF (SELECT count(*) FROM public.necesidades WHERE ejecucion_id=e)<>2 OR (SELECT posicion FROM public.necesidades WHERE ejecucion_id=e AND datos_version='smoke-2')<>1 THEN RAISE EXCEPTION 'No persistió cálculo versionado'; END IF;
 SELECT to_jsonb(x) INTO antes FROM public.ejecuciones x WHERE ejecucion_id=e;
 SELECT count(*) INTO eventos_antes FROM public.eventos WHERE ejecucion_id=e;
 copia:=jsonb_set(lote,'{entradas,0,solicitud_demanda,demanda,confirmacion,confirmado_en}',to_jsonb(fecha+interval '2 minutes'));
 copia:=jsonb_set(copia,'{entradas,0,evaluacion,confirmacion_demanda,confirmado_en}',to_jsonb(fecha+interval '2 minutes'));
 IF public.ra_preparar_priorizacion_v2(e,u,copia)->>'repetido' IS DISTINCT FROM 'true' OR
  antes IS DISTINCT FROM (SELECT to_jsonb(x) FROM public.ejecuciones x WHERE ejecucion_id=e) OR
  eventos_antes<>(SELECT count(*) FROM public.eventos WHERE ejecucion_id=e) OR
  (SELECT count(*) FROM public.necesidades WHERE ejecucion_id=e)<>2
 THEN RAISE EXCEPTION 'Repetición después de guardar necesidad modificó datos'; END IF;
 -- Cambios sustantivos de cantidad, actor o motivo nunca se ocultan como reintentos.
 FOR copia IN SELECT value FROM jsonb_array_elements(jsonb_build_array(
  jsonb_set(lote,'{entradas,0,solicitud_demanda,demanda,litros_declarados}','1200'),
  jsonb_set(lote,'{entradas,0,solicitud_demanda,demanda,confirmacion,usuario_id}',to_jsonb(gen_random_uuid())),
  jsonb_set(lote,'{entradas,0,solicitud_demanda,demanda,confirmacion,motivo}','"Motivo distinto"')
 )) LOOP
  rechazado:=false;
  BEGIN PERFORM public.ra_preparar_priorizacion_v2(e,u,copia);
  EXCEPTION WHEN SQLSTATE '22023' THEN rechazado:=true; END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Cambio sustantivo tratado como repetido'; END IF;
 END LOOP;
 RAISE NOTICE 'OK: reintentos antes/durante/después, sin necesidad, sin eventos extra, reserva intacta y cambios versionados.';
END $$;
ROLLBACK;
