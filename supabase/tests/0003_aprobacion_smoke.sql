-- Smoke de 0003_aprobacion.sql. Datos sintéticos; termina en ROLLBACK (no deja nada).
-- Ejecutar completo, con rol administrativo, DESPUÉS de aplicar 0001 a 0011 en un entorno de prueba.
-- Inserta usuarios temporales en auth.users solo para poder crear coordinadores de prueba.
BEGIN;

-- Intenta una llamada y devuelve 'ok' o 'SQLSTATE|mensaje'. Lo que haga la llamada se deshace si falla.
CREATE FUNCTION pg_temp.intenta(p_sql text) RETURNS text LANGUAGE plpgsql AS $$
BEGIN EXECUTE p_sql; RETURN 'ok';
EXCEPTION WHEN OTHERS THEN RETURN SQLSTATE||'|'||SQLERRM; END $$;

-- Aplica un cambio, intenta la llamada y deshace SIEMPRE el cambio. Devuelve 'SQLSTATE|mensaje'
-- (o 'XX999|sin_error' si la llamada no falló, que es lo que NO se espera).
CREATE FUNCTION pg_temp.intenta_con(p_cambio text, p_sql text) RETURNS text LANGUAGE plpgsql AS $$
BEGIN EXECUTE p_cambio; EXECUTE p_sql; RAISE EXCEPTION 'sin_error' USING ERRCODE='XX999';
EXCEPTION WHEN OTHERS THEN RETURN SQLSTATE||'|'||SQLERRM; END $$;

-- Un plan pendiente de revisión, verificado y esperando validación, con su snapshot de entradas.
CREATE FUNCTION pg_temp.fx(u uuid, pol text, s uuid, p uuid, d uuid, v uuid, n text) RETURNS uuid[]
LANGUAGE plpgsql AS $$
DECLARE e uuid:=gen_random_uuid(); i uuid:=gen_random_uuid(); pl uuid:=gen_random_uuid(); ruta uuid:=gen_random_uuid();
  t0 timestamptz:=now()+interval '1 hour'; sol jsonb;
BEGIN
  INSERT INTO public.ejecuciones(ejecucion_id,origen,estado,etapa) VALUES (e,'sintetico','espera_validacion','planificacion');
  INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,periodo_inicio,periodo_fin,primera_deteccion_en,origen)
    VALUES (i,e,s,p,now(),now()+interval '1 hour',now(),'sintetico');
  sol:=jsonb_build_object('datos_version','smoke-'||n,'deposito',jsonb_build_object('deposito_id',d),
    'vehiculos',jsonb_build_array(jsonb_build_object('vehiculo_id',v)),
    'necesidades',jsonb_build_array(jsonb_build_object('incidente_id',i,'punto_atencion_id',p)),
    'puntos',jsonb_build_array(jsonb_build_object('punto_atencion_id',p)),
    'politica',jsonb_build_object('politica_version',pol));
  INSERT INTO public.escenarios_planificacion_v3(ejecucion_id,plan_id,version,solicitud,usuario_revision,motivo)
    VALUES (e,pl,1,sol,u,'smoke aprobacion');
  UPDATE public.escenarios_planificacion_v3 SET cierre_snapshot=public.ra_snapshot_planificacion_v3(e) WHERE ejecucion_id=e;
  INSERT INTO public.planes(plan_id,version,ejecucion_id,datos_version,politica_version,estado,estado_solver,deposito_id,
      solicitud_snapshot,no_atendidos,bloqueos_publicacion,verificado,verificacion,origen,propuesta)
    VALUES (pl,1,e,'smoke-'||n,pol,'pendiente_revision','factible',d,sol,'[]',
      ARRAY['Sin verificación independiente ni aprobación autorizada de esta versión.',
            'Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.',
            'ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.'],
      true,'{"valido":true,"violaciones":[],"comprobaciones":[]}','sintetico','{}');
  INSERT INTO public.rutas(ruta_id,plan_id,version,vehiculo_id,deposito_id,salida_estimada,retorno_estimado)
    VALUES (ruta,pl,1,v,d,now(),now()+interval '3 hours');
  INSERT INTO public.paradas(ruta_id,plan_id,version,incidente_id,punto_atencion_id,orden,litros_asignados,llegada_estimada,inicio_descarga,fin_descarga)
    VALUES (ruta,pl,1,i,p,1,2500,t0,t0,t0+interval '10 minutes');
  RETURN ARRAY[pl,e,i];
