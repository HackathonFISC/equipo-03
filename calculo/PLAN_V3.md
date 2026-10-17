# Plan V3: solver completo del MVP y verificador independiente

Dueño: José. Bloques 4 y 5. Implementación sobre contratos 1.0, seis puntos como máximo, dos cisternas como máximo y un depósito. No amplía el modelo a recargas ni entregas divididas.

```python
from calculo.solver import solve_routes
from calculo.verificador import verify_plan
```

`solve_routes(SolicitudResolverRutas) -> PropuestaDistribucion` se expone desde solver.py; su implementación está en solver_v3.py. `solve_routes_minimo` conserva V1 sin sustituir su comportamiento. `verify_plan(SolicitudVerificarPlan) -> InformeVerificacion` está en verificador.py. No se requieren dependencias nuevas.

## Objetivo y alcance de la selección

Se maximiza primero el número de críticos confirmados cubiertos. Después se prefiere lexicográficamente la cobertura del ranking V2 (críticos antes que generales); finalmente se minimiza la suma de las duraciones de ruta. La prioridad determina la selección de puntos; su secuencia física respeta viajes, ventanas y duración. No se promete orden universal de llegada entre camiones distintos.

Dos críticos que caben juntos prevalecen sobre uno de mayor puntaje que impediría cubrirlos. Incluso con la mayor cobertura posible, un crítico sin atender impide una verificación válida y exige escalamiento. Una propuesta parcial que cubre todos los críticos puede ser estructuralmente válida con generales pendientes explícitos; sigue necesitando aprobación y los controles de publicación.

El solver recalcula los puntajes/componentes y el orden relativo con score_needs para rechazar rankings obsoletos respecto a la política/factores del snapshot. No modifica la entrada ni confirma información. Una necesidad sin demanda validada, prioridad calculada o ventana queda pendiente. La demanda cero validada no genera una parada de litros ficticios. Una estimación cero sin validar sigue siendo información pendiente.

## Restricciones y método

Para el límite de seis puntos se enumeran rutas candidatas por vehículo y subconjunto. Cada candidata cumple capacidad, disponibilidad, ventana completa de descarga, viajes dirigidos, arcos bloqueados `null` y retorno al depósito dentro del turno. Se conserva la mejor ruta de cada vehículo/subconjunto y OR-Tools CP-SAT selecciona una combinación disjunta, con una salida máxima por vehículo.

La enumeración usa la matriz por UUID, sin inferir rutas a partir de coordenadas. El horario se calcula con microsegundos enteros para conservar los límites de los contratos; se fija el retorno más temprano y se retrasa la salida compatible para reducir espera inicial. Las cantidades son exactas hasta mililitros, con máximo de 10^12 litros por valor; un exceso o precisión no admitida produce error de contrato, no redondeo silencioso. Horizonte de flota superior a 10^13 microsegundos se rechaza en este MVP.

El método es específico de este límite y no se presenta como solución escalable a flotas o catálogos mayores. Los tiempos sintéticos/estimados conservan su etiqueta y no acreditan tráfico, carretera o acceso físico. La recepción procede de la validación V2: la solicitud de rutas no contiene por sí sola el tanque ni un certificado sanitario.

