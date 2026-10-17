# Demanda y prioridad V2

José implementa dos funciones puras síncronas sobre los contratos 1.0 de Emilia:

```python
from calculo.demanda import validate_need
from calculo.prioridad import score_needs
```

No leen `.env`, consultan Supabase, llaman al modelo, envían mensajes ni autentican coordinadores. El backend autorizado debe comprobar quién confirma datos y activa políticas. Los registros de confirmación son evidencia estructurada, no una comprobación de permisos.

## Validación de demanda

`validate_need(SolicitudValidarNecesidad) -> ResultadoValidarNecesidad` admite litros declarados o la fórmula `max(0, personas × dotación × días − reserva)`. Conserva el método, fuente, supuestos, contexto, IDs y versión. La dotación y días son parámetros de escenario; no se infieren de las horas sin agua.

Una demanda se valida solo con cantidad calculable, confirmación explícita y capacidad de recepción conocida y suficiente. Las ausencias producen `pendiente`, con campos y motivos. Si puede calcular una estimación pese a faltar confirmación o recepción, conserva los litros, pero sigue pendiente. Si falta reserva u otro factor, los litros quedan en `null`; cero explícito sí participa en el cálculo. Si supera la recepción no recorta litros. Un resultado que excede la representación numérica se conserva pendiente, sin emitir infinito. No se inventan umbrales de anomalía o dotaciones oficiales.

Los valores negativos, booleanos en cantidades, números no finitos y campos extra provocan `ValidationError` del contrato antes de calcular. Los pendientes esperados son resultados, no excepciones técnicas.

## Cálculo de prioridad

`score_needs(SolicitudPriorizarNecesidades) -> ResultadoPriorizarNecesidades` exige política activa. En otro caso lanza `ExcepcionContrato` con un `ErrorDominio` cuyo código es `politica_no_activa`. Noel debe adaptar esta excepción al 409 acordado cuando integre estas tools; el manejador actual de `ErrorApi` no convierte automáticamente `ExcepcionContrato`.

Usa los pesos, topes y valor de vulnerabilidad moderada de la política recibida. Clases: crítico antes de general. Puntaje: suma de duración, vulnerabilidad validada y población normalizadas contra topes fijos; nunca contra el máximo del lote. El conteo de quejas no es una entrada del contrato. La información nueva de un reporte podría justificar corregir los hechos; repetirlo no modifica factores ni antigüedad.

Conserva todo el lote. Una necesidad no validada, rechazada, incompleta o con asuntos pendientes queda fuera del ranking, sin puntaje ni posición. No borra alertas urgentes previas; un crítico pendiente genera alerta. La ausencia de clase no se convierte en general: el integrador debe pasar `clase_prioridad=null`, `confirmacion_clase=null` y, si existe sospecha de urgencia, `requiere_revision_urgente=true`.

Se conserva cualquier motivo pendiente que venga del integrador. Solo se retira el marcador de preparación `Cálculo de prioridad todavía no ejecutado.`, usado por el ejemplo compartido. El backend debe reconstruir y revalidar el objeto tras resolver cada asunto con evidencia, retirando explícitamente los motivos resueltos. La herramienta no levanta observaciones de una persona por ver campos numéricos completos. Los puntajes preexistentes se recalculan, sin confiar en el orden anterior.

Si horas o población superan la escala de demo, se satura únicamente el componente y se emite alerta contextual de revisión; no se recorta el dato original ni se rechaza la necesidad automáticamente. Esos topes no son límites sanitarios ni prueban que la cifra sea errónea. Por diseño `PoliticaPrioridad` solo admite origen sintético: el resultado y sus evaluaciones se etiquetan sintéticos aunque los factores procedan de un reporte real, para no presentar una decisión de demo como operativa.

## Desempate

Por clase y puntaje descendente, con grupos construidos comparando contra el puntaje mayor de cada grupo y tolerancia absoluta de 1e-9, sin redondeo previo. Si todos tienen historial, última atención confirmada más antigua, después primera detección y UUID de incidente canónico. Si falta historial en alguno, todo el grupo usa primera detección e ID. Las fechas se comparan como instantes con zona horaria, no como cadenas. Las posiciones son consecutivas para las necesidades calculadas. Solo la presentación usa dos decimales.

## Ejecución y evidencia

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_v2
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_necesidades_v2.py -q
```

La demo muestra 2500 L por demanda directa, 1500 L por fórmula y demanda desconocida cuando falta reserva. Después valida y prioriza los seis puntos sintéticos del fixture de rutas, usando recepción de 5000 L por punto como supuesto exclusivo de ese ensayo. Todas las confirmaciones y la política activa del fixture son ficticias. No cambia `datos/escenario/`: muestra también sus seis necesidades pendientes.

Se guardó entrada, resultado, esperado, métricas y traza en `evals/resultados/necesidades_v2.json`, y resultados de la regresión en `evals/resultados/v2_pruebas.xml`. Para guardar otro ensayo, usar `python -m calculo.demo_v2 --salida ruta_nueva.json`; no sobrescribe una evidencia existente.

## Integración pendiente

Emilia compone `EvaluacionNecesidades` con el resultado de demanda y factores confirmados; mantiene las pruebas de territorio y consolidación, y registra las tools en sus agentes. `ResultadoValidarNecesidad` y `EvaluacionNecesidades` son objetos diferentes: no intercambiarlos directamente. El proceso registra entrada/salida en eventos al invocar las funciones. Las funciones puras no crean trazas en BD por sí solas.

El cierre conjunto V2 requiere incidentes persistidos, agrupación reversible, aclaración y reanudación por el bot, aceptación de parámetros y política del escenario. Estas funciones no acreditan ese recorrido. La elección de cobertura con recursos insuficientes y `verify_plan` siguen en V3; el solver mínimo V1 conserva su alcance de ensayo completo.
