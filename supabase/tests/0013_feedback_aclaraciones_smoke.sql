-- Después de 0013, 0007/0010 Territorial y semilla 01. Datos sintéticos y ROLLBACK.
-- No usa el sondeo global de la bandeja: no afecta preguntas previas de otros reportes.
BEGIN;
CREATE FUNCTION pg_temp.responder_feedback(a uuid,chat text,u uuid,msg integer) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE r jsonb;
BEGIN
 -- Reserva simulada local de esta fila; envío y aceptación usan las RPC reales.
 UPDATE public.aclaraciones SET trabajador_id='smoke-feedback',reservada_en=clock_timestamp(),reserva_hasta=clock_timestamp()+interval '60 seconds' WHERE aclaracion_id=a;
 PERFORM public.ra_registrar_envio_aclaracion(a,'smoke-feedback','enviado',msg::text,NULL);
 r:=public.ra_aceptar_respuesta_aclaracion(chat,msg::text,chat||':'||(msg+1),u,'Referencia sintética todavía sin correspondencia',NULL);
 IF r->>'resultado'<>'aceptada' THEN RAISE EXCEPTION 'Respuesta no aceptada: %',r; END IF;
END $$;
CREATE FUNCTION pg_temp.reinterpretar_feedback(e uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE t jsonb; r uuid;
BEGIN
 t:=public.ra_tomar_ingesta(e,'smoke-feedback');r:=(t->'reporte'->>'reporte_id')::uuid;
 PERFORM public.ra_finalizar_ingesta(e,'smoke-feedback',t->'reporte',
 jsonb_build_object('reporte_id',r,'ejecucion_id',e,'origen','sintetico','modalidad','texto',
 'interpretacion',jsonb_build_object('campos',jsonb_build_object('horas_sin_agua',48,'personas_afectadas',120,'tipo_problema','sin_suministro'),
 'evidencia_textual',jsonb_build_array('Falta agua'),'requiere_aclaracion',false,'fuera_de_alcance',false,'faltantes','[]'::jsonb),
 'evidencias',jsonb_build_array(jsonb_build_object('reporte_id',r))),
 jsonb_build_object('evento_id',gen_random_uuid(),'ejecucion_id',e,'agente','ingesta','origen','sintetico','esquema_version','1.0','creado_en',now(),
 'decision','Entregar a Territorial','resultado','Extracción simulada','duracion_ms',0,'entrada_ids',jsonb_build_array(r),'salida_ids','[]'::jsonb,'siguiente_estado','pendiente'),NULL);
END $$;
DO $$
DECLARE u uuid;d uuid;r uuid;e uuid;a uuid;a2 uuid;chat text;t jsonb;x jsonb;caso text;p uuid;antes integer;previa text;
BEGIN
 IF has_function_privilege('anon','public.ra_crear_aclaracion(uuid,text[],text)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_crear_aclaracion(uuid,text[],text)','EXECUTE') THEN
 RAISE EXCEPTION 'RPC expuesta al navegador'; END IF;
 SELECT punto_atencion_id INTO p FROM public.puntos_atencion WHERE activo ORDER BY punto_atencion_id LIMIT 1;
 IF p IS NULL THEN RAISE EXCEPTION 'Aplicar catálogo antes del smoke'; END IF;
 FOREACH caso IN ARRAY ARRAY['sin_resolver','mixta','resuelta','coordenadas'] LOOP
 u:=gen_random_uuid();d:=gen_random_uuid();r:=gen_random_uuid();e:=gen_random_uuid();
 chat:='-'||(1000000000000+floor(random()*1000000000000)::bigint)::text;
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram',u::text);
 INSERT INTO public.destinos(destino_id,canal,identificador_externo) VALUES(d,'telegram',chat);
 INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen,destino_origen_id,interpretacion)
 VALUES(r,u,'telegram',chat||':1','texto','Falta agua, prueba sintética.','sintetico',d,'{"campos":{"horas_sin_agua":48,"personas_afectadas":120,"tipo_problema":"sin_suministro"}}');
 INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen,estado,etapa) VALUES(e,r,'sintetico','pendiente','territorial');
 IF caso='mixta' THEN
 UPDATE public.ejecuciones SET estado='espera_aclaracion',etapa='ingesta' WHERE ejecucion_id=e;
 PERFORM public.ra_crear_aclaracion(e,ARRAY['ubicación','horas_sin_agua','personas_afectadas'],'Pregunta mixta inicial');
 ELSE
 t:=public.ra_tomar_etapa_v2(e,'smoke-feedback','territorial');
 x:=public.ra_finalizar_territorial(e,'smoke-feedback',t,'{"estado":"desconocida","motivo":"Sin correspondencia en prueba"}');
 END IF;
 SELECT aclaracion_id,pregunta INTO a,previa FROM public.aclaraciones WHERE ejecucion_id=e;
 IF caso<>'mixta' AND (previa NOT LIKE 'Para ubicar tu reporte%' OR previa LIKE '%cuántas horas%') THEN RAISE EXCEPTION 'Primera pregunta incorrecta'; END IF;
 SELECT count(*) INTO antes FROM public.eventos WHERE ejecucion_id=e;
 x:=public.ra_crear_aclaracion(e,ARRAY['ubicacion'],'Texto que no debe sobrescribir');
 IF x->>'aclaracion_id'<>a::text OR (SELECT pregunta FROM public.aclaraciones WHERE aclaracion_id=a)<>previa
 OR (SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)<>antes THEN RAISE EXCEPTION 'Repetición modificó pregunta activa o duplicó traza'; END IF;
 PERFORM pg_temp.responder_feedback(a,chat,u,10);
 PERFORM pg_temp.reinterpretar_feedback(e);
 t:=public.ra_tomar_etapa_v2(e,'smoke-feedback','territorial');
 IF caso='resuelta' THEN
 x:=public.ra_finalizar_territorial(e,'smoke-feedback',t,jsonb_build_object('estado','resuelta','motivo','Punto reconocido en prueba','punto_atencion_id',p));
 IF x->>'etapa'<>'priorizacion' OR (SELECT count(*) FROM public.aclaraciones WHERE ejecucion_id=e)<>1 THEN RAISE EXCEPTION 'Repreguntó tras resolver'; END IF;
 ELSIF caso='coordenadas' THEN
 x:=public.ra_finalizar_territorial(e,'smoke-feedback',t,'{"estado":"revision","motivo":"Confirmar correspondencia de ubicación compartida"}');
 IF x->>'estado'<>'espera_revision' OR (SELECT count(*) FROM public.aclaraciones WHERE ejecucion_id=e)<>1 THEN RAISE EXCEPTION 'Coordenadas de revisión causaron otra pregunta'; END IF;
 ELSE
 x:=public.ra_finalizar_territorial(e,'smoke-feedback',t,'{"estado":"desconocida","motivo":"Todavía sin correspondencia en prueba"}');
 SELECT aclaracion_id INTO a2 FROM public.aclaraciones WHERE ejecucion_id=e AND respondida_en IS NULL;
 IF a2 IS NULL OR a2=a THEN RAISE EXCEPTION 'No creó seguimiento'; END IF;
 IF (SELECT pregunta FROM public.aclaraciones WHERE aclaracion_id=a2) NOT LIKE 'Recibimos tu respuesta, pero no encontramos una coincidencia única%'
 OR (SELECT pregunta FROM public.aclaraciones WHERE aclaracion_id=a2) NOT LIKE '%Esto no significa que el lugar esté fuera de cobertura.%'
 OR (SELECT pregunta FROM public.aclaraciones WHERE aclaracion_id=a2) NOT LIKE '%revisión humana.%'
 OR (SELECT pregunta FROM public.aclaraciones WHERE aclaracion_id=a2) LIKE '%cuántas personas%' THEN RAISE EXCEPTION 'Seguimiento no reconoce respuesta o repide cantidades'; END IF;
 PERFORM pg_temp.responder_feedback(a2,chat,u,20);
 PERFORM pg_temp.reinterpretar_feedback(e);
 t:=public.ra_tomar_etapa_v2(e,'smoke-feedback','territorial');
 x:=public.ra_finalizar_territorial(e,'smoke-feedback',t,'{"estado":"desconocida","motivo":"No se identificó el punto con dos respuestas"}');
 IF x->>'estado'<>'espera_revision' OR (SELECT count(*) FROM public.aclaraciones WHERE ejecucion_id=e)<>2
 OR EXISTS(SELECT 1 FROM public.aclaraciones WHERE ejecucion_id=e AND respondida_en IS NULL AND cerrada_en IS NULL)
 OR (SELECT ultimo_error->>'codigo' FROM public.ejecuciones WHERE ejecucion_id=e)<>'ubicacion_sin_resolver_tras_aclaraciones' THEN RAISE EXCEPTION 'Bucle de repreguntas no detenido'; END IF;
 IF (SELECT respuesta_texto FROM public.aclaraciones WHERE aclaracion_id=a) IS NULL
 OR (SELECT pregunta FROM public.aclaraciones WHERE aclaracion_id=a)<>previa THEN RAISE EXCEPTION 'Perdió evidencia histórica'; END IF;
 IF EXISTS(SELECT 1 FROM public.vinculos_reportes WHERE reporte_id=r) THEN RAISE EXCEPTION 'Inventó asociación'; END IF;
 END IF;
 END LOOP;
END $$;
ROLLBACK;
