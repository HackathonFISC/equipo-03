# Bitácora de IA: emilia

| Fecha y hora | Herramienta | Uso | Salida aprovechada | Cambios y revisión humana |
| --- | --- | --- | --- | --- |
| 2026-10-16 17:11 EST | Codex | Integrar contratos V0 basados en decisiones de demanda, prioridad y plan de versiones | Cinco contratos principales, objetos auxiliares, cuatro firmas, 24 ejemplos sintéticos y 18 JSON Schema; 43 pruebas de contratos aprobadas desde este clon con Python del entorno de Codex y Pydantic 2.13.5 | Revisión humana y aceptación con Noel/José pendientes. Política 50/30/20 propuesta para demo; no norma oficial. Noel conserva bot y mensajería. No se creó commit ni PR; no se validaron servicios externos. |
| 2026-10-16 17:48 EST | Codex | Definir e integrar 0001 sobre proyecto declarado vacio | Esquema de 23 tablas, 10 enums compatibles con contratos, constraints, indices, RLS cerrado y smoke con ROLLBACK. Probado en PostgreSQL temporal PGlite; bloqueo anon/authenticated y segunda ejecucion no destructiva comprobados | No aplicado a Supabase real. URL/credenciales no utilizadas. 0002, 0003, servicios y aprobacion humana siguen pendientes; no commit ni push. |
