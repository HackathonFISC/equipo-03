"""Contratos compartidos de RutaAgua Oeste. Importar modelos desde contratos.modelos."""
from .modelos import (
    AvisoComunidad, EvaluacionNecesidades, ExtraccionReporteLLM,
    IncidenteConsolidado, PropuestaDistribucion, ReporteInterpretado,
)

__all__ = [
    "AvisoComunidad", "EvaluacionNecesidades", "ExtraccionReporteLLM",
    "IncidenteConsolidado", "PropuestaDistribucion", "ReporteInterpretado",
]

from .consultas import EstadoSector, SolicitudEstadoSector

__all__ += ["EstadoSector", "SolicitudEstadoSector"]
