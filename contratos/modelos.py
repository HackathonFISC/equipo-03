"""Contratos v1.0 para V0–V6. Python >=3.10 y Pydantic >=2.13,<3.

Validar estructura no verifica hechos, permisos, rutas físicas ni vigencia en BD.
Los modelos del servidor NO deben usarse como salida directa del LLM.
"""
from __future__ import annotations

from math import isclose
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .estados import (
    Agente, ClasePrioridad, EstadoAviso, EstadoEjecucion, EstadoParada,
    EstadoPlan, EstadoSolver, EstadoValidacion, NivelVulnerabilidad, OrigenDato,
)

Texto = Annotated[str, Field(min_length=1, max_length=4000)]
Cantidad = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
CantidadPositiva = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
Proporcion = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
EnteroNoNegativo = Annotated[int, Field(ge=0, strict=True)]
EnteroPositivo = Annotated[int, Field(gt=0, strict=True)]


class Contrato(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Contexto(Contrato):
    """Lo crea el backend, jamás el modelo de lenguaje."""
    esquema_version: Literal["1.0"] = "1.0"
    ejecucion_id: UUID
    creado_en: AwareDatetime
    origen: OrigenDato


class Evidencia(Contrato):
    evidencia_id: UUID
    reporte_id: UUID
    tipo: Literal["texto", "ubicacion", "audio", "foto", "coordinador"]
    referencia: Texto  # ID interno o ruta privada, no URL pública firmada ni secreto.
    descripcion: Texto
    campos_respaldados: list[Texto] = Field(min_length=1)


class Ubicacion(Contrato):
    latitud: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False, strict=True)]
    longitud: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False, strict=True)]
    fuente: Literal["catalogo", "compartida", "coordinador", "escenario"]
    precision_metros: Cantidad | None = None
    representa_punto_atencion: bool | None = None


class VentanaTiempo(Contrato):
    inicio: AwareDatetime
    fin: AwareDatetime

    @model_validator(mode="after")
    def orden(self):
        if self.fin <= self.inicio:
            raise ValueError("La ventana debe tener fin posterior al inicio")
        return self


class ConfirmacionCoordinador(Contrato):
    usuario_id: UUID
    confirmado_en: AwareDatetime
    motivo: Texto


class CamposReporte(Contrato):
    horas_sin_agua: Cantidad | None = None
    personas_afectadas: EnteroNoNegativo | None = None
    vulnerabilidad_declarada: Texto | None = None
    institucion_declarada: Texto | None = None
    tipo_problema: Literal["sin_suministro", "intermitencia", "otro", "desconocido"]


class EntradaReporte(Contrato):
    """Adaptador de Noel; IDs externos sirven para deduplicar, no para autorizar."""
    canal: Literal["telegram", "panel"]
    mensaje_externo_id: Texto
    remitente_ref: UUID
    modalidad: Literal["texto", "voz", "foto", "ubicacion"]
    texto: Texto | None = None
    adjunto_id: UUID | None = None
    ubicacion_compartida: Ubicacion | None = None

    @model_validator(mode="after")
    def contenido(self):
        if self.modalidad == "texto" and self.texto is None:
            raise ValueError("Texto requiere contenido")
        if self.modalidad in ("voz", "foto") and self.adjunto_id is None:
            raise ValueError("Modalidad multimedia requiere adjunto privado")
        if self.modalidad == "ubicacion" and self.ubicacion_compartida is None:
            raise ValueError("Modalidad ubicación requiere coordenadas del adaptador")
        return self


class ReporteRegistrado(Contexto):
    reporte_id: UUID
    entrada: EntradaReporte


class ExtraccionReporteLLM(Contrato):
    """Única forma de extracción para el LLM; no acepta IDs, coordenadas o permisos."""
    resumen: Texto
    ubicacion_declarada: Texto | None
    campos: CamposReporte
    evidencia_textual: list[Texto]
    faltantes: list[Texto]
    requiere_aclaracion: bool
    fuera_de_alcance: bool

    @model_validator(mode="after")
    def aclaracion(self):
        if self.requiere_aclaracion and not self.faltantes:
            raise ValueError("Una aclaración necesita faltantes explícitos")
        return self


