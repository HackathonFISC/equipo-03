-- Requiere 0019. Transcripciones normalizadas a texto; no almacena grabaciones.
BEGIN;
ALTER TABLE public.reportes ADD COLUMN fuente_texto text NOT NULL DEFAULT 'escrito'
 CHECK(fuente_texto IN ('escrito','transcripcion_audio')),
 ADD CONSTRAINT reporte_transcripcion_texto CHECK(fuente_texto<>'transcripcion_audio' OR (modalidad='texto' AND texto IS NOT NULL));
ALTER TABLE public.aclaraciones ADD COLUMN respuesta_fuente_texto text NOT NULL DEFAULT 'escrito'
 CHECK(respuesta_fuente_texto IN ('escrito','transcripcion_audio')),
 ADD CONSTRAINT aclaracion_transcripcion_texto CHECK(respuesta_fuente_texto<>'transcripcion_audio' OR respuesta_texto IS NOT NULL);

CREATE FUNCTION public.ra_aceptar_respuesta_audio(p_chat_id text,p_pregunta_mensaje_id text,p_respuesta_externo_id text,p_remitente_ref uuid,p_texto text,p_ubicacion jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE resultado jsonb;
BEGIN
 IF p_texto IS NULL OR p_ubicacion IS NOT NULL THEN
  RAISE EXCEPTION 'La transcripción requiere texto sin ubicación adjunta' USING ERRCODE='22023';
 END IF;
 -- Reutiliza autor, pregunta, plazo e idempotencia; no crea nuevas identidades.
 resultado:=public.ra_aceptar_respuesta_aclaracion(p_chat_id,p_pregunta_mensaje_id,p_respuesta_externo_id,p_remitente_ref,p_texto,p_ubicacion);
 IF resultado->>'resultado'='aceptada' THEN
  UPDATE public.aclaraciones SET respuesta_fuente_texto='transcripcion_audio'
  WHERE respuesta_externo_id=p_respuesta_externo_id AND respuesta_remitente_ref=p_remitente_ref;
 END IF;
 RETURN resultado;
END $$;
REVOKE ALL ON FUNCTION public.ra_aceptar_respuesta_audio(text,text,text,uuid,text,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_aceptar_respuesta_audio(text,text,text,uuid,text,jsonb) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
