-- Después de 0006. Datos sintéticos; se revierte TODO. No llama Telegram ni Gemini.
BEGIN;
DO $$
DECLARE caso text; u uuid; otro uuid; d uuid; r uuid; e uuid; a uuid; chat text; x jsonb; toma jsonb; ubicacion jsonb; n integer; antes integer; rechazado boolean;
BEGIN
 FOREACH caso IN ARRAY ARRAY['texto','ubicacion','vencida','incierto','reserva','fallido'] LOOP
  u:=gen_random_uuid();otro:=gen_random_uuid();d:=gen_random_uuid();r:=gen_random_uuid();e:=gen_random_uuid();
  chat:='-'||(1000000000000+floor(random()*1000000000000)::bigint)::text;
  INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram',u::text),(otro,'telegram',otro::text);
  -- Un grupo puede carecer de remitente; no tiene autorización para avisos de sector.
  INSERT INTO public.destinos(destino_id,canal,identificador_externo) VALUES(d,'telegram',chat);
  INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen,destino_origen_id)
   VALUES(r,u,'telegram',chat||':1','texto','Falta agua, prueba sintética.','sintetico',d);
  INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen,estado) VALUES(e,r,'sintetico','pendiente');
  -- Cierre de Ingesta y creación de pregunta deben compartir transacción.
  toma:=public.ra_tomar_ingesta(e,'smoke-ingesta');
  x:=public.ra_finalizar_ingesta(e,'smoke-ingesta',toma->'reporte',
   jsonb_build_object('reporte_id',r,'ejecucion_id',e,'origen','sintetico','modalidad','texto',
    'interpretacion',jsonb_build_object('resumen','Falta agua','ubicacion_declarada',NULL,'campos',jsonb_build_object('tipo_problema','sin_suministro'),
      'evidencia_textual',jsonb_build_array('Falta agua'),'requiere_aclaracion',true,'fuera_de_alcance',false,'faltantes',jsonb_build_array('ubicacion')),
    'evidencias',jsonb_build_array(jsonb_build_object('reporte_id',r))),
   jsonb_build_object('evento_id',gen_random_uuid(),'ejecucion_id',e,'agente','ingesta','origen','sintetico','esquema_version','1.0','creado_en',now(),
    'decision','Solicitar datos','resultado','Datos pendientes','duracion_ms',0,'entrada_ids',jsonb_build_array(r),'salida_ids','[]'::jsonb,'siguiente_estado','espera_aclaracion'),NULL);
  IF (SELECT count(*) FROM public.aclaraciones WHERE ejecucion_id=e)<>1 OR x->>'estado'<>'espera_aclaracion' THEN RAISE EXCEPTION 'Ingesta no creó pregunta atómicamente'; END IF;
  x:=public.ra_crear_aclaracion(e,ARRAY['ubicacion'],'¿Dónde falta el agua?');a:=(x->>'aclaracion_id')::uuid;
  IF public.ra_crear_aclaracion(e,ARRAY['ubicacion'],'Otra pregunta')->>'aclaracion_id'<>a::text THEN RAISE EXCEPTION 'Más de una aclaración activa'; END IF;
  toma:=public.ra_reservar_aclaracion('smoke-A');
  IF toma->>'aclaracion_id'<>a::text OR toma->>'chat_id'<>chat OR toma->>'mensaje_externo_id'<>chat||':1' THEN RAISE EXCEPTION 'Reserva o destino incorrecto'; END IF;
  IF public.ra_reservar_aclaracion('smoke-B') IS NOT NULL THEN RAISE EXCEPTION 'Doble reserva o reenvío'; END IF;
  rechazado:=false;
  BEGIN PERFORM public.ra_registrar_envio_aclaracion(a,'otro','enviado','80',NULL); EXCEPTION WHEN SQLSTATE '55000' THEN rechazado:=true; END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Otro trabajador confirmó envío'; END IF;
  IF caso='reserva' THEN
   UPDATE public.aclaraciones SET reserva_hasta=clock_timestamp()-interval '1 second' WHERE aclaracion_id=a;
   PERFORM public.ra_revisar_aclaraciones();
   IF public.ra_reservar_aclaracion('smoke-C') IS NOT NULL THEN RAISE EXCEPTION 'Reserva vencida provocó reenvío'; END IF;
   -- Un acuse tardío conserva el ID, pero jamás reactiva la ejecución.
   PERFORM public.ra_registrar_envio_aclaracion(a,'smoke-A','enviado','80',NULL);
   x:=public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':100',u,'Respuesta tardía',NULL);
   IF x->>'resultado'<>'vencida' OR (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=e)<>'espera_revision' THEN RAISE EXCEPTION 'Reserva vencida aceptó respuesta'; END IF;
   CONTINUE;
  ELSIF caso IN ('incierto','fallido') THEN
   PERFORM public.ra_registrar_envio_aclaracion(a,'smoke-A',caso,NULL,'Fallo simulado');
   IF (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=e)<>'espera_revision' OR public.ra_reservar_aclaracion('smoke-C') IS NOT NULL THEN RAISE EXCEPTION 'Resultado de envío sin revisión'; END IF;
   CONTINUE;
  END IF;
  PERFORM public.ra_registrar_envio_aclaracion(a,'smoke-A','enviado','80',NULL);
  SELECT count(*) INTO antes FROM public.eventos WHERE ejecucion_id=e;
  PERFORM public.ra_registrar_envio_aclaracion(a,'smoke-A','enviado','80',NULL);
  IF (SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)<>antes THEN RAISE EXCEPTION 'Acuse repetido duplicó evento'; END IF;
  IF (SELECT abs(extract(epoch FROM vence_en-enviado_en)-1800) FROM public.aclaraciones WHERE aclaracion_id=a)>1 THEN RAISE EXCEPTION 'Plazo no es 30 minutos'; END IF;
  x:=public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':100',otro,'Respuesta ajena',NULL);
  IF x->>'resultado'<>'autor_distinto' THEN RAISE EXCEPTION 'Aceptó otro autor del grupo'; END IF;
  x:=public.ra_aceptar_respuesta_aclaracion(chat||'0','80',chat||'0:100',u,'Otro chat',NULL);
  IF x->>'resultado'<>'no_encontrada' THEN RAISE EXCEPTION 'Aceptó otro chat'; END IF;
  x:=public.ra_aceptar_respuesta_aclaracion(chat,'999',chat||':100',u,'Otra pregunta',NULL);
  IF x->>'resultado'<>'no_encontrada' THEN RAISE EXCEPTION 'Aceptó otra pregunta'; END IF;
  IF caso='vencida' THEN
   UPDATE public.aclaraciones SET vence_en=clock_timestamp()-interval '1 second' WHERE aclaracion_id=a;
   x:=public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':100',u,'Tarde',NULL);
   IF x->>'resultado'<>'vencida' OR (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=e)<>'espera_revision' THEN RAISE EXCEPTION 'Aceptó respuesta vencida'; END IF;
   CONTINUE;
  END IF;
  rechazado:=false;
  BEGIN PERFORM public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':99',u,repeat('a',4001),NULL); EXCEPTION WHEN SQLSTATE '22023' THEN rechazado:=true; END;
  IF NOT rechazado OR (SELECT respondida_en FROM public.aclaraciones WHERE aclaracion_id=a) IS NOT NULL THEN RAISE EXCEPTION 'Límite de texto o rollback incorrecto'; END IF;
  ubicacion:='{"latitud":8.9,"longitud":-79.7,"fuente":"compartida","precision_metros":12,"representa_punto_atencion":null}';
  IF caso='ubicacion' THEN
   rechazado:=false;
   BEGIN PERFORM public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':99',u,NULL,jsonb_set(ubicacion,'{representa_punto_atencion}','true')); EXCEPTION WHEN SQLSTATE '22023' THEN rechazado:=true; END;
   IF NOT rechazado THEN RAISE EXCEPTION 'Ubicación ciudadana autorizó punto'; END IF;
  END IF;
  x:=public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':100',u,CASE WHEN caso='texto' THEN 'Escuela El Coco' END,CASE WHEN caso='ubicacion' THEN ubicacion END);
  IF x->>'resultado'<>'aceptada' OR (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=e)<>'pendiente' OR (SELECT etapa FROM public.ejecuciones WHERE ejecucion_id=e)<>'ingesta' THEN RAISE EXCEPTION 'Respuesta no reanudó Ingesta'; END IF;
  SELECT count(*) INTO antes FROM public.eventos WHERE ejecucion_id=e;
  x:=public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':100',u,'No sobrescribir',NULL);
  IF x->>'resultado'<>'repetida' OR (SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)<>antes THEN RAISE EXCEPTION 'Reply repetido produjo cambios'; END IF;
  x:=public.ra_aceptar_respuesta_aclaracion(chat,'80',chat||':101',u,'Segunda respuesta',NULL);
  IF x->>'resultado'<>'ya_respondida' THEN RAISE EXCEPTION 'Se sobrescribió una respuesta'; END IF;
  IF (SELECT texto FROM public.reportes WHERE reporte_id=r)<>'Falta agua, prueba sintética.' THEN RAISE EXCEPTION 'Se cambió texto original'; END IF;
 END LOOP;
 IF has_function_privilege('anon','public.ra_aceptar_respuesta_aclaracion(text,text,text,uuid,text,jsonb)','EXECUTE') OR has_function_privilege('authenticated','public.ra_reservar_aclaracion(text)','EXECUTE') THEN RAISE EXCEPTION 'RPC pública'; END IF;
 RAISE NOTICE 'OK: identidad de grupos, reserva exclusiva, seis resultados, acuses/replies idempotentes, ubicación, caducidad y conservación de original.';
END $$;
ROLLBACK;
