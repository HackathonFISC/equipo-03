"""Cuerpos de petición y respuesta propios de la API (no son contratos compartidos)."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from contratos.estados import Agente, EstadoEjecucion
from contratos.modelos import ExtraccionReporteLLM

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
