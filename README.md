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

## Evals

Al menos 15 casos de prueba, métrica y resultados.

## Bitácora de IA

Qué partes se hicieron con IA, con qué herramienta y qué se modificó a mano.

---

Entrega: tag de git `final-24h` sobre el último commit válido, al cumplirse la hora 24.
