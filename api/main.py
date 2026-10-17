"""Punto de entrada de la API de H2Oeste."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.errores_http import ErrorApi, respuesta_error
from api.rutas import imagen, audio, aclaraciones, avisos, ejecuciones, eventos, incidentes, planes, politicas, priorizacion, reportes, sectores, sesion
from contratos.errores import CodigoError
from orquestador.servicio import ciclo_vida_agentes

app = FastAPI(title="H2Oeste API", version="0.0.1", lifespan=ciclo_vida_agentes)

# Permite que el panel React (servidor de desarrollo de Vite) llame a la API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorApi)
async def manejar_error_api(request: Request, error: ErrorApi):
    return respuesta_error(error)


@app.exception_handler(RequestValidationError)
async def manejar_validacion(request: Request, error: RequestValidationError):
    # Solo nombres de campo: nunca el valor recibido, que puede ser texto de una persona.
    errores = error.errors()
    if any(e["type"] == "json_invalid" for e in errores):
        # En este caso loc trae la posición del fallo, no un nombre de campo.
        return respuesta_error(
            ErrorApi(
                CodigoError.CONTRATO_INVALIDO,
                "El cuerpo de la petición no es un JSON válido.",
                campos=["cuerpo"],
            )
        )
    campos = sorted({".".join(str(p) for p in e["loc"][1:]) or "cuerpo" for e in errores})
    return respuesta_error(
        ErrorApi(
            CodigoError.CONTRATO_INVALIDO,
            "La petición no cumple el formato esperado.",
            campos=campos,
        )
    )


app.include_router(reportes.router)
app.include_router(ejecuciones.router)
app.include_router(eventos.router)
app.include_router(priorizacion.router)
app.include_router(politicas.router)
app.include_router(aclaraciones.router)
app.include_router(audio.router)
app.include_router(imagen.router)
app.include_router(avisos.router)
app.include_router(incidentes.router)
app.include_router(sesion.router)
app.include_router(planes.router)
app.include_router(sectores.router)


@app.get("/salud")
def salud() -> dict[str, str]:
    """Endpoint de prueba de V0: confirma que la API está viva."""
    return {"estado": "ok"}


@app.get("/salud/agentes")
def salud_agentes(request: Request) -> dict[str, str]:
    """Estado del proceso local; no acredita servicios externos ni avance de la cola."""
    servicio = getattr(request.app.state, 'servicio_agentes', None)
    return {'estado': servicio.consultar() if servicio is not None else 'sin_iniciar'}
