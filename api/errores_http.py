"""Errores de dominio como respuestas HTTP (decisión D003 de docs/decisiones.md)."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.responses import JSONResponse

from contratos.errores import CodigoError, ErrorDominio
from contratos.estados import OrigenDato

ESTADO_HTTP: dict[CodigoError, int] = {
    CodigoError.CONTRATO_INVALIDO: 422,
    CodigoError.DATOS_INSUFICIENTES: 422,
    CodigoError.UBICACION_AMBIGUA: 422,
    CodigoError.FUERA_DE_AREA: 422,
    CodigoError.SIN_PERMISO: 403,
    CodigoError.POLITICA_NO_ACTIVA: 409,
    CodigoError.VERSION_OBSOLETA: 409,
    CodigoError.PLAN_NO_VERIFICADO: 409,
    CodigoError.COBERTURA_CRITICA_PENDIENTE: 409,
    CodigoError.PROVEEDOR_NO_DISPONIBLE: 503,
    CodigoError.ENVIO_INCIERTO: 502,
}


class ErrorApi(Exception):
    """Error de dominio de la API. Sus mensajes nunca deben incluir secretos ni datos de personas."""

    def __init__(
        self,
        codigo: CodigoError,
        mensaje: str,
        *,
        recuperable: bool = False,
        campos: list[str] | None = None,
    ):
        self.codigo = codigo
        self.mensaje = mensaje
        self.recuperable = recuperable
        self.campos = campos or []
        super().__init__(f"{codigo.value}: {mensaje}")


def respuesta_error(error: ErrorApi) -> JSONResponse:
    """Devuelve el ErrorDominio completo como cuerpo.

    Un error de la API no pertenece a una ejecución real: el ejecucion_id es un
    UUID nuevo que solo cumple el contrato y no existe en la base de datos.
    """
    detalle = ErrorDominio(
        ejecucion_id=uuid4(),
        creado_en=datetime.now(timezone.utc),
        origen=OrigenDato.SINTETICO,
        codigo=error.codigo,
        mensaje=error.mensaje,
        recuperable=error.recuperable,
        campos=error.campos,
    )
    return JSONResponse(
        status_code=ESTADO_HTTP[error.codigo],
        content=detalle.model_dump(mode="json"),
    )
