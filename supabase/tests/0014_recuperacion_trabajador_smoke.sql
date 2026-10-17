-- Ejecutar completo en entorno aislado después de 0014. ROLLBACK.
-- El mantenimiento global también revisa reservas preexistentes dentro de la transacción.
BEGIN;
DO $$
DECLARE e uuid:=gen_random_uuid(); otro uuid:=gen_random_uuid(); cerrado uuid:=gen_random_uuid(); n integer;
BEGIN
 IF has_function_privilege('anon','public.ra_marcar_error_trabajador(uuid,text)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_marcar_error_trabajador(uuid,text)','EXECUTE')
 OR NOT has_function_privilege('service_role','public.ra_marcar_error_trabajador(uuid,text)','EXECUTE')
 THEN RAISE EXCEPTION 'Permisos incorrectos'; END IF;
 INSERT INTO public.ejecuciones(ejecucion_id,origen,estado,etapa,trabajador_id,bloqueada_hasta)
 VALUES(e,'sintetico','ejecutando','comunicacion','smoke',clock_timestamp()-interval '1 second'),
 (otro,'sintetico','ejecutando','comunicacion','otro',clock_timestamp()+interval '1 hour'),
 (cerrado,'sintetico','completada','comunicacion',NULL,NULL);
 IF public.ra_marcar_error_trabajador(otro,'smoke') OR public.ra_marcar_error_trabajador(cerrado,'smoke')
 THEN RAISE EXCEPTION 'Modificó otra reserva o un cierre confirmado'; END IF;
 n:=public.ra_mantenimiento_v2();
 IF (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=e)<>'espera_revision'
 OR (SELECT trabajador_id FROM public.ejecuciones WHERE ejecucion_id=e) IS NOT NULL
 OR (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=otro)<>'ejecutando'
 THEN RAISE EXCEPTION 'Caducidad de Comunicación incorrecta'; END IF;
 IF NOT public.ra_marcar_error_trabajador(otro,'otro')
 OR public.ra_marcar_error_trabajador(otro,'otro')
 THEN RAISE EXCEPTION 'Marca de revisión no idempotente'; END IF;
 IF (SELECT count(*) FROM public.eventos WHERE ejecucion_id=otro)<>1
 THEN RAISE EXCEPTION 'Traza ausente o duplicada'; END IF;
END $$;
ROLLBACK;
