"""Identidad de quien llama: se verifica el token de Supabase Auth y el usuario sale de ahí.

El navegador nunca dice quién es: un `usuario_id` enviado en el cuerpo o en la URL no se usa.
La contraseña no pasa por esta API: el panel inicia sesión directamente con Supabase Auth y envía
solo el token en `Authorization: Bearer`. Importar este módulo no lee claves ni abre conexiones.

- `usuario_autenticado`: sesión válida de Supabase Auth (no anónima).
- `coordinador_actual`: además, coordinador activo en `usuarios_operativos`. Es un control temprano
  para dar un 403 claro; las RPC de aprobación lo vuelven a comprobar dentro de la transacción.
"""
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import httpx
from dotenv import dotenv_values
from fastapi import Depends, Header
from postgrest.exceptions import APIError

from api.dependencias import obtener_db, secreto_configurado, verificar_secreto_bot
from api.errores_http import ErrorApi
from comun.config import RAIZ_PROYECTO, ErrorConfiguracion, cargar_configuracion
from contratos.errores import CodigoError

logger = logging.getLogger("api.auth")

# Un JWT son tres tramos base64url; el límite evita pasar basura enorme al proveedor.
TOKEN_VALIDO = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
LARGO_MAXIMO_TOKEN = 4096
ERRORES_INFRAESTRUCTURA = (APIError, httpx.HTTPError)


@dataclass(frozen=True)
class UsuarioAutenticado:
    usuario_id: UUID


def _sin_sesion(mensaje: str = "Falta una sesión válida. Inicia sesión de nuevo.") -> ErrorApi:
    return ErrorApi(CodigoError.SIN_PERMISO, mensaje)


def _no_verificada() -> ErrorApi:
    return ErrorApi(
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
        "No se pudo verificar la sesión. Inténtalo de nuevo.",
        recuperable=True,
    )


def extraer_token(authorization: str | None = Header(default=None)) -> str:
    """Devuelve el token del encabezado `Authorization: Bearer <token>` o rechaza con 403."""
    if not authorization:
        raise _sin_sesion()
    partes = authorization.split(" ")
    if len(partes) != 2 or partes[0].lower() != "bearer":
        raise _sin_sesion()
    token = partes[1]
    if len(token) > LARGO_MAXIMO_TOKEN or not TOKEN_VALIDO.fullmatch(token):
        raise _sin_sesion()
    return token


@lru_cache(maxsize=1)
def _clave_publica() -> str:
    """SUPABASE_ANON_KEY de .env o del entorno. Reinicia la API tras cambiarla."""
    valores: dict[str, str | None] = {}
    ruta = RAIZ_PROYECTO / ".env"
    if ruta.is_file():
        valores.update(dotenv_values(ruta, interpolate=False))
    valores.update(os.environ)
    return (valores.get("SUPABASE_ANON_KEY") or "").strip()


class VerificadorSupabase:
    """Pregunta a Supabase Auth quién es el dueño del token (`GET /auth/v1/user`).

    Así se respeta el cierre de sesión y no hace falta guardar el secreto de firma del proyecto.
    """

    def __init__(self, url: str, clave_publica: str, *, transporte: httpx.BaseTransport | None = None):
        self.url = url.rstrip("/")
        self.clave_publica = clave_publica
        self.transporte = transporte

    def usuario_id(self, token: str) -> UUID:
        try:
            with httpx.Client(timeout=5, transport=self.transporte, follow_redirects=False) as cliente:
                respuesta = cliente.get(
                    f"{self.url}/auth/v1/user",
                    headers={"apikey": self.clave_publica, "Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as error:
            # Solo el tipo: el mensaje del cliente HTTP podría incluir la petición.
            logger.error("Fallo al verificar la sesión: %s", type(error).__name__)
            raise _no_verificada() from None
        if respuesta.status_code in (400, 401, 403):
            raise _sin_sesion("La sesión no es válida o venció. Inicia sesión de nuevo.")
        if respuesta.status_code != 200:
            logger.error("Supabase Auth respondió HTTP %s", respuesta.status_code)
            raise _no_verificada()
        try:
            datos = respuesta.json()
            anonimo = datos.get("is_anonymous") is True
            identificador = UUID(str(datos["id"]))
        except (ValueError, KeyError, TypeError, AttributeError):
            logger.error("Supabase Auth devolvió una respuesta inesperada")
            raise _no_verificada() from None
        if anonimo:
            raise _sin_sesion("Una sesión anónima no puede hacer esta operación.")
        return identificador


@lru_cache(maxsize=1)
def obtener_verificador() -> VerificadorSupabase:
    """Verificador del proceso. Las pruebas lo sustituyen con `dependency_overrides`."""
    clave = _clave_publica()
    try:
        url = cargar_configuracion().supabase_url
    except ErrorConfiguracion:
        url = ""
    if not url or not clave:
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La API no tiene configurada la verificación de sesiones (SUPABASE_URL y SUPABASE_ANON_KEY).",
            recuperable=True,
        )
    return VerificadorSupabase(url, clave)


def usuario_autenticado(
    token: str = Depends(extraer_token),
    verificador: VerificadorSupabase = Depends(obtener_verificador),
) -> UsuarioAutenticado:
    return UsuarioAutenticado(verificador.usuario_id(token))


def rol_operativo(db, usuario_id: UUID) -> dict | None:
    """Fila de `usuarios_operativos` de esa persona (rol y si está activa), o None si no tiene."""
    try:
        filas = (
            db.table("usuarios_operativos")
            .select("rol,activo")
            .eq("usuario_id", str(usuario_id))
            .limit(1)
            .execute()
            .data
        )
    except ERRORES_INFRAESTRUCTURA as error:
        logger.error("Fallo al leer el rol: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudo comprobar el rol. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
    return filas[0] if filas else None


def coordinador_actual(
    usuario: UsuarioAutenticado = Depends(usuario_autenticado),
    db=Depends(obtener_db),
) -> UsuarioAutenticado:
    fila = rol_operativo(db, usuario.usuario_id)
    if not fila or fila.get("rol") != "coordinador" or fila.get("activo") is not True:
        raise ErrorApi(CodigoError.SIN_PERMISO, "Solo un coordinador activo puede hacer esto.")
    return usuario


def verificador_opcional() -> VerificadorSupabase | None:
    """El verificador si está configurado; None si no. Permite que una ruta acepte también el secreto del bot."""
    try:
        return obtener_verificador()
    except ErrorApi:
        return None


def sesion_o_bot(
    x_secreto_bot: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    secreto: str = Depends(secreto_configurado),
    verificador: VerificadorSupabase | None = Depends(verificador_opcional),
) -> None:
    """Lecturas que puede pedir el panel (con sesión válida) o el bot (con su secreto). No identifica a nadie."""
    if x_secreto_bot is not None:
        verificar_secreto_bot(x_secreto_bot, secreto)
        return
    token = extraer_token(authorization)
    if verificador is None:
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La API no tiene configurada la verificación de sesiones (SUPABASE_URL y SUPABASE_ANON_KEY).",
            recuperable=True,
        )
    verificador.usuario_id(token)
