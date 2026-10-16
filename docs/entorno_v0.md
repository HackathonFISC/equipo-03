# Entorno de cálculo V0

Este procedimiento prepara las herramientas de José y verifica contratos y escenario sin credenciales. Probado en Windows de 64 bits con Python 3.12.14. Todavía no arranca API, agentes, Supabase ni Telegram y no implementa las cuatro tools.

## Preparación desde la raíz del repositorio

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/verificar_entorno.py
.\.venv\Scripts\python.exe -m pytest contratos/tests -q
```

No se requiere activar el entorno en PowerShell: se usa su ejecutable directamente. En macOS/Linux la ruta equivalente es `.venv/bin/python`; esos sistemas no se probaron en esta revisión.

`requirements.txt` se organiza en contratos compartidos de Emilia, API/persistencia/bot de Noel (`fastapi`, `uvicorn[standard]`, `supabase`, `python-telegram-bot`) y cálculo/pruebas de José (OR-Tools y pytest). `requirements-lock.txt` restringe la resolución a las versiones exactas comprobadas, incluidas las dependencias indirectas. La instalación necesita acceso a PyPI; las comprobaciones posteriores funcionan sin conexión. Para actualizar dependencias, regenerar la lista en un entorno limpio y repetir las comprobaciones. Este archivo aún no incluye las dependencias de agentes de Emilia ni las de React, que se coordinan por separado.

## Configuración y secretos

La verificación local de cálculo no necesita `.env`. Para la integración posterior, copiar `.env.example` a `.env` y completar solo los valores acordados con cada dueño. No registrar claves ni destinos privados. El `.gitignore` existente ya excluye `.venv/`, `.env`, variantes privadas, cachés de Python y pytest. `.env.example` permanece versionable. No se cambia ese archivo para simular credenciales disponibles.

## Evidencia de esta preparación

- Instalación limpia inicial en un entorno temporal y repetición en `.venv` de `equipo-03` con Python 3.12.14, el 16 de octubre de 2026 a las 17:51 (UTC−05:00).
- Pydantic 2.14.1 (dentro del rango compartido de Emilia), OR-Tools 9.15.6755 y pytest 9.1.1.
- 43 pruebas de contratos y 24 subpruebas aprobadas.
- Componentes de los tres JSON validados contra los modelos de Emilia; identificadores, cantidades de objetos y versiones contrastados.
- Motor nativo de OR-Tools inicializado; no se resolvió una ruta del escenario.
- `pip check` sin conflictos de dependencias.
- Ampliación del 16 de octubre a las 17:56 (UTC−05:00): FastAPI 0.143.3, Uvicorn 0.54.0 con extras `standard`, Supabase 2.33.0 y python-telegram-bot 22.8 instalados junto con las dependencias anteriores. Importaciones comprobadas, verificador y pruebas de contratos repetidos con éxito. Archivo de versiones actualizado desde ese entorno. No se probaron conexiones reales a Supabase/Telegram ni el servicio API de Noel.

La política está en `propuesta_demo`, las necesidades siguen pendientes y ninguna confirmación operativa se acredita por validar JSON. El cierre de V0 del equipo requiere además los acuerdos y las pruebas de Emilia y Noel.

## Aplicación al repositorio

La propuesta se probó primero fuera de `equipo-03`, en una copia temporal de contratos y datos. Tras la instrucción del usuario se aplicaron las dependencias, el verificador y esta guía al repositorio. Se creó allí un entorno virtual nuevo y se repitieron las comprobaciones con éxito. El entorno virtual permanece excluido de Git; los demás integrantes deben crear el suyo con los pasos anteriores. El usuario realiza el commit y el push.