class ReporteInterpretado(Contexto):
    reporte_id: UUID
    modalidad: Literal["texto", "voz", "foto", "ubicacion"]
    interpretacion: ExtraccionReporteLLM
    evidencias: list[Evidencia] = Field(min_length=1)
    ubicacion_compartida: Ubicacion | None = None  # Backend de Noel; nunca LLM.

    @model_validator(mode="after")
    def referencias(self):
        if any(e.reporte_id != self.reporte_id for e in self.evidencias):
            raise ValueError("La evidencia debe pertenecer al reporte")
        return self


class IncidenteConsolidado(Contexto):
    incidente_id: UUID
    version: EnteroPositivo
    sector_id: UUID | None = None
    punto_atencion_id: UUID | None = None
    reportes_ids: list[UUID] = Field(min_length=1)
    reportes_independientes: EnteroNoNegativo
    ubicacion: Ubicacion | None = None
    estado_validacion: EstadoValidacion
    confianza: Proporcion | None = None
    conflictos: list[Texto] = Field(default_factory=list)
    faltantes: list[Texto] = Field(default_factory=list)
    requiere_revision_urgente: bool = False
    periodo_incidente: VentanaTiempo
    primera_deteccion_en: AwareDatetime  # No se reinicia por duplicados.

    @model_validator(mode="after")
    def consolidacion(self):
        if len(self.reportes_ids) != len(set(self.reportes_ids)):
            raise ValueError("No repetir un mismo reporte en el vínculo")
        if self.reportes_independientes > len(self.reportes_ids):
            raise ValueError("Corroboraciones mayores que reportes vinculados")
        if self.estado_validacion == EstadoValidacion.VALIDADA:
            if not self.sector_id or not self.punto_atencion_id or not self.ubicacion:
                raise ValueError("Incidente validado necesita punto, sector y ubicación")
            if self.ubicacion.representa_punto_atencion is not True:
                raise ValueError("Debe confirmar qué lugar representa la ubicación")
        return self


class PoliticaPrioridad(Contrato):
    politica_version: Texto
    estado: Literal["propuesta_demo", "activa"]
    origen: Literal["sintetico"] = "sintetico"
    peso_duracion: Proporcion
    peso_vulnerabilidad: Proporcion
    peso_poblacion: Proporcion
    tope_horas: CantidadPositiva
    tope_personas: EnteroPositivo
    vulnerabilidad_moderada: Proporcion
    fundamento: Texto
    confirmacion_activacion: ConfirmacionCoordinador | None = None
    criticos_obligatorios: Literal[True] = True
    faltantes_fuera_ranking: Literal[True] = True
    orden_desempate: Literal["ultima_atencion_luego_incidente_luego_id"] = "ultima_atencion_luego_incidente_luego_id"

    @model_validator(mode="after")
    def politica(self):
        if not isclose(self.peso_duracion + self.peso_vulnerabilidad + self.peso_poblacion, 1, abs_tol=1e-9):
            raise ValueError("Los pesos deben sumar 1")
        if not 0 < self.vulnerabilidad_moderada < 1:
            raise ValueError("Vulnerabilidad moderada debe estar entre 0 y 1")
        if self.estado == "activa" and not self.confirmacion_activacion:
            raise ValueError("El backend necesita registrar activación del coordinador")
        return self


class ComponentesPrioridad(Contrato):
    duracion_normalizada: Proporcion
    vulnerabilidad_normalizada: Proporcion
    poblacion_normalizada: Proporcion
    aporte_duracion: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)]
    aporte_vulnerabilidad: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)]
    aporte_poblacion: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)]


