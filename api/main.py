"""Punto de entrada de la API de RutaAgua Oeste."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.errores_http import ErrorApi, respuesta_error
from api.rutas import aclaraciones, avisos, ejecuciones, incidentes, reportes
from contratos.errores import CodigoError

app = FastAPI(title="RutaAgua Oeste API", version="0.0.1")

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
app.include_router(aclaraciones.router)
app.include_router(avisos.router)
app.include_router(incidentes.router)


@app.get("/salud")
def salud() -> dict[str, str]:
    """Endpoint de prueba de V0: confirma que la API está viva."""
    return {"estado": "ok"}
