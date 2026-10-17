"""Registro general de eventos: qué decidió cada agente, con qué herramienta y con qué resultado."""
import logging
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query
from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.auth import usuario_autenticado
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import EventoRegistro
from contratos.errores import CodigoError, ErrorDominio
from contratos.estados import Agente

logger = logging.getLogger("api.eventos")

router = APIRouter(
    tags=["eventos"],
    responses={
        403: {"model": ErrorDominio, "description": "Sin sesión válida."},
        422: {"model": ErrorDominio, "description": "Un filtro no es válido."},
        503: {"model": ErrorDominio, "description": "Base de datos o verificación de sesión no disponibles."},
    },
)

# Sin detalles, entrada_ids, salida_ids ni usuario_id: son internos de los agentes.
COLUMNAS = (
    "evento_id,ejecucion_id,agente,actor_tipo,decision,herramienta,resultado,"
    "duracion_ms,siguiente_estado,origen,creado_en"
)
LIMITE_MAXIMO = 200


@router.get(
    "/eventos",
    response_model=list[EventoRegistro],
    dependencies=[Depends(usuario_autenticado)],
    summary="Eventos recientes de agentes y personas, del más nuevo al más antiguo (requiere sesión)",
)
def listar_eventos(
    agente: Agente | None = None,
    actor_tipo: Literal["agente", "coordinador", "conductor", "sistema"] | None = None,
    ejecucion_id: UUID | None = None,
    limite: int = Query(default=100, ge=1, le=LIMITE_MAXIMO),
    db=Depends(obtener_db),
):
    try:
        consulta = db.table("eventos").select(COLUMNAS)
        if agente is not None:
            consulta = consulta.eq("agente", agente.value)
        if actor_tipo is not None:
            consulta = consulta.eq("actor_tipo", actor_tipo)
        if ejecucion_id is not None:
            consulta = consulta.eq("ejecucion_id", str(ejecucion_id))
        filas = consulta.order("creado_en", desc=True).limit(limite).execute().data
        return [EventoRegistro.model_validate(f) for f in filas or []]
    except (APIError, httpx.HTTPError) as error:
        logger.error("Fallo de la base de datos: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudo consultar el registro de eventos. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
    except ValidationError:
        logger.error("Un evento guardado no cumple el formato esperado")
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE, "Un evento guardado no tiene el formato esperado.", recuperable=False
        ) from None
