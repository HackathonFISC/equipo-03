-- Ejecutar después de 0001 y 0004, como postgres en el SQL Editor.
-- Datos sintéticos, sin Telegram real. Todos los INSERT se revierten.
BEGIN;
DO $$
DECLARE
  a uuid; b uuid; panel_a uuid; panel_b uuid; original uuid; repetido uuid;
  identidad_a text := 'smoke-identidad:' || gen_random_uuid()::text;
  identidad_b text := 'smoke-identidad:' || gen_random_uuid()::text;
  chat_a text := '-100' || (100000000 + floor(random()*899999999)::bigint)::text;
  chat_b text := '-100' || (1000000000 + floor(random()*899999999)::bigint)::text;
  rechazado boolean;
  n integer;
BEGIN
  INSERT INTO public.remitentes(canal, identificador_externo)
    VALUES ('telegram', identidad_a) RETURNING remitente_ref INTO a;
  -- Misma identidad, incluso ante intento de alta repetida: conservar UUID.
  INSERT INTO public.remitentes(canal, identificador_externo)
    VALUES ('telegram', identidad_a) ON CONFLICT (canal, identificador_externo) DO NOTHING;
  SELECT remitente_ref INTO repetido FROM public.remitentes
    WHERE canal='telegram' AND identificador_externo=identidad_a;
  IF a <> repetido THEN RAISE EXCEPTION 'Cambió el UUID interno'; END IF;
  SELECT count(*) INTO n FROM public.remitentes
    WHERE canal='telegram' AND identificador_externo=identidad_a;
  IF n <> 1 THEN RAISE EXCEPTION 'Identidad duplicada'; END IF;

  INSERT INTO public.remitentes(canal, identificador_externo)
    VALUES ('telegram', identidad_b) RETURNING remitente_ref INTO b;
  INSERT INTO public.remitentes(canal, identificador_externo)
    VALUES ('panel', identidad_a) RETURNING remitente_ref INTO panel_a;
  INSERT INTO public.remitentes(canal, identificador_externo)
    VALUES ('panel', identidad_b) RETURNING remitente_ref INTO panel_b;
  IF panel_a = a THEN RAISE EXCEPTION 'Se mezclaron identidades entre canales'; END IF;

  INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES(a,'telegram',chat_a || ':7','texto','Prueba sintética','sintetico')
    RETURNING reporte_id INTO original;
  INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES(a,'telegram',chat_a || ':7','texto','Reintento sintético','sintetico')
    ON CONFLICT DO NOTHING;
  SELECT count(*) INTO n FROM public.reportes WHERE canal='telegram' AND mensaje_externo_id=chat_a || ':7';
  IF n <> 1 THEN RAISE EXCEPTION 'El reintento creó otro reporte'; END IF;
  SELECT reporte_id INTO repetido FROM public.reportes WHERE canal='telegram' AND mensaje_externo_id=chat_a || ':7';
  IF repetido <> original THEN RAISE EXCEPTION 'El reintento cambió el reporte original'; END IF;

  rechazado := false;
  BEGIN
    INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
      VALUES(b,'telegram',chat_a || ':7','texto','Mismo mensaje con otro remitente','sintetico');
  EXCEPTION WHEN unique_violation THEN rechazado := true;
  END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Duplicado aceptado al cambiar remitente'; END IF;

  -- message_id solo es único dentro del chat; estos dos son mensajes distintos.
  INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES(a,'telegram',chat_b || ':7','texto','Mismo ID, otro chat','sintetico');
  INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES(a,'telegram',chat_a || ':8','texto','Otro ID, mismo chat','sintetico');

  rechazado := false;
  BEGIN
    INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
      VALUES(panel_a,'telegram',chat_a || ':9','texto','Canal incorrecto','sintetico');
  EXCEPTION WHEN foreign_key_violation THEN rechazado := true;
  END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Reporte aceptado con remitente de otro canal'; END IF;

  -- También protege cambios posteriores, no solo INSERT.
  rechazado := false;
  BEGIN
    UPDATE public.remitentes SET canal='panel', identificador_externo=identidad_a || ':cambio' WHERE remitente_ref=a;
  EXCEPTION WHEN foreign_key_violation THEN rechazado := true;
  END;
  IF NOT rechazado THEN RAISE EXCEPTION 'Se cambió el canal de un remitente referenciado'; END IF;

  -- Panel conserva la regla anterior: mensaje por remitente, no por canal completo.
  INSERT INTO public.reportes(remitente_ref,canal,mensaje_externo_id,modalidad,texto,origen)
    VALUES(panel_a,'panel','smoke-panel','texto','Panel A sintético','sintetico'),
          (panel_b,'panel','smoke-panel','texto','Panel B sintético','sintetico');
  RAISE NOTICE 'OK: UUID estable, identidad por canal, deduplicación Telegram y FK de canal. ROLLBACK elimina los datos sintéticos.';
END $$;
ROLLBACK;
