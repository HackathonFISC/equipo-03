"""Cuerpos de petición y respuesta propios de la API (no son contratos compartidos)."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from contratos.estados import Agente, EstadoEjecucion
from contratos.modelos import EvaluacionNecesidades, ExtraccionReporteLLM

IdPositivo = Annotated[int, Field(strict=True, gt=0)]


class NuevoReporteTelegram(BaseModel):
    """Lo que envía el bot. La API crea los UUID, el origen y el mensaje_externo_id."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    usuario_telegram_id: IdPositivo
    chat_id: Annotated[int, Field(strict=True)]
    message_id: IdPositivo
    # 4000 es el máximo de Texto en contratos/modelos.py; Telegram admite hasta 4096.
    texto: Annotated[str, Field(min_length=1, max_length=4000)]

    @field_validator("chat_id")
    @classmethod
    def chat_no_cero(cls, valor: int) -> int:
        if valor == 0:
            raise ValueError("chat_id no puede ser 0")
        return valor


class EntradaPanel(BaseModel):
    canal: Literal["telegram", "panel"]
    modalidad: Literal["texto", "voz", "foto", "ubicacion"]
    texto: str | None


class RegistradoPanel(BaseModel):
    """Vista para el panel: sin remitente_ref ni identificadores externos."""

    reporte_id: UUID
    ejecucion_id: UUID | None
    creado_en: AwareDatetime
    origen: Literal["real", "estimado", "sintetico"]
    entrada: EntradaPanel


class InterpretadoPanel(BaseModel):
    interpretacion: ExtraccionReporteLLM


Etapa = Literal["ingesta", "territorial", "priorizacion", "planificacion", "comunicacion", "terminada"]


class SeguimientoPanel(BaseModel):
    """Dónde va la ejecución del reporte. Lo cambian los agentes, nunca la API."""

    estado: EstadoEjecucion
    etapa: Etapa


class ReporteListado(BaseModel):
    registrado: RegistradoPanel
    interpretado: InterpretadoPanel | None
    seguimiento: SeguimientoPanel | None


class EventoPanel(BaseModel):
    """Traza de una decisión. Sin detalles internos, prompts ni texto de personas."""

    evento_id: UUID
    agente: Agente | None
    actor_tipo: Literal["agente", "coordinador", "conductor", "sistema"]
    decision: str
    herramienta: str | None
    resultado: str
    duracion_ms: int
    siguiente_estado: EstadoEjecucion | None
    creado_en: AwareDatetime


class EjecucionPanel(BaseModel):
    ejecucion_id: UUID
    reporte_id: UUID | None
    estado: EstadoEjecucion
    etapa: Etapa
    intentos: int
    error_codigo: str | None
    creado_en: AwareDatetime
    actualizado_en: AwareDatetime
    eventos: list[EventoPanel]


# --- Circuito de aclaración (V2, acuerdo D004 con Emilia) ---

class Peticion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReservaAclaracion(Peticion):
    """El bot identifica su proceso para que la RPC sepa quién tiene la reserva."""

    trabajador_id: Annotated[str, Field(min_length=1, max_length=200)]


class AclaracionPorEnviar(BaseModel):
    aclaracion_id: UUID
    pregunta: str
    chat_id: int
    # Mensaje del reporte original, para enviar la pregunta como reply. None si no se puede leer.
    mensaje_original_id: int | None


class ResultadoEnvio(Peticion):
    trabajador_id: Annotated[str, Field(min_length=1, max_length=200)]
    estado: Literal["enviado", "fallido", "incierto"]
    proveedor_mensaje_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    error: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    @model_validator(mode="after")
    def coherente(self):
        # Mismas reglas que las restricciones de la tabla aclaraciones (0001_esquema.sql).
        if self.estado == "enviado" and (self.proveedor_mensaje_id is None or self.error is not None):
            raise ValueError("Un envío confirmado lleva el ID del mensaje y ningún error")
        if self.estado != "enviado" and (self.error is None or self.proveedor_mensaje_id is not None):
            raise ValueError("Un envío fallido o incierto lleva un error y ningún ID de mensaje")
        return self


class UbicacionTelegram(Peticion):
    latitud: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    longitud: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
    precision_metros: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None


class RespuestaDelBot(Peticion):
    """Un reply a la pregunta del bot: texto o ubicación, nunca ambos."""

    usuario_telegram_id: IdPositivo
    chat_id: Annotated[int, Field(strict=True)]
    pregunta_mensaje_id: IdPositivo
    message_id: IdPositivo
    texto: Annotated[str, Field(min_length=1, max_length=4000)] | None = None
    ubicacion: UbicacionTelegram | None = None

    @model_validator(mode="after")
    def un_contenido(self):
        if (self.texto is None) == (self.ubicacion is None):
            raise ValueError("La respuesta lleva texto o ubicación, uno de los dos")
        return self


