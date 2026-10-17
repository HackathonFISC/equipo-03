# Revisión del pull y pendientes de entrega

17 de octubre de 2026, José. Base revisada: d35d80e → 9dbd4f8; incluye nuestra
entrega V6 af51b97. Revisión local de código/evidencia, sin servicios externos.
Las recomendaciones de este informe no cambian el alcance ni activan funciones.

## Cambios incorporados

- Nuestra preparación V6 quedó integrada por PR #47.
- Noel añadió ForceReply a las preguntas de aclaración. Facilita responder al
  mensaje correcto; no sustituye validación de remitente/chat ni resuelve por sí
  solo ubicaciones ambiguas.
- D015 registra aceptación de Noel al arranque automático del trabajador.
- PR #48 vincula resultados de consulta al sector actual y muestra origen en
  sector, puntos y selector de planes. Reproducida la corrección del caso A→B
  con los handlers reales extraídos y estado/promesa simulados, sin navegador.
- Rediseño del panel, acceso de cuenta independiente y estado de sesión en App.
  Las cuatro tools y contratos no cambiaron respecto a d35d80e.

## Comprobaciones

- Copia candidata sin .env, usando dependencias Python instaladas: 715 pruebas y
  66 subpruebas aprobadas (781 JUnit), cuatro advertencias conocidas, cero saltos.
- pip check, entorno V0, demos V1/V2/V3, comparación V5 y cuatro pruebas Node aprobadas.
- ESLint y build Vite aprobados sobre el frontend del pull.
- Enlaces de entrada de nuestra documentación correctos.
- La auditoría inicial devuelve fallo documental: solo la fuente Noel cambió
  respecto al hash de la bitácora consolidada. No fallan cálculo ni dependencias.
  Se regenera la consolidación después de registrar esta revisión.

No se prueba navegación visual, Supabase remoto, migraciones aplicadas, Gemini,
Telegram, roles reales ni recuperación de procesos conectados. El build no
demuestra usabilidad ni el recorrido integral. Evidencia inicial en la carpeta
local externa tmp/revision_pull_9dbd4f8; no sustituye la evidencia histórica V6.

## Lo entregado por José

| Etapa | Implementación y prueba propias | Pendiente para el cierre conjunto |
| --- | --- | --- |
| V0 | Dependencias, restricciones de versiones, configuración de ejemplo, escenario y verificador de entorno. | Reproducir instalación nueva; distinguir entorno local de compatibilidad de las tres laptops. |
| V1 | Solver mínimo y demo reproducible con capacidad/ventanas/descarga/retorno; finalizadores corregidos. | Mantener regresión; su cobertura completa es histórica, V3 implementa selección parcial. |
| V2 | validate_need y score_needs; fórmula, recepción, faltantes, orígenes, política 40/40/20 versionada y críticos primero. | Carga/proceso/consulta del lote revisado con evidencia real; no confundir fixture calculable con demanda ciudadana confirmada. |
| V3 | Solver completo, verificador independiente, matriz sintética, selección parcial y motivos por punto. | Paso revisado de necesidades a escenario; persistencia/despliegue y visualización del mismo plan/versionado. |
| V4 | Ejecutor de regresión y perfiles HTTP, preparación de casos 18/20/21, pruebas adversas locales. | Inyección con proveedor real, rechazo de versión y concurrencia reales, aprobación y aviso recibido. |
| V5 | Comparador FIFO, retiro puro antes de salida, métricas/denominadores, cinco escenarios y fronteras HTTP. | Casos 19/22/23/24/25 integrados; retiro persistido, nueva aprobación y aviso, sin duplicados ni pérdida al reiniciar. |
| V6 | README, infraestructura, auditoría/manifiesto, consolidación, D017 y evidencia local. | Instalación nueva, tres recorridos estables, acceso, exposición, tag/envío del equipo. |

Las cuatro tools están implementadas. Preparación local completa de una etapa
no equivale al cierre de la versión del equipo. No asignar porcentajes de avance
sin denominador ni afirmar V0–V3 integradas solo por sus pruebas numéricas.

## Pendientes que más afectan la demostración

