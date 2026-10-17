"""Consulta de estado V4. Proyección de lectura compuesta por la API, nunca por el LLM."""
from typing import Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, model_validator

from .estados import EstadoParada, OrigenDato
from .modelos import CantidadPositiva, Contrato, EnteroPositivo, Texto, VentanaTiempo


class SolicitudEstadoSector(Contrato):
    esquema_version: Literal["1.0"] = "1.0"
    sector_id: UUID


class ResumenSector(Contrato):
    sector_id: UUID
    nombre: Texto
    distrito: Texto
    corregimiento: Texto | None = None
    origen: OrigenDato
    estado_informacion: Literal[
        "sin_informacion", "pendiente_verificar", "necesidad_conocida", "atencion_reciente"
    ]


class PlanVigenteSector(Contrato):
    plan_id: UUID
    version: EnteroPositivo
    ejecucion_id: UUID
    datos_version: Texto
    politica_version: Texto
    origen: OrigenDato
    estado: Literal["aprobado"]
    verificado: Literal[True]
    aprobacion_id: UUID
    aprobado_en: AwareDatetime

    @model_validator(mode="before")
    @classmethod
    def verificacion_booleana(cls, valores):
        # Literal[True] por sí solo puede aceptar el entero 1.
        if isinstance(valores, dict) and valores.get("verificado") is not True:
            raise ValueError("verificado debe ser el booleano true explícito")
        return valores


class EstadoPuntoSector(Contrato):
    punto_atencion_id: UUID
    sector_id: UUID
    nombre: Texto
    origen: OrigenDato
    estado: EstadoParada | Literal["sin_asignacion"]
    parada_id: UUID | None = None
    litros_asignados: CantidadPositiva | None = None
    ventana_estimada: VentanaTiempo | None = None
    motivo_sin_asignacion: Texto | None = None

    @model_validator(mode="after")
    def asignacion(self):
        campos = (self.parada_id, self.litros_asignados, self.ventana_estimada)
        if self.estado == "sin_asignacion":
            if any(campo is not None for campo in campos) or not self.motivo_sin_asignacion:
                raise ValueError("Sin asignación requiere motivo y parada, litros y ventana en null")
        elif any(campo is None for campo in campos) or self.motivo_sin_asignacion is not None:
            raise ValueError("Una parada requiere ID, litros y ventana, sin motivo de falta de asignación")
        return self


class EstadoSector(Contrato):
    """Snapshot del servicio: no autoriza publicación ni acredita entrega de agua."""
    esquema_version: Literal["1.0"] = "1.0"
    consultado_en: AwareDatetime
    origen: OrigenDato
    sector: ResumenSector
    estado: Literal["con_plan_vigente", "sin_plan_vigente"]
    plan_vigente: PlanVigenteSector | None
    puntos: list[EstadoPuntoSector]

    @model_validator(mode="after")
    def snapshot(self):
        if (self.estado == "con_plan_vigente") != (self.plan_vigente is not None):
            raise ValueError("El estado del sector debe coincidir con la presencia de plan vigente")
        ids = [p.punto_atencion_id for p in self.puntos]
        paradas = [p.parada_id for p in self.puntos if p.parada_id is not None]
        if len(ids) != len(set(ids)) or len(paradas) != len(set(paradas)):
            raise ValueError("No repetir puntos ni paradas en la consulta")
        if any(p.sector_id != self.sector.sector_id for p in self.puntos):
            raise ValueError("Todos los puntos deben pertenecer al sector consultado")
        if self.plan_vigente is None:
            if any(p.estado != "sin_asignacion" for p in self.puntos):
                raise ValueError("Sin plan vigente no se muestran asignaciones históricas")
        elif self.plan_vigente.aprobado_en > self.consultado_en:
            raise ValueError("La aprobación no puede ser posterior a la consulta")
        if self.plan_vigente is not None:
            for punto in self.puntos:
                if punto.estado == "sin_asignacion":
                    continue
                if (self.plan_vigente.origen == OrigenDato.SINTETICO and punto.origen != OrigenDato.SINTETICO
                        or self.plan_vigente.origen == OrigenDato.ESTIMADO and punto.origen == OrigenDato.REAL):
                    raise ValueError("El origen del punto asignado debe conservar el origen del plan")
        origenes = {self.sector.origen, *(p.origen for p in self.puntos)}
        if self.plan_vigente is not None:
            origenes.add(self.plan_vigente.origen)
        esperado = (OrigenDato.SINTETICO if OrigenDato.SINTETICO in origenes else
                    OrigenDato.ESTIMADO if OrigenDato.ESTIMADO in origenes else OrigenDato.REAL)
        if self.origen != esperado:
            raise ValueError("El resumen conserva origen sintético o estimado si alguna fuente lo contiene")
        return self


class ConsultasSectores(Protocol):
    """Firma de lectura que implementa Noel; transporte HTTP y permisos en su API."""
    def estado_sector(self, entrada: SolicitudEstadoSector) -> EstadoSector: ...
