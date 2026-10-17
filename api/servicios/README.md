# api/servicios

**Dueño:** Noel

aprobacion.py (request_approval), bandeja_salida.py (publish_approved_messages)

Implementados: `priorizacion.py` (lote revisado de priorización para `ra_preparar_priorizacion_v2`), `sectores.py` (RPC de la migración 0012: estado, plan por sector, destino de ensayo), `planes.py` (lectura de planes guardados), `aprobacion.py` (aprobar y rechazar planes con las RPC de la migración 0003), `reportes.py` (persistencia idempotente de reportes y destinos), `ejecuciones.py` (seguimiento), `aclaraciones.py` (llamadas a las RPC de Emilia) `incidentes.py` (incidentes con su necesidad, desde las RPC de Emilia) y `bandeja_salida.py` (V4, RPC de la migración 0011). Detalle en [../README.md](../README.md).
