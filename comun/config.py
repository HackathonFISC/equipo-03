"""Configuración del backend. Importar este módulo no lee claves ni abre conexiones."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]


class ErrorConfiguracion(ValueError):
    """Configuración ausente o inválida, con mensajes que no incluyen secretos."""


@dataclass(frozen=True)
class Configuracion:
    supabase_url: str
    supabase_service_role_key: str = field(repr=False)


def cargar_configuracion(
    archivo_env: Path | str | None = None,
    *,
    entorno: Mapping[str, str] | None = None,
) -> Configuracion:
    """Lee .env en la raíz; las variables del proceso tienen precedencia.

    `entorno` permite probar la configuración sin modificar os.environ.
    No se requieren claves de Gemini, Telegram o frontend para usar la base.
    """
    ruta = Path(archivo_env) if archivo_env is not None else RAIZ_PROYECTO / ".env"
    valores: dict[str, str | None] = {}
    if ruta.is_file():
        try:
            from dotenv import dotenv_values
        except ImportError:
            raise ErrorConfiguracion(
                "Falta python-dotenv. Instala las dependencias de requirements.txt."
            ) from None
        try:
            # Sin interpolación: los secretos se conservan literalmente.
            valores.update(dotenv_values(ruta, interpolate=False))
        except (OSError, UnicodeError):
            raise ErrorConfiguracion("No se pudo leer el archivo .env.") from None
    valores.update(os.environ if entorno is None else entorno)
    url = (valores.get("SUPABASE_URL") or "").strip().rstrip("/")
    clave = (valores.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url:
        raise ErrorConfiguracion("Falta SUPABASE_URL en .env o en el entorno.")
    try:
        partes = urlsplit(url)
        puerto = partes.port  # Valida el formato del puerto sin mostrar la URL.
        local = partes.hostname in {"localhost", "127.0.0.1", "::1"}
        valida = (
            bool(partes.hostname)
            and (partes.scheme == "https" or (partes.scheme == "http" and local))
            and not partes.username and not partes.password
            and not partes.query and not partes.fragment
            and partes.path == ""
            and puerto != 0
            and not any(c.isspace() for c in url)
        )
    except ValueError:
        valida = False
    if not valida:
        raise ErrorConfiguracion(
            "SUPABASE_URL debe ser la URL HTTPS del proyecto (HTTP solo para localhost), sin rutas ni credenciales."
        )
    if not clave:
        raise ErrorConfiguracion(
            "Falta SUPABASE_SERVICE_ROLE_KEY. Usa la clave de servidor, no la anon."
        )
    if clave.startswith("sb_publishable_"):
        raise ErrorConfiguracion("La clave publishable no sirve para este cliente de servidor.")
    return Configuracion(url, clave)
