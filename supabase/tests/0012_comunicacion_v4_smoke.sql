-- Smoke V4 0012. Datos sintéticos; termina en ROLLBACK (no deja nada).
-- Ejecutar completo tras 0012. Transacción sintética, sin Telegram; termina en ROLLBACK.
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


CREATE TEMP TABLE evidencia_estado_sector_v4(datos jsonb);
DO $$
DECLARE u uuid:=gen_random_uuid(); s uuid:=gen_random_uuid(); pu uuid:=gen_random_uuid(); extra uuid:=gen_random_uuid();
 d uuid:=gen_random_uuid(); v uuid:=gen_random_uuid(); dest uuid:=gen_random_uuid(); externo uuid:=gen_random_uuid();
 pol text:='smoke-v4-'||gen_random_uuid(); f uuid[]; pl uuid; e uuid; r jsonb; r2 jsonb; previo integer; av uuid; papel text;
 bl text[]:=ARRAY['Sin verificación independiente ni aprobación autorizada de esta versión.',
 'Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.',
 'ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.'];
BEGIN
 FOREACH papel IN ARRAY ARRAY['anon','authenticated'] LOOP
 IF has_function_privilege(papel,'public.ra_comunicar_plan_v4(uuid,text)','EXECUTE')
 OR has_function_privilege(papel,'public.ra_estado_sector_v4(uuid)','EXECUTE')
 OR has_function_privilege(papel,'public.ra_configurar_destino_ensayo_v4(uuid,uuid,boolean,text)','EXECUTE')
 THEN RAISE EXCEPTION 'Permiso de navegador indebido'; END IF;
 END LOOP;
 INSERT INTO auth.users(id) VALUES(u);
 INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES(u,'coordinador',true,'Smoke V4');
 INSERT INTO public.sectores(sector_id,nombre,origen,fuente) VALUES(s,'Sector V4','sintetico','Smoke');
 INSERT INTO public.puntos_atencion(punto_atencion_id,sector_id,nombre,origen,fuente)
 VALUES(pu,s,'Punto V4','sintetico','Smoke'),(extra,s,'Punto sin asignación','sintetico','Smoke');
 INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
 VALUES(pol,'activa','sintetico',.4,.4,.2,168,500,.5,'Smoke',jsonb_build_object('usuario_id',u,'confirmado_en',now(),'motivo','Smoke'));
 INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,origen,fuente) VALUES(d,'Depósito V4',0,0,'escenario','sintetico','Smoke');
 INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,turno_inicio,turno_fin,deposito_id,origen) VALUES(v,'Camión V4',10000,now(),now()+interval '6 hours',d,'sintetico');
 f:=pg_temp.fx(u,pol,s,pu,d,v,'v4');pl:=f[1];e:=f[2];
 r:=public.ra_estado_sector_v4(s);
 IF r->>'estado'<>'sin_plan_vigente' OR jsonb_array_length(r->'puntos')<>2 THEN RAISE EXCEPTION 'Sin plan debe mostrar todos los puntos'; END IF;
 IF pg_temp.intenta(format('SELECT public.ra_seleccionar_plan_sector_v4(%L,%L,%L,1,%L)',u,s,pl,'Sin aprobar')) NOT LIKE '40001|version_obsoleta%' THEN RAISE EXCEPTION 'Selección sin aprobación permitida'; END IF;
 PERFORM public.ra_aprobar_plan(u,pl,1,'smoke-v4',pol,'Solo ensayo',bl);
 r:=public.ra_comunicar_plan_v4(e,'prueba');
 IF r->>'codigo'<>'seleccion_sector_pendiente' THEN RAISE EXCEPTION 'Selección humana no exigida: %',r; END IF;
 IF pg_temp.intenta(format('SELECT public.ra_seleccionar_plan_sector_v4(%L,%L,%L,1,%L)',gen_random_uuid(),s,pl,'Sin rol')) NOT LIKE '42501|sin_permiso%' THEN RAISE EXCEPTION 'Selección sin rol permitida'; END IF;
 PERFORM public.ra_seleccionar_plan_sector_v4(u,s,pl,1,'Vigente solo para prueba');
 r:=public.ra_estado_sector_v4(s);
 IF r->>'estado'<>'con_plan_vigente' THEN RAISE EXCEPTION 'No muestra plan seleccionado'; END IF;
 IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(r->'puntos') p WHERE p->>'punto_atencion_id'=extra::text AND p->>'estado'='sin_asignacion' AND p->'litros_asignados'='null'::jsonb AND p->'ventana_estimada'='null'::jsonb) THEN RAISE EXCEPTION 'Punto no asignado omitido o convertido a cero'; END IF;
 INSERT INTO evidencia_estado_sector_v4 VALUES(r);
 r:=public.ra_comunicar_plan_v4(e,'prueba');
 IF r->>'codigo'<>'destino_autorizado_pendiente' THEN RAISE EXCEPTION 'Destino autorizado no exigido'; END IF;
 INSERT INTO public.destinos(destino_id,canal,identificador_externo,autorizado,autorizado_por,autorizado_en,motivo)
 VALUES(dest,'telegram','smoke-v4-'||dest,true,u,now(),'Solo chat de ensayo'),(externo,'telegram','smoke-v4-'||externo,true,u,now(),'Destino comunitario que debe excluirse');
 INSERT INTO public.suscripciones_sector(destino_id,sector_id,activa) VALUES(dest,s,true),(externo,s,true);
 PERFORM public.ra_configurar_destino_ensayo_v4(u,dest,false,'Deshabilitado inicialmente');
 UPDATE public.ejecuciones SET estado='pendiente' WHERE ejecucion_id=e;
 r:=public.ra_comunicar_plan_v4(e,'prueba');
 IF r->>'codigo'<>'destino_autorizado_pendiente' OR EXISTS(SELECT 1 FROM public.avisos WHERE ejecucion_id=e) THEN RAISE EXCEPTION 'Plan sintético enviado a destino normal/deshabilitado'; END IF;
 PERFORM public.ra_configurar_destino_ensayo_v4(u,dest,true,'Habilitar exclusivamente prueba');
 r:=public.ra_comunicar_plan_v4(e,'prueba');
 IF r->>'estado'<>'completada' OR (r->>'avisos_creados')::int<>1 THEN RAISE EXCEPTION 'No crea un aviso: %',r; END IF;
 IF EXISTS(SELECT 1 FROM public.avisos WHERE ejecucion_id=e AND destino_id=externo) THEN RAISE EXCEPTION 'Aviso sintético a destino comunitario'; END IF;
 SELECT count(*) INTO previo FROM public.eventos WHERE ejecucion_id=e;
 r2:=public.ra_comunicar_plan_v4(e,'otro');
 IF r2->>'repetido'<>'true' OR (SELECT count(*) FROM public.eventos WHERE ejecucion_id=e)<>previo
 OR (SELECT count(*) FROM public.avisos WHERE ejecucion_id=e)<>1 THEN RAISE EXCEPTION 'Duplicó comunicación'; END IF;
 UPDATE public.paradas SET estado='iniciada' WHERE plan_id=pl AND version=1;
 IF NOT public.ra_plan_valido_v4(pl,1) THEN RAISE EXCEPTION 'Actualizar solo estado invalidó la asignación'; END IF;
 r:=public.ra_reservar_aviso('bot-prueba');
 IF r->>'punto_nombre' NOT LIKE 'ENSAYO SINTÉTICO, SIN ENTREGA REAL%' THEN RAISE EXCEPTION 'Falta etiqueta de ensayo para plantilla del bot: %',r; END IF;
 av:=(r->>'aviso_id')::uuid;
 PERFORM public.ra_registrar_envio_aviso(av,'bot-prueba','incierto',NULL,'Simulación de timeout');
 IF public.ra_reservar_aviso('otro') IS NOT NULL THEN RAISE EXCEPTION 'Reenvió incierto'; END IF;
 -- Nuevo cierre y aviso para comprobar invalidación posterior sin reescribir el histórico.
 DELETE FROM public.cierres_comunicacion_v4 WHERE ejecucion_id=e;
 UPDATE public.ejecuciones SET estado='pendiente',etapa='comunicacion' WHERE ejecucion_id=e;
 -- Conservamos aviso incierto; debe seguir sin ser reservable incluso al cambiar las entradas.
 UPDATE public.vehiculos SET capacidad_litros=9000 WHERE vehiculo_id=v;
 IF (SELECT estado FROM public.planes WHERE plan_id=pl AND version=1)<>'invalidado' THEN RAISE EXCEPTION 'No invalida al cambiar flota'; END IF;
 r:=public.ra_estado_sector_v4(s);
 IF r->>'estado'<>'sin_plan_vigente' OR EXISTS(SELECT 1 FROM jsonb_array_elements(r->'puntos') p WHERE p->'litros_asignados'<>'null'::jsonb) THEN RAISE EXCEPTION 'Muestra litros históricos'; END IF;
 IF public.ra_reservar_aviso('otro') IS NOT NULL THEN RAISE EXCEPTION 'Reservó plan obsoleto'; END IF;
 IF (SELECT estado_envio FROM public.avisos WHERE aviso_id=av)<>'incierto' THEN RAISE EXCEPTION 'Borró incertidumbre histórica'; END IF;
 IF pg_temp.intenta(format('SELECT public.ra_aprobar_plan(%L,%L,1,%L,%L,%L,%L::text[])',u,pl,'smoke-v4',pol,'Solo ensayo',bl::text))='ok' THEN RAISE EXCEPTION 'Aceptó aprobación obsoleta'; END IF;
END $$;
SELECT datos FROM evidencia_estado_sector_v4;
ROLLBACK;