class EvaluacionNecesidades(Contexto):
    incidente_id: UUID
    punto_atencion_id: UUID
    datos_version: Texto
    politica_version: Texto
    estado_demanda: EstadoValidacion
    demanda_litros: Cantidad | None = None
    metodo_demanda: Literal["directa", "formula"]
    confirmacion_demanda: ConfirmacionCoordinador | None = None
    clase_prioridad: ClasePrioridad | None = None
    confirmacion_clase: ConfirmacionCoordinador | None = None
    ventana_atencion: VentanaTiempo | None = None
    horas_sin_agua: Cantidad | None = None
    personas_atendidas: EnteroNoNegativo | None = None
    vulnerabilidad: NivelVulnerabilidad | None = None
    confirmacion_vulnerabilidad: ConfirmacionCoordinador | None = None
    ultima_atencion_confirmada_en: AwareDatetime | None = None
    primera_deteccion_en: AwareDatetime
    estado_prioridad: Literal["pendiente", "calculada"]
    puntaje: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False, strict=True)] | None = None
    componentes: ComponentesPrioridad | None = None
    posicion: EnteroPositivo | None = None
    pendientes: list[Texto] = Field(default_factory=list)
    supuestos: list[Texto] = Field(default_factory=list)
    requiere_revision_urgente: bool = False

    @model_validator(mode="after")
    def evaluacion(self):
        if self.estado_demanda == EstadoValidacion.VALIDADA:
            if self.demanda_litros is None or self.confirmacion_demanda is None:
                raise ValueError("Demanda validada necesita litros y confirmación")
        if self.estado_demanda == EstadoValidacion.PENDIENTE and not self.pendientes:
            raise ValueError("Demanda pendiente necesita motivo")
        if self.clase_prioridad and not self.confirmacion_clase:
            raise ValueError("La clase debe estar confirmada por coordinador")
        if self.clase_prioridad == ClasePrioridad.CRITICO and not self.ventana_atencion:
            raise ValueError("Punto crítico necesita ventana de atención")
        if self.estado_prioridad == "pendiente":
            if any(x is not None for x in (self.puntaje, self.componentes, self.posicion)):
                raise ValueError("Pendientes no llevan puntaje ni posición")
            if not self.pendientes:
                raise ValueError("Prioridad pendiente necesita motivo")
        else:
            required = (self.horas_sin_agua, self.personas_atendidas, self.vulnerabilidad,
                        self.confirmacion_vulnerabilidad, self.clase_prioridad,
                        self.confirmacion_clase, self.puntaje, self.componentes, self.posicion)
            if any(x is None for x in required):
                raise ValueError("Prioridad calculada necesita factores validados y desglose")
            if self.estado_demanda != EstadoValidacion.VALIDADA or self.pendientes:
                raise ValueError("No entra al ranking una necesidad pendiente")
            total = self.componentes.aporte_duracion + self.componentes.aporte_vulnerabilidad + self.componentes.aporte_poblacion
            if not isclose(self.puntaje, total, abs_tol=1e-6):
                raise ValueError("El puntaje debe coincidir con sus aportes")
        if self.ultima_atencion_confirmada_en and self.ultima_atencion_confirmada_en > self.creado_en:
            raise ValueError("La atención confirmada no puede ser futura")
        return self


class PuntoAtencion(Contrato):
    punto_atencion_id: UUID
    sector_id: UUID
    nombre: Texto
    ubicacion: Ubicacion
    origen: OrigenDato


class Vehiculo(Contrato):
    vehiculo_id: UUID
    capacidad_litros: CantidadPositiva
    disponible: bool
    turno: VentanaTiempo
    origen: OrigenDato


class Deposito(Contrato):
    deposito_id: UUID
    nombre: Texto
    ubicacion: Ubicacion
    origen: OrigenDato


class ParadaPlan(Contrato):
    parada_id: UUID
    punto_atencion_id: UUID
    incidente_id: UUID
    orden: EnteroPositivo
    litros_asignados: CantidadPositiva
    llegada_estimada: AwareDatetime
    inicio_descarga: AwareDatetime
    fin_descarga: AwareDatetime
    estado: EstadoParada = EstadoParada.PROGRAMADA

    @model_validator(mode="after")
    def tiempos(self):
        if not self.llegada_estimada <= self.inicio_descarga < self.fin_descarga:
            raise ValueError("Orden inválido de llegada e intervalo de descarga")
        return self


