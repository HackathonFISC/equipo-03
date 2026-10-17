-- Después de 0015. Ejecutar completo en entorno aislado; mantenimiento global.
-- Datos sintéticos, sin Gemini/Telegram; ROLLBACK revierte todas las filas.
BEGIN;
CREATE FUNCTION pg_temp.crear_ingesta_a4() RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE e uuid:=gen_random_uuid(); r uuid:=gen_random_uuid(); u uuid:=gen_random_uuid();
BEGIN
 INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo) VALUES(u,'telegram','smoke-a4:'||u);
 INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
 VALUES(r,u,'telegram','smoke-a4:'||r,'texto','En P1 faltó agua 48 horas; hay 120 personas.','sintetico');
 INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,origen) VALUES(e,r,'sintetico');
 RETURN e;
END $$;
CREATE FUNCTION pg_temp.error_ingesta_a4(e uuid,t jsonb,v uuid,recuperable boolean,configuracion boolean,estado text,trabajador text DEFAULT 'smoke-a4')
RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
 RETURN public.ra_finalizar_ingesta(e,trabajador,t->'reporte',NULL,
  jsonb_build_object('evento_id',v,'ejecucion_id',e,'agente','ingesta','origen','sintetico','esquema_version','1.0',
   'creado_en','2026-10-17T07:00:00-05:00','decision','Fallo simulado controlado','herramienta','gemini.generateContent',
   'entrada_ids',jsonb_build_array(t->'reporte'->>'reporte_id'),'salida_ids','[]'::jsonb,
   'resultado','Sin efectos externos','duracion_ms',0,'siguiente_estado',estado),
  jsonb_build_object('ejecucion_id',e,'origen','sintetico','codigo','proveedor_no_disponible',
   'mensaje','Error sintético','recuperable',recuperable,
   'campos',CASE WHEN configuracion THEN '["configuracion_gemini"]'::jsonb ELSE '[]'::jsonb END));
END $$;
DO $$
DECLARE e uuid; t jsonb; v uuid; salida jsonb; cantidad integer; n integer; rechazado boolean;
 incierto uuid; correcto uuid; r uuid; ev jsonb; resultado jsonb;
