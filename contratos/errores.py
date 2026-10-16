"""Errores de dominio tipados. Los timeouts del solver son resultados, no inviabilidad."""
from enum import Enum

from .modelos import Contexto, Texto


class CodigoError(str, Enum):
    CONTRATO_INVALIDO = "contrato_invalido"
    DATOS_INSUFICIENTES = "datos_insuficientes"
    UBICACION_AMBIGUA = "ubicacion_ambigua"
    FUERA_DE_AREA = "fuera_de_area"
    POLITICA_NO_ACTIVA = "politica_no_activa"
    VERSION_OBSOLETA = "version_obsoleta"
    SIN_PERMISO = "sin_permiso"
    PLAN_NO_VERIFICADO = "plan_no_verificado"
    COBERTURA_CRITICA_PENDIENTE = "cobertura_critica_pendiente"
    PROVEEDOR_NO_DISPONIBLE = "proveedor_no_disponible"
    ENVIO_INCIERTO = "envio_incierto"


class ErrorDominio(Contexto):
    codigo: CodigoError
    mensaje: Texto
    recuperable: bool
    campos: list[Texto]


class ExcepcionContrato(ValueError):
    """Adaptador opcional; no usar para sustituir ValidationError de Pydantic."""
    def __init__(self, detalle: ErrorDominio):
        self.detalle = detalle
        super().__init__(f"{detalle.codigo.value}: {detalle.mensaje}")