class RutaVehiculo(Contrato):
    vehiculo_id: UUID
    deposito_id: UUID
    salida_estimada: AwareDatetime
    retorno_estimado: AwareDatetime
    paradas: list[ParadaPlan] = Field(min_length=1)

    @model_validator(mode="after")
    def secuencia(self):
        if self.retorno_estimado <= self.salida_estimada:
            raise ValueError("El retorno debe ser posterior a la salida")
        if [p.orden for p in self.paradas] != list(range(1, len(self.paradas) + 1)):
            raise ValueError("El orden de paradas debe ser consecutivo desde 1")
        anterior = self.salida_estimada
        for p in self.paradas:
            if p.llegada_estimada < anterior or p.fin_descarga > self.retorno_estimado:
                raise ValueError("Paradas fuera del intervalo de la ruta o superpuestas")
            anterior = p.fin_descarga
        return self


class NoAtendido(Contrato):
    incidente_id: UUID
    punto_atencion_id: UUID
    clase_prioridad: ClasePrioridad | None
    demanda_pendiente_litros: Cantidad | None
    codigo: Literal["sin_capacidad", "demanda_supera_vehiculo", "ventana", "sin_acceso", "datos_pendientes", "timeout", "otro"]
    motivo: Texto


class ViolacionPlan(Contrato):
    codigo: Literal["capacidad", "horario", "ventana", "retorno", "asignacion", "demanda", "version", "cobertura_critica", "otro"]
    detalle: Texto
    referencia_id: UUID | None = None


class InformeVerificacion(Contexto):
    plan_id: UUID
    version: EnteroPositivo
    datos_version: Texto
    politica_version: Texto
    valido: bool
    violaciones: list[ViolacionPlan]
    comprobaciones: list[Literal["capacidad", "horarios", "ventanas", "retorno", "asignacion_unica", "demanda_completa", "version_entradas", "cobertura_critica"]]

    @model_validator(mode="after")
    def informe(self):
        if self.valido and self.violaciones:
            raise ValueError("Verificación válida no puede contener violaciones")
        if not self.valido and not self.violaciones:
            raise ValueError("Verificación inválida debe explicar incumplimientos")
        checks = {"capacidad", "horarios", "ventanas", "retorno", "asignacion_unica", "demanda_completa", "version_entradas", "cobertura_critica"}
        if self.valido and set(self.comprobaciones) != checks:
            raise ValueError("Informe válido requiere todas las comprobaciones del MVP")
        return self


class AprobacionPlan(Contrato):
    """Registro emitido por servicio autorizado, no salida de un agente."""
    aprobacion_id: UUID
    plan_id: UUID
    version: EnteroPositivo
    datos_version: Texto
    politica_version: Texto
    coordinador: ConfirmacionCoordinador


