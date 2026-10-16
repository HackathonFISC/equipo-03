"""Valores serializados compartidos. No representan permisos ni transiciones autorizadas."""
from enum import Enum


class EstadoEjecucion(str, Enum):
    PENDIENTE = "pendiente"
    EJECUTANDO = "ejecutando"
    ESPERA_ACLARACION = "espera_aclaracion"
    ESPERA_VALIDACION = "espera_validacion"
    ESPERA_REVISION = "espera_revision"
    COMPLETADA = "completada"
    FALLIDA = "fallida"


class EstadoPlan(str, Enum):
    CALCULANDO = "calculando"
    PENDIENTE_REVISION = "pendiente_revision"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    INVALIDADO = "invalidado"


class EstadoAviso(str, Enum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    FALLIDO = "fallido"
    INCIERTO = "incierto"
    CANCELADO = "cancelado"


class EstadoParada(str, Enum):
    PROGRAMADA = "programada"
    INICIADA = "iniciada"
    ATENDIDA = "atendida"
    CON_INCIDENCIA = "con_incidencia"


class EstadoValidacion(str, Enum):
    PENDIENTE = "pendiente"
    VALIDADA = "validada"
    RECHAZADA = "rechazada"


class OrigenDato(str, Enum):
    REAL = "real"
    ESTIMADO = "estimado"
    SINTETICO = "sintetico"


class ClasePrioridad(str, Enum):
    CRITICO = "critico"
    GENERAL = "general"


class NivelVulnerabilidad(str, Enum):
    SIN_CONDICION_IDENTIFICADA = "sin_condicion_identificada"
    MODERADA = "moderada"
    ALTA = "alta"


class EstadoSolver(str, Enum):
    FACTIBLE = "factible"
    TIMEOUT_SIN_SOLUCION = "timeout_sin_solucion"
    INVIABILIDAD_DEMOSTRADA = "inviabilidad_demostrada"
    ERROR = "error"


class Agente(str, Enum):
    INGESTA = "ingesta"
    TERRITORIAL = "territorial"
    PRIORIZACION = "priorizacion"
    PLANIFICACION = "planificacion"
    COMUNICACION = "comunicacion"
