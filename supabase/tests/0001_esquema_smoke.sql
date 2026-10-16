-- Emilia: ejecutar DESPUES de 0001, como postgres en el SQL Editor.
-- Todo es sintetico y temporal. ROLLBACK revierte TODOS los INSERT de esta prueba.
-- No prueba Auth real, Storage, 0002/0003, el solver ni los agentes.
BEGIN;
DO $$
DECLARE
  tablas text[] := ARRAY[
    'usuarios_operativos','sectores','puntos_atencion','depositos','vehiculos',
    'politicas_prioridad','remitentes','destinos','suscripciones_sector','reportes',
    'adjuntos','ejecuciones','incidentes','vinculos_reportes','necesidades','planes',
    'rutas','paradas','aprobaciones','avisos','aclaraciones','eventos','confirmaciones_entrega'];
  nombre text;
  s uuid := gen_random_uuid(); p uuid := gen_random_uuid(); r uuid := gen_random_uuid();
  remitente uuid := gen_random_uuid(); e uuid := gen_random_uuid(); i uuid := gen_random_uuid();
  d uuid := gen_random_uuid(); v uuid := gen_random_uuid(); pl uuid := gen_random_uuid();
  evt uuid := gen_random_uuid(); ne uuid := gen_random_uuid(); ruta uuid := gen_random_uuid();
  politica text := 'smoke-' || gen_random_uuid()::text;
  denegado boolean;
  n integer;
