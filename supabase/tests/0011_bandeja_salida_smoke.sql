-- Smoke de 0011_bandeja_salida.sql. Datos sintéticos; termina en ROLLBACK (no deja nada).
-- Ejecutar con rol administrativo, completo, en un entorno SIN avisos previos (lo comprueba al inicio).
-- Inserta un usuario temporal en auth.users solo para poder crear una aprobación de prueba.
BEGIN;

DO $$
DECLARE
  u uuid:=gen_random_uuid(); s uuid:=gen_random_uuid(); p uuid:=gen_random_uuid();
  rem uuid:=gen_random_uuid(); r uuid:=gen_random_uuid(); e uuid:=gen_random_uuid(); i uuid:=gen_random_uuid();
  pol text:='smoke-bandeja-' || left(gen_random_uuid()::text,8);
  d uuid:=gen_random_uuid(); v uuid:=gen_random_uuid(); ruta uuid:=gen_random_uuid();
  pl uuid:=gen_random_uuid(); ap uuid:=gen_random_uuid(); pl2 uuid:=gen_random_uuid(); ap2 uuid:=gen_random_uuid();
  d1 uuid:=gen_random_uuid(); d2 uuid:=gen_random_uuid(); d3 uuid:=gen_random_uuid();
  a1 uuid:=gen_random_uuid(); a2 uuid:=gen_random_uuid(); a3 uuid:=gen_random_uuid();
  a4 uuid:=gen_random_uuid(); a5 uuid:=gen_random_uuid();
  t0 timestamptz:=now()+interval '1 hour';
  res jsonb; n integer; denegado boolean; fila public.avisos%ROWTYPE;
