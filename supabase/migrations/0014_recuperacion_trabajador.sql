-- Emilia. Requiere 0012; no reenvía avisos ni repite operaciones inciertas.
BEGIN;
CREATE OR REPLACE FUNCTION public.ra_mantenimiento_v2()
RETURNS integer LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
DECLARE x record; n integer; c integer:=0;
BEGIN
 n:=public.ra_revisar_aclaraciones();
 FOR x IN SELECT ejecucion_id FROM public.ejecuciones
 WHERE estado='ejecutando' AND etapa IN ('ingesta','territorial','priorizacion','planificacion','comunicacion')
 AND bloqueada_hasta<=clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
  UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
   ultimo_error=jsonb_build_object('codigo','reserva_trabajador_vencida','mensaje','Revisar resultado antes de reintentar')
   WHERE ejecucion_id=x.ejecucion_id;
  PERFORM public.ra_traza_aclaracion(x.ejecucion_id,'Revisar reserva de trabajador vencida'); c:=c+1;
 END LOOP;
 RETURN n+c;
END $$;

CREATE FUNCTION public.ra_marcar_error_trabajador(p_ejecucion_id uuid,p_trabajador_id text)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
 -- Si el cierre confirmó antes de perderse la respuesta, ya no hay reserva propia.
 -- Tampoco se modifica una reserva tomada por otro trabajador tras un reinicio.
 UPDATE public.ejecuciones SET estado='espera_revision',trabajador_id=NULL,bloqueada_hasta=NULL,
  ultimo_error=jsonb_build_object('codigo','resultado_trabajador_incierto','mensaje','Revisar resultado antes de reintentar')
 WHERE ejecucion_id=p_ejecucion_id AND estado='ejecutando'
 AND trabajador_id=p_trabajador_id
 AND etapa IN ('ingesta','territorial','priorizacion','planificacion','comunicacion');
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM public.ra_traza_aclaracion(p_ejecucion_id,'Revisar resultado incierto del trabajador');
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.ra_mantenimiento_v2() FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.ra_marcar_error_trabajador(uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ra_mantenimiento_v2() TO service_role;
GRANT EXECUTE ON FUNCTION public.ra_marcar_error_trabajador(uuid,text) TO service_role;
NOTIFY pgrst,'reload schema';
COMMIT;
