"""Entradas y salidas de las cuatro funciones puras de José.

Estos contratos no ejecutan las funciones, no conectan Supabase y no autorizan acciones.
"""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .estados import EstadoValidacion
from .modelos import (
    Cantidad, CantidadPositiva, ConfirmacionCoordinador, Contexto, Contrato,
    Deposito, EnteroNoNegativo, EnteroPositivo, EvaluacionNecesidades,
    InformeVerificacion, PoliticaPrioridad, PropuestaDistribucion,
    PuntoAtencion, Texto, Vehiculo,
)


class DemandaDirecta(Contrato):
    metodo: Literal["directa"]
    litros_declarados: Cantidad | None = None
    fuente: Texto
    confirmacion: ConfirmacionCoordinador | None = None


class DemandaPorFormula(Contrato):
    metodo: Literal["formula"]
    personas_atendidas: EnteroNoNegativo | None = None
    dotacion_litros_persona_dia: CantidadPositiva | None = None
    dias_cobertura: CantidadPositiva | None = None
    reserva_utilizable_litros: Cantidad | None = None
    fuente: Texto
    confirmacion: ConfirmacionCoordinador | None = None


class SolicitudValidarNecesidad(Contexto):
    incidente_id: UUID
    punto_atencion_id: UUID
    datos_version: Texto
    demanda: Annotated[DemandaDirecta | DemandaPorFormula, Field(discriminator="metodo")]
    capacidad_recepcion_litros: Cantidad | None = None
    supuestos: list[Texto] = Field(default_factory=list)

class ResultadoValidarNecesidad(Contexto):
    incidente_id: UUID
    punto_atencion_id: UUID
    datos_version: Texto
    metodo: Literal["directa", "formula"]
    estado: EstadoValidacion
    demanda_litros: Cantidad | None = None
    fuente: Texto
    confirmacion: ConfirmacionCoordinador | None = None
    faltantes: list[Texto]
    motivos: list[Texto]
    supuestos: list[Texto]

    @model_validator(mode="after")
    def resultado(self):
        if self.estado == EstadoValidacion.VALIDADA:
            if self.demanda_litros is None or not self.confirmacion or self.faltantes:
                raise ValueError("Validada requiere cantidad, confirmación y sin faltantes")
        elif not self.motivos:
            raise ValueError("Resultado pendiente/rechazado necesita motivo")
        return self


class SolicitudPriorizarNecesidades(Contexto):
    datos_version: Texto
    politica: PoliticaPrioridad
    necesidades: list[EvaluacionNecesidades] = Field(min_length=1)

    @model_validator(mode="after")
    def versiones(self):
        ids = [n.incidente_id for n in self.necesidades]
        puntos = [n.punto_atencion_id for n in self.necesidades]
        if len(ids) != len(set(ids)) or len(puntos) != len(set(puntos)):
            raise ValueError("Consolidar a una necesidad por punto antes de priorizar")
        if any(n.datos_version != self.datos_version or n.politica_version != self.politica.politica_version
               or n.ejecucion_id != self.ejecucion_id for n in self.necesidades):
            raise ValueError("Necesidades y solicitud deben compartir versiones y ejecución")
        return self


class ResultadoPriorizarNecesidades(Contexto):
    datos_version: Texto
    politica_version: Texto
    evaluaciones: list[EvaluacionNecesidades] = Field(min_length=1)
    alertas_revision: list[Texto]

    @model_validator(mode="after")
    def ranking(self):
        if any(n.datos_version != self.datos_version or n.politica_version != self.politica_version
               or n.ejecucion_id != self.ejecucion_id for n in self.evaluaciones):
            raise ValueError("Resultado con versiones o ejecución mezcladas")
        ids = [n.punto_atencion_id for n in self.evaluaciones]
        if len(ids) != len(set(ids)):
            raise ValueError("Puntos duplicados en ranking")
        posiciones = sorted(n.posicion for n in self.evaluaciones if n.estado_prioridad == "calculada")
        if posiciones != list(range(1, len(posiciones) + 1)):
            raise ValueError("Posiciones consecutivas, únicas, sin pendientes")
        ordenadas = sorted((n for n in self.evaluaciones if n.posicion is not None), key=lambda n: n.posicion)
        aparece_general = False
        for n in ordenadas:
            if n.clase_prioridad.value == "general":
                aparece_general = True
            elif aparece_general:
                raise ValueError("La clase crítica precede a la general en el ranking")
        return self


