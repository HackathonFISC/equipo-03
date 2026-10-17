-- Solo fixtures aislados. Requiere 0017 y semilla 01. No llama proveedores.
BEGIN;
CREATE FUNCTION pg_temp.lote_rebasado(s jsonb) RETURNS jsonb LANGUAGE sql AS $$
 SELECT jsonb_set(s->'revision'->'lote','{entradas}',(SELECT jsonb_agg(
 jsonb_set(jsonb_set(f,'{solicitud_demanda}',(f->'solicitud_demanda')||jsonb_build_object(
 'ejecucion_id',s->'ejecucion'->'ejecucion_id','creado_en',s->'ejecucion'->'creado_en',
 'datos_version','auto-'||md5((s->'ejecucion'->>'ejecucion_id')||(s->'revision'->>'evento_id')))),
 '{evaluacion}',(f->'evaluacion')||jsonb_build_object('ejecucion_id',s->'ejecucion'->'ejecucion_id',
 'creado_en',s->'ejecucion'->'creado_en','datos_version','auto-'||md5((s->'ejecucion'->>'ejecucion_id')||(s->'revision'->>'evento_id')))) ORDER BY ord)
 FROM jsonb_array_elements(s->'revision'->'lote'->'entradas') WITH ORDINALITY j(f,ord)));
$$;
CREATE FUNCTION pg_temp.caso_lote(cambio text,procedencia public.ra_origen DEFAULT 'sintetico') RETURNS void LANGUAGE plpgsql AS $$
DECLARE u uuid:=gen_random_uuid(); e uuid:=gen_random_uuid(); t uuid:=gen_random_uuid(); i uuid:=gen_random_uuid();
 ensayo uuid:=gen_random_uuid(); r uuid:=gen_random_uuid(); m uuid:=gen_random_uuid(); punto public.puntos_atencion%ROWTYPE; marca jsonb; lote jsonb; f jsonb; s jsonb; salida jsonb;
 pol jsonb; inicial jsonb; numero integer; rechazado boolean:=false;
