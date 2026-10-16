"""Firmas que implementa José. Emilia consume funciones con estos contratos."""
from typing import Protocol

from .modelos import InformeVerificacion, PropuestaDistribucion
from .solicitudes import (
    ResultadoPriorizarNecesidades, ResultadoValidarNecesidad,
    SolicitudPriorizarNecesidades, SolicitudResolverRutas,
    SolicitudValidarNecesidad, SolicitudVerificarPlan,
)


class HerramientasCalculo(Protocol):
    def validate_need(self, entrada: SolicitudValidarNecesidad) -> ResultadoValidarNecesidad: ...

    def score_needs(self, entrada: SolicitudPriorizarNecesidades) -> ResultadoPriorizarNecesidades: ...

    def solve_routes(self, entrada: SolicitudResolverRutas) -> PropuestaDistribucion: ...

    def verify_plan(self, entrada: SolicitudVerificarPlan) -> InformeVerificacion: ...
