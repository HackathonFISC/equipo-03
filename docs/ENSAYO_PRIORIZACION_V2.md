# Lote V2 aprobado, separado del ensayo Telegram

Emilia aprobó explícitamente el uso de las seis demandas (15 000 L), recepción,
clases, ventanas y política 40/40/20 exclusivamente como ensayo sintético. La
revisión usa su UID real de coordinadora; no se copian identidades ficticias como
si fueran autorizaciones. La fuente de parámetros sigue siendo el fixture de
José. No es aprobación de un plan ni validación de campo.

## Instalar

Aplicar completo `supabase/migrations/0010_ensayos_priorizacion_v2.sql` y después
`supabase/tests/0010_ensayos_priorizacion_v2_smoke.sql` (termina en ROLLBACK).
Requiere 0008 y catálogo oeste-1.0; **no requiere 0009** ni ejecuta rutas.
La numeración permite instalar V3 y este ajuste independientemente en SQL Editor.
No reinstalar si ya está aplicada.

0010 añade ámbitos de ensayo a ejecuciones/incidentes, conserva las firmas
existentes y añade dos RPC backend:

- `ra_registrar_ensayo_priorizacion_v2(p_usuario_id uuid, p_paquete jsonb, p_motivo text)`.
  Registra revisión/política/incidentes y llama a `ra_preparar_priorizacion_v2`
  atómicamente. Un reintento idéntico no reactiva la ejecución ni añade eventos.
- `ra_incidentes_contexto_v2(p_ejecucion_id uuid)` devuelve los incidentes del
  ámbito de esa ejecución. Solo service_role puede llamarlas.

Cada caso tiene seis incidentes exclusivos, una ejecución y datos_version propia.
No se crean mensajes, reportes ni vínculos ciudadanos ficticios para forzar el
cálculo. La toma de priorización admite una ejecución de ensayo revisada sin
reporte; el flujo ciudadano continúa exigiendo interpretación. Los controles de
lote completo, pertenencia, versión, origen y coordinador se mantienen dentro de
cada ámbito. La invalidación por Territorial/separación se limita al ámbito
ciudadano; los ensayos no se incluyen en su consolidación.

## Registrar y ejecutar

Desde la raíz del repositorio, con el entorno activo:

```bash
python -m scripts.ensayo_priorizacion_v2 preparar --coordinador-uid UID_REVISADO --motivo "Revisión explícita del fixture sintético, sin autorización de reparto" --salida /tmp/lotes_v2.json
python -m scripts.ensayo_priorizacion_v2 registrar --entrada /tmp/lotes_v2.json --evidencia /tmp/v2_registro.json
python -m scripts.ensayo_priorizacion_v2 procesar --entrada /tmp/lotes_v2.json --evidencia /tmp/v2_proceso.json
python -m scripts.ensayo_priorizacion_v2 verificar --entrada /tmp/lotes_v2.json --evidencia /tmp/v2_resultados.json
```

Conservar el mismo archivo y motivo para reintentos; no regenerar identidades.
Las salidas no sobrescriben archivos existentes. El procesamiento selecciona solo
las dos ejecuciones preparadas: no arranca el trabajador global, Gemini ni bot.
Se comprueba el snapshot ciudadano antes/después. Actividad externa concurrente
puede cambiar ese snapshot y debe investigarse, sin deshacer datos ajenos.

Resultados: caso calculable con seis prioridades y 15 000 L; caso con reserva de
Burunga desconocida conserva demanda/puntaje/posición en null, prioridad pendiente
y revisión urgente. No sustituir null por cero. Comparar persistencia y resultados
con validate_need y score_needs reales. No ejecutar solver ni verify_plan aquí.

## Acuerdo de API/panel con Noel

V2 no incorpora login ni separación desde la API; la sesión y token derivado son
V4. El script es una herramienta administrativa backend para la revisión explícita
acordada; no recibe un UID libre del navegador. Mantener service_role privado.

`ra_incidentes_snapshot_v2()` sigue mostrando solo incidentes ciudadanos con
vínculos activos. Para visualizar cada caso, Noel puede ofrecer un filtro de
lectura por ejecución que use `ra_incidentes_contexto_v2` y la proyección segura
actual del panel. No mezclar rankings de los dos casos ni del ensayo Telegram.
Sin ese filtro el panel seguirá mostrando el incidente original, deliberadamente.

## Estado

Migración y casos probados en PostgreSQL temporal, con regresiones de 0005–0009,
service_role y denegación de anon/authenticated. No se aplicó 0010 ni se registraron
estos lotes en Supabase real. El UID activo de Emilia ya se comprobó aparte.
Pendientes reales: aplicar 0010/smoke, registrar/procesar/verificar, filtro y
confirmación visual de Noel; duplicado tras prioridad calculada y vencimiento
real de aclaración. El POST duplicado segundo y el panel V2 pendiente ya fueron
confirmados por Noel; el primer reply a otro mensaje es comportamiento previsto.
