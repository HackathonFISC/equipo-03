# orquestador

**Dueño:** Emilia

trabajador.py y flujo.py

## Arranque automático

Al iniciar la API, su ciclo de vida lanza `python -m orquestador.trabajador`
con el mismo intérprete y la raíz del proyecto. No hace falta abrir una cuarta
terminal. Procesa ejecuciones pendientes cada cinco segundos y mantiene las
esperas de aclaración, revisión y validación. Requiere configuración de Supabase,
Gemini y migraciones correspondientes; arrancar no completa esas dependencias.

`TRABAJADOR_AUTOMATICO` vale `true` por defecto; `false` se reserva al despliegue
con un trabajador externo. Con modo automático no iniciar además uno manual.
Un bloqueo de archivo en `.runtime/` evita hijos administrados duplicados entre
instancias de API de este checkout; las reservas transaccionales de la BD siguen
protegiendo las ejecuciones entre procesos y equipos distintos.

Al cerrar la API, el trabajador recibe una señal de parada y deja de tomar nuevas
ejecuciones. Tiene hasta 60 segundos para terminar la etapa actual. Si no sale,
se detiene el proceso; una reserva pendiente queda sujeta a los controles de
caducidad/revisión existentes. Un cierre abrupto del sistema no acredita cierre
ordenado ni reanudación automática de trabajos inciertos.

`GET /salud/agentes` muestra iniciado/desactivado/otra_instancia/fallido/finalizado.
Es estado del proceso local, no prueba conectividad ni éxito de Gemini/Supabase.
Una salida inesperada se registra y no se reinicia ciegamente. Revisar su causa
y reiniciar la API. El monitor comprueba el proceso cada dos segundos.

Las pruebas desactivan el trabajador real mediante `conftest.py`; las de arranque
utilizan procesos ficticios. No arrancar una API real de ensayo con producción
configurada esperando que pytest la aísle: ese aislamiento solo aplica a los tests.

## V2

Trabajador y flujo implementados. Ver [guía V2](../docs/V2_EMILIA.md) antes de arrancar: procesa ejecuciones pendientes del Supabase configurado. Requiere migraciones 0006/0007.


## V3

Planificación añadida al despacho y al trabajador. Requiere 0009 para registrar y
procesar el ensayo separado. Usar `--una-vuelta --planificacion-id UUID` para
procesar exclusivamente ese escenario sin mantenimiento global ni consumo de la
cola V2. Gemini decide calcular/revisar; `solve_routes` y `verify_plan` hacen el
trabajo determinístico. Sin aprobación ni mensajería. Ver [guía V3](../docs/V3_EMILIA.md).

## Etapa Comunicación V4

El sondeo normal incluye `pendiente/comunicacion` y despacha al agente de
Comunicación. La aprobación de Noel entrega esa etapa; faltas de selección o
destino quedan en espera_validacion, no en un bucle de envío. El filtro
`--planificacion-id` sigue limitado al ensayo V3. No arrancar un segundo proceso
si la API ya administra el trabajador. Requiere 0012; ver [V4](../docs/V4_EMILIA.md).

## Recuperación acotada del trabajador

El candidato de corrección del 17/10 protege cada vuelta de mantenimiento y
selección con espera exponencial (intervalo, doble, hasta 60 segundos). Después
de cinco fallos consecutivos sale con código 1; `--max-fallos` admite 1–20.
Una vuelta completada reinicia el contador. `--una-vuelta` fallida sale 1.
Las excepciones se registran con traceback y mensaje saneado.

Si una etapa falla después de reservar, `ra_marcar_error_trabajador` (0014) marca
revisión solo si conserva el mismo propietario y estado ejecutando. Un cierre
ya confirmado o una reserva ajena no se modifica. Si no se confirma esa marca,
el vencimiento existente sigue siendo la recuperación conservadora. No se
reintenta una llamada de efecto incierto ni se reenvían avisos.

`--archivo-salud` escribe atómicamente `ultima_vuelta_exitosa` con zona UTC solo
tras completar una vuelta. ServicioAgentes expone esa marca o null; falta que
Noel la incluya en `/salud/agentes`. Instalar 0014 antes de este trabajador.
La marca acredita mantenimiento/selección local completados, no entrega física
ni conectividad integral. Ver `docs/REVISION_EMILIA_20261017.md`.

## Ingesta recuperable A4

Con el código A4 instalar **0015 después de 0014**, antes de reiniciar el
trabajador. El preflight comprueba metadatos de Gemini y columnas de 0015 antes
de reservar; errores transitorios se recuperan con el backoff existente, errores
de configuración detienen con mensaje explícito. El modelo verificado se conserva
durante el proceso. No hay llamadas HTTP repetidas dentro de una extracción.

Los errores recuperables confirmados de Ingesta esperan cinco/diez segundos en
`espera_validacion/ingesta`; mantenimiento reanuda solo los que tienen fecha
persistida. Dos reintentos adicionales como máximo, después revisión humana.
Las reservas inciertas siguen el tratamiento conservador de 0014. Una espera
programada no bloquea el proceso ni ocupa uno de los veinte pendientes seleccionados.
Ver `docs/INGESTA_A4.md`; no reactivar fallos históricos automáticamente.
