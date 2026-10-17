# Conexión compartida del backend

**Dueña:** Emilia. Noel puede importar el cliente desde la API y el bot.

## Preparación

Desde la raíz del repositorio, con Python 3.10 o superior:

```bash
python -m pip install -r requirements.txt
```

Guarda `.env` en la raíz (con punto inicial), usando `.env.example` como guía.
Completa `SUPABASE_URL` con la URL del proyecto y
`SUPABASE_SERVICE_ROLE_KEY` con la clave de servidor: `service_role` heredada
o una clave nueva `sb_secret_...`. Las claves anon/publishable no permiten
acceder al esquema cerrado de este proyecto. No subas `.env` a Git ni pases
esta clave a React. No hace falta completar Gemini o Telegram para esta prueba.

La configuración lee `.env` desde la raíz aunque cambie el directorio de trabajo.
Las variables del proceso tienen prioridad, incluso si están vacías. Importar
los módulos no abre conexiones ni requiere credenciales. La clave se oculta en
la representación de la configuración; los errores propios no imprimen secretos.

## Prueba real de solo lectura

Con la migración 0001 ya aplicada:

```bash
python -m comun.db
```

Resultado esperado (0 o 1 filas):

```json
{"estado": "ok", "tabla": "sectores", "filas_leidas": 0}
```

Una tabla vacía es correcta. El comando solo lee `sector_id` y no muestra
registros, URL ni claves. En error termina con código 1 y un mensaje seguro.
La prueba confirma acceso REST a `public.sectores`; no valida todo el esquema
ni Gemini, Telegram, agentes o el endpoint `/salud` de Noel.

## Uso desde API, agentes y bot

```python
from comun.db import get_supabase

db = get_supabase()
respuesta = db.table("sectores").select("sector_id").limit(1).execute()
```

El cliente es síncrono y se reutiliza por proceso. En FastAPI úsalo desde
funciones `def` o mediante ejecución en un hilo para no bloquear un endpoint
`async def`. Reinicia el proceso si cambias `.env`. No uses `auth.sign_in`,
`sign_out` ni sesiones de usuarios con este cliente compartido: conserva
credenciales de servidor y no persiste ni refresca sesiones.

`crear_cliente(configuracion)` crea un cliente independiente.
`comprobar_conexion(cliente)` permite verificar uno ya creado. La inicialización
sigue la [API oficial de Supabase para Python](https://supabase.com/docs/reference/python/initializing).

## Pruebas locales

```bash
python -m unittest discover -s comun/tests -v
python -m unittest discover -s contratos/tests -v
```

Las pruebas locales usan datos sintéticos y dobles del SDK. No sustituyen
`python -m comun.db` contra el proyecto real. No se aplican migraciones ni se
escriben datos desde estos módulos.
