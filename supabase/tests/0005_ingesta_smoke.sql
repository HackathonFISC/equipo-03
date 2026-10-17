-- Después de 0001 y 0005. Sintético, sin Gemini. ROLLBACK elimina las filas.
BEGIN;
DO $$
DECLARE
  caso text; remitente uuid; reporte uuid; ejecucion uuid; evento uuid;
  toma jsonb; salida jsonb; traza jsonb; error_json jsonb; respuesta jsonb;
  rechazado boolean; n integer; estado_esperado text; etapa_esperada text;
BEGIN
  FOREACH caso IN ARRAY ARRAY['valido','aclaracion','fuera','fallo','rollback','cambio','reserva','vencida'] LOOP
    remitente:=gen_random_uuid(); reporte:=gen_random_uuid(); ejecucion:=gen_random_uuid(); evento:=gen_random_uuid();
    INSERT INTO public.remitentes(remitente_ref,canal,identificador_externo)
      VALUES(remitente,'telegram','smoke-ingesta:'||remitente::text);
    INSERT INTO public.reportes(reporte_id,remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
      VALUES(reporte,remitente,'telegram','smoke:'||reporte::text,'texto','En P1: 48 horas sin agua, 120 personas.','sintetico');
    INSERT INTO public.ejecuciones(ejecucion_id,reporte_id,clave_idempotencia,origen)
      VALUES(ejecucion,reporte,'ingesta:'||reporte::text,'sintetico');
    toma:=public.ra_tomar_ingesta(ejecucion,'smoke-A');
    IF toma IS NULL OR toma->'ejecucion'->>'estado'<>'ejecutando' THEN
      RAISE EXCEPTION 'No se tomó el trabajo';
    END IF;
    IF public.ra_tomar_ingesta(ejecucion,'smoke-B') IS NOT NULL THEN
      RAISE EXCEPTION 'Dos trabajadores tomaron el mismo trabajo';
    END IF;
    estado_esperado:='pendiente'; etapa_esperada:='territorial'; error_json:=NULL;
    IF caso='aclaracion' THEN estado_esperado:='espera_aclaracion'; etapa_esperada:='ingesta'; END IF;
    IF caso='fuera' THEN estado_esperado:='completada'; etapa_esperada:='terminada'; END IF;
    salida:=jsonb_build_object(
      'esquema_version','1.0','ejecucion_id',ejecucion,'reporte_id',reporte,'origen','sintetico',
      'modalidad','texto','creado_en',now(),
      'interpretacion',jsonb_build_object('resumen','Prueba sintética','ubicacion_declarada','P1',
        'campos',jsonb_build_object('horas_sin_agua',48,'personas_afectadas',120,
          'vulnerabilidad_declarada',NULL,'institucion_declarada',NULL,'tipo_problema','sin_suministro'),
        'evidencia_textual',jsonb_build_array('48 horas sin agua'),'faltantes',
          CASE WHEN caso='aclaracion' THEN '["dato pendiente"]'::jsonb ELSE '[]'::jsonb END,
        'requiere_aclaracion',caso='aclaracion','fuera_de_alcance',caso='fuera'),
      'evidencias',jsonb_build_array(jsonb_build_object('evidencia_id',gen_random_uuid(),
        'reporte_id',reporte,'tipo','texto','referencia','reportes/'||reporte::text||'/texto',
        'descripcion','Texto sintético persistido','campos_respaldados',jsonb_build_array('entrada.texto'))));
    IF caso='fallo' THEN
      estado_esperado:='fallida'; etapa_esperada:='ingesta'; salida:=NULL;
      error_json:=jsonb_build_object('esquema_version','1.0','ejecucion_id',ejecucion,'creado_en',now(),
        'origen','sintetico','codigo','proveedor_no_disponible','mensaje','Prueba de fallo controlado',
        'recuperable',true,'campos','[]'::jsonb);
    END IF;
    traza:=jsonb_build_object('evento_id',evento,'ejecucion_id',ejecucion,'esquema_version','1.0',
      'creado_en',now(),'origen','sintetico','agente','ingesta','decision','Decisión sintética',
      'herramienta','gemini.generateContent','entrada_ids',jsonb_build_array(reporte),
      'salida_ids','[]'::jsonb,'resultado','Prueba local','duracion_ms',12,'siguiente_estado',estado_esperado);

    IF caso IN ('cambio','reserva','vencida') THEN
      IF caso='cambio' THEN UPDATE public.reportes SET texto='Editado durante la extracción' WHERE reporte_id=reporte; END IF;
      IF caso='vencida' THEN UPDATE public.ejecuciones SET bloqueada_hasta=now()-interval '1 second' WHERE ejecucion_id=ejecucion; END IF;
      rechazado:=false;
      BEGIN
        PERFORM public.ra_finalizar_ingesta(ejecucion,CASE WHEN caso='reserva' THEN 'otro-trabajador' ELSE 'smoke-A' END,
          toma->'reporte',salida,traza,error_json);
      EXCEPTION WHEN SQLSTATE '40001' OR SQLSTATE '55000' THEN rechazado:=true;
      END;
      IF NOT rechazado THEN RAISE EXCEPTION 'No se bloqueó el caso %',caso; END IF;
      IF EXISTS(SELECT 1 FROM public.eventos WHERE evento_id=evento) THEN RAISE EXCEPTION 'Cierre rechazado dejó evento'; END IF;
      CONTINUE;
    END IF;
    IF caso='rollback' THEN
      rechazado:=false;
      BEGIN
        -- El UPDATE del reporte ocurre antes del INSERT inválido de la traza.
        PERFORM public.ra_finalizar_ingesta(ejecucion,'smoke-A',toma->'reporte',salida,traza-'decision',NULL);
      EXCEPTION WHEN not_null_violation THEN rechazado:=true;
      END;
      IF NOT rechazado THEN RAISE EXCEPTION 'Se aceptó una traza incompleta'; END IF;
      IF EXISTS(SELECT 1 FROM public.reportes WHERE reporte_id=reporte AND interpretacion IS NOT NULL)
         OR EXISTS(SELECT 1 FROM public.eventos WHERE evento_id=evento)
         OR (SELECT estado FROM public.ejecuciones WHERE ejecucion_id=ejecucion)<>'ejecutando' THEN
        RAISE EXCEPTION 'El cierre parcial no se revirtió';
      END IF;
    END IF;
    respuesta:=public.ra_finalizar_ingesta(ejecucion,'smoke-A',toma->'reporte',salida,traza,error_json);
    IF respuesta->>'estado'<>estado_esperado OR respuesta->>'etapa'<>etapa_esperada THEN
      RAISE EXCEPTION 'Transición incorrecta para %',caso;
    END IF;
    SELECT count(*) INTO n FROM public.eventos WHERE evento_id=evento AND actor_tipo='agente' AND agente='ingesta';
    IF n<>1 THEN RAISE EXCEPTION 'Falta traza única'; END IF;
    IF caso='fallo' THEN
      IF (SELECT ultimo_error->>'codigo' FROM public.ejecuciones WHERE ejecucion_id=ejecucion)<>'proveedor_no_disponible'
         OR (SELECT interpretacion FROM public.reportes WHERE reporte_id=reporte) IS NOT NULL THEN
        RAISE EXCEPTION 'Fallo sin error o con interpretación persistida';
      END IF;
    ELSIF (SELECT interpretacion FROM public.reportes WHERE reporte_id=reporte) IS DISTINCT FROM salida->'interpretacion' THEN
      RAISE EXCEPTION 'Se guardó un wrapper en vez de ExtraccionReporteLLM';
    END IF;
    IF public.ra_tomar_ingesta(ejecucion,'smoke-C') IS NOT NULL THEN RAISE EXCEPTION 'Se retomó trabajo ya procesado'; END IF;
    respuesta:=public.ra_finalizar_ingesta(ejecucion,'smoke-A',toma->'reporte',salida,traza,error_json);
    IF respuesta->>'reintento'<>'true' THEN RAISE EXCEPTION 'Repetición de cierre no reconocida'; END IF;
    SELECT count(*) INTO n FROM public.eventos WHERE evento_id=evento;
    IF n<>1 THEN RAISE EXCEPTION 'El reintento duplicó traza'; END IF;
    rechazado:=false;
    BEGIN
      PERFORM public.ra_finalizar_ingesta(ejecucion,'smoke-A',toma->'reporte',salida,
        jsonb_set(traza,'{resultado}','"Otro cierre"'),error_json);
    EXCEPTION WHEN unique_violation THEN rechazado:=true;
    END;
    IF NOT rechazado THEN RAISE EXCEPTION 'Mismo evento aceptó otro contenido'; END IF;
  END LOOP;
  IF has_function_privilege('anon','public.ra_tomar_ingesta(uuid,text)','EXECUTE')
     OR has_function_privilege('authenticated','public.ra_finalizar_ingesta(uuid,text,jsonb,jsonb,jsonb,jsonb)','EXECUTE') THEN
    RAISE EXCEPTION 'RPC accesible desde navegador';
  END IF;
  RAISE NOTICE 'OK Ingesta: toma exclusiva, 4 transiciones, snapshot, reserva, rollback y repetición de cierre. Sin red ni Gemini.';
END $$;
ROLLBACK;