ResultadoAclaracion = Literal[
    "aceptada", "repetida", "ya_respondida", "autor_distinto", "no_encontrada", "vencida"
]


class ResultadoRespuesta(BaseModel):
    resultado: ResultadoAclaracion
    ejecucion_id: UUID | None = None


# --- Incidentes para la página Necesidades (V2) ---


class PuntoPanel(BaseModel):
    """Nombre del punto según el catálogo activo (ra_catalogo_v2)."""

    punto_atencion_id: UUID
    nombre: str
    distrito: str | None = None
    corregimiento: str | None = None


class IncidentePanel(BaseModel):
    """Un incidente con vínculos activos. Sin remitentes, chats ni textos de reportes."""

    incidente_id: UUID
    ejecucion_id: UUID
    version: int
    origen: Literal["real", "estimado", "sintetico"]
    sector_id: UUID | None
    punto_atencion_id: UUID | None
    punto: PuntoPanel | None
    estado_validacion: Literal["pendiente", "validada", "rechazada"]
    tipo_problema: str
    episodio_establecido: bool
    periodo_inicio: AwareDatetime
    periodo_fin: AwareDatetime
    primera_deteccion_en: AwareDatetime
    confianza: float | None
    conflictos: list[str]
    faltantes: list[str]
    requiere_revision_urgente: bool
    # Reportes con vínculo activo; reportes_independientes cuenta remitentes distintos.
    reportes_vinculados: int
    reportes_independientes: int
    evaluacion_necesidad: EvaluacionNecesidades | None
    pendientes_calculo: list[str]


# --- Bandeja de salida de avisos (V4) ---


class AvisoPorEnviar(BaseModel):
    """Lo mínimo para redactar un aviso: el bot arma el texto con la plantilla, no con texto libre."""

    aviso_id: UUID
    chat_id: int
    tipo: Literal["distribucion", "actualizacion"]
    version: Annotated[int, Field(gt=0)]
    punto_nombre: str
    litros_asignados: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    ventana_inicio: AwareDatetime
    ventana_fin: AwareDatetime


# --- Aprobación de planes (V4, migración 0003) ---

class AprobarPlan(Peticion):
    """Lo que la persona revisó. Quién aprueba sale del token, nunca de este cuerpo."""

    datos_version: Annotated[str, Field(min_length=1, max_length=200)]
    politica_version: Annotated[str, Field(min_length=1, max_length=200)]
    motivo: Annotated[str, Field(min_length=1, max_length=4000)]
    # Cada bloqueo que el plan trae y que la persona reconoce de forma expresa.
    bloqueos_reconocidos: Annotated[list[Annotated[str, Field(min_length=1, max_length=500)]], Field(max_length=20)]


class RechazarPlan(Peticion):
    motivo: Annotated[str, Field(min_length=1, max_length=4000)]


class ResultadoPlan(BaseModel):
    plan_id: UUID
    version: Annotated[int, Field(gt=0)]
    estado: Literal["aprobado", "rechazado"]
    aprobacion_id: UUID | None = None
    ejecucion_id: UUID | None = None
    repetido: bool


# --- Planes guardados para el panel (V4) ---

class ParadaPanel(BaseModel):
    parada_id: UUID
    orden: int
    punto_atencion_id: UUID
    punto: PuntoPanel | None
    litros_asignados: float
    llegada_estimada: AwareDatetime
    inicio_descarga: AwareDatetime
    fin_descarga: AwareDatetime
    estado: str


class RutaPanel(BaseModel):
    ruta_id: UUID
    vehiculo_id: UUID
    salida_estimada: AwareDatetime
    retorno_estimado: AwareDatetime
    paradas: list[ParadaPanel]


class PlanPanel(BaseModel):
    """Una versión de plan tal como quedó guardada. El panel manda de vuelta `datos_version` y
    `politica_version` al aprobar: así la base sabe qué versión revisó la persona."""

    plan_id: UUID
    version: int
    ejecucion_id: UUID
    estado: Literal["calculando", "pendiente_revision", "aprobado", "rechazado", "invalidado"]
    estado_solver: str | None
    datos_version: str
    politica_version: str
    verificado: bool
    bloqueos_publicacion: list[str]
    no_atendidos: list[dict]
    supuestos: list[str]
    aprobacion_id: UUID | None
    origen: Literal["real", "estimado", "sintetico"]
    creado_en: AwareDatetime
    rutas: list[RutaPanel]


