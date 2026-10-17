# A1 De las necesidades persistidas a un plan de ensayo

El recorrido queda preparado en backend para conservar el reporte, su procedencia
y la misma ejecución mientras los agentes calculan un escenario con recursos
ficticios. No se acredita disponibilidad de IDAAN, programación operativa ni
entrega física. Requiere 0016 después de 0015; la aplicación remota sigue pendiente.

## Alcance confirmado y procedencia

El 17 de octubre el usuario precisó que el flujo debe recibir una queja por
Telegram, pasarla entre agentes, utilizar recursos sintéticos porque no se tienen
datos verificados de IDAAN y devolver la decisión de ensayo tras revisión humana.
También autorizó preparar el cambio que conserva reportes reales cuando corresponda.
La procedencia y el modo de ejecución tienen funciones distintas.

| Objeto | Valor conservado o impuesto |
| --- | --- |
| Reporte, incidente y ejecución | Su origen registrado: real, estimado o sintético. Real significa reporte sobre una situación declarada real; no prueba el hecho denunciado. |
| Necesidad | Su origen, cantidades, faltantes, confirmaciones y versión persistidos. No se copian demandas del fixture. |
| Política | La versión activa que seleccionó el coordinador para ese lote. No se activan copias ni se eligen porcentajes automáticamente. |
| Recursos | Dos vehículos ficticios de 10 000 L, turno 08:00–12:00 del 17/10, depósito y matriz manual del ensayo 3 confirmado. No son recursos IDAAN comprobados. |
| Escenario, propuesta e informe | `origen=sintetico`, porque la asignación usa recursos ficticios; no reetiqueta los hechos de entrada. Registro del escenario con `modo=ensayo`. |
| Traza | Mismo ejecucion_id y origen de la ejecución; Planificación añade origen_escenario y modo a los detalles. |
| Aviso | De ensayo, con rótulo explícito y solo destino de prueba autorizado, después de aprobación humana y selección por sector. |

El campo origen del plan describe el escenario calculado, no certifica que todos
sus antecedentes sean ficticios. La interfaz debe mostrar ambas procedencias:
«Reporte real declarado · Recursos sintéticos · Propuesta de ensayo».
No se crea un enum mixto ni se modifican contratos o las cuatro herramientas.
Una operación real sigue fuera de esta habilitación.

## Implementación

1. La ruta de Noel prepara la revisión del lote mediante la RPC existente.
2. Al cerrar Priorización, una cola se guarda en la misma transacción que deja
   las necesidades persistidas. También se encolan los cierres anteriores elegibles
   al instalar 0016. No se reabren fallos históricos de Ingesta.
3. Cada vuelta global del trabajador procesa esa cola antes de seleccionar etapas.
   La construcción es local y determinista: no llama al modelo ni autoriza nada.
   La cola sobrevive al reinicio; repetir un registro confirmado es idempotente.
4. El puente lee todas las necesidades de la versión vigente desde la tabla,
   conserva las pendientes e incluye motivos. Consulta versión de incidentes y
   política. Un punto con dos episodios no se elige ni suma: queda para revisión.
5. El ámbito de `ra_incidentes_contexto_v2` se explicita por origen de ejecución y
   ensayo, cuando existe. Se incluyen todos los incidentes activos de ese ámbito;
   no se recorta por el sector mostrado en el panel. Los demás orígenes siguen
   visibles en sus propios ámbitos y no se fusionan.
6. La infraestructura inicial se lee del archivo versionado del ensayo 3,
   seleccionando solo depósito, flota, puntos, matriz, servicios y límite del solver.
   No se leen de él demandas, población, clase, vulnerabilidad, política o revisiones.
   Para menos de seis puntos se selecciona la submatriz; no se crean otras demandas.
7. Los recursos ficticios ausentes se registran con nuevas filas, sin sobrescribir
   recursos existentes. Si una cisterna ya está retirada, su disponibilidad no se
   restablece. Cambios posteriores se comprueban en el snapshot.
8. La RPC de registro verifica rol coordinador de la revisión original, snapshot,
   ámbito, procedencias, política y contenido exacto de las necesidades. Registra
   el escenario sobre la misma ejecución y avanza a pendiente/planificacion.
   No crea incidentes o necesidades nuevos, ni llama al antiguo creador de fixtures V3.
9. Solver y verificador existentes calculan y comprueban. Su resultado espera
   revisión. Se conservan aprobación, selección de sector y bandeja existentes.
   Todos los planes de este puente son escenarios sintéticos: las restricciones
   de destino de ensayo de 0012 siguen aplicándose aun si la ejecución es real.
