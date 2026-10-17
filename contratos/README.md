# Contratos de RutaAgua Oeste

**Dueño:** Emilia. Contratos compartidos: avisar a Noel y José antes de cambiar su interfaz.

Versión de intercambio **1.0**. Entrega para **V0 Base compartida**. Python 3.10 o superior y `pydantic>=2.13,<3`. Validado con Pydantic 2.13.5.

## Integración local y próximos pasos

Los contratos están integrados en este clon sobre la rama `Emilia`. No se creó commit ni se publicó un PR.

1. En el entorno Python del equipo, instala la dependencia desde la raíz:

   ```bash
   python -m pip install -r contratos/requirements.txt
   python -m unittest discover -s contratos/tests -v
   ```

2. José mantiene `requirements.txt` general, que aún es un esqueleto. Debe incluir `-r contratos/requirements.txt` o la misma dependencia al completar el entorno común. No basta con instalar el archivo general vacío.
3. Revisa con Noel y José los cinco ejemplos principales y las firmas de `funciones.py`. Los contratos no equivalen a la implementación del solver, API, bot o agentes.
4. Las pruebas corresponden a estos contratos. La revisión de los tres, el esquema aplicado, una llamada real al modelo y FastAPI siguen siendo condiciones pendientes de V0.
5. Revisa los cambios de `contratos/` y `docs/bitacora_ia/emilia.md`; después prepara tu commit y PR según el acuerdo del equipo.

Puedes regenerar los JSON Schema con `python -m contratos.exportar_esquemas`.

## Archivos y propietarios

| Archivo | Para qué sirve |
| --- | --- |
| `modelos.py` | Cinco contratos principales, extracción del LLM y objetos auxiliares tipados |
| `consultas.py` | Solicitud y respuesta de `estado_sector` V4; firma de lectura que implementa Noel |
| `ESTADO_SECTOR.md` | Semántica, responsabilidades y decisiones confirmadas para la consulta |
| `estados.py` | Estados y enumeraciones serializados en español |
| `solicitudes.py` | Entradas y salidas de las herramientas de cálculo |
| `funciones.py` | Firmas de las cuatro funciones puras que implementa José |
| `errores.py` | Códigos y respuesta estructurada de error |
| `ejemplos/` | 28 fixtures sintéticos y manifiesto que identifica el modelo de cada JSON |
| `tests/` | 63 pruebas de contratos, ejecutables con unittest o pytest |
| `esquemas/` | JSON Schema para revisar e integrar con la API y frontend de Noel |
| `POLITICA_PRIORIDAD.md` | Política de demo diseñada y decisiones aprobadas por el usuario |

Emilia mantiene estos contratos. Noel conserva **API, permisos, bot, aprobación y toda la mensajería**. José implementa cálculo, verificador, pruebas independientes y documentación sin GUI. Las pruebas aquí incluidas son de los contratos de Emilia; no sustituyen las pruebas independientes de José.

## Los cinco contratos principales

| Contrato | Quién lo compone | Quién lo consume | Primera versión |
| --- | --- | --- | --- |
| `ReporteInterpretado` | Backend de Emilia a partir de extracción validada y datos reales del adaptador | Territorial | V1 |
| `IncidenteConsolidado` | Territorial y funciones de geografía de Emilia | Priorización | V2 |
| `EvaluacionNecesidades` | Priorización con resultados de José | Planificación y panel | V2 |
| `PropuestaDistribucion` | Planificación con solver y verificador de José | API y panel de Noel | V3 |
| `AvisoComunidad` | Comunicación, completado por servicios autorizados de Noel | Bandeja de salida de Noel | V4 |

Los cinco heredan contexto: `esquema_version`, `ejecucion_id`, `creado_en` y `origen`. Los UUID se serializan como cadenas JSON. El servidor crea los identificadores; no hay IDs aleatorios automáticos al cargar o reintentar un contrato. Un reintento conserva el ID del objeto y usa control de idempotencia.

### V1 y salida del modelo

Noel produce `ReporteRegistrado`, que contiene `EntradaReporte`. La entrada cruda conserva identificador externo y referencia interna del remitente para deduplicar y reanudar aclaraciones. Emilia envía al modelo únicamente el contenido pertinente y usa **`ExtraccionReporteLLM` como salida estructurada de Ingesta**.

```python
from contratos.modelos import ExtraccionReporteLLM, ReporteInterpretado

# Configuración de salida del agente de Ingesta:
# output_type=ExtraccionReporteLLM
# Después, el backend asocia UUID, origen, fecha y evidencias del reporte guardado.
interpretacion = ExtraccionReporteLLM.model_validate(datos_extraidos)
reporte = ReporteInterpretado.model_validate(payload_compuesto_por_backend)
```

No uses `ReporteInterpretado`, `PropuestaDistribucion` o `AvisoComunidad` completos como salida directa del LLM. En los demás agentes aplica la misma separación: el modelo propone una decisión acotada y el backend conserva los IDs, las versiones, las cantidades devueltas por las herramientas, los permisos y el destino autorizado. El catálogo resuelve coordenadas; el LLM no las inventa. Una foto respalda solo hechos visibles.

