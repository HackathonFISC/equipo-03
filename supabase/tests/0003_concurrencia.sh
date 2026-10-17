#!/bin/bash
# Prueba de concurrencia de 0003 con varias sesiones reales de psql (caso 21 de José).
# Solo para una base DESECHABLE con 0001 a 0011 y 0003 aplicadas (con 0012 de Emilia también se prueba la invalidación): crea datos sintéticos y los deja confirmados.
# Uso:  PSQL="psql -h /tmp -p 5544 -U postgres" ./0003_concurrencia.sh nombre_base_desechable
# Requiere bash, bc y psql. Cada escenario crea su propio plan pendiente.
set -u
DB="${1:?Indica el nombre de una base desechable}"
PSQL="${PSQL:-psql}"
Q="$PSQL -d $DB -q -t -A"
AQUI="$(cd "$(dirname "$0")" && pwd)"
BL="ARRAY['Sin verificación independiente ni aprobación autorizada de esta versión.','Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.','ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.']"
fallos=0

# La función que arma el plan sale del smoke, para no mantenerla en dos sitios.
sed -n '/^CREATE FUNCTION pg_temp.fx/,/^END \$\$;/p' "$AQUI/0003_aprobacion_smoke.sql" | sed 's/CREATE FUNCTION pg_temp.fx/CREATE OR REPLACE FUNCTION public.fx_conc/' | $Q -v ON_ERROR_STOP=1 -f - >/dev/null || { echo "No se pudo crear fx_conc"; exit 2; }

nuevo() {  # imprime: usuario plan vehiculo
  $PSQL -d "$DB" -v ON_ERROR_STOP=1 -q -t -A -F ' ' <<'SQL'
BEGIN;
CREATE TEMP TABLE ids AS SELECT gen_random_uuid() u, gen_random_uuid() s, gen_random_uuid() p, gen_random_uuid() d, gen_random_uuid() v, 'conc-'||left(gen_random_uuid()::text,8) pol;
INSERT INTO auth.users(id) SELECT u FROM ids;
INSERT INTO public.usuarios_operativos(usuario_id,rol,activo,motivo) SELECT u,'coordinador',true,'conc' FROM ids;
INSERT INTO public.sectores(sector_id,nombre,origen,fuente) SELECT s,'C sector','sintetico','conc' FROM ids;
INSERT INTO public.puntos_atencion(punto_atencion_id,sector_id,nombre,origen,fuente) SELECT p,s,'C punto','sintetico','conc' FROM ids;
INSERT INTO public.politicas_prioridad(politica_version,estado,origen,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,vulnerabilidad_moderada,fundamento,confirmacion_activacion)
  SELECT pol,'activa','sintetico',.4,.4,.2,168,500,.5,'conc',jsonb_build_object('usuario_id',u,'confirmado_en',now(),'motivo','conc') FROM ids;
INSERT INTO public.depositos(deposito_id,nombre,latitud,longitud,fuente_ubicacion,origen,fuente) SELECT d,'C dep',0,0,'escenario','sintetico','conc' FROM ids;
INSERT INTO public.vehiculos(vehiculo_id,nombre,capacidad_litros,turno_inicio,turno_fin,deposito_id,origen) SELECT v,'C veh',10000,now(),now()+interval '6 hours',d,'sintetico' FROM ids;
SELECT u, (public.fx_conc(u,pol,s,p,d,v,'c'))[1], v FROM ids \gset
COMMIT;
SELECT :'u', :'fx_conc', :'v';
SQL
}
aprobar() { echo "SELECT public.ra_aprobar_plan('$1','$2',1,'smoke-c',(SELECT politica_version FROM public.planes WHERE plan_id='$2'),'m',$BL)"; }
estado() { $Q -c "SELECT estado FROM public.planes WHERE plan_id='$1'"; }
verifica() { if [ "$2" = "$3" ]; then echo "  ok: $1"; else echo "  FALLA: $1 (esperado '$3', obtenido '$2')"; fallos=$((fallos+1)); fi; }

echo "A: alguien cambia una entrada sin confirmar y llega la aprobación (debe esperar y luego ser version_obsoleta)"
read U PL V < <(nuevo)
( $Q <<SQL
BEGIN; UPDATE public.vehiculos SET capacidad_litros=9000 WHERE vehiculo_id='$V'; SELECT pg_sleep(2.5); COMMIT;
SQL
) & sleep 0.8
t0=$(date +%s.%N); R=$($Q -c "$(aprobar $U $PL)" 2>&1 | head -1); t1=$(date +%s.%N); wait
verifica "la aprobación se rechaza por versión obsoleta" "$([[ "$R" == *"version_obsoleta: las entradas cambiaron"* ]] && echo si || echo "$R")" si
verifica "la aprobación esperó al otro cambio" "$([ "$(echo "$t1-$t0>1" | bc)" = 1 ] && echo si || echo no)" si
verifica "el plan sigue pendiente" "$(estado $PL)" pendiente_revision

echo "B: la aprobación está en curso y alguien cambia una entrada (el cambio espera y el plan queda invalidado)"
read U PL V < <(nuevo)
( $Q <<SQL
BEGIN; $(aprobar $U $PL); SELECT pg_sleep(2.5); COMMIT;
SQL
) >/dev/null & sleep 0.8
t0=$(date +%s.%N); $Q -c "UPDATE public.vehiculos SET capacidad_litros=9000 WHERE vehiculo_id='$V'" >/dev/null 2>&1; t1=$(date +%s.%N); wait
verifica "el cambio esperó a la aprobación" "$([ "$(echo "$t1-$t0>1" | bc)" = 1 ] && echo si || echo no)" si
if [ "$($Q -c "SELECT to_regprocedure('public.ra_invalidar_planes_v4()') IS NOT NULL")" = t ]; then
  verifica "el plan quedó invalidado (0012)" "$(estado $PL)" invalidado
  verifica "hay evento de invalidación" "$($Q -c "SELECT count(*) FROM public.eventos WHERE detalles->>'plan_id'='$PL' AND decision LIKE 'Invalidar%'")" 1
else
  echo "  (sin 0012 no hay invalidación posterior; se comprueba solo que el cambio esperó)"
fi

echo "C: dos aprobaciones iguales a la vez (una sola aprobación guardada)"
read U PL V < <(nuevo)
( $Q -c "$(aprobar $U $PL)" >/dev/null 2>&1 ) & ( $Q -c "$(aprobar $U $PL)" >/dev/null 2>&1 ) & wait
verifica "una sola aprobación" "$($Q -c "SELECT count(*) FROM public.aprobaciones WHERE plan_id='$PL'")" 1
verifica "plan aprobado" "$(estado $PL)" aprobado

echo "D: aprobar y rechazar a la vez (gana una sola)"
read U PL V < <(nuevo)
( $Q -c "$(aprobar $U $PL)" >/dev/null 2>&1 ) & ( $Q -c "SELECT public.ra_rechazar_plan('$U','$PL',1,'no')" >/dev/null 2>&1 ) & wait
EST="$(estado $PL)"; APR="$($Q -c "SELECT count(*) FROM public.aprobaciones WHERE plan_id='$PL'")"
if [ "$EST" = aprobado ]; then verifica "aprobado con una aprobación" "$APR" 1; else verifica "rechazado sin aprobaciones" "$EST/$APR" "rechazado/0"; fi

[ $fallos -eq 0 ] && echo "OK: concurrencia de 0003" || { echo "$fallos comprobación(es) fallaron"; exit 1; }