class PropuestaDistribucion(Contexto):
    plan_id: UUID
    version: EnteroPositivo
    datos_version: Texto
    politica_version: Texto
    estado: EstadoPlan
    estado_solver: EstadoSolver
    rutas: list[RutaVehiculo]
    no_atendidos: list[NoAtendido]
    verificacion: InformeVerificacion | None = None
    supuestos: list[Texto]
    bloqueos_publicacion: list[Texto]
    aprobacion: AprobacionPlan | None = None

    @model_validator(mode="after")
    def coherencia(self):
        if self.estado_solver != EstadoSolver.FACTIBLE and self.rutas:
            raise ValueError("No declarar rutas cuando no hay solución factible")
        if self.estado_solver != EstadoSolver.FACTIBLE and not self.bloqueos_publicacion:
            raise ValueError("Estado sin solución necesita bloqueo explícito")
        if len({r.vehiculo_id for r in self.rutas}) != len(self.rutas):
            raise ValueError("Una salida por vehículo en el MVP")
        puntos = [p.punto_atencion_id for r in self.rutas for p in r.paradas]
        paradas = [p.parada_id for r in self.rutas for p in r.paradas]
        pendientes = [n.punto_atencion_id for n in self.no_atendidos]
        if len(puntos) != len(set(puntos)) or len(paradas) != len(set(paradas)):
            raise ValueError("No se permiten entregas divididas ni IDs de parada repetidos")
        if len(pendientes) != len(set(pendientes)) or set(puntos) & set(pendientes):
            raise ValueError("Un punto no puede figurar atendido y pendiente a la vez")
        if any(n.clase_prioridad == ClasePrioridad.CRITICO for n in self.no_atendidos) and not self.bloqueos_publicacion:
            raise ValueError("Crítico no atendido debe bloquear publicación")
        for obj in (self.verificacion, self.aprobacion):
            if obj and (obj.plan_id, obj.version, obj.datos_version, obj.politica_version) != (
                self.plan_id, self.version, self.datos_version, self.politica_version
            ):
                raise ValueError("Verificación/aprobación no corresponde a la versión")
        if self.verificacion and self.verificacion.ejecucion_id != self.ejecucion_id:
            raise ValueError("La verificación pertenece a otra ejecución")
        if self.estado == EstadoPlan.APROBADO:
            if not self.aprobacion or not self.verificacion or not self.verificacion.valido:
                raise ValueError("Plan aprobado necesita registro y verificación válida")
            if self.estado_solver != EstadoSolver.FACTIBLE or self.bloqueos_publicacion:
                raise ValueError("No aprobar un plan bloqueado")
        elif self.aprobacion and self.estado != EstadoPlan.INVALIDADO:
            raise ValueError("Solo aprobado o invalidado puede conservar aprobación")
        return self


class AvisoComunidad(Contexto):
    """Solo distribución autorizada. Aclaraciones usan SolicitudAclaracion."""
    aviso_id: UUID
    plan_id: UUID
    version: EnteroPositivo
    aprobacion_id: UUID
    sector_id: UUID
    punto_atencion_id: UUID
    destino_id: UUID  # Referencia interna autorizada, no chat_id generado por LLM.
    tipo: Literal["distribucion", "actualizacion"]
    ventana_estimada: VentanaTiempo
    litros_asignados: CantidadPositiva
    texto: Texto
    audio_adjunto_id: UUID | None = None
    estado_envio: EstadoAviso
    proveedor_mensaje_id: Texto | None = None
    enviado_en: AwareDatetime | None = None
    ultimo_error: Texto | None = None

    @property
    def clave_idempotencia(self) -> str:
        return f"{self.plan_id}:{self.version}:{self.sector_id}:{self.punto_atencion_id}:{self.destino_id}:{self.tipo}"

    @model_validator(mode="after")
    def envio(self):
        if self.estado_envio == EstadoAviso.ENVIADO:
            if not self.proveedor_mensaje_id or not self.enviado_en:
                raise ValueError("Enviado necesita ID del proveedor y fecha")
        elif self.proveedor_mensaje_id or self.enviado_en:
            raise ValueError("Solo enviado lleva confirmación de envío")
        if self.estado_envio in (EstadoAviso.FALLIDO, EstadoAviso.INCIERTO) and not self.ultimo_error:
            raise ValueError("Fallo o incertidumbre necesitan motivo")
        return self


class SolicitudAclaracion(Contexto):
    aclaracion_id: UUID
    reporte_id: UUID
    destino_id: UUID
    campos_solicitados: list[Texto] = Field(min_length=1)
    pregunta: Texto


class RespuestaAclaracion(Contexto):
    aclaracion_id: UUID
    reporte_id: UUID
    texto: Texto
    ubicacion_compartida: Ubicacion | None = None


class EventoTraza(Contexto):
    evento_id: UUID
    agente: Agente
    decision: Texto
    herramienta: Texto | None = None
    entrada_ids: list[UUID]
    salida_ids: list[UUID]
    resultado: Texto
    duracion_ms: EnteroNoNegativo
    siguiente_estado: EstadoEjecucion


class ConfirmacionEntrega(Contexto):
    """Solo conductor/coordinador autorizado; no modifica litros asignados."""
    parada_id: UUID
    usuario_id: UUID
    rol: Literal["conductor", "coordinador"]
    litros_entregados: Cantidad
    atendida_en: AwareDatetime
    observaciones: Texto | None = None
