-- Después de 0007 y semilla 01. Sintético, sin red; ROLLBACK conserva catálogo.
BEGIN;
DO $$
DECLARE k integer; u uuid; r uuid; e uuid; p uuid; p2 uuid; i uuid; primero uuid; r1 uuid; e1 uuid; coordinador uuid;
 toma jsonb; resultado jsonb; nuevo uuid; rechazado boolean; snapshot jsonb; estado_actual text;
BEGIN
 SELECT punto_atencion_id INTO p FROM public.puntos_atencion ORDER BY punto_atencion_id LIMIT 1;
 SELECT punto_atencion_id INTO p2 FROM public.puntos_atencion WHERE punto_atencion_id<>p ORDER BY punto_atencion_id LIMIT 1;
 IF p2 IS NULL THEN RAISE EXCEPTION 'Aplicar semilla 01 antes del smoke'; END IF;
 FOR k IN 1..6 LOOP
  u:=gen_random_uuid();r:=gen_random_uuid();e:=gen_random_uuid();
  INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram',u::text);
  INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen,interpretacion,creado_en)
  VALUES(r,u,'telegram','smoke-territorial:'||r,'texto','48 horas sin agua, 120 personas, prueba sintética.','sintetico',
   jsonb_build_object('campos',jsonb_build_object('horas_sin_agua',CASE WHEN k=6 THEN NULL ELSE 48 END,'personas_afectadas',120,'tipo_problema','sin_suministro')),
   clock_timestamp()-CASE WHEN k=5 THEN interval '10 days' ELSE interval '0' END);
  INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen,etapa) VALUES(e,r,'sintetico','territorial');
  toma:=public.ra_tomar_etapa_v2(e,'smoke-T','territorial');
  IF public.ra_tomar_etapa_v2(e,'smoke-otro','territorial') IS NOT NULL THEN RAISE EXCEPTION 'Doble toma territorial'; END IF;
  IF k=1 THEN
   rechazado:=false;
   BEGIN PERFORM public.ra_finalizar_territorial(e,'otro',toma,'{}'); EXCEPTION WHEN SQLSTATE '55000' THEN rechazado:=true; END;
   IF NOT rechazado THEN RAISE EXCEPTION 'Otro trabajador cerró Territorial'; END IF;
   snapshot:=jsonb_set(toma,'{catalogo}','[]');rechazado:=false;
   BEGIN PERFORM public.ra_finalizar_territorial(e,'smoke-T',snapshot,'{}'); EXCEPTION WHEN SQLSTATE '40001' THEN rechazado:=true; END;
   IF NOT rechazado OR EXISTS(SELECT 1 FROM public.vinculos_reportes WHERE reporte_id=r) THEN RAISE EXCEPTION 'Snapshot inválido dejó cambios'; END IF;
  END IF;
  resultado:=public.ra_finalizar_territorial(e,'smoke-T',toma,jsonb_build_object('estado','resuelta','motivo','Instalación reconocida en prueba','punto_atencion_id',CASE WHEN k=4 THEN p2 ELSE p END));
  i:=(resultado->>'incidente_id')::uuid;
  IF resultado->>'estado'<>'pendiente' OR resultado->>'etapa'<>'priorizacion' THEN RAISE EXCEPTION 'No avanzó a prioridad'; END IF;
  IF k=1 THEN primero:=i;r1:=r;e1:=e; END IF;
  IF k IN(2,3) AND i<>primero THEN RAISE EXCEPTION 'Tres reportes compatibles no se consolidaron'; END IF;
  IF k IN(4,5,6) AND i=primero THEN RAISE EXCEPTION 'Se mezclaron puntos, episodios o períodos desconocidos'; END IF;
 END LOOP;
 IF (SELECT count(*) FROM public.vinculos_reportes WHERE incidente_id=primero AND desvinculado_en IS NULL)<>3 OR (SELECT reportes_independientes FROM public.incidentes WHERE incidente_id=primero)<>3 THEN RAISE EXCEPTION 'Vínculos o independientes incorrectos'; END IF;
 IF (SELECT estado_validacion FROM public.incidentes WHERE incidente_id=primero)<>'pendiente' THEN RAISE EXCEPTION 'Identificar validó la operación'; END IF;
 -- No duplica el mensaje original, aunque cambie el autor.
 rechazado:=false;
 BEGIN INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
 SELECT u,'telegram',mensaje_externo_id,'texto','Repetido','sintetico' FROM public.reportes WHERE reporte_id=r1;
 EXCEPTION WHEN unique_violation THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Duplicado permitido'; END IF;
 toma:=public.ra_tomar_etapa_v2(e1,'smoke-P','priorizacion');
 resultado:=public.ra_finalizar_priorizacion_v2(e1,'smoke-P',toma,NULL,ARRAY['Faltan herramientas y datos de José']);
 IF resultado->>'estado'<>'espera_validacion' OR (SELECT evaluacion_necesidad FROM public.incidentes WHERE incidente_id=primero) IS NOT NULL THEN RAISE EXCEPTION 'Se inventó cálculo sin herramientas'; END IF;
 -- Corrección reversible: queda historial y baja el número de corroboraciones.
 rechazado:=false;
 BEGIN PERFORM public.ra_separar_reporte(r1,gen_random_uuid(),'Prueba'); EXCEPTION WHEN insufficient_privilege THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Separación sin coordinador'; END IF;
 coordinador:=gen_random_uuid();INSERT INTO auth.users(id) VALUES(coordinador);
 INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES(coordinador,'coordinador',true,'Coordinador sintético de smoke');
 nuevo:=public.ra_separar_reporte(r1,coordinador,'Otro episodio confirmado en prueba sintética');
 IF nuevo=primero OR (SELECT count(*) FROM public.vinculos_reportes WHERE reporte_id=r1)<>2
  OR (SELECT count(*) FROM public.vinculos_reportes WHERE reporte_id=r1 AND desvinculado_en IS NULL)<>1
  OR (SELECT reportes_independientes FROM public.incidentes WHERE incidente_id=primero)<>2 THEN RAISE EXCEPTION 'Separación perdió historial o conteo'; END IF;
 IF has_function_privilege('authenticated','public.ra_separar_reporte(uuid,uuid,text)','EXECUTE') THEN RAISE EXCEPTION 'Corrección abierta al navegador'; END IF;
 RAISE NOTICE 'OK: tres reportes/episodio, cercanos distintos, períodos desconocidos separados, snapshot, duplicados, necesidad pendiente y separación reversible.';
END $$;
ROLLBACK;