class MatrizTiempos(Contrato):
    matriz_version: Texto
    origen: Literal["sintetico", "estimado"]
    nodos_ids: list[UUID] = Field(min_length=2)
    minutos: list[list[EnteroNoNegativo | None]]
    descripcion: Texto

    @model_validator(mode="after")
    def cuadrada(self):
        n = len(self.nodos_ids)
        if len(set(self.nodos_ids)) != n or len(self.minutos) != n or any(len(r) != n for r in self.minutos):
            raise ValueError("Matriz cuadrada con identificadores únicos")
        if any(self.minutos[i][i] != 0 for i in range(n)):
            raise ValueError("Diagonal de la matriz debe ser cero")
        return self


class TiempoServicio(Contrato):
    punto_atencion_id: UUID
    descarga_minutos: EnteroPositivo


class SolicitudResolverRutas(Contexto):
    plan_id: UUID
    version: EnteroPositivo
    datos_version: Texto
    politica: PoliticaPrioridad
    deposito: Deposito
    vehiculos: list[Vehiculo] = Field(max_length=2)
    puntos: list[PuntoAtencion] = Field(min_length=1, max_length=6)
    necesidades: list[EvaluacionNecesidades] = Field(min_length=1)
    matriz: MatrizTiempos
    servicios: list[TiempoServicio]
    limite_solver_segundos: EnteroPositivo
    recargas_permitidas: Literal[False] = False
    entregas_parciales_permitidas: Literal[False] = False

    @model_validator(mode="after")
    def escenario(self):
        puntos = [p.punto_atencion_id for p in self.puntos]
        vehiculos = [v.vehiculo_id for v in self.vehiculos]
        servicios = [s.punto_atencion_id for s in self.servicios]
        necesidades = [n.punto_atencion_id for n in self.necesidades]
        if self.deposito.deposito_id in puntos:
            raise ValueError("El depósito no puede compartir ID con un punto")
        if len(puntos) != len(set(puntos)) or len(vehiculos) != len(set(vehiculos)):
            raise ValueError("IDs duplicados en flota o puntos")
        if len(servicios) != len(set(servicios)) or set(servicios) != set(puntos):
            raise ValueError("Un tiempo de servicio por punto")
        if len(necesidades) != len(set(necesidades)) or set(necesidades) != set(puntos):
            raise ValueError("Una necesidad por punto, incluyendo pendientes")
        if set(self.matriz.nodos_ids) != {self.deposito.deposito_id, *puntos}:
            raise ValueError("Matriz debe referenciar depósito y todos los puntos")
        if any(n.datos_version != self.datos_version or n.politica_version != self.politica.politica_version
               or n.ejecucion_id != self.ejecucion_id for n in self.necesidades):
            raise ValueError("Entradas de planificación con versiones diferentes")
        return self


class SolicitudVerificarPlan(Contexto):
    solicitud_original: SolicitudResolverRutas
    propuesta: PropuestaDistribucion

    @model_validator(mode="after")
    def snapshot(self):
        a, b = self.solicitud_original, self.propuesta
        if (a.plan_id, a.version, a.datos_version, a.politica.politica_version) != (
            b.plan_id, b.version, b.datos_version, b.politica_version
        ):
            raise ValueError("La propuesta no corresponde a la solicitud original")
        if self.ejecucion_id != a.ejecucion_id or a.ejecucion_id != b.ejecucion_id:
            raise ValueError("La verificación requiere una misma ejecución")
        return self
