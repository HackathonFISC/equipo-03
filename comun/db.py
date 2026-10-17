"""Cliente Supabase síncrono y comprobación de lectura para el backend."""

from functools import lru_cache
from typing import TYPE_CHECKING

from comun.config import Configuracion, ErrorConfiguracion, cargar_configuracion

if TYPE_CHECKING:
    from supabase import Client


class ErrorConexion(RuntimeError):
    """Error de infraestructura cuyo mensaje no expone claves ni respuestas crudas."""


def crear_cliente(configuracion: Configuracion | None = None) -> "Client":
    """Crea el cliente sin consultar tablas. Solo para procesos del backend."""
    config = configuracion if configuracion is not None else cargar_configuracion()
    try:
        from supabase import create_client
        from supabase.client import ClientOptions
    except ImportError:
        raise ErrorConexion(
            "Falta el SDK de Supabase. Instala las dependencias de requirements.txt."
        ) from None
    try:
        return create_client(
            config.supabase_url,
            config.supabase_service_role_key,
            options=ClientOptions(
                schema="public",
                postgrest_client_timeout=10,
                storage_client_timeout=10,
                persist_session=False,
                auto_refresh_token=False,
            ),
        )
    except Exception:
        raise ErrorConexion(
            "No se pudo crear el cliente Supabase. Revisa URL, clave de servidor y dependencias."
        ) from None


@lru_cache(maxsize=1)
def get_supabase() -> "Client":
    """Un cliente por proceso, creado cuando se solicita por primera vez.

    Reinicia el proceso tras cambiar .env. No uses auth.sign_in/sign_out con
    este cliente compartido: su credencial es exclusivamente de servidor.
    """
    return crear_cliente()


def comprobar_conexion(cliente: "Client | None" = None) -> dict[str, object]:
    """Comprueba acceso REST al esquema con SELECT, sin modificar datos.

    Una tabla vacía también es un resultado correcto. No comprueba las otras
    tablas, Gemini, Telegram ni el estado completo de las migraciones.
    """
    db = cliente if cliente is not None else get_supabase()
    try:
        respuesta = db.table("sectores").select("sector_id").limit(1).execute()
        if not isinstance(respuesta.data, list):
            raise ValueError("Respuesta inesperada")
        return {"estado": "ok", "tabla": "sectores", "filas_leidas": len(respuesta.data)}
    except Exception:
        raise ErrorConexion(
            "No se pudo leer public.sectores. Revisa conexión, clave de servidor, permisos y migración 0001."
        ) from None


def main() -> int:
    import json

    try:
        print(json.dumps(comprobar_conexion(), ensure_ascii=False))
        return 0
    except (ErrorConfiguracion, ErrorConexion) as error:
        print(json.dumps({"estado": "error", "mensaje": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