| Prioridad | Pendiente y consecuencia | Responsable |
| --- | --- | --- |
| 1 | Definir el paso de necesidad ciudadana revisada al escenario de planificación. V3_EMILIA declara fixture separado: hoy no se acredita Telegram→plan continuo. | Emilia coordina, José valida entradas/contratos, Noel muestra resultado. |
| 1 | Confirmar migraciones y smoke por entorno, permisos, selección por sector y destino autorizado; activar avisos solo después. AVISOS_ACTIVOS sigue false. | Emilia y Noel; José contrasta evidencias. |
| 1 | Conectar Plan al servicio persistido o demostrar explícitamente Aprobación como vista real. USAR_EJEMPLOS_PLANES sigue true; no mezclar versiones con Necesidades. | Noel; José comprueba cantidades/déficit. |
| 1 | Ejecutar núcleo V4 y casos 18–25 según alcance, conservando efectos persistidos y mensaje recibido. | Equipo, con caja negra de José. |
| 2 | Replanificación real ante retiro antes de salida: invalidación, nueva versión, déficit, aprobación y comunicación. simular_retiro no modifica BD. | Emilia y Noel; José verifica recálculo. |
| 2 | Instalación desde clon nuevo y tres recorridos consecutivos con uno adverso. | Equipo. |
| 3 | Mapa y página independiente de eventos son pendientes del diseño; priorizarlos después del núcleo funcional. Trazas por reporte ya existen. | Noel con datos de Emilia. |

La ausencia del archivo reservado 0002 no demuestra por sí misma tablas expuestas:
otras migraciones definen RLS/permisos. Debe comprobarse el resultado efectivo con
roles reales, sin suponer seguridad o vulnerabilidad por un nombre de archivo.

## Dos detalles adicionales para Noel

1. ComunicacionSector.jsx compara UUID como texto con distinción de mayúsculas
   (línea 52), pero admite mayúsculas al validar el input. Un UUID válido pegado
   en mayúsculas recibe la misma identidad normalizada por la API y muestra
   erróneamente «La API respondió por otro sector». Reproducido con handler real
   y respuesta simulada. Normalizar identidad antes de comparar.
2. Líneas 136–138 indican que todo plan distinto de real solo puede ir a ensayo,
   incluyendo estimado. La RPC 0012 restringe específicamente sintetico
   (líneas 160/172/312), no estimado. Alinear texto con regla vigente; si el equipo
   quiere otra regla, coordinar backend y decisión, no cambiar permisos desde UI.

No se modifican estos archivos ajenos durante esta revisión.

## Cómo mejorar nuestra parte

1. Convertir perfiles genéricos V4 en casos concretos de ensayo sobre el backend
   autorizado: identidades/versiones conocidas, esperado, efecto antes/después,
   resultado y traza. No marcar aprobado solo por HTTP 200 o cambiar flags de cierre.
2. Reunir evidencia V4/V5 por caso con commit, escenario, datos_version,
   politica_version y referencias de BD/acuse sanitizadas. Hoy el ejecutor V4
   conserva pendientes y la comparación V5 es local; faltan resultados conjuntos.
3. Medir recepción→propuesta y aprobación→envío con tiempos persistidos reales.
   Mantener null lo no medido y separado el tiempo de solver/verificador.
4. Probar timeout del solver con agotamiento real controlado. Las regresiones
   de timeout y FEASIBLE no óptimo actuales simulan estados del motor; no son
   evidencia de timeout real. Nunca reclasificarlo como inviabilidad.
5. Diversificar comparación con orden de llegada: cola actual deliberadamente
   adversa, generales antes que críticos. Añadir casos de empate y colas distintas
   cuando se evalúe generalización; conservar igual snapshot/recursos y posibles
   resultados desfavorables. No usar el caso actual para prometer mejora universal.
6. Mantener documentos sincronizados después de pulls: esta revisión actualiza
   nuestra lista V6 y consolidación; Emilia debe revisar V4_EMILIA, que todavía
   describe como pendientes piezas de 0003/API ya implementadas. Documentar
   implementación, ejecución local y despliegue por separado.
7. Antes de publicar la versión final, repetir auditoría sobre ese commit y
   verificar instalación limpia. Los hashes crudos de bitácoras identifican bytes
   exactos: CRLF/LF entre plataformas puede exigir regenerar consolidación sin
   que hayan cambiado hechos. Unificar finales de línea sería una mejora posterior
   coordinada; no normalizar todo el repositorio durante la entrega.

No hace falta sustituir las cuatro tools ni abrir otra arquitectura para avanzar.
La prioridad es conectar, comprobar y documentar el recorrido existente.