BEGIN
 SELECT * INTO punto FROM public.puntos_atencion WHERE activo ORDER BY punto_atencion_id LIMIT 1;
 IF NOT FOUND THEN RAISE EXCEPTION 'Falta semilla 01'; END IF;
 INSERT INTO auth.users(id) VALUES(u);
 INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) VALUES(u,'coordinador',true,'FIXTURE 0017');
 marca:=jsonb_build_object('usuario_id',u,'confirmado_en',now()-interval '1 minute','motivo','FIXTURE: revisión humana simulada');
 INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
 VALUES('oeste-prioridad-apoyo-pa-1','activa','sintetico',.4,.4,.2,168,500,.5,'FIXTURE 0017: no modifica la política compartida fuera de ROLLBACK',marca)
 ON CONFLICT(politica_version) DO UPDATE SET estado='activa',peso_duracion=.4,peso_vulnerabilidad=.4,peso_poblacion=.2,confirmacion_activacion=marca;
 SELECT to_jsonb(p)-ARRAY['creado_en','creado_por'] INTO pol FROM public.politicas_prioridad p WHERE politica_version='oeste-prioridad-apoyo-pa-1';
 INSERT INTO public.ensayos_priorizacion_v2(ensayo_id,usuario_id,caso,paquete,motivo) VALUES(ensayo,u,'calculable','{}','FIXTURE aislado');
 INSERT INTO public.ejecuciones(ejecucion_id,etapa,origen,ensayo_priorizacion_id) VALUES(e,'priorizacion',procedencia,ensayo),(t,'priorizacion',procedencia,ensayo);
 INSERT INTO public.incidentes(incidente_id,ejecucion_id,sector_id,punto_atencion_id,primera_deteccion_en,periodo_inicio,periodo_fin,origen,ensayo_priorizacion_id,estado_validacion,ubicacion)
 VALUES(i,e,punto.sector_id,punto.punto_atencion_id,now()-interval '1 hour',now()-interval '2 hours',now()+interval '1 hour',procedencia,ensayo,'validada',jsonb_build_object('latitud',punto.latitud,'longitud',punto.longitud,'fuente',punto.fuente_ubicacion,'representa_punto_atencion',punto.representa_punto_atencion));
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(m,'telegram','fixture0017:'||m);
 INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen) VALUES(r,m,'telegram','fixture0017:'||r,'texto','FIXTURE: reporte de prueba',procedencia);
 INSERT INTO public.vinculos_reportes(incidente_id,reporte_id,motivo) VALUES(i,r,'FIXTURE');
 lote:=$fixture${"politica": {"politica_version": "oeste-prioridad-apoyo-pa-1-v2-f96f836f14df5cc9a12d251976d849da", "estado": "activa", "origen": "sintetico", "peso_duracion": 0.4, "peso_vulnerabilidad": 0.4, "peso_poblacion": 0.2, "tope_horas": 168.0, "tope_personas": 500, "vulnerabilidad_moderada": 0.5, "fundamento": "Pol\u00edtica t\u00e9cnica del proyecto apoyada en normativa paname\u00f1a, no f\u00f3rmula oficial del Estado. Cr\u00edticos confirmados antes de generales. Puntaje intraclase: 40% vulnerabilidad confirmada, 40% tiempo sin suministro y 20% poblaci\u00f3n efectivamente atendida. El antecedente operativo IDAAN/SERTV de 02-04-2026 respalda considerar dependencia sanitaria, sin imponer porcentajes. ASEP AN 1480-Agua y DGNTI-COPANIT 21-2019 con reforma 122/2021 orientan requisitos sanitarios fuera del puntaje; su control no est\u00e1 implementado por score_needs. Topes 168 horas y 500 personas y nivel moderado 0.5 son decisiones de escala del proyecto, sin car\u00e1cter legal. Estado de propuesta para ensayo sint\u00e9tico; uso real requiere validaci\u00f3n del operador y adaptaci\u00f3n del contrato. Ver docs/politica_prioridad_oeste.md. Copia de ensayo con revisi\u00f3n de coordinadora autorizada; cifras ficticias.", "confirmacion_activacion": {"usuario_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "confirmado_en": "2026-10-17T13:47:13.064560Z", "motivo": "ENSAYO SINT\u00c9TICO aprobado exclusivamente para pruebas: FIXTURE LOCAL 0017"}, "criticos_obligatorios": true, "faltantes_fuera_ranking": true, "orden_desempate": "ultima_atencion_luego_incidente_luego_id"}, "entradas": [{"version_incidente": 1, "solicitud_demanda": {"esquema_version": "1.0", "ejecucion_id": "2ab629fc-36a3-5238-b78b-7bc6ad399a00", "creado_en": "2026-10-17T07:00:00-05:00", "origen": "sintetico", "incidente_id": "a2641d17-f634-5200-84cf-35519883250e", "punto_atencion_id": "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e", "datos_version": "oeste-1.0-ensayo-3-v2-calculable-f96f836f14df5cc9a12d251976d849da", "demanda": {"metodo": "formula", "personas_atendidas": 160, "dotacion_litros_persona_dia": 20.0, "dias_cobertura": 1.0, "reserva_utilizable_litros": 200.0, "fuente": "Hip\u00f3tesis dom\u00e9sticas sint\u00e9ticas de parametros.json; no demanda institucional medida.", "confirmacion": {"usuario_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "confirmado_en": "2026-10-17T13:47:13.064560Z", "motivo": "ENSAYO SINT\u00c9TICO aprobado exclusivamente para pruebas: FIXTURE LOCAL 0017"}}, "capacidad_recepcion_litros": 4550.0, "supuestos": ["Cinco personas por familia es una hip\u00f3tesis de tama\u00f1o de grupo, no promedio censal de Panam\u00e1 Oeste.", "20 L/persona/d\u00eda durante un d\u00eda para un ensayo de cobertura dom\u00e9stica b\u00e1sica de emergencia; no cubre todo uso dom\u00e9stico o institucional ni es una cuota legal paname\u00f1a.", "Reserva utilizable igual al agua almacenada solo por hip\u00f3tesis de este ensayo; la calidad real no se ha comprobado.", "Tanques nominales de 5000 L o banco equivalente de dos tanques de 5000 L. No se afirma que existan en estas instalaciones.", "Margen de almacenamiento 5%, caudal de descarga 300 L/min y preparaci\u00f3n 5 min son decisiones arbitrarias de modelado, no normas.", "CASO FICTICIO: grupo domiciliario; nivel de vulnerabilidad inventado para probar ponderaciones.", "Grupos vecinales ficticios asociados a referencias documentales; no son mediciones o diagn\u00f3sticos de las instalaciones."]}, "evaluacion": {"esquema_version": "1.0", "ejecucion_id": "2ab629fc-36a3-5238-b78b-7bc6ad399a00", "creado_en": "2026-10-17T07:00:00-05:00", "origen": "sintetico", "incidente_id": "a2641d17-f634-5200-84cf-35519883250e", "punto_atencion_id": "920f8af3-1bfe-5ab6-a4f2-7fbcb323825e", "datos_version": "oeste-1.0-ensayo-3-v2-calculable-f96f836f14df5cc9a12d251976d849da", "politica_version": "oeste-prioridad-apoyo-pa-1-v2-f96f836f14df5cc9a12d251976d849da", "estado_demanda": "validada", "demanda_litros": 3000.0, "metodo_demanda": "formula", "confirmacion_demanda": {"usuario_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "confirmado_en": "2026-10-17T13:47:13.064560Z", "motivo": "ENSAYO SINT\u00c9TICO aprobado exclusivamente para pruebas: FIXTURE LOCAL 0017"}, "clase_prioridad": "general", "confirmacion_clase": {"usuario_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "confirmado_en": "2026-10-17T13:47:13.064560Z", "motivo": "ENSAYO SINT\u00c9TICO aprobado exclusivamente para pruebas: FIXTURE LOCAL 0017"}, "ventana_atencion": {"inicio": "2026-10-17T08:00:00-05:00", "fin": "2026-10-17T12:00:00-05:00"}, "horas_sin_agua": 72.0, "personas_atendidas": 160, "vulnerabilidad": "moderada", "confirmacion_vulnerabilidad": {"usuario_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "confirmado_en": "2026-10-17T13:47:13.064560Z", "motivo": "ENSAYO SINT\u00c9TICO aprobado exclusivamente para pruebas: FIXTURE LOCAL 0017"}, "ultima_atencion_confirmada_en": null, "primera_deteccion_en": "2026-10-17T07:00:00-05:00", "estado_prioridad": "pendiente", "puntaje": null, "componentes": null, "posicion": null, "pendientes": ["Requiere ejecutar validate_need y score_needs en este ensayo"], "supuestos": ["Cinco personas por familia es una hip\u00f3tesis de tama\u00f1o de grupo, no promedio censal de Panam\u00e1 Oeste.", "20 L/persona/d\u00eda durante un d\u00eda para un ensayo de cobertura dom\u00e9stica b\u00e1sica de emergencia; no cubre todo uso dom\u00e9stico o institucional ni es una cuota legal paname\u00f1a.", "Reserva utilizable igual al agua almacenada solo por hip\u00f3tesis de este ensayo; la calidad real no se ha comprobado.", "Tanques nominales de 5000 L o banco equivalente de dos tanques de 5000 L. No se afirma que existan en estas instalaciones.", "Margen de almacenamiento 5%, caudal de descarga 300 L/min y preparaci\u00f3n 5 min son decisiones arbitrarias de modelado, no normas.", "CASO FICTICIO: grupo domiciliario; nivel de vulnerabilidad inventado para probar ponderaciones.", "Grupos vecinales ficticios asociados a referencias documentales; no son mediciones o diagn\u00f3sticos de las instalaciones."], "requiere_revision_urgente": false}}]}$fixture$::jsonb;
 f:=lote->'entradas'->0;
 f:=jsonb_set(f,'{version_incidente}','1');
 f:=jsonb_set(f,'{solicitud_demanda}',(f->'solicitud_demanda')||jsonb_build_object('ejecucion_id',e,'incidente_id',i,'punto_atencion_id',punto.punto_atencion_id,'origen',procedencia,'datos_version','fixture-0017'));
 f:=jsonb_set(f,'{solicitud_demanda,demanda,confirmacion}',marca);
 f:=jsonb_set(f,'{evaluacion}',(f->'evaluacion')||jsonb_build_object('ejecucion_id',e,'incidente_id',i,'punto_atencion_id',punto.punto_atencion_id,'origen',procedencia,'datos_version','fixture-0017',
 'politica_version','oeste-prioridad-apoyo-pa-1','primera_deteccion_en',now()-interval '1 hour','confirmacion_demanda',marca,'confirmacion_clase',marca,'confirmacion_vulnerabilidad',marca,
 'ventana_atencion',jsonb_build_object('inicio',now(),'fin',now()+interval '1 day')));
 lote:=jsonb_build_object('politica',pol,'entradas',jsonb_build_array(f));
 IF cambio<>'sin_revision' THEN PERFORM public.ra_preparar_priorizacion_v2(e,u,lote); END IF;
 IF cambio='version' THEN UPDATE public.incidentes SET version=version+1 WHERE incidente_id=i; END IF;
 IF cambio='punto' THEN UPDATE public.puntos_atencion SET activo=false WHERE punto_atencion_id=punto.punto_atencion_id; END IF;
 IF cambio='reporte' THEN UPDATE public.reportes SET texto='FIXTURE: texto cambiado sin nueva confirmación' WHERE reporte_id=r; END IF;
 IF cambio='ambito' THEN INSERT INTO public.incidentes(ejecucion_id,sector_id,punto_atencion_id,primera_deteccion_en,periodo_inicio,periodo_fin,origen,ensayo_priorizacion_id) VALUES(e,punto.sector_id,punto.punto_atencion_id,now(),now(),now()+interval '1 hour',procedencia,ensayo); END IF;
 IF cambio='conflicto' THEN UPDATE public.incidentes SET conflictos=ARRAY['Población discrepante'] WHERE incidente_id=i; END IF;
 IF cambio='urgente' THEN UPDATE public.incidentes SET requiere_revision_urgente=true WHERE incidente_id=i; END IF;
 IF cambio='politica' THEN UPDATE public.politicas_prioridad SET peso_duracion=.3,peso_vulnerabilidad=.5 WHERE politica_version='oeste-prioridad-apoyo-pa-1'; END IF;
 IF cambio='inactivo' THEN UPDATE public.usuarios_operativos SET activo=false WHERE usuario_id=u; END IF;
 IF cambio IN ('ventana','faltante','confirmacion','capacidad') THEN
  IF cambio='ventana' THEN lote:=jsonb_set(lote,'{entradas,0,evaluacion,ventana_atencion}',jsonb_build_object('inicio',now()-interval '2 days','fin',now()-interval '1 day')); END IF;
  IF cambio='faltante' THEN lote:=jsonb_set(lote,'{entradas,0,evaluacion,horas_sin_agua}','null'); END IF;
  IF cambio='confirmacion' THEN lote:=jsonb_set(lote,'{entradas,0,evaluacion,confirmacion_clase}','null'); END IF;
  IF cambio='capacidad' THEN lote:=jsonb_set(lote,'{entradas,0,solicitud_demanda,capacidad_recepcion_litros}','null'); END IF;
  UPDATE public.ejecuciones SET entrada_priorizacion=NULL WHERE ejecucion_id=e;
  PERFORM public.ra_preparar_priorizacion_v2(e,u,lote);
 END IF;
 s:=public.ra_contexto_lote_confirmado_v2(t);
 IF cambio='concurrencia' THEN
  UPDATE public.incidentes SET version=version+1 WHERE incidente_id=i;
  BEGIN
   PERFORM public.ra_registrar_lote_confirmado_v2(t,s,pg_temp.lote_rebasado(s));
  EXCEPTION WHEN serialization_failure THEN rechazado:=true; END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Aceptó snapshot anterior al cambio'; END IF;
  RETURN;
 END IF;
 IF cambio='alterado' THEN
  BEGIN
   PERFORM public.ra_registrar_lote_confirmado_v2(t,s,jsonb_set(pg_temp.lote_rebasado(s),'{entradas,0,solicitud_demanda,demanda,litros_declarados}','99999'));
  EXCEPTION WHEN invalid_parameter_value THEN rechazado:=true; END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Aceptó demanda sustituida'; END IF;
  RETURN;
 END IF;
 salida:=public.ra_registrar_lote_confirmado_v2(t,s,pg_temp.lote_rebasado(s));
 IF cambio='valido' THEN
  IF salida->>'estado'<>'preparado' THEN RAISE EXCEPTION 'No preparó lote vigente: %',salida; END IF;
  SELECT entrada_priorizacion INTO inicial FROM public.ejecuciones WHERE ejecucion_id=t;
  IF inicial->'entradas'->0->'evaluacion'->'confirmacion_clase' IS DISTINCT FROM marca
  OR inicial->'entradas'->0->'solicitud_demanda'->'demanda' IS DISTINCT FROM lote->'entradas'->0->'solicitud_demanda'->'demanda'
  OR inicial->'entradas'->0->'evaluacion'->>'origen' IS DISTINCT FROM procedencia::text
  THEN RAISE EXCEPTION 'Inventó confirmaciones, cantidades o procedencia'; END IF;
  SELECT count(*) INTO numero FROM public.eventos WHERE ejecucion_id=t;
  salida:=public.ra_registrar_lote_confirmado_v2(t,s,inicial);
  IF salida->>'estado'<>'existente' OR (SELECT count(*) FROM public.eventos WHERE ejecucion_id=t)<>numero
  THEN RAISE EXCEPTION 'Repetición no idempotente'; END IF;
  IF (SELECT count(*) FROM public.revisiones_lote_v2 WHERE ejecucion_id=t)<>0
  OR NOT EXISTS(SELECT 1 FROM public.eventos WHERE ejecucion_id=t AND detalles->>'preparacion'='automatica' AND detalles->>'revision_ejecucion_id'=e::text)
  THEN RAISE EXCEPTION 'Atribuyó nueva revisión humana o perdió fuente'; END IF;
 ELSE
  IF salida->>'estado'<>'requiere_revision' OR (SELECT entrada_priorizacion FROM public.ejecuciones WHERE ejecucion_id=t) IS NOT NULL
  THEN RAISE EXCEPTION 'No bloqueó %: %',cambio,salida; END IF;
 END IF;
 IF EXISTS(SELECT 1 FROM public.planes WHERE ejecucion_id=t) OR EXISTS(SELECT 1 FROM public.avisos WHERE ejecucion_id=t)
 THEN RAISE EXCEPTION 'El preparador creó plan o aviso'; END IF;
END $$;
DO $$ BEGIN
 IF has_function_privilege('anon','public.ra_registrar_lote_confirmado_v2(uuid,jsonb,jsonb,text)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_contexto_lote_confirmado_v2(uuid)','EXECUTE')
 OR has_table_privilege('authenticated','public.revisiones_lote_v2','SELECT')
 OR NOT has_function_privilege('service_role','public.ra_registrar_lote_confirmado_v2(uuid,jsonb,jsonb,text)','EXECUTE')
 THEN RAISE EXCEPTION 'Permisos incorrectos'; END IF;
END $$;
SELECT pg_temp.caso_lote('valido','real');
SELECT pg_temp.caso_lote('valido','estimado');
SELECT pg_temp.caso_lote(c) FROM unnest(ARRAY['valido','sin_revision','version','punto','reporte','ambito','conflicto','urgente','politica','inactivo','ventana','faltante','confirmacion','capacidad','concurrencia','alterado']) c;
ROLLBACK;
