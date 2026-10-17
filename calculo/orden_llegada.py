"""Comparador experimental de V5; no es una quinta tool ni una ruta publicable."""
from contratos.solicitudes import SolicitudResolverRutas
from contratos.modelos import PropuestaDistribucion
from .solver_v3 import _resolver


def solve_routes_orden_llegada(entrada: SolicitudResolverRutas) -> PropuestaDistribucion:
    """FIFO por primera detección del incidente, con desempate UUID.

    Optimiza rutas sobre las mismas restricciones de V3. Solo cambia el objetivo
    de cobertura: el incidente más antiguo precede al siguiente, sin clase ni
    puntaje. No implica orden cronológico global de visitas entre vehículos.
    Conserva los bloqueos de cobertura crítica y publicación.
    """
    return _resolver(entrada, por_llegada=True)
