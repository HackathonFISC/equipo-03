# Dataset de escritorio H2Oeste: 30 casos PED

Datos sintéticos para pruebas, no para carga operativa. Se conservan seis UUID
del catálogo, dos vehículos ficticios, un depósito y los supuestos del ensayo 3.
La base suma 860 personas y 15 000 L. Recursos, demandas, clases, recepción y
personajes no describen una operación real de esas instalaciones.

## Archivos

| Archivo | Contenido |
| --- | --- |
| `indice.json` | Treinta casos, grupo, alcance y SHA-256 de cada archivo. |
| `base.json` | Referencias originales, seis perfiles, infraestructura y oráculos manuales. |
| `casos/PED-01.json` a `PED-30.json` | Mensajes, contexto propio, revisión ficticia, entradas, pasos y esperado. |

Todos los obtenidos de las entradas permanecen `no_ejecutado`: la evidencia real
se escribe aparte, nunca dentro del caso. Cada caso tiene ejecución/plan/episodio
deterministas e independientes. Los alias P1–P6 no crean puntos nuevos.
Las identidades externas de mensajes son ficticias; no enviarlas a Telegram.

La revisión simulada respeta `PrepararPriorizacion`, pero no concede rol a su
identidad ficticia ni activa una política real. En integración la identidad y la
confirmación salen de la sesión autorizada. No enviar el JSON completo como un
snapshot confiable a la API ni cargar confirmaciones de fixture en Supabase.

## Casos

| IDs | Grupo | Ejecución disponible |
| --- | --- | --- |
| PED-01–06 | Seis reportes completos, demanda y prioridad | Cálculo local real; no prueba extracción LLM del mensaje. |
| PED-07–12 | Ubicación, familias, evidencia, duplicados e inyección | Guiones completos pendientes de integración controlada. |
| PED-13–18 | Faltantes, recepción, cero, exceso y política inactiva | Validación/prioridad locales; cero/exceso también pasan por solver/verificador. |
| PED-19–24 | Completo, retiro, flota, ventanas, accesos y obsolescencia | Solver/verificador reales sobre inputs sintéticos. |
| PED-25–30 | Rol, comunicación, fallos, reinicio y reintentos | Guiones completos pendientes de integración controlada. |

Son 30 casos, no 30 puntos ni necesariamente 30 mensajes. Las entradas de cálculo
locales están estructuradas de antemano: no atribuir su construcción al modelo.
Los casos sin inputs de tools incluyen revisión/contexto y protocolo propio, no
resultados ficticios de servicios externos. Los casos PED no sustituyen los casos
oficiales 1–25 del plan del equipo.

## Uso desde la raíz

Validar los treinta archivos, su manifiesto y contratos:

```powershell
.\.venv\Scripts\python.exe -m evals.escritorio --validar
```

Ejecutar los 18 casos de tools y registrar los 12 pendientes, en carpeta nueva:

```powershell
.\.venv\Scripts\python.exe -m evals.escritorio --salida ../tmp/escritorio_resultados_01
```

No usa red, API en ejecución, Gemini, Telegram ni Supabase. Código 2 significa
pendientes de integración; 1 indica fallos/errores y 0 solo si no hay pendientes.
Un crítico pendiente puede ser un rechazo correcto del plan y aprobar su caso
adverso; el informe conserva ambas cosas por separado.

Ejecutar pruebas del dataset:

```powershell
.\.venv\Scripts\python.exe -m pytest evals/independientes/test_dataset_escritorio.py -q
```

Regenerar una copia reproducible para comparar, sin sobrescribir:

```powershell
.\.venv\Scripts\python.exe scripts/generar_dataset_escritorio.py --salida ../tmp/dataset_ped_nuevo
```

El generador usa el snapshot versionado del ensayo 3, no extrae datos personales.
No cambia esos archivos. Las fuentes se identifican por hashes y fecha fija.
Editar base/casos requiere regenerar manifiesto; los hashes normalizan CRLF a LF
en archivos de texto, para tolerar checkout Git entre plataformas.

Resultados locales: [informe de ejecución](../../../evals/resultados/escritorio_v1/informe.json).
Detalle conceptual: [propuesta](../../../docs/PROPUESTA_PRUEBAS_ESCRITORIO.md).
Retiro persistido y autorización/envío reales siguen requiriendo al equipo.