El texto de evidencia de Ingesta debe cotejarse con la entrada original; un fragmento devuelto por el LLM no demuestra por sí solo que estaba en el reporte. El backend vincula cada evidencia con el reporte original persistido. Inyección de instrucciones requiere pruebas reales del agente además del rechazo de campos extra.

### V2 y aclaraciones

`SolicitudAclaracion` no exige `plan_id` ni aprobación de ruta. Noel envía la pregunta; `RespuestaAclaracion` referencia la ejecución, el reporte y la aclaración. Su API comprueba que el remitente corresponda antes de reanudarla. No se deja una llamada al modelo abierta esperando.

Una necesidad puede estar pendiente con motivo y alerta urgente, sin puntaje ni posición. El incidente conserva todos sus reportes y permite corregir sus vínculos; `reportes_independientes` no puede superar el número de reportes. La confianza no entra en el puntaje ni sustituye la revisión de una posible urgencia. `primera_deteccion_en` no cambia cuando llega un duplicado.

## Entradas y salidas de José

| Función | Entrada | Salida |
| --- | --- | --- |
| `validate_need` | `SolicitudValidarNecesidad` | `ResultadoValidarNecesidad` |
| `score_needs` | `SolicitudPriorizarNecesidades` | `ResultadoPriorizarNecesidades` |
| `solve_routes` | `SolicitudResolverRutas` | `PropuestaDistribucion` |
| `verify_plan` | `SolicitudVerificarPlan` | `InformeVerificacion` |

Las funciones son síncronas, puras respecto a red y BD: no envían mensajes ni escriben Supabase. El trabajador decide cómo ejecutarlas sin bloquear la API. `HerramientasCalculo` es un Protocol con las firmas; no es la implementación de las funciones.

`score_needs` devuelve el lote completo, incluidos los pendientes. Los cinco contratos no son cinco tablas obligatorias: Noel y Emilia acuerdan persistir columnas y relaciones a partir del esquema sin duplicar innecesariamente JSON.

### Reglas de demanda

- `demanda.metodo=directa`: litros declarados, fuente y confirmación explícita del coordinador.
- `demanda.metodo=formula`: población atendida, dotación, días y reserva. Resultado esperado: `max(0, personas × dotacion × dias − reserva)`.
- Si falta un factor o confirmación, José devuelve pendiente con campos y motivos. La reserva `null` no se vuelve cero. Se admite una estimación previa sin validación, pero no puede entrar al ranking ni al solver como demanda confirmada.
- La capacidad de recepción va en `SolicitudValidarNecesidad.capacidad_recepcion_litros`. Si se desconoce, pedir validación o registrar un supuesto confirmado. Si la demanda supera la capacidad, no recortarla silenciosamente: queda pendiente de ajuste explícito.
- Validar instituciones con supuestos propios. No multiplicar la población completa del corregimiento por cada incidente. Cero explícito es distinto de desconocido; demanda cero no se convierte en una parada de entrega positiva.
- Una salida de fórmula también requiere confirmación para quedar validada. Registrar método, fuente y supuestos en la evaluación, y conservar solicitud y resultado en la traza para auditoría.

### Reglas de rutas

Escenario base: seis puntos, dos vehículos, un depósito; demanda completa por punto, una salida y retorno por vehículo. Se permite una flota de cero, uno o dos vehículos para representar incidencias. `disponible=false` significa que el solver no puede asignar ese vehículo. No hay recargas ni reparto parcial.

La matriz usa minutos enteros, diagonal cero y un orden explícito de nodos. `null` representa un arco bloqueado, no cero minutos. El solver debe excluirlo y el verificador comprobarlo. No se impone simetría. La matriz sintética no acredita transitabilidad de una carretera real.

José incorpora el tiempo de descarga y las ventanas de atención como intervalos de servicio: el inicio y fin de descarga deben quedar dentro de la ventana. Una hora de llegada anterior puede dar lugar a espera. La ruta respeta disponibilidad y turno, incluido retorno. Una demanda mayor que la capacidad individual queda pendiente: no se divide.

El solver debe reflejar las clases y el ranking en su selección de cobertura. No basta con minimizar viaje y agregar una explicación de prioridad después. Las obligaciones críticas son restricciones: si no se cubren, registrar el déficit y bloquear publicación. No se exige un orden temporal global entre camiones que contradiga ventanas; «críticos primero» significa prioridad de cobertura y clase antes del ranking general.

`SolicitudResolverRutas` incluye todas las necesidades de los puntos, incluso pendientes, para impedir que un crítico no validado desaparezca de la revisión. Pendientes y demanda cero no se asignan como entregas. El resultado conserva todo punto con demanda positiva que no pueda atenderse y su motivo; los críticos pendientes bloquean publicación. El verificador compara el resultado contra **toda** la solicitud original.

`TIMEOUT_SIN_SOLUCION` no significa inviabilidad. Si el solver encuentra una solución válida antes del límite, el estado es `factible` aunque no haya probado optimalidad. `inviabilidad_demostrada` exige una justificación comprobable; no mapear genéricamente «no devolvió solución» a ese estado.

