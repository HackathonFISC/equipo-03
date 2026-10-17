# Nombre del proyecto

<!-- Cambia el 0 por el número de su reto y deja la línea tal cual ("Reto: N"):
       1 = Agua · 2 = Educación · 3 = Empleabilidad
     No cambien de reto sin autorización de los organizadores. -->
Reto: 1

## Equipo

- José Saavedra (@jos051225)
- Noel Echeverría (@NoelRevotn)
- Emilia Demercado (@Mochi-coder-star)

## Problema

Qué problema resuelve el proyecto, para quién y con qué datos.

## Arquitectura de agentes

Agentes, herramientas, flujos y punto de intervención humana (incluir el diagrama).

## Tecnologías y fuentes de datos

## Instalación y ejecución

Para preparar el entorno de cálculo V0, desde la raíz del repositorio en Windows con Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/verificar_entorno.py
.\.venv\Scripts\python.exe -m pytest contratos/tests -q
```

Consulta [la guía del entorno V0](docs/entorno_v0.md) para el alcance y las versiones comprobadas. Estas verificaciones no necesitan credenciales. La integración con API, agentes, Supabase y Telegram se prepara por separado; no se arranca con estos comandos. Para esa integración se usa `.env.example` sin publicar claves reales.

Para ejecutar el solver mínimo sintético V1 de José:

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_v1
.\.venv\Scripts\python.exe -m pytest calculo/tests contratos/tests -q
```

Consulta [el alcance del ensayo V1](calculo/README.md). La demo calcula rutas locales con OR-Tools, sin publicar planes ni conectar servicios externos. La salida de referencia y las pruebas ejecutadas están en `evals/resultados/solver_minimo_v1.json` y `evals/resultados/v1_pruebas.xml`.

Para probar selección parcial y verificación independiente de V3:

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_plan_v3
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_plan_v3.py -q
```

Consultar [solver y verificador V3](calculo/PLAN_V3.md). Se prueban seis puntos con dos cisternas, retiro de una cisterna y déficit crítico. La integración de Planificación de Emilia añade persistencia comprobada en PostgreSQL temporal; aplicación de 0009 en Supabase, API/panel y recorrido conjunto siguen pendientes según la evidencia del repositorio. Las propuestas conservan bloqueos de publicación.

## Evals

Para reunir la regresión del equipo y las comprobaciones preparatorias de V4:

```powershell
.\.venv\Scripts\python.exe -m evals.ejecutar --salida ../tmp/evaluacion_v4_01
```

La carpeta debe ser nueva. El código de salida 2 indica integración pendiente;
los resultados locales no acreditan aprobación ni envío real. Consultar
[alcance, pruebas y coordinación de V4](evals/V4.md).

Para probar demanda y prioridad de V2 sin servicios externos:

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_v2
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_necesidades_v2.py -q
```

Consultar [las tools de V2](calculo/NECESIDADES_V2.md). La demo usa confirmaciones ficticias y no activa la política del escenario compartido.

Al menos 15 casos de prueba, métrica y resultados.

## Bitácora de IA

Qué partes se hicieron con IA, con qué herramienta y qué se modificó a mano.

---

Entrega: tag de git `final-24h` sobre el último commit válido, al cumplirse la hora 24.