Presupuesto compartido de enumeración y búsqueda; un solo trabajador CP-SAT y semilla fija. La óptima cobertura solo se declara cuando terminó la enumeración y CP-SAT devuelve OPTIMAL. FEASIBLE produce una propuesta factible sin afirmar óptimo. UNKNOWN o enumeración incompleta sin propuesta produce `timeout_sin_solucion`, nunca prueba de inviabilidad. [Estados oficiales de CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

## Pendientes y estado del solver

Cada punto aparece exactamente una vez, atendido o pendiente, con identidad y litros conservados. La cantidad desconocida sigue en null.

| Situación | Código de pendiente |
| --- | --- |
| Demanda/prioridad/ventana incompletas | datos_pendientes |
| Demanda indivisible superior a toda cisterna disponible | demanda_supera_vehiculo |
| Ninguna cisterna disponible o capacidad insuficiente comprobada | sin_capacidad |
| Sin camino dirigido desde depósito y regreso | sin_acceso |
| Ninguna ruta cumple tiempos incluso relajando capacidad | ventana |
| Presupuesto agotado sin propuesta | timeout |
| Selección conjunta, diagnóstico no completado u otra limitación | otro, con explicación |

Para distinguir capacidad de tiempo en recorridos que necesitan pasar por otros puntos atendidos, el diagnóstico puede repetir la enumeración relajando capacidad, dentro del presupuesto. Si no completa ese diagnóstico, no inventa una causa concreta.

`inviabilidad_demostrada` significa que no puede realizarse ninguna entrega positiva validada bajo las restricciones del snapshot (por ejemplo sin flota, todas las demandas demasiado grandes o enumeración completa sin rutas). No significa que los puntos sin datos sean imposibles ni que una propuesta parcial positiva sea inviable por no cubrir todo. Si solo faltan datos se devuelve error con esos pendientes; si toda demanda es cero validada, la propuesta vacía puede ser factible.

## Verificación independiente y versión de entradas

El verificador no importa OR-Tools, no invoca el solver ni reutiliza su enumeración, rutas candidatas o aritmética de carga/horarios. Ignora cualquier informe válido adjunto y comprueba otra vez:

- Suma de litros por vehículo, disponibilidad y una salida por cisterna.
- Identidad de depósito, puntos, incidentes y paradas; contabilidad completa de atendidos/pendientes.
- Demanda positiva validada y entrega íntegra por punto, sin dividirla.
- Llegada desde la salida/descarga anterior, duración exacta de servicio, espera y ventana.
- Retorno desde la última parada y cumplimiento de turno.
- Versiones, ejecución, origen, política activa y cobertura crítica/urgencias pendientes.

Las comprobaciones usan la matriz y servicios originales, no las estimaciones que el solver afirma como válidas. Viajes/descargas extremos se comparan como duraciones enteras sin construir fechas que desborden. Una propuesta que incumple el contrato también se rechaza; los errores de estructura se informan sin afirmar que se realizaron las ocho comprobaciones.

La solicitud se serializa mediante `model_dump(mode='json')`, JSON UTF-8 con `ensure_ascii=False`, claves ordenadas y separadores `(',', ':')`. El solver incluye su SHA-256 en una única entrada de supuestos: `HUELLA_ENTRADAS_SHA256=<hex>`. El verificador recalcula esa huella de manera independiente. Así detecta cambios de pesos, flota, ventanas, matriz o cantidades aun cuando se conserve indebidamente la etiqueta datos_version. Una propuesta antigua sin huella no queda verificada automáticamente.

El servicio debe conservar supuestos y el snapshot original. La huella no es una firma, permiso ni consulta de vigencia en BD: invalidación concurrente y aprobación de versión vigente siguen correspondiendo al backend. El informe usa el contexto del snapshot e identifica violaciones; nunca cambia el estado a aprobado.

## Ejecución y evidencia

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_plan_v3
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_plan_v3.py -q
```

| Caso sintético | Atendidos | Pendientes | Litros asignados | Verificación |
| --- | ---: | ---: | ---: | --- |
| Seis puntos, dos cisternas | 6 | 0 | 15 000 | Válida |
| Una cisterna disponible | 4 | 2 | 9000 | Válida; dos críticos cubiertos |
| Crítico con demanda de 12 000 L | 5 | 1 | 12 000 | Inválida por cobertura crítica |

Las demos actualizan versiones para cada variante y guardan solicitudes, esperado, obtenido, propuestas, informes, métricas y huellas del código en `evals/resultados/plan_v3_bloques_4_5.json`. El XML de regresión se conserva en `plan_v3_pruebas.xml`. `--salida ruta_nueva.json` guarda otra evidencia sin sobrescribir. Los tests de timeout y FEASIBLE sin optimalidad usan estados simulados y no acreditan un timeout real medido.

## Entrega al equipo y límites

Las funciones de esta entrega de bloques 4/5 ya son invocadas por `agentes/planificacion.py` y el trabajador de Emilia, con snapshot/propuesta/informe y escalamiento. Ver [integración V3](../docs/V3_EMILIA.md), con pruebas locales y PostgreSQL temporal. Noel puede mostrar rutas, cantidades, pendientes, motivo, versión y verificación. La conexión de API/panel corresponde al bloque 6 y debe verificarse con Noel; esta entrega de herramientas no modifica sus módulos ni acredita despliegue.

La salida de `solve_routes` queda en pendiente_revision, con bloqueos de publicación y sin aprobación; el solver no adjunta un informe como si ya estuviera verificado. El agente de Planificación ejecuta después `verify_plan` y conserva su informe independiente. El informe independiente puede ser válido en términos del modelo y seguir sin existir autorización operativa. Las confirmaciones, recursos y necesidades del ensayo son ficticios; las referencias de lugares conservan origen documental real y validación operativa pendiente. No se certifica calidad del agua, recepción, acceso, rol, entrega física ni vigencia de la BD.
