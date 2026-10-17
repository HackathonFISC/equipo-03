-- Requiere 0020_transcripciones_audio. Conserva solo descripción y texto adjunto.
BEGIN;
ALTER TABLE public.reportes DROP CONSTRAINT reportes_fuente_texto_check;
ALTER TABLE public.reportes ADD CONSTRAINT reportes_fuente_texto_check
 CHECK(fuente_texto IN ('escrito','transcripcion_audio','descripcion_imagen'));
ALTER TABLE public.reportes ADD CONSTRAINT reporte_imagen_texto
 CHECK(fuente_texto<>'descripcion_imagen' OR (modalidad='texto' AND texto IS NOT NULL));
ALTER TABLE public.aclaraciones DROP CONSTRAINT aclaraciones_respuesta_fuente_texto_check;
ALTER TABLE public.aclaraciones ADD CONSTRAINT aclaraciones_respuesta_fuente_texto_check
 CHECK(respuesta_fuente_texto IN ('escrito','transcripcion_audio','descripcion_imagen'));
ALTER TABLE public.aclaraciones ADD CONSTRAINT aclaracion_imagen_texto
 CHECK(respuesta_fuente_texto<>'descripcion_imagen' OR respuesta_texto IS NOT NULL);

CREATE FUNCTION public.ra_aceptar_respuesta_imagen(p_chat_id text,p_pregunta_mensaje_id text,p_respuesta_externo_id text,p_remitente_ref uuid,p_texto text,p_ubicacion jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE resultado jsonb;
BEGIN
 IF p_texto IS NULL OR p_ubicacion IS NOT NULL THEN
  RAISE EXCEPTION 'La descripción de foto requiere texto sin ubicación adjunta' USING ERRCODE='22023';
 END IF;
 -- Reutiliza autor, pregunta, plazo e idempotencia; no crea nuevas identidades.
 resultado:=public.ra_aceptar_respuesta_aclaracion(p_chat_id,p_pregunta_mensaje_id,p_respuesta_externo_id,p_remitente_ref,p_texto,p_ubicacion);
 IF resultado->>'resultado'='aceptada' THEN
  UPDATE public.aclaraciones SET respuesta_fuente_texto='descripcion_imagen'
  WHERE respuesta_externo_id=p_respuesta_externo_id AND respuesta_remitente_ref=p_remitente_ref;
 END IF;
 RETURN resultado;
END $$;
REVOKE ALL ON FUNCTION public.ra_aceptar_respuesta_imagen(text,text,text,uuid,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_aceptar_respuesta_imagen(text,text,text,uuid,text,jsonb) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
