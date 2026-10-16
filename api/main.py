"""Punto de entrada de la API de RutaAgua Oeste (V0)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RutaAgua Oeste API", version="0.0.1")

# Permite que el panel React (servidor de desarrollo de Vite) llame a la API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/salud")
def salud() -> dict[str, str]:
    """Endpoint de prueba de V0: confirma que la API está viva."""
    return {"estado": "ok"}
