# calculo

**Dueño:** José

demanda, prioridad, matriz, solver, verificador, orden_llegada

## Plan V3: bloques 4 y 5

Disponibles `calculo.solver.solve_routes` (implementado en `solver_v3.py`) y `calculo.verificador.verify_plan`. Selección parcial por criticidad/ranking, restricciones del MVP, motivos por punto e informe independiente. Consultar [método, estados y límites](PLAN_V3.md).

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_plan_v3
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_plan_v3.py -q
```

Las tres demos de plan cubren propuesta completa, una cisterna y déficit crítico. Ningún resultado autoriza publicación. Las funciones y pruebas locales no acreditan la integración del bloque 6.

## Tools de necesidad V2

Disponibles `calculo.demanda.validate_need` y `calculo.prioridad.score_needs` con los contratos compartidos. Consultar [reglas y límites de V2](NECESIDADES_V2.md).

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_v2
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_necesidades_v2.py -q
```

## Solver mínimo V1

Desde la raíz del repositorio, con el entorno V0 instalado:

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_v1
.\.venv\Scripts\python.exe -m pytest calculo/tests contratos/tests -q
```

La demo ejecuta `solve_routes_minimo(SolicitudResolverRutas) -> PropuestaDistribucion` en `solver.py`. Consume el fixture sintético de Emilia en `contratos/ejemplos/solicitud_resolver_rutas.json`: dos cisternas de 10 000 L, un depósito, seis puntos con 18 000 L, diez minutos por viaje y diez por descarga. No modifica ese ejemplo ni activa la política pendiente de `datos/escenario/`. Las confirmaciones ficticias del fixture están identificadas como tales; no son autorización humana real.

El ensayo exige cobertura completa. OR-Tools calcula rutas con capacidad, disponibilidad, ventanas completas de servicio, espera y retorno dentro del turno. Usa la matriz por identificadores, respeta dirección y arcos `null` bloqueados. Las cantidades se representan exactamente en mililitros; se rechazan más de tres decimales y cantidades superiores a 10^12 L en este ensayo. El tiempo interno usa segundos UTC, redondeando límites de forma conservadora; la consola muestra las horas UTC−05:00 del fixture. IDs de parada derivados de plan/versión/vehículo/punto conservan estabilidad al repetir la entrada.

Si no puede cubrir el conjunto completo, V1 devuelve todas las necesidades como pendientes con motivo y sin rutas; no distribuye una fracción ni afirma inviabilidad del problema de reparto parcial. Un timeout sin solución se distingue del fallo genérico. Son estados del ensayo completo, no resultados de optimización de cobertura. La selección por criticidad/ranking, casos pendientes/cero del flujo operativo y diagnóstico individual de déficit corresponden al solver completo de V3.

Todas las salidas están pendientes de revisión, sin aprobación ni informe de verificación y con publicación bloqueada. Las aserciones de las pruebas comprueban físicamente rutas calculadas, pero no implementan `verify_plan` ni sustituyen el verificador independiente de V3. No registrar esta función como `solve_routes` operativa antes de completar esa versión.

Los finalizadores fijan primero retornos tempranos para todos los vehículos y después maximizan sus salidas sin retrasar esos retornos. Así se evita la espera inicial innecesaria cuando el turno empieza antes que las ventanas. No se promete eliminar esperas intermedias impuestas por ventanas diferentes ni optimizar globalmente todas las rutas. La regresión con turno desde 06:00 sale a 07:50, inicia servicio a 08:00 y retorna a 09:00; la demo base sigue 08:00–09:10. Son ahora 17 pruebas V1, incluidas las dos de esta corrección; el XML de V1 conserva la ejecución histórica original de 15 pruebas de cálculo más contratos.

## Evidencia reproducible

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_v1 --salida evals/resultados/solver_minimo_v1.json
```

No sobrescribe un archivo de evidencia existente. Usar otro nombre para guardar un nuevo ensayo. La evidencia conserva entrada, salida, esperado, métricas con denominador, versión y duración. `evals/resultados/v1_pruebas.xml` conserva el resultado de la ejecución de pruebas registrada durante el desarrollo. Los horarios de atención son simulados del escenario, no horarios de entrega del hackatón.

Las pruebas cubren carga, servicio y ventanas, retorno, espera, unicidad y cantidades completas, capacidades distintas, flota no disponible, matriz reordenada/asimétrica/bloqueada, política propuesta, datos pendientes, origen no sintético y traducción de estados del motor. El timeout se comprueba con un resultado del motor simulado, no como evidencia de timeout real.

Referencias de implementación: [OR-Tools capacidad](https://developers.google.com/optimization/routing/cvrp) y [OR-Tools ventanas](https://developers.google.com/optimization/routing/vrptw). No se usan rutas viales reales.

Integración posterior de las herramientas: el agente y trabajador de Emilia ya
invocan solver/verificador en el fixture separado; ver [guía V3](../docs/V3_EMILIA.md).
Las evidencias locales no acreditan por sí solas despliegue, panel ni cierre conjunto.
