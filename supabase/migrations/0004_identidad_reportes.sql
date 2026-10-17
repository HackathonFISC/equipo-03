-- Emilia: endurecimiento de identidad y deduplicación; no implementa el bot.
-- Requiere 0001. El número 0004 reserva 0002 y 0003 para Noel.
-- Ejecutar una vez mediante el mecanismo de migraciones del equipo.
-- Ante datos incompatibles, aborta sin borrarlos ni corregirlos automáticamente.
BEGIN;

-- Evita escrituras entre la comprobación previa y la instalación de restricciones.
LOCK TABLE public.remitentes, public.reportes IN SHARE ROW EXCLUSIVE MODE;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.reportes r
    JOIN public.remitentes m ON m.remitente_ref = r.remitente_ref
    WHERE r.canal <> m.canal
  ) THEN
    RAISE EXCEPTION '0004: existen reportes cuyo canal difiere del remitente. Revisar con Noel antes de migrar; no se modificaron datos.';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.reportes
    WHERE canal = 'telegram'
    GROUP BY canal, mensaje_externo_id HAVING count(*) > 1
  ) THEN
    RAISE EXCEPTION '0004: existen mensajes Telegram duplicados entre remitentes. Revisar con Noel antes de migrar; no se modificaron datos.';
  END IF;
END $$;

ALTER TABLE public.remitentes
  ADD CONSTRAINT remitentes_ref_canal_unico UNIQUE (remitente_ref, canal);

ALTER TABLE public.reportes
  ADD CONSTRAINT reportes_remitente_canal_fk
  FOREIGN KEY (remitente_ref, canal)
  REFERENCES public.remitentes (remitente_ref, canal) ON DELETE RESTRICT;

-- No modifica el alcance de idempotencia de panel.
CREATE UNIQUE INDEX reportes_telegram_mensaje_unico
  ON public.reportes (canal, mensaje_externo_id)
  WHERE canal = 'telegram';

COMMENT ON INDEX public.reportes_telegram_mensaje_unico IS
  'Un mensaje Telegram por chat_id:message_id canónico, independiente del remitente. El adaptador de Noel construye la clave desde el mensaje recibido.';
COMMENT ON CONSTRAINT reportes_remitente_canal_fk ON public.reportes IS
  'El UUID interno y el canal del reporte deben identificar al mismo remitente.';

COMMIT;
