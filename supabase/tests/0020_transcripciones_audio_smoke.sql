-- Audio simulado; no graba ni consulta Gemini/Telegram. Todo se revierte.
BEGIN;
DO $$
DECLARE u uuid:=gen_random_uuid(); otro uuid:=gen_random_uuid(); d uuid:=gen_random_uuid();
 rid uuid:=gen_random_uuid(); eid uuid:=gen_random_uuid(); a uuid; toma jsonb; x jsonb; antes integer;
 chat text:= '-'||(1000000000000+floor(random()*1000000000000)::bigint)::text;
BEGIN
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram',u::text),(otro,'telegram',otro::text);
 INSERT INTO public.destinos(destino_id,canal,identificador_externo) VALUES(d,'telegram',chat);
 INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,fuente_texto,origen,destino_origen_id)
 VALUES(rid,u,'telegram',chat||':1','texto','Falta agua en Escuela El Coco','transcripcion_audio','sintetico',d);
 INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen,estado) VALUES(eid,rid,'sintetico','pendiente');
 toma:=public.ra_tomar_ingesta(eid,'smoke-audio');
 IF toma->'reporte'->>'fuente_texto'<>'transcripcion_audio' THEN RAISE EXCEPTION 'Perdió procedencia de audio'; END IF;
 x:=public.ra_finalizar_ingesta(eid,'smoke-audio',toma->'reporte',
   jsonb_build_object('reporte_id',rid,'ejecucion_id',eid,'origen','sintetico','modalidad','texto',
    'interpretacion',jsonb_build_object('resumen','Falta agua','ubicacion_declarada','Escuela El Coco','campos',jsonb_build_object('tipo_problema','sin_suministro'),
      'evidencia_textual',jsonb_build_array('Falta agua'),'requiere_aclaracion',true,'fuera_de_alcance',false,'faltantes',jsonb_build_array('personas_afectadas')),
    'evidencias',jsonb_build_array(jsonb_build_object('reporte_id',rid,'tipo','audio','descripcion','Transcripción automática'))),
   jsonb_build_object('evento_id',gen_random_uuid(),'ejecucion_id',eid,'agente','ingesta','origen','sintetico','esquema_version','1.0','creado_en',now(),
    'decision','Solicitar datos','resultado','Datos pendientes','duracion_ms',0,'entrada_ids',jsonb_build_array(rid),'salida_ids','[]'::jsonb,'siguiente_estado','espera_aclaracion'),NULL);
 a:=(SELECT aclaracion_id FROM public.aclaraciones WHERE ejecucion_id=eid);
 toma:=public.ra_reservar_aclaracion('smoke-audio-bot');
 IF toma->>'aclaracion_id'<>a::text THEN RAISE EXCEPTION 'No reservó la pregunta'; END IF;
 PERFORM public.ra_registrar_envio_aclaracion(a,'smoke-audio-bot','enviado','80',NULL);
 x:=public.ra_aceptar_respuesta_audio(chat,'80',chat||':100',otro,'Somos 120 personas',NULL);
 IF x->>'resultado'<>'autor_distinto' OR (SELECT respuesta_fuente_texto FROM public.aclaraciones WHERE aclaracion_id=a)<>'escrito'
 THEN RAISE EXCEPTION 'Aceptó audio ajeno o alteró metadatos'; END IF;
 x:=public.ra_aceptar_respuesta_audio(chat,'80',chat||':100',u,'Somos 120 personas',NULL);
 IF x->>'resultado'<>'aceptada' OR (SELECT respuesta_fuente_texto FROM public.aclaraciones WHERE aclaracion_id=a)<>'transcripcion_audio'
 THEN RAISE EXCEPTION 'No persistió fuente de respuesta de audio'; END IF;
 SELECT count(*) INTO antes FROM public.eventos WHERE ejecucion_id=eid;
 x:=public.ra_aceptar_respuesta_audio(chat,'80',chat||':100',u,'Texto distinto en reintento',NULL);
 IF x->>'resultado'<>'repetida' OR (SELECT respuesta_texto FROM public.aclaraciones WHERE aclaracion_id=a)<>'Somos 120 personas'
 OR (SELECT count(*) FROM public.eventos WHERE ejecucion_id=eid)<>antes THEN RAISE EXCEPTION 'Reintento modificó datos o duplicó traza'; END IF;
 toma:=public.ra_tomar_ingesta(eid,'smoke-audio-reingesta');
 IF toma->'aclaraciones'->0->>'respuesta_fuente_texto'<>'transcripcion_audio' THEN RAISE EXCEPTION 'Ingesta perdió fuente de respuesta'; END IF;
 IF has_function_privilege('anon','public.ra_aceptar_respuesta_audio(text,text,text,uuid,text,jsonb)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_aceptar_respuesta_audio(text,text,text,uuid,text,jsonb)','EXECUTE') THEN RAISE EXCEPTION 'RPC audio expuesta'; END IF;
END $$;
ROLLBACK;
