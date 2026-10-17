# Entorno de cálculo V0

Este procedimiento prepara el entorno Python compartido de Emilia, Noel y José y verifica contratos, conexión simulada y escenario sin credenciales. Probado con Python 3.12.14 en Windows de 64 bits y macOS 15.8.1 Apple Silicon (arm64). La preparación no arranca API, agentes ni Telegram y no ejecuta conexiones reales a Supabase. No acredita la implementación de las cuatro tools.

## macOS: preparación desde la raíz del repositorio

Usar Python 3.12 para reproducir el entorno comprobado. Comprobar primero
`python3.12 --version`; el `python3` predeterminado de este Mac apunta a 3.14,
que no se ha validado para este proyecto. Si no existe `python3.12`, instalar
Python 3.12 antes de crear el entorno o usar el intérprete local indicado abajo.
Crear cada entorno en el propio equipo; no copiar `.venv` desde Windows ni
entre equipos Intel y Apple Silicon.

```bash
cd /Users/hdemercado/Documents/GitHub/equipo-03
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python scripts/verificar_entorno.py
.venv/bin/python -m pytest contratos/tests comun/tests -q
```

**En este Mac ya se creó `.venv`** con Python 3.12.14 arm64 del runtime de
Codex. La ruta usada para crearlo fue:

```bash
/Users/hdemercado/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .venv
```

Esta ruta es específica del equipo y depende de conservar el runtime de Codex.
Para usar ahora el entorno existente no hace falta recrearlo: ejecutar los
comandos `.venv/bin/python ...` desde la raíz. Para recrearlo con una instalación
independiente, usar Python 3.12 y reinstalar las dependencias. No sustituir la
versión de Python dentro de un entorno existente.

Activación opcional en Terminal de macOS (zsh o bash):

```bash
source .venv/bin/activate
python --version
python -m pip check
# Al terminar:
deactivate
```

Sin activarlo, `.venv/bin/python` siempre selecciona el intérprete del proyecto.
En el editor seleccionar `equipo-03/.venv/bin/python` como intérprete. No usar
`sudo pip`, instalar dependencias globalmente ni omitir el entorno para evitar
errores de un Python administrado por el sistema.

## Windows: preparación desde la raíz del repositorio

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/verificar_entorno.py
.\.venv\Scripts\python.exe -m pytest contratos/tests -q
```

No se requiere activar el entorno en PowerShell: se usa su ejecutable directamente. Para incluir las pruebas actuales de conexión simulada, añadir `comun/tests` al comando de pytest. Linux no se ha probado en esta revisión; macOS tiene procedimiento y evidencia propios arriba.

`requirements.txt` se organiza en contratos compartidos de Emilia, API/persistencia/bot de Noel (`fastapi`, `uvicorn[standard]`, `supabase`, `python-dotenv`, `python-telegram-bot`) y cálculo/pruebas de José (OR-Tools y pytest). `requirements-lock.txt` restringe la resolución a las versiones exactas comprobadas, incluidas las dependencias indirectas. En macOS, `uvicorn[standard]` instala además `uvloop`; su versión comprobada se restringe con un marcador de plataforma que no obliga a instalarlo en Windows. Las restricciones no fuerzan por sí solas paquetes que la plataforma no requiere, como `colorama` o `tzdata`. La instalación necesita acceso a PyPI; las comprobaciones posteriores funcionan sin conexión. Para actualizar dependencias, regenerar la lista en un entorno limpio y repetir las comprobaciones. Este archivo aún no incluye las dependencias de agentes de Emilia ni las de React, que se coordinan por separado.

## Configuración y secretos

La verificación local de cálculo no necesita `.env`. Para la integración posterior, copiar `.env.example` a `.env` y completar solo los valores acordados con cada dueño. No registrar claves ni destinos privados. El `.gitignore` existente ya excluye `.venv/`, `.env`, variantes privadas, cachés de Python y pytest. `.env.example` permanece versionable. No se cambia ese archivo para simular credenciales disponibles.

`comun/config.py` y `comun/db.py` ya están disponibles. Después de completar
`SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` en `.env`, la comprobación real y
separada de solo lectura se ejecuta en macOS con:

```bash
.venv/bin/python -m comun.db
```

Usar `service_role` o una clave `sb_secret_...` exclusivamente en el backend.
Una clave `anon` no permite leer las tablas del esquema cerrado. En la prueba
anterior de conexión se obtuvo el error de permisos 42501 porque el valor local
tenía rol `anon`; queda pendiente corregir esa clave y repetir la lectura.
Las pruebas locales aprobadas no acreditan acceso real a Supabase. Ver
[guía de conexión](../comun/README.md).

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

## Evidencia de macOS (2026-10-16 19:19 EST)

- `.venv` creado en este clon con Python 3.12.14, macOS 15.8.1 y arquitectura arm64; el intérprete confirmó que está dentro de un entorno virtual.
- Instalación completa de `requirements.txt` con las restricciones compartidas. Pydantic 2.14.1, OR-Tools 9.15.6755, pytest 9.1.1, FastAPI 0.143.3, Uvicorn 0.54.0, Supabase 2.33.0 y python-telegram-bot 22.8.
- `python-dotenv` 1.2.4 y `uvloop` 0.23.0 instalados. Se añade la restricción de `uvloop` solo para CPython en macOS/Linux; Linux continúa sin comprobarse.
- `pip check`: sin conflictos. Verificador V0: motor nativo de OR-Tools, escenario e importaciones de API y bot correctos.
- `pytest contratos/tests comun/tests`: **60 pruebas y 30 subpruebas aprobadas**. Las pruebas de conexión usan dobles y datos sintéticos, sin red ni claves.
- `.venv/` y `.env` excluidos de Git. No se modificaron credenciales, datos remotos ni los pasos existentes de Windows. No se inició la API ni se enviaron mensajes. No se hizo commit ni push.

En macOS Intel, otras versiones de macOS y Python 3.14 no se han repetido estas
comprobaciones. Si falta un paquete binario compatible, conservar el error,
comprobar versión y arquitectura de Python y coordinar el ajuste de versiones
con José; no regenerar el archivo compartido de versiones sin revisión.
