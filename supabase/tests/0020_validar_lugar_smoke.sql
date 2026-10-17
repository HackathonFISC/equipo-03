-- Solo fixtures aislados. Requiere 0020 y la semilla 01. Termina en ROLLBACK: no deja datos.
BEGIN;
CREATE FUNCTION pg_temp.debe_fallar(llamada text, esperado text) RETURNS void LANGUAGE plpgsql AS $$
DECLARE obtenido text:='sin_error';
BEGIN
  BEGIN EXECUTE llamada; EXCEPTION WHEN OTHERS THEN obtenido:=SQLSTATE; END;
  IF obtenido<>esperado THEN RAISE EXCEPTION 'Se esperaba % y fue %: %',esperado,obtenido,llamada; END IF;
END $$;

DO $$
DECLARE
  u uuid:=gen_random_uuid(); intruso uuid:=gen_random_uuid(); e uuid:=gen_random_uuid(); m uuid:=gen_random_uuid(); r uuid:=gen_random_uuid();
  i uuid:=gen_random_uuid(); i_sin_punto uuid:=gen_random_uuid(); i_sin_reporte uuid:=gen_random_uuid();
  punto public.puntos_atencion%ROWTYPE; ubic jsonb; res jsonb; fila public.incidentes%ROWTYPE; n integer; ev jsonb;
  marcador text:='Validación operativa del lugar y de la necesidad';
BEGIN
  SELECT * INTO punto FROM public.puntos_atencion WHERE activo ORDER BY punto_atencion_id LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'Falta semilla 01'; END IF;
  ubic:=jsonb_build_object('latitud',punto.latitud,'longitud',punto.longitud,'fuente',punto.fuente_ubicacion,'precision_metros',punto.precision_metros,'representa_punto_atencion',punto.representa_punto_atencion);
  INSERT INTO auth.users(id) VALUES(u),(intruso);
  INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES(u,'coordinador',true,'FIXTURE 0020');
  INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(m,'telegram','fixture0020:'||m);
  INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen) VALUES(r,m,'telegram','fixture0020:'||r,'texto','FIXTURE: reporte de prueba','sintetico');
  INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen) VALUES(e,r,'sintetico');
  INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,ubicacion,primera_deteccion_en,periodo_inicio,periodo_fin,origen,faltantes)
  VALUES(i,e,punto.sector_id,punto.punto_atencion_id,ubic,now()-interval '1 hour',now()-interval '2 hours',now()+interval '1 hour','sintetico',ARRAY[marcador,'Otro faltante que no se toca']);
  INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo) VALUES(i,r,'FIXTURE');
  INSERT INTO public.incidentes(incidente_id,ejecucion_id,primera_deteccion_en,periodo_inicio,periodo_fin,origen,faltantes)
  VALUES(i_sin_punto,e,now()-interval '1 hour',now()-interval '2 hours',now()+interval '1 hour','sintetico',ARRAY[marcador]);
  INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,ubicacion,primera_deteccion_en,periodo_inicio,periodo_fin,origen,faltantes)
  VALUES(i_sin_reporte,e,punto.sector_id,punto.punto_atencion_id,ubic,now()-interval '1 hour',now()-interval '2 hours',now()+interval '1 hour','sintetico',ARRAY[marcador])
  ON CONFLICT DO NOTHING;

  -- Rechazos, sin cambiar nada.
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,1,%L)$q$,intruso,i,'Llamé a la junta comunal y confirmaron el punto'),'42501');
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,1,%L)$q$,u,i,'corta'),'22023');
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,1,%L)$q$,u,i,repeat('x',2001)),'22023');
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,7,%L)$q$,u,i,'Llamé a la junta comunal y confirmaron el punto'),'40001');
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,1,%L)$q$,u,gen_random_uuid(),'Llamé a la junta comunal y confirmaron el punto'),'22023');
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,1,%L)$q$,u,i_sin_punto,'Llamé a la junta comunal y confirmaron el punto'),'22023');
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,1,%L)$q$,u,i_sin_reporte,'Llamé a la junta comunal y confirmaron el punto'),'22023');
  SELECT * INTO fila FROM public.incidentes WHERE incidente_id=i;
  IF fila.estado_validacion<>'pendiente' OR fila.version<>1 OR cardinality(fila.faltantes)<>2 THEN RAISE EXCEPTION 'Un rechazo cambió el incidente'; END IF;

  -- Éxito: solo se quita el faltante del lugar y la versión sube.
  res:=public.ra_validar_lugar_v1(u,i,1,'Llamé a la junta comunal y confirmaron el punto');
  SELECT * INTO fila FROM public.incidentes WHERE incidente_id=i;
  IF fila.estado_validacion<>'validada' OR fila.version<>2 THEN RAISE EXCEPTION 'No quedó validada o no subió la versión'; END IF;
  IF fila.faltantes<>ARRAY['Otro faltante que no se toca'] THEN RAISE EXCEPTION 'Se tocaron otros faltantes: %',fila.faltantes; END IF;
  IF res->>'estado_validacion'<>'validada' OR (res->>'version')::int<>2 THEN RAISE EXCEPTION 'Respuesta inesperada: %',res; END IF;

  -- Auditoría: un evento humano con la evidencia y las versiones.
  SELECT count(*) INTO n FROM public.eventos WHERE ejecucion_id=e AND actor_tipo='coordinador' AND usuario_id=u AND decision='Validar lugar del incidente';
  IF n<>1 THEN RAISE EXCEPTION 'Falta el evento de auditoría (%)',n; END IF;
  SELECT detalles INTO ev FROM public.eventos WHERE ejecucion_id=e AND decision='Validar lugar del incidente';
  IF ev->>'evidencia'<>'Llamé a la junta comunal y confirmaron el punto' OR (ev->>'version_anterior')::int<>1 OR (ev->>'version_nueva')::int<>2 THEN
    RAISE EXCEPTION 'Detalles del evento incorrectos: %',ev; END IF;

  -- No se valida dos veces.
  PERFORM pg_temp.debe_fallar(format($q$SELECT public.ra_validar_lugar_v1(%L,%L,2,%L)$q$,u,i,'Llamé a la junta comunal otra vez para repetir'),'55000');
  -- La RPC no la puede llamar un usuario de la API pública.
  IF has_function_privilege('authenticated','public.ra_validar_lugar_v1(uuid,uuid,integer,text)','EXECUTE') THEN RAISE EXCEPTION 'authenticated puede ejecutarla'; END IF;
  IF NOT has_function_privilege('service_role','public.ra_validar_lugar_v1(uuid,uuid,integer,text)','EXECUTE') THEN RAISE EXCEPTION 'service_role no puede ejecutarla'; END IF;
  RAISE NOTICE '0020 validar lugar: correcto';
END $$;
ROLLBACK;
