-- Administración manual en SQL Editor. NO es una migración.
-- Crear primero cuentas reales en Authentication > Users. No crear auth.users a mano.
-- Copiar sus User UID en el arreglo: pueden ser Emilia y Noel, o solo Emilia.
-- No compartir claves ni contraseñas. El arreglo vacío se rechaza sin cambios.
BEGIN;
DO $$
DECLARE usuarios uuid[]:=ARRAY[]::uuid[]; uid uuid;
BEGIN
 IF cardinality(usuarios)=0 THEN RAISE EXCEPTION 'Completar el arreglo usuarios con los User UID revisados'; END IF;
 FOREACH uid IN ARRAY usuarios LOOP
  IF uid IS NULL OR NOT EXISTS(SELECT 1 FROM auth.users WHERE id=uid) THEN
   RAISE EXCEPTION 'UID sin cuenta de Supabase Auth; no se registró ningún rol'; END IF;
  IF EXISTS(SELECT 1 FROM public.usuarios_operativos WHERE usuario_id=uid AND rol<>'coordinador') THEN
   RAISE EXCEPTION 'El usuario tiene otro rol; revisar antes de sustituirlo'; END IF;
  INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo)
  VALUES(uid,'coordinador',true,'Alta explícita para revisión del ensayo V3; aprobación de planes sigue pendiente de V4')
  ON CONFLICT(usuario_id) DO UPDATE SET activo=true,
   motivo='Reactivación explícita para revisión del ensayo V3';
 END LOOP;
END $$;
COMMIT;
