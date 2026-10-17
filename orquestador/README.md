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