BEGIN
 IF has_function_privilege('anon','public.ra_finalizar_ingesta(uuid,text,jsonb,jsonb,jsonb,jsonb)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_tomar_ingesta(uuid,text)','EXECUTE')
 OR has_function_privilege('authenticated','public.ra_mantenimiento_v2()','EXECUTE')
 OR NOT has_function_privilege('service_role','public.ra_finalizar_ingesta(uuid,text,jsonb,jsonb,jsonb,jsonb)','EXECUTE')
 THEN RAISE EXCEPTION 'Permisos de Ingesta incorrectos'; END IF;
 e:=pg_temp.crear_ingesta_a4();
 FOR cantidad IN 0..2 LOOP
  t:=public.ra_tomar_ingesta(e,'smoke-a4'); v:=gen_random_uuid();
  IF t IS NULL OR (t->'ejecucion'->>'reintentos_ingesta')::integer<>cantidad
  THEN RAISE EXCEPTION 'Toma sin contador persistido'; END IF;
  salida:=pg_temp.error_ingesta_a4(e,t,v,true,false,CASE WHEN cantidad<2 THEN 'espera_validacion' ELSE 'espera_revision' END);
  IF cantidad<2 THEN
   IF salida->>'estado'<>'espera_validacion'
   OR (SELECT reintentos_ingesta FROM public.ejecuciones WHERE ejecucion_id=e)<>cantidad+1
   OR (SELECT proximo_intento_ingesta FROM public.ejecuciones WHERE ejecucion_id=e)<=clock_timestamp()
   OR (SELECT trabajador_id FROM public.ejecuciones WHERE ejecucion_id=e) IS NOT NULL
   THEN RAISE EXCEPTION 'Reintento no programado o reserva retenida'; END IF;
   salida:=pg_temp.error_ingesta_a4(e,t,v,true,false,'espera_validacion');
   IF NOT (salida->>'reintento')::boolean
   OR (SELECT reintentos_ingesta FROM public.ejecuciones WHERE ejecucion_id=e)<>cantidad+1
   OR (SELECT count(*) FROM public.eventos WHERE evento_id=v)<>1
   THEN RAISE EXCEPTION 'Cierre repetido duplicó contador o evento'; END IF;
   PERFORM public.ra_mantenimiento_v2();
   IF public.ra_tomar_ingesta(e,'smoke-temprano') IS NOT NULL
   THEN RAISE EXCEPTION 'Reintento antes del plazo'; END IF;
   UPDATE public.ejecuciones SET proximo_intento_ingesta=clock_timestamp()-interval '1 second' WHERE ejecucion_id=e;
   PERFORM public.ra_mantenimiento_v2();
   IF (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=e)<>'pendiente'
   THEN RAISE EXCEPTION 'No reanudó el reintento confirmado'; END IF;
  ELSE
   IF salida->>'estado'<>'espera_revision'
   OR (SELECT proximo_intento_ingesta FROM public.ejecuciones WHERE ejecucion_id=e) IS NOT NULL
   THEN RAISE EXCEPTION 'Presupuesto agotado no fue a revisión'; END IF;
  END IF;
 END LOOP;
 -- Configuración no consume reintentos por reporte; error no recuperable sigue fallida.
 FOR cantidad IN 0..1 LOOP
  e:=pg_temp.crear_ingesta_a4();t:=public.ra_tomar_ingesta(e,'smoke-a4');
  salida:=pg_temp.error_ingesta_a4(e,t,gen_random_uuid(),cantidad=0,cantidad=0,
    CASE WHEN cantidad=0 THEN 'espera_revision' ELSE 'fallida' END);
  IF (SELECT reintentos_ingesta FROM public.ejecuciones WHERE ejecucion_id=e)<>0
   OR (SELECT proximo_intento_ingesta FROM public.ejecuciones WHERE ejecucion_id=e) IS NOT NULL
  THEN RAISE EXCEPTION 'Configuración/terminal programó reintento'; END IF;
 END LOOP;
 -- Un resultado de persistencia incierto no programa una nueva extracción.
 incierto:=pg_temp.crear_ingesta_a4();t:=public.ra_tomar_ingesta(incierto,'smoke-a4');
 PERFORM public.ra_marcar_error_trabajador(incierto,'smoke-a4');
 PERFORM public.ra_mantenimiento_v2();
 IF (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=incierto)<>'espera_revision'
 OR public.ra_tomar_ingesta(incierto,'smoke-otro') IS NOT NULL
 THEN RAISE EXCEPTION 'Reintentó un resultado incierto'; END IF;
 -- Propietario, snapshot y reserva siguen siendo obligatorios.
 e:=pg_temp.crear_ingesta_a4();t:=public.ra_tomar_ingesta(e,'smoke-a4');
 rechazado:=false;
 BEGIN
  PERFORM pg_temp.error_ingesta_a4(e,t,gen_random_uuid(),true,false,'espera_validacion','otro');
 EXCEPTION WHEN SQLSTATE '55000' THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Aceptó propietario ajeno'; END IF;
 UPDATE public.reportes SET texto='Reporte cambiado durante intento' WHERE reporte_id=(t->'reporte'->>'reporte_id')::uuid;
 rechazado:=false;
 BEGIN
  PERFORM pg_temp.error_ingesta_a4(e,t,gen_random_uuid(),true,false,'espera_validacion');
 EXCEPTION WHEN SQLSTATE '40001' THEN rechazado:=true; END;
 IF NOT rechazado THEN RAISE EXCEPTION 'Aceptó snapshot obsoleto'; END IF;
 -- Éxito tras un reintento conserva interpretación/traza y limpia la programación.
 correcto:=pg_temp.crear_ingesta_a4();t:=public.ra_tomar_ingesta(correcto,'smoke-a4');
 PERFORM pg_temp.error_ingesta_a4(correcto,t,gen_random_uuid(),true,false,'espera_validacion');
 UPDATE public.ejecuciones SET proximo_intento_ingesta=clock_timestamp()-interval '1 second' WHERE ejecucion_id=correcto;
 PERFORM public.ra_mantenimiento_v2();
 t:=public.ra_tomar_ingesta(correcto,'smoke-a4');r:=(t->'reporte'->>'reporte_id')::uuid;
 resultado:=jsonb_build_object('reporte_id',r,'ejecucion_id',correcto,'origen','sintetico','modalidad','texto',
  'interpretacion',jsonb_build_object('requiere_aclaracion',false,'fuera_de_alcance',false,'faltantes','[]'::jsonb),
  'evidencias',jsonb_build_array(jsonb_build_object('reporte_id',r)));
 ev:=jsonb_build_object('evento_id',gen_random_uuid(),'ejecucion_id',correcto,'agente','ingesta','origen','sintetico','esquema_version','1.0',
  'creado_en',now(),'decision','Interpretación validada','resultado','Éxito simulado','duracion_ms',1,
  'entrada_ids',jsonb_build_array(r),'salida_ids',jsonb_build_array(r),'siguiente_estado','pendiente');
 salida:=public.ra_finalizar_ingesta(correcto,'smoke-a4',t->'reporte',resultado,ev,NULL);
 IF salida->>'etapa'<>'territorial'
 OR (SELECT proximo_intento_ingesta FROM public.ejecuciones WHERE ejecucion_id=correcto) IS NOT NULL
 OR (SELECT ultimo_error FROM public.ejecuciones WHERE ejecucion_id=correcto) IS NOT NULL
 THEN RAISE EXCEPTION 'Éxito dejó error o programación'; END IF;
 -- Acuse perdido: el mismo cierre se reconoce; no vuelve a reservar ni extraer.
 salida:=public.ra_finalizar_ingesta(correcto,'smoke-a4',t->'reporte',resultado,ev,NULL);
 IF NOT (salida->>'reintento')::boolean OR public.ra_tomar_ingesta(correcto,'smoke-a4') IS NOT NULL
 THEN RAISE EXCEPTION 'Cierre exitoso repetido reabrió Ingesta'; END IF;
END $$;
ROLLBACK;