BEGIN
  IF EXISTS (SELECT 1 FROM public.avisos) THEN
    RAISE EXCEPTION 'Esta prueba exige un entorno sin avisos previos';
  END IF;

  -- Permisos: solo el backend ejecuta las RPC de la bandeja.
  IF has_function_privilege('authenticated','public.ra_reservar_aviso(text)','EXECUTE')
     OR has_function_privilege('anon','public.ra_registrar_envio_aviso(uuid,text,text,text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'Las RPC de avisos no deben ser ejecutables desde el navegador';
  END IF;
  IF NOT has_function_privilege('service_role','public.ra_reservar_aviso(text)','EXECUTE') THEN
    RAISE EXCEPTION 'Falta permiso del backend';
  END IF;

  -- Fixture: un plan aprobado con una parada, y un segundo plan que luego se invalida.
  INSERT INTO auth.users(id) VALUES (u);
  INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES (u,'coordinador',true,'smoke bandeja');
  INSERT INTO public.sectores(sector_id,nombre,origen,fuente) VALUES (s,'PRUEBA sector','sintetico','smoke');
  INSERT INTO public.puntos_atencion(punto_atencion_id,sector_id,nombre,origen,fuente) VALUES (p,s,'PRUEBA punto','sintetico','smoke');
  INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES (rem,'telegram','smoke:'||rem::text);
  INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES (r,rem,'telegram','smoke:bandeja','texto','Reporte sintetico','sintetico');
  INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen) VALUES (e,r,'sintetico');
  INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,periodo_inicio,periodo_fin,primera_deteccion_en,origen)
    VALUES (i,e,s,p,now(),now()+interval '1 hour',now(),'sintetico');
  INSERT INTO public.politicas_prioridad(politica_version,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento)
    VALUES (pol,'sintetico',.5,.3,.2,168,500,.5,'Prueba temporal, no politica activa');
  INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,origen,fuente)
    VALUES (d,'PRUEBA deposito',0,0,'escenario','sintetico','smoke');
  INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,turno_inicio,turno_fin,deposito_id,origen)
    VALUES (v,'PRUEBA vehiculo',10000,now(),now()+interval '6 hours',d,'sintetico');

  INSERT INTO public.planes(plan_id,version,ejecucion_id,datos_version,politica_version,deposito_id,solicitud_snapshot,origen)
    VALUES (pl,1,e,'smoke-1',pol,d,'{}','sintetico'),(pl2,1,e,'smoke-1',pol,d,'{}','sintetico');
  INSERT INTO public.rutas(ruta_id,plan_id,version,vehiculo_id,deposito_id,salida_estimada,retorno_estimado)
    VALUES (ruta,pl,1,v,d,now(),now()+interval '3 hours');
  INSERT INTO public.paradas(ruta_id,plan_id,version,incidente_id,punto_atencion_id,orden,litros_asignados,llegada_estimada,inicio_descarga,fin_descarga)
    VALUES (ruta,pl,1,i,p,1,2500,t0,t0,t0+interval '10 minutes');
  INSERT INTO public.aprobaciones(aprobacion_id,plan_id,version,datos_version,politica_version,usuario_id,motivo)
    VALUES (ap,pl,1,'smoke-1',pol,u,'smoke'),(ap2,pl2,1,'smoke-1',pol,u,'smoke');
  UPDATE public.planes SET estado='aprobado',estado_solver='factible',verificado=true,
         verificacion='{"valido":true}',aprobacion_id=CASE plan_id WHEN pl THEN ap ELSE ap2 END
   WHERE plan_id IN (pl,pl2);

  -- Destinos: d1 y d3 autorizados y suscritos; d2 autorizado pero con suscripción inactiva.
  INSERT INTO public.destinos(destino_id,canal,identificador_externo,autorizado,autorizado_por,autorizado_en,motivo)
    VALUES (d1,'telegram','smoke-chat-'||d1::text,true,u,now(),'smoke'),
           (d2,'telegram','smoke-chat-'||d2::text,true,u,now(),'smoke'),
           (d3,'telegram','smoke-chat-'||d3::text,true,u,now(),'smoke');
  INSERT INTO public.suscripciones_sector(destino_id,sector_id,activa,creado_por,motivo)
    VALUES (d1,s,true,u,'smoke'),(d2,s,false,u,'smoke'),(d3,s,true,u,'smoke');

  -- 1. Sin avisos: no hay nada que reservar.
  IF public.ra_reservar_aviso('smoke-trabajador') IS NOT NULL THEN
    RAISE EXCEPTION 'Sin avisos no debe devolver nada';
  END IF;

  -- Avisos de prueba, creados en orden para que se reserven en ese orden.
  INSERT INTO public.avisos(aviso_id,ejecucion_id,aprobacion_id,plan_id,version,sector_id,punto_atencion_id,destino_id,tipo,ventana_inicio,ventana_fin,litros_asignados,texto,origen,creado_en)
    VALUES (a1,e,ap,pl,1,s,p,d1,'distribucion',t0,t0+interval '10 minutes',2500,'texto del aviso','sintetico',now()-interval '5 minutes'),
           (a2,e,ap,pl,1,s,p,d1,'actualizacion',t0,t0+interval '10 minutes',999,'litros que no coinciden','sintetico',now()-interval '4 minutes'),
           (a3,e,ap,pl,1,s,p,d2,'distribucion',t0,t0+interval '10 minutes',2500,'suscripcion inactiva','sintetico',now()-interval '3 minutes'),
           (a5,e,ap2,pl2,1,s,p,d1,'distribucion',t0,t0+interval '10 minutes',2500,'plan invalidado','sintetico',now()-interval '2 minutes'),
           (a4,e,ap,pl,1,s,p,d3,'distribucion',t0,t0+interval '10 minutes',2500,'reserva que vence','sintetico',now()-interval '1 minute');
  UPDATE public.planes SET estado='invalidado' WHERE plan_id=pl2;

  -- 2. Primera reserva: a1, vigente. Trae solo lo necesario para redactar el mensaje.
  res:=public.ra_reservar_aviso('smoke-trabajador');
  IF res IS NULL OR (res->>'aviso_id')::uuid<>a1 THEN RAISE EXCEPTION 'Debía reservar el primer aviso vigente'; END IF;
  IF res->>'chat_id'<>'smoke-chat-'||d1::text OR (res->>'litros_asignados')::numeric<>2500
     OR res->>'punto_nombre'<>'PRUEBA punto' OR res->>'tipo'<>'distribucion' THEN
    RAISE EXCEPTION 'Datos de reserva incorrectos: %',res;
  END IF;
  IF res ? 'texto' OR res ? 'aprobacion_id' OR res ? 'ejecucion_id' THEN
    RAISE EXCEPTION 'La reserva no debe exponer texto libre ni ids internos';
  END IF;
  SELECT * INTO fila FROM public.avisos WHERE aviso_id=a1;
  IF fila.intentos<>1 OR fila.trabajador_id<>'smoke-trabajador' OR fila.estado_envio<>'pendiente' THEN
    RAISE EXCEPTION 'Estado incorrecto tras reservar';
  END IF;

  -- 3. Los que dejaron de ser vigentes se cancelan con motivo y no se reservan: a2, a3 y a5 quedan cancelados.
  --    La siguiente reserva salta directo a a4.
  res:=public.ra_reservar_aviso('smoke-trabajador-2');
  IF res IS NULL OR (res->>'aviso_id')::uuid<>a4 THEN RAISE EXCEPTION 'Debía saltar a los cancelados y reservar a4: %',res; END IF;
  IF (SELECT estado_envio FROM public.avisos WHERE aviso_id=a2)<>'cancelado'
     OR (SELECT ultimo_error FROM public.avisos WHERE aviso_id=a2) NOT LIKE '%litros o la ventana%' THEN
    RAISE EXCEPTION 'a2 debía cancelarse por litros distintos';
  END IF;
  IF (SELECT estado_envio FROM public.avisos WHERE aviso_id=a3)<>'cancelado'
     OR (SELECT ultimo_error FROM public.avisos WHERE aviso_id=a3) NOT LIKE '%suscripción%' THEN
    RAISE EXCEPTION 'a3 debía cancelarse por suscripción inactiva';
  END IF;
  IF (SELECT estado_envio FROM public.avisos WHERE aviso_id=a5)<>'cancelado'
     OR (SELECT ultimo_error FROM public.avisos WHERE aviso_id=a5) NOT LIKE '%ya no está aprobado%' THEN
    RAISE EXCEPTION 'a5 debía cancelarse porque el plan se invalidó';
  END IF;

  -- 4. Nada más por reservar mientras a1 y a4 estén en curso.
  IF public.ra_reservar_aviso('smoke-trabajador') IS NOT NULL THEN
    RAISE EXCEPTION 'Un aviso reservado no debe reservarse dos veces';
  END IF;

  -- 5. Registrar el envío: solo quien reservó; formato válido; idempotente.
  denegado:=false;
  BEGIN PERFORM public.ra_registrar_envio_aviso(a1,'otro-trabajador','enviado','101',NULL);
  EXCEPTION WHEN SQLSTATE '55000' THEN denegado:=true; END;
  IF NOT denegado THEN RAISE EXCEPTION 'Aceptó el resultado de otro trabajador'; END IF;
  denegado:=false;
  BEGIN PERFORM public.ra_registrar_envio_aviso(a1,'smoke-trabajador','enviado','no-es-numero',NULL);
  EXCEPTION WHEN SQLSTATE '22023' THEN denegado:=true; END;
  IF NOT denegado THEN RAISE EXCEPTION 'Aceptó un ID de mensaje inválido'; END IF;
  denegado:=false;
  BEGIN PERFORM public.ra_registrar_envio_aviso(a1,'smoke-trabajador','fallido',NULL,NULL);
  EXCEPTION WHEN SQLSTATE '22023' THEN denegado:=true; END;
  IF NOT denegado THEN RAISE EXCEPTION 'Aceptó fallido sin motivo'; END IF;

  PERFORM public.ra_registrar_envio_aviso(a1,'smoke-trabajador','enviado','101',NULL);
  SELECT * INTO fila FROM public.avisos WHERE aviso_id=a1;
  IF fila.estado_envio<>'enviado' OR fila.proveedor_mensaje_id<>'101' OR fila.enviado_en IS NULL THEN
    RAISE EXCEPTION 'No registró el envío';
  END IF;
  PERFORM public.ra_registrar_envio_aviso(a1,'smoke-trabajador','enviado','101',NULL); -- repetir: seguro
  denegado:=false;
  BEGIN PERFORM public.ra_registrar_envio_aviso(a1,'smoke-trabajador','enviado','999',NULL);
  EXCEPTION WHEN SQLSTATE '55000' THEN denegado:=true; END;
  IF NOT denegado THEN RAISE EXCEPTION 'Sobrescribió un envío ya registrado'; END IF;

  -- 6. Reserva vencida sin resultado: pasa a incierto (no se reenvía) y se ve en la traza.
  UPDATE public.avisos SET reserva_hasta=clock_timestamp()-interval '1 second' WHERE aviso_id=a4;
  n:=public.ra_revisar_avisos();
  IF n<>1 OR (SELECT estado_envio FROM public.avisos WHERE aviso_id=a4)<>'incierto' THEN
    RAISE EXCEPTION 'La reserva vencida debía quedar incierta';
  END IF;
  IF public.ra_reservar_aviso('smoke-trabajador') IS NOT NULL THEN
    RAISE EXCEPTION 'Un aviso incierto no debe reservarse otra vez';
  END IF;
  -- El acuse tardío de quien envió sí resuelve el incierto con el ID real.
  PERFORM public.ra_registrar_envio_aviso(a4,'smoke-trabajador-2','enviado','202',NULL);
  IF (SELECT estado_envio FROM public.avisos WHERE aviso_id=a4)<>'enviado' THEN
    RAISE EXCEPTION 'El acuse tardío debía resolver el incierto';
  END IF;

  -- 7. Quedó traza del sistema para las cancelaciones y los envíos.
  SELECT count(*) INTO n FROM public.eventos WHERE ejecucion_id=e AND actor_tipo='sistema'
    AND decision IN ('Aviso cancelado antes de enviar','Registrar envío de aviso','Aviso incierto por reserva vencida');
  -- 3 cancelaciones + envío de a1 + incierto de a4 + acuse tardío de a4; repetir un envío no añade eventos.
  IF n<>6 THEN RAISE EXCEPTION 'Traza esperada: 6 eventos, hay %',n; END IF;

  RAISE NOTICE 'OK: bandeja de salida';
END $$;

ROLLBACK;
