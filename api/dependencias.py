"""Dependencias compartidas de las rutas: secreto del bot y cliente de base de datos."""
import hmac
import os
from functools import lru_cache

from dotenv import dotenv_values
from fastapi import Depends, Header

from api.errores_http import ErrorApi
from comun.config import RAIZ_PROYECTO, ErrorConfiguracion
from comun.db import ErrorConexion, get_supabase
from contratos.errores import CodigoError

LARGO_MINIMO_SECRETO = 16


@lru_cache(maxsize=1)
def secreto_configurado() -> str:
    """Lee API_SECRETO_BOT de .env o del entorno. Reinicia la API tras cambiarlo."""
    valores: dict[str, str | None] = {}
    ruta = RAIZ_PROYECTO / ".env"
    if ruta.is_file():
        valores.update(dotenv_values(ruta, interpolate=False))
    valores.update(os.environ)
    return (valores.get("API_SECRETO_BOT") or "").strip()


def verificar_secreto_bot(
    x_secreto_bot: str | None = Header(default=None),
    secreto: str = Depends(secreto_configurado),
) -> None:
    """Exige el encabezado X-Secreto-Bot. Sin secreto configurado, la ruta se cierra."""
    if len(secreto) < LARGO_MINIMO_SECRETO:
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La API no tiene configurado un secreto del bot válido.",
        )
    if not x_secreto_bot or not hmac.compare_digest(
        x_secreto_bot.encode("utf-8"), secreto.encode("utf-8")
    ):
        raise ErrorApi(CodigoError.SIN_PERMISO, "Secreto del bot ausente o incorrecto.")


def obtener_db():
    """Cliente de Supabase del proceso. Los fallos de configuración devuelven 503."""
    try:
        return get_supabase()
    except (ErrorConfiguracion, ErrorConexion):
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La base de datos no está disponible.",
            recuperable=True,
        ) from None