# --- Operaciones de V4 con las RPC de Emilia (0012) ---

class SeleccionarPlanSector(Peticion):
    """El plan aprobado que Comunicación usará para este sector. Quién selecciona sale del token."""

    plan_id: UUID
    version: Annotated[int, Field(gt=0)]
    motivo: Annotated[str, Field(min_length=1, max_length=4000)]


class ResultadoSeleccion(BaseModel):
    sector_id: UUID
    plan_id: UUID | None = None
    version: Annotated[int, Field(gt=0)] | None = None
    repetido: bool


class DestinoEnsayo(Peticion):
    habilitado: bool
    motivo: Annotated[str, Field(min_length=1, max_length=4000)]


class ResultadoDestinoEnsayo(BaseModel):
    destino_id: UUID
    habilitado: bool


class SectorPanel(BaseModel):
    """Un sector del catálogo, para elegirlo en el panel sin pegar su identificador."""

    sector_id: UUID
    nombre: str
    distrito: str
    corregimiento: str | None = None
    origen: Literal["real", "estimado", "sintetico"]


class DestinoPanel(BaseModel):
    """Un destino de Telegram. Solo se muestra el final de su identificador; el completo no sale de la API."""

    destino_id: UUID
    referencia: str
    autorizado: bool
    habilitado_ensayo: bool | None = None  # None: la migración 0012 aún no está aplicada


# --- Priorización de incidentes (V2): el coordinador revisa y el servidor arma el lote ---


class VentanaRevisada(Peticion):
    inicio: AwareDatetime
    fin: AwareDatetime


class DemandaRevisada(Peticion):
    """Demanda de agua que el coordinador confirma. La confirmación (quién y cuándo) la pone el servidor."""

    metodo: Literal["directa", "formula"]
    fuente: Annotated[str, Field(min_length=1, max_length=500)]
    litros_declarados: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)] | None = None
    personas_atendidas: Annotated[int, Field(ge=0, strict=True)] | None = None
    dotacion_litros_persona_dia: Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)] | None = None
    dias_cobertura: Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)] | None = None
    reserva_utilizable_litros: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)] | None = None

    @model_validator(mode="after")
    def campos_del_metodo(self):
        de_formula = (self.personas_atendidas, self.dotacion_litros_persona_dia, self.dias_cobertura, self.reserva_utilizable_litros)
        if self.metodo == "directa" and any(v is not None for v in de_formula):
            raise ValueError("La demanda directa no lleva campos de fórmula")
        if self.metodo == "formula" and self.litros_declarados is not None:
            raise ValueError("La demanda por fórmula no lleva litros declarados")
        return self


class RevisionIncidente(Peticion):
    """Lo que el coordinador confirma de un incidente. Lo que no se envía queda pendiente, nunca se inventa."""

    incidente_id: UUID
    version_incidente: Annotated[int, Field(gt=0)]
    demanda: DemandaRevisada | None = None
    clase_prioridad: Literal["critico", "general"] | None = None
    ventana_atencion: VentanaRevisada | None = None
    vulnerabilidad: Literal["sin_condicion_identificada", "moderada", "alta"] | None = None
    capacidad_recepcion_litros: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)] | None = None
    horas_sin_agua: Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)] | None = None
    personas_atendidas: Annotated[int, Field(ge=0, strict=True)] | None = None
    ultima_atencion_confirmada_en: AwareDatetime | None = None

    @model_validator(mode="after")
    def critico_con_ventana(self):
        if self.clase_prioridad == "critico" and self.ventana_atencion is None:
            raise ValueError("Un punto crítico necesita ventana de atención")
        if self.ventana_atencion is not None and self.ventana_atencion.fin <= self.ventana_atencion.inicio:
            raise ValueError("La ventana debe terminar después de empezar")
        return self


class PrepararPriorizacion(Peticion):
    """Quién revisa sale del token. La política se elige de forma explícita: nunca se toma "la más reciente"."""

    politica_version: Annotated[str, Field(min_length=1, max_length=200)]
    motivo: Annotated[str, Field(min_length=1, max_length=2000)]
    revisiones: Annotated[list[RevisionIncidente], Field(max_length=200)] = Field(default_factory=list)


class ResultadoPriorizacion(BaseModel):
    ejecucion_id: UUID
    estado: str
    etapa: str
    repetido: bool = False
    datos_version: str
    incidentes: int
    sin_revisar: int