10. La vigencia incorpora las necesidades persistidas. Si cambian después de la
    aprobación, se invalida el plan y se cancelan avisos pendientes no reservados.
    Los enviados o inciertos no se borran ni reenvían automáticamente.

El primer puente registra un escenario por ejecución. Sustituir uno ya registrado
se bloquea para preservar su historial; la replanificación persistida con una nueva
versión sigue siendo el trabajo B2. No se presenta esta cola como cierre de B2.
Errores de datos/permisos se dejan en revisión; errores de conexión o snapshot
obsoleto se recuperan por el bucle acotado. No se ocultan como éxito.

## Preparación por Noel

Ver `HANDOFF_NOEL_A1.md`. La constante de origen de Telegram sigue pendiente. La falta de capacidad
de recepción detectada en f6d3448 fue corregida por Noel en f1fe718; su formulario
y su paso al contrato se conservaron íntegros. No se modificaron api/, bot/ o frontend/ en este trabajo.

La revisión del coordinador continúa siendo necesaria para demanda, recepción,
clase, vulnerabilidad y ventanas. Las suposiciones de ensayo se declaran con su
fuente y no se convierten en observaciones de campo. Si falta información, el
puente conserva la necesidad pendiente y el cálculo muestra el motivo; no fabrica
una asignación para conseguir una demo con cobertura completa.

## Instalar y probar

1. Confirmación del usuario: 0014, 0015 y ambos smoke validados; reinicio en curso.
2. Revisar y ejecutar una vez **0016_puente_necesidades_v3.sql**, completa.
3. Ejecutar **0016_puente_necesidades_v3_smoke.sql** completo. Usa ámbitos aislados
   dentro de una transacción y termina ROLLBACK; no llama a servicios externos.
4. Reiniciar el único trabajador o la API que lo administra. El preflight comprueba
   la tabla de la cola antes de reservar. `--planificacion-id` sigue siendo un modo
   aislado para escenarios ya registrados; no procesa globalmente esta cola.
5. Con Noel, corregir captura de origen y comprobar el formulario nuevo de recepción, revisar el lote de prueba,
   comprobar traza, aprobar la propuesta vigente y seleccionar todos sus sectores.
6. Conservar AVISOS_ACTIVOS=false hasta cerrar controles. En la prueba final,
   únicamente Noel habilita el envío en su máquina, a un destino de ensayo revisado.
   Registrar el ID real de Telegram; bandeja creada no significa aviso recibido.

## Evidencia

Base inicial f6d3448: 825 pruebas + 66 subpruebas. Candidato inicial: 843 pruebas + 66 subpruebas.
Recepción de Noel integrada desde f1fe718: base 828, candidato final **846 pruebas + 66 subpruebas**,
cuatro advertencias conocidas de dependencias. El smoke 0016 pasó en PostgreSQL
local PGlite, para procedencias sintético, real y estimado. También pasaron los
smoke 0006, 0009 Planificación, 0010 ensayo V2, 0012 Comunicación, 0013, 0014 y 0015.

La integración local usa reportes y revisiones de fixture, algunos con campo origen
real para comprobar que no cambia. No contiene situaciones reales de ciudadanos.
Ingesta usa un extractor simulado; Territorial, validate_need, score_needs, solver,
verificador, persistencia, aprobación y Comunicación usan sus implementaciones.
La persona y aprobación son simuladas dentro del fixture. Resultado: 15 000 L,
seis necesidades, seis avisos de ensayo y traza de los cinco agentes en una ejecución.
Destino no habilitado bloqueado; cambiar necesidades invalida y cancela los avisos.
Evidencia sin texto ciudadano en `agentes/evidencias/puente_necesidades_v3_local.json`.

Ejecutor reproducible: `supabase/tests/0016_integracion_local.mjs`. Requiere Node,
Python del proyecto y PGlite como herramienta temporal; no se agrega al lock del
proyecto. `RA_PGLITE_PACKAGE` apunta al package.json del directorio temporal que
contiene esa dependencia, `RA_PYTHON` al intérprete instalado y `RA_EVIDENCIA` permite
otra salida. El ejecutor no usa claves, Gemini, Telegram ni Supabase remoto.

Esta evidencia no acredita recepción real, carga concurrente, despliegue ni los
tres recorridos de entrega. La prueba integrada con la API nueva y Telegram sigue
pendiente de los ajustes de Noel y del SQL en Supabase.