END $$;

DO $$
DECLARE
  u uuid:=gen_random_uuid(); u_cons uuid:=gen_random_uuid(); u_inact uuid:=gen_random_uuid();
  s uuid:=gen_random_uuid(); p uuid:=gen_random_uuid(); d uuid:=gen_random_uuid(); v uuid:=gen_random_uuid();
  pol text:='smoke-aprob-'||left(gen_random_uuid()::text,8);
  f uuid[]; f2 uuid[]; pl uuid; e uuid; pl2 uuid; e2 uuid; res jsonb; r text; n1 integer; n2 integer;
  bl text[]:=ARRAY['Sin verificación independiente ni aprobación autorizada de esta versión.',
            'Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.',
            'ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.'];
  dest uuid:=gen_random_uuid(); av uuid:=gen_random_uuid(); ap uuid; t0 timestamptz:=now()+interval '1 hour';
  llamada text;
BEGIN
  -- Permisos: solo el backend ejecuta las RPC.
  IF has_function_privilege('authenticated','public.ra_aprobar_plan(uuid,uuid,integer,text,text,text,text[])','EXECUTE')
     OR has_function_privilege('anon','public.ra_aprobar_plan(uuid,uuid,integer,text,text,text,text[])','EXECUTE')
     OR has_function_privilege('authenticated','public.ra_rechazar_plan(uuid,uuid,integer,text)','EXECUTE') THEN
    RAISE EXCEPTION 'Las RPC de aprobación no deben ser ejecutables desde el navegador';
  END IF;
  IF NOT has_function_privilege('service_role','public.ra_aprobar_plan(uuid,uuid,integer,text,text,text,text[])','EXECUTE')
     OR NOT has_function_privilege('service_role','public.ra_rechazar_plan(uuid,uuid,integer,text)','EXECUTE') THEN
    RAISE EXCEPTION 'Falta permiso del backend';
  END IF;

  -- Catálogo mínimo y usuarios.
  INSERT INTO auth.users(id) VALUES (u),(u_cons),(u_inact);
  INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo)
    VALUES (u,'coordinador',true,'smoke'),(u_cons,'consulta',true,'smoke'),(u_inact,'coordinador',false,'smoke');
  INSERT INTO public.sectores(sector_id,nombre,origen,fuente) VALUES (s,'PRUEBA sector','sintetico','smoke');
  INSERT INTO public.puntos_atencion(punto_atencion_id,sector_id,nombre,origen,fuente) VALUES (p,s,'PRUEBA punto','sintetico','smoke');
  INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
    VALUES (pol,'activa','sintetico',.4,.4,.2,168,500,.5,'Prueba temporal',
            jsonb_build_object('usuario_id',u,'confirmado_en',now(),'motivo','smoke'));
  INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,origen,fuente)
    VALUES (d,'PRUEBA deposito',0,0,'escenario','sintetico','smoke');
  INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,turno_inicio,turno_fin,deposito_id,origen)
    VALUES (v,'PRUEBA vehiculo',10000,now(),now()+interval '6 hours',d,'sintetico');

  f:=pg_temp.fx(u,pol,s,p,d,v,'a'); pl:=f[1]; e:=f[2];
  llamada:=format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a',pol,'motivo smoke',bl::text);

  -- 1. Quién puede aprobar: solo un coordinador activo.
  FOREACH r IN ARRAY ARRAY[u_cons::text,u_inact::text,gen_random_uuid()::text] LOOP
    IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',r,pl,'smoke-a',pol,'m',bl::text)) NOT LIKE '42501|sin_permiso%' THEN
      RAISE EXCEPTION 'Debía rechazar por sin_permiso a %',r;
    END IF;
  END LOOP;

  -- 2. Entradas inválidas.
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a',pol,'   ',bl::text)) NOT LIKE '22023|contrato_invalido%' THEN
    RAISE EXCEPTION 'Motivo vacío debía ser contrato_invalido'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,NULL)',u,pl,'smoke-a',pol,'m')) NOT LIKE '22023|contrato_invalido%' THEN
    RAISE EXCEPTION 'Bloqueos nulos debían ser contrato_invalido'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,gen_random_uuid(),'smoke-a',pol,'m',bl::text)) NOT LIKE '22023|contrato_invalido%' THEN
    RAISE EXCEPTION 'Plan inexistente debía ser contrato_invalido'; END IF;

  -- 3. Versión: lo que la persona revisó ya no es el plan.
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'otra-version',pol,'m',bl::text)) NOT LIKE '40001|version_obsoleta%' THEN
    RAISE EXCEPTION 'Datos_version distinta debía ser version_obsoleta'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a','otra-politica','m',bl::text)) NOT LIKE '40001|version_obsoleta%' THEN
    RAISE EXCEPTION 'Política distinta debía ser version_obsoleta'; END IF;
  r:=pg_temp.intenta_con(format($c$INSERT INTO public.planes(plan_id,version,ejecucion_id,datos_version,politica_version,estado,estado_solver,deposito_id,solicitud_snapshot,origen)
      VALUES (%L,2,%L,'smoke-a2',%L,'pendiente_revision','factible',%L,'{}','sintetico')$c$,pl,e,pol,d),llamada);
  IF r NOT LIKE '40001|version_obsoleta%' THEN RAISE EXCEPTION 'Con una versión más reciente debía ser version_obsoleta: %',r; END IF;

  -- 4. Entradas: si cambió la flota, el depósito o la política desde el cálculo, el plan está obsoleto.
  r:=pg_temp.intenta_con(format('UPDATE public.vehiculos SET capacidad_litros=9000 WHERE vehiculo_id=%L',v),llamada);
  IF r NOT LIKE '40001|version_obsoleta%' THEN RAISE EXCEPTION 'Cambio de flota debía ser version_obsoleta: %',r; END IF;
  r:=pg_temp.intenta_con(format('UPDATE public.depositos SET nombre=''otro'' WHERE deposito_id=%L',d),llamada);
  IF r NOT LIKE '40001|version_obsoleta%' THEN RAISE EXCEPTION 'Cambio de depósito debía ser version_obsoleta: %',r; END IF;
  r:=pg_temp.intenta_con(format('UPDATE public.incidentes SET periodo_fin=periodo_fin+interval ''1 hour'' WHERE incidente_id=%L',f[3]),llamada);
  IF r NOT LIKE '40001|version_obsoleta%' THEN RAISE EXCEPTION 'Cambio de incidente debía ser version_obsoleta: %',r; END IF;

  -- 5. Política y verificación.
  r:=pg_temp.intenta_con(format($c$UPDATE public.politicas_prioridad SET estado='propuesta_demo' WHERE politica_version=%L$c$,pol),llamada);
  IF r NOT LIKE '55000|politica_no_activa%' THEN RAISE EXCEPTION 'Política inactiva debía ser politica_no_activa: %',r; END IF;
  r:=pg_temp.intenta_con(format($c$UPDATE public.planes SET verificado=false,verificacion='{"valido":false,"violaciones":[{"codigo":"capacidad"}]}' WHERE plan_id=%L$c$,pl),llamada);
  IF r NOT LIKE '55000|plan_no_verificado%' THEN RAISE EXCEPTION 'Sin verificación válida debía ser plan_no_verificado: %',r; END IF;
  r:=pg_temp.intenta_con(format($c$UPDATE public.planes SET estado_solver='timeout_sin_solucion' WHERE plan_id=%L$c$,pl),llamada);
  IF r NOT LIKE '55000|plan_no_verificado%' THEN RAISE EXCEPTION 'Solver sin solución debía ser plan_no_verificado: %',r; END IF;
  r:=pg_temp.intenta_con(format($c$UPDATE public.ejecuciones SET estado='espera_revision' WHERE ejecucion_id=%L$c$,e),llamada);
  IF r NOT LIKE '55000|plan_no_verificado%' THEN RAISE EXCEPTION 'Ejecución fuera de validación debía ser plan_no_verificado: %',r; END IF;

  -- 6. Cobertura crítica y bloqueos que una aprobación no puede levantar.
  r:=pg_temp.intenta_con(format($c$UPDATE public.planes SET no_atendidos='[{"clase_prioridad":"critico"}]' WHERE plan_id=%L$c$,pl),llamada);
  IF r NOT LIKE '55000|cobertura_critica_pendiente%' THEN RAISE EXCEPTION 'Crítico sin atender debía bloquear: %',r; END IF;
  r:=pg_temp.intenta_con(format($c$UPDATE public.planes SET bloqueos_publicacion=bloqueos_publicacion||ARRAY['Cobertura crítica o posible urgencia pendiente: escalar y bloquear publicación.'] WHERE plan_id=%L$c$,pl),llamada);
  IF r NOT LIKE '55000|cobertura_critica_pendiente%' THEN RAISE EXCEPTION 'Bloqueo de cobertura crítica debía bloquear: %',r; END IF;
  r:=pg_temp.intenta_con(format($c$UPDATE public.planes SET bloqueos_publicacion=bloqueos_publicacion||ARRAY['Bloqueo desconocido.'] WHERE plan_id=%L$c$,pl),
    format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a',pol,'m',(bl||ARRAY['Bloqueo desconocido.'])::text));
  IF r NOT LIKE '55000|plan_no_verificado: bloqueos que una aprobación no puede levantar%' THEN
    RAISE EXCEPTION 'Un bloqueo ajeno no se levanta aunque la persona lo "reconozca": %',r; END IF;

  -- 7. La persona debe reconocer cada bloqueo explícitamente.
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a',pol,'m',(ARRAY[bl[1],bl[2]])::text)) NOT LIKE '22023|bloqueos_sin_reconocer%' THEN
    RAISE EXCEPTION 'Faltaba reconocer un bloqueo'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a',pol,'m','{}')) NOT LIKE '22023|bloqueos_sin_reconocer%' THEN
    RAISE EXCEPTION 'Sin reconocer nada debía rechazarse'; END IF;

  -- Nada de lo anterior dejó rastro.
  IF (SELECT estado FROM public.planes WHERE plan_id=pl)<>'pendiente_revision'
     OR EXISTS (SELECT 1 FROM public.aprobaciones WHERE plan_id=pl)
     OR (SELECT estado||etapa FROM public.ejecuciones WHERE ejecucion_id=e)<>'espera_validacionplanificacion'
     OR EXISTS (SELECT 1 FROM public.eventos WHERE ejecucion_id=e AND actor_tipo='coordinador') THEN
    RAISE EXCEPTION 'Un rechazo dejó efectos secundarios';
  END IF;

  -- 8. Aprobación correcta.
  res:=public.ra_aprobar_plan(u,pl,1,'smoke-a',pol,'motivo smoke',bl);
  IF res->>'estado'<>'aprobado' OR (res->>'repetido')::boolean OR (res->>'aprobacion_id') IS NULL THEN
    RAISE EXCEPTION 'Respuesta de aprobación incorrecta: %',res; END IF;
  ap:=(res->>'aprobacion_id')::uuid;
  IF NOT EXISTS (SELECT 1 FROM public.planes WHERE plan_id=pl AND estado='aprobado' AND aprobacion_id=ap AND cardinality(bloqueos_publicacion)=0) THEN
    RAISE EXCEPTION 'El plan no quedó aprobado y enlazado'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.aprobaciones WHERE aprobacion_id=ap AND usuario_id=u AND motivo='motivo smoke'
                   AND datos_version='smoke-a' AND politica_version=pol) THEN
    RAISE EXCEPTION 'Aprobación mal registrada'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.ejecuciones WHERE ejecucion_id=e AND estado='pendiente' AND etapa='comunicacion') THEN
    RAISE EXCEPTION 'La ejecución debía pasar a Comunicación'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.eventos WHERE ejecucion_id=e AND actor_tipo='coordinador' AND usuario_id=u
                   AND decision='Aprobar plan' AND jsonb_array_length(detalles->'bloqueos_reconocidos')=3) THEN
    RAISE EXCEPTION 'Falta el evento con los bloqueos reconocidos'; END IF;
  -- El mantenimiento de V2/V3 no debe tocar una ejecución que ya está en Comunicación.
  PERFORM public.ra_mantenimiento_v2();
  IF NOT EXISTS (SELECT 1 FROM public.ejecuciones WHERE ejecucion_id=e AND estado='pendiente' AND etapa='comunicacion') THEN
    RAISE EXCEPTION 'El mantenimiento alteró la ejecución en Comunicación'; END IF;

  -- 9. Repetir la misma aprobación no duplica nada; otra distinta se rechaza.
  SELECT count(*) INTO n1 FROM public.eventos WHERE ejecucion_id=e;
  res:=public.ra_aprobar_plan(u,pl,1,'smoke-a',pol,'motivo smoke',bl);
  IF NOT (res->>'repetido')::boolean OR (res->>'aprobacion_id')::uuid<>ap THEN RAISE EXCEPTION 'Repetir debía devolver el acuse: %',res; END IF;
  SELECT count(*) INTO n2 FROM public.eventos WHERE ejecucion_id=e;
  IF n1<>n2 OR (SELECT count(*) FROM public.aprobaciones WHERE plan_id=pl)<>1 THEN RAISE EXCEPTION 'Repetir duplicó registros'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-a',pol,'otro motivo',bl::text)) NOT LIKE '55000|plan_ya_resuelto%' THEN
    RAISE EXCEPTION 'Una segunda aprobación distinta debía rechazarse'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_rechazar_plan(%L,%L,1,%L)',u,pl,'tarde')) NOT LIKE '55000|plan_ya_resuelto%' THEN
    RAISE EXCEPTION 'No se rechaza un plan ya aprobado'; END IF;

  -- 10. Un plan aprobado así es válido para la bandeja de avisos (0011): se reserva y trae sus datos.
  INSERT INTO public.destinos(destino_id,canal,identificador_externo,autorizado,autorizado_por,autorizado_en,motivo)
    VALUES (dest,'telegram','smoke-chat-'||dest::text,true,u,now(),'smoke');
  INSERT INTO public.suscripciones_sector(destino_id,sector_id,activa,creado_por,motivo) VALUES (dest,s,true,u,'smoke');
  INSERT INTO public.avisos(aviso_id,ejecucion_id,aprobacion_id,plan_id,version,sector_id,punto_atencion_id,destino_id,tipo,ventana_inicio,ventana_fin,litros_asignados,texto,origen)
    VALUES (av,e,ap,pl,1,s,p,dest,'distribucion',t0,t0+interval '10 minutes',2500,'texto','sintetico');
  res:=public.ra_reservar_aviso('smoke-trabajador');
  IF res IS NULL OR (res->>'aviso_id')::uuid<>av THEN RAISE EXCEPTION 'El aviso de un plan aprobado debía poder reservarse: %',res; END IF;

  -- 11. Rechazo: segundo plan.
  f2:=pg_temp.fx(u,pol,s,p,d,v,'b'); pl2:=f2[1]; e2:=f2[2];
  IF pg_temp.intenta(format('SELECT public.ra_rechazar_plan(%L,%L,1,%L)',u_cons,pl2,'m')) NOT LIKE '42501|sin_permiso%' THEN
    RAISE EXCEPTION 'Solo un coordinador activo rechaza'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_rechazar_plan(%L,%L,1,%L)',u,pl2,'  ')) NOT LIKE '22023|contrato_invalido%' THEN
    RAISE EXCEPTION 'El rechazo exige motivo'; END IF;
  res:=public.ra_rechazar_plan(u,pl2,1,'datos no confiables');
  IF res->>'estado'<>'rechazado' OR (res->>'repetido')::boolean THEN RAISE EXCEPTION 'Rechazo incorrecto: %',res; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.planes WHERE plan_id=pl2 AND estado='rechazado' AND aprobacion_id IS NULL)
     OR NOT EXISTS (SELECT 1 FROM public.ejecuciones WHERE ejecucion_id=e2 AND estado='espera_revision')
     OR NOT EXISTS (SELECT 1 FROM public.eventos WHERE ejecucion_id=e2 AND decision='Rechazar plan' AND usuario_id=u AND detalles->>'motivo'='datos no confiables')
     OR EXISTS (SELECT 1 FROM public.aprobaciones WHERE plan_id=pl2) THEN
    RAISE EXCEPTION 'El rechazo dejó un estado incorrecto'; END IF;
  IF NOT (public.ra_rechazar_plan(u,pl2,1,'datos no confiables')->>'repetido')::boolean THEN RAISE EXCEPTION 'Repetir el rechazo debía ser idempotente'; END IF;
  IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl2,'smoke-b',pol,'m',bl::text)) NOT LIKE '55000|plan_ya_resuelto%' THEN
    RAISE EXCEPTION 'No se aprueba un plan rechazado'; END IF;

  RAISE NOTICE 'OK: 0003 aprobación atómica (permisos, versiones, vigencia, verificación, bloqueos, idempotencia, rechazo, integración con 0011)';
END $$;

ROLLBACK;
