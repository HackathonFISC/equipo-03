# Correcciones del paso de Necesidades a Plan

José autorizó corregir el flujo y repetir el ensayo sintético hasta Plan, sin aprobar ni enviar avisos.

## Política

El puente validaba la política con Pydantic y reenviaba su serialización JSON. La fecha UTC de la confirmación pasaba de `+00:00` a `Z`; la RPC compara cadenas JSON y rechazaba la solicitud aunque el instante fuera igual. Ahora se valida el contrato y se conservan los valores originales de sus campos para la RPC. No se modifica la política de Supabase ni se relajan permisos.

Regresión nueva: conserva fechas UTC y fechas con fracciones/desfase; no muta el snapshot y sigue rechazando fechas inválidas. La prueba UTC falló antes del cambio y pasa después.

## Ventanas

Los campos `datetime-local` también guardan el evento `input`. En la reproducción anterior se mostraba un valor que desaparecía al cambiar otro campo. En el navegador se comprobó que, tras la corrección, los cuatro valores sobreviven a editar el motivo y recargar. La lectura posterior del lote en Supabase confirma ambas ventanas del 17/10/2026, 08:00–12:00 UTC−05:00.

## Comprobaciones

- 984 pruebas Python y 66 subpruebas aprobadas; cuatro advertencias conocidas de dependencias.
- 36 pruebas Node aprobadas; lint y compilación del panel correctos.
- El puente pasó a registrado y creó el escenario de planificación con necesidades persistidas.
- Cálculo y verificación en memoria: una ruta, dos puntos, 5100 litros; informe válido. Esto no acredita persistencia ni aprobación.

## Recuperación e integración comprobada

El trabajador terminó el intento de planificación con `resultado_trabajador_incierto`. La lectura posterior confirma que no hay resultado guardado en el escenario. Google Routes está activado y su RPC está expuesta; no se atribuye todavía la causa del fallo a Google, Gemini, el solver ni SQL sin el error concreto.

Se preparó fuera del repositorio `tmp/recuperar_plan_sintetico_20261017.sql`, solicitado por José para ejecutarlo en SQL Editor. Comprueba ensayo, estado, ausencia de resultado/plan, reserva libre, coordinador y fuente de necesidades vigente; registra el error anterior y permite un reintento. No crea una RPC general, borra datos, cambia cantidades, aprueba planes ni envía avisos. José ejecutó el SQL y comunicó Success. La lectura posterior confirmó planificación en curso; después se guardaron resultado y propuesta. El navegador muestra Plan versión 1: 5100 L, dos puntos atendidos, cero sin atender, una cisterna y verificador válido. Matriz de origen estimado de Google Routes. Horarios de ensayo: salida 08:00, Nuevo Arraiján 08:09–08:24, El Coco 08:43–08:57, retorno 09:13 (UTC−05:00). La ejecución queda en espera_revision con resultado persistido, no en resultado incierto; el plan está pendiente_revision. No se atribuye el fallo transitorio anterior a una causa no demostrada. No se aprobaron planes ni se enviaron avisos.

La pantalla conserva un bloqueo genérico que menciona ausencia de verificación aunque el informe actual es válido; esa redacción no debe interpretarse como fallo del verificador. Los bloqueos de aprobación y ensayo siguen vigentes. La evidencia de este recorrido no sustituye los tres recorridos de cierre V6.

No se hicieron commit ni push.


## Confirmaciones por incidente al recalcular el lote

La API conserva entradas de revisiones humanas persistidas para incidentes intactos, aunque otro punto invalide el ranking del lote. Compara por incidente el origen, ensayo, version, punto completo y huellas/vinculos de reportes, y usa la guarda existente de 0017 para politica, coordinadores activos, conflictos, faltantes y vigencia de ventana. No copia el puntaje ni la posicion: conserva las confirmaciones originales y adapta solo el contexto de calculo a una nueva datos_version. Una revision explicita del usuario prevalece sobre la conservada.

El formulario consulta las identidades/versiones reutilizables y las muestra como confirmacion anterior vigente, con opcion de modificar. POST vuelve a comprobar; las confirmaciones vencidas o cambiadas requieren revision. El historial anterior a 0017 o sin una revision persistida compatible no se reconstruye automaticamente. No requiere migracion nueva; requiere 0017 ya aplicada, reiniciar API y recargar frontend. No restaura ni aprueba planes anteriores.

Validacion local: 638 pruebas y 33 subpruebas correctas en API, contratos, calculo y lotes automaticos; despues de ampliar la prueba de idempotencia y agregar consulta autenticada, suite focalizada: 49 pruebas correctas. Frontend lint y build correctos. No se ejecutaron escrituras remotas ni envios para validar este cambio.