## Responsabilidades de Noel en V4

1. Validar rol, versión vigente y datos dentro de una operación atómica. Las confirmaciones de estos modelos son registros; UUID y campos bien formados no autentican a una persona.
2. Obtener el resultado del verificador real sobre el contenido que se aprobará. Cada edición relevante incrementa la versión/invalida el plan. Un informe copiado con IDs iguales no acredita el contenido de un plan modificado.
3. Persistir la aprobación y avisos antes de enviar; revisar vigencia al publicar. La API es la única autoridad de aprobación.
4. Resolver `destino_id` en su tabla privada de destinos autorizados. Los JSON no contienen chat IDs reales ni claves.
5. Persistir `aviso.clave_idempotencia` con unicidad. Incluye **punto** además de plan, versión, sector, destino y tipo: evita colisiones si dos puntos comparten sector y destinatario. Esta versión usa avisos por punto; no agregarlos por sector sin cambiar el contrato.
6. Renderizar datos aprobados con plantillas. Pydantic no comprueba que el texto libre o audio diga exactamente los litros y horarios de sus campos estructurados.
7. Un timeout del proveedor queda `incierto`, sin reenvío ciego. `enviado` exige ID del proveedor y fecha; no demuestra recepción ni entrega física de agua. Una nueva versión genera una clave de aviso diferente.

`ConfirmacionEntrega` separa litros entregados de asignados y la registra solo un conductor o coordinador autorizado. Si cambia flota/demanda/política, invalidar el plan, conservar su aprobación histórica y recalcular antes de nuevos avisos.

## Validación y errores

Campos extra se rechazan; las fechas llevan zona horaria. Números negativos, no finitos y booleanos usados como cantidades no pasan. Los modelos comprueban coherencia interna; no prueban geografía real, acceso a datos, capacidad física o permisos.

Usa `model_validate`/`model_validate_json` antes de aceptar datos y `model_dump(mode="json")` al intercambiarlos. No uses `model_construct` ni `model_copy(update=...)` para aceptar cambios no validados. No modifiques un objeto validado y asumas que se ha vuelto a validar: vuelve a construirlo desde su payload. La vigencia de BD siempre se comprueba en el servicio de Noel.

Pydantic devuelve `ValidationError` para errores de forma. Los pendientes esperados son resultados de dominio, no excepciones técnicas. `ErrorDominio` y `ExcepcionContrato` pueden representar fallos de operación; Noel decide el mapeo HTTP. Por ejemplo, una política aún propuesta no produce un ranking operativo: devuelve `politica_no_activa` o mantiene la ejecución en validación.

## Ejemplos y alcance de las pruebas

Los 24 JSON son **fixtures sintéticos creados a mano**. Incluso `plan_aprobado_simulado.json`, las confirmaciones y `informe_verificacion.json` son ejemplos de formato: no son aprobaciones reales, resultados de OR-Tools ni pruebas ejecutadas de un backend. La ubicación y la dotación de los ejemplos no son datos operativos ni recomendaciones.

Resultado de verificación local: **43 pruebas de contratos aprobadas** y 24 ejemplos con roundtrip JSON correcto. No se ejecutaron los 25 evals del sistema, Gemini, Telegram, Supabase ni un solver real. Las modalidades opcionales tienen forma de entrada, pero no están implementadas por este paquete.

## Fuentes de las decisiones

- `RutaAgua_Oeste_Versiones_Implementacion.docx`, aportado por el usuario: V0–V6, cinco contratos y cuatro herramientas.
- Decisiones del usuario: demanda directa y fórmula; crítico/general; bloqueo ante déficit crítico; pendientes sin cero; alerta urgente; desempate por atención y antigüedad; Noel dueño del bot y mensajería.
- Diseño técnico: UUID, nombres JSON, comprobaciones estructurales, formatos de errores, campos auxiliares y política propuesta de demo. No se presentan como decisiones ya confirmadas por los tres integrantes.
- Documentación de Pydantic para modelos y serialización: https://pydantic.dev/docs/validation/latest/concepts/models/

Los puntos reales, dotación, capacidades, horarios, descarga y despliegue siguen siendo decisiones del escenario. Los tipos de los contratos permiten acordarlos sin renombrar campos ni tomar por reales los fixtures.

## Consulta de estado del sector (ampliación V4)

`SolicitudEstadoSector` y `EstadoSector` están en `contratos/consultas.py` y
también se exportan desde `contratos`. Noel implementa la firma
`estado_sector(entrada: SolicitudEstadoSector) -> EstadoSector`.
Solo se muestran planes aprobados y válidos y todos los puntos activos del
sector. Sin asignación: litros y ventana en `null`, con motivo. Sin plan
vigente: no se rescatan asignaciones históricas.

Ver [especificación de estado_sector](ESTADO_SECTOR.md) para selección de
vigencia, proyección, ejemplos, origen y revisión pendiente de Noel/José.
La consulta no crea ejecuciones de agentes ni sustituye las comprobaciones
de vigencia y permisos de la API. Es una ampliación aditiva: conserva las
interfaces existentes y agrega cuatro fixtures y dos JSON Schema raíz.