BEGIN
  -- 23 tablas, RLS encendido y sin permisos directos para navegador.
  FOREACH nombre IN ARRAY tablas LOOP
    IF to_regclass('public.' || nombre) IS NULL THEN RAISE EXCEPTION 'Falta tabla %', nombre; END IF;
    IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass('public.' || nombre)) THEN
      RAISE EXCEPTION 'Falta RLS en %', nombre;
    END IF;
    IF has_table_privilege('anon', 'public.' || nombre, 'SELECT')
       OR has_table_privilege('anon', 'public.' || nombre, 'INSERT')
       OR has_table_privilege('authenticated', 'public.' || nombre, 'SELECT')
       OR has_table_privilege('authenticated', 'public.' || nombre, 'UPDATE') THEN
      RAISE EXCEPTION 'Permisos de navegador no cerrados en %', nombre;
    END IF;
    IF NOT has_table_privilege('service_role', 'public.' || nombre, 'INSERT') THEN
      RAISE EXCEPTION 'Falta permiso del backend en %', nombre;
    END IF;
  END LOOP;

  INSERT INTO public.sectores(sector_id,nombre,origen,fuente)
    VALUES(s,'PRUEBA TEMPORAL sector','sintetico','smoke rollback');
  INSERT INTO public.puntos_atencion(punto_atencion_id,sector_id,nombre,origen,fuente)
    VALUES(p,s,'PRUEBA TEMPORAL punto','sintetico','smoke rollback');
  IF (SELECT capacidad_recepcion_litros IS NOT NULL FROM public.puntos_atencion WHERE punto_atencion_id = p) THEN
    RAISE EXCEPTION 'Capacidad desconocida no debe convertirse en cero';
  END IF;
  INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo)
    VALUES(remitente,'telegram','smoke:' || remitente::text);
  INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES(r,remitente,'telegram','smoke:mensaje','texto','Reporte sintetico de prueba','sintetico');
  INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen)
    VALUES(e,r,'sintetico');
  IF NOT EXISTS (SELECT 1 FROM public.ejecuciones WHERE ejecucion_id=e AND estado='pendiente') THEN
    RAISE EXCEPTION 'Ejecucion inicial debe estar pendiente';
  END IF;
  denegado := false;
  BEGIN
    INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
      VALUES(remitente,'telegram','smoke:mensaje','texto','Mensaje repetido','sintetico');
  EXCEPTION WHEN unique_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se acepto mensaje duplicado'; END IF;

  denegado := false;
  BEGIN
    INSERT INTO public.puntos_atencion(sector_id,nombre,latitud,longitud,origen,fuente)
      VALUES(s,'Coordenada invalida',91,0,'sintetico','smoke');
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se acepto latitud invalida'; END IF;

  INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,periodo_inicio,periodo_fin,primera_deteccion_en,origen)
    VALUES(i,e,s,p,now(),now()+interval '1 hour',now(),'sintetico');
  INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo)
    VALUES(i,r,'Asociacion sintetica');
  denegado := false;
  BEGIN
    INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo) VALUES(i,r,'Duplicado');
  EXCEPTION WHEN unique_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se acepto vinculo activo duplicado'; END IF;
  UPDATE public.vinculos_reportes SET desvinculado_en=now(),motivo='Correccion sintetica' WHERE reporte_id=r;
  INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo) VALUES(i,r,'Asociacion corregida');
  SELECT count(*) INTO n FROM public.vinculos_reportes WHERE reporte_id=r;
  IF n <> 2 THEN RAISE EXCEPTION 'Se perdio historial de vinculacion'; END IF;

  INSERT INTO public.politicas_prioridad(politica_version,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento)
    VALUES(politica,'sintetico',.5,.3,.2,168,500,.5,'Prueba temporal, no politica activa');
  denegado := false;
  BEGIN
    INSERT INTO public.politicas_prioridad(politica_version,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento)
      VALUES(politica || '-incorrecta','sintetico',.8,.8,.8,168,500,.5,'No debe pasar');
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Pesos que no suman uno aceptados'; END IF;

  INSERT INTO public.necesidades(necesidad_id,ejecucion_id,incidente_id,punto_atencion_id,datos_version,politica_version,
    metodo_demanda,entrada_demanda,primera_deteccion_en,pendientes,origen)
    VALUES(ne,e,i,p,'smoke-1',politica,'directa','{}',now(),ARRAY['demanda por confirmar'],'sintetico');
  IF NOT (SELECT demanda_litros IS NULL AND puntaje IS NULL FROM public.necesidades WHERE necesidad_id=ne) THEN
    RAISE EXCEPTION 'Pendiente no debe tener litros ni puntaje imputados';
  END IF;
  denegado := false;
  BEGIN
    UPDATE public.necesidades SET puntaje=0 WHERE necesidad_id=ne;
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se acepto puntaje para necesidad pendiente'; END IF;

  INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,origen,fuente)
    VALUES(d,'PRUEBA TEMPORAL deposito',0,0,'escenario','sintetico','smoke rollback');
  INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,turno_inicio,turno_fin,deposito_id,origen)
    VALUES(v,'PRUEBA TEMPORAL vehiculo',10000,now(),now()+interval '4 hours',d,'sintetico');
  denegado := false;
  BEGIN
    UPDATE public.vehiculos SET capacidad_litros='NaN'::numeric WHERE vehiculo_id=v;
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se acepto NaN como capacidad'; END IF;
  denegado := false;
  BEGIN
    UPDATE public.vehiculos SET capacidad_litros=-1 WHERE vehiculo_id=v;
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se acepto capacidad negativa'; END IF;

  INSERT INTO public.planes(plan_id,version,ejecucion_id,datos_version,politica_version,deposito_id,solicitud_snapshot,origen)
    VALUES(pl,1,e,'smoke-1',politica,d,'{}','sintetico');
  denegado := false;
  BEGIN
    UPDATE public.planes SET estado='aprobado',estado_solver='factible' WHERE plan_id=pl AND version=1;
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se aprobo plan sin registro/verificacion'; END IF;
  denegado := false;
  BEGIN
    UPDATE public.planes SET no_atendidos='[{"clase_prioridad":"critico"}]' WHERE plan_id=pl AND version=1;
  EXCEPTION WHEN check_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Deficit critico sin bloqueo'; END IF;
  UPDATE public.planes SET no_atendidos='[{"clase_prioridad":"critico"}]',bloqueos_publicacion=ARRAY['critico pendiente'] WHERE plan_id=pl AND version=1;

  INSERT INTO public.rutas(ruta_id,plan_id,version,vehiculo_id,deposito_id,salida_estimada,retorno_estimado)
    VALUES(ruta,pl,1,v,d,now(),now()+interval '1 hour');
  INSERT INTO public.paradas(ruta_id,plan_id,version,incidente_id,punto_atencion_id,orden,litros_asignados,llegada_estimada,inicio_descarga,fin_descarga)
    VALUES(ruta,pl,1,i,p,1,100,now(),now(),now()+interval '10 minutes');
  denegado := false;
  BEGIN
    INSERT INTO public.paradas(ruta_id,plan_id,version,incidente_id,punto_atencion_id,orden,litros_asignados,llegada_estimada,inicio_descarga,fin_descarga)
      VALUES(ruta,pl,1,i,p,2,100,now(),now(),now()+interval '10 minutes');
  EXCEPTION WHEN unique_violation THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Punto repetido en version de plan'; END IF;

  INSERT INTO public.eventos(evento_id,ejecucion_id,agente,actor_tipo,decision,resultado,duracion_ms,origen)
    VALUES(evt,e,'ingesta','agente','Prueba temporal','OK estructural',0,'sintetico');
  denegado := false;
  BEGIN
    UPDATE public.eventos SET resultado='reescrito' WHERE evento_id=evt;
  EXCEPTION WHEN SQLSTATE '55000' THEN denegado := true;
  END;
  IF NOT denegado THEN RAISE EXCEPTION 'Se reescribio evento historico'; END IF;
  RAISE NOTICE 'OK: tablas, permisos iniciales, persistencia V1 y restricciones estructurales comprobadas. ROLLBACK eliminara los datos de prueba.';
END $$;
ROLLBACK;
