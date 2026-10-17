"""Texto de los avisos a la comunidad: se arma con código a partir de los datos aprobados.

El bot nunca envía texto libre de un modelo: cantidad, horario, lugar y versión salen de la parada
aprobada. Es una estimación del plan, no una promesa de entrega.
"""
from datetime import datetime, timedelta, timezone

# Panamá no usa horario de verano: UTC-5 fijo, sin depender de la base de zonas horarias del sistema.
PANAMA = timezone(timedelta(hours=-5))


def _litros(valor: float) -> str:
    entero = round(valor)
    return str(entero) if abs(valor - entero) < 1e-9 else f"{valor:.1f}".replace(".", ",")


def _hora(valor: datetime) -> str:
    return valor.astimezone(PANAMA).strftime("%H:%M")


def texto_aviso(
    *,
    tipo: str,
    punto_nombre: str,
    litros_asignados: float,
    ventana_inicio: datetime,
    ventana_fin: datetime,
    version: int,
) -> str:
    """Mensaje del aviso. Lanza ValueError si el tipo no es de distribución o actualización."""
    if tipo not in ("distribucion", "actualizacion"):
        raise ValueError("Tipo de aviso desconocido")
    inicio = ventana_inicio.astimezone(PANAMA)
    fecha = inicio.strftime("%d/%m/%Y")
    estimacion = (
        f"se estima la entrega de {_litros(litros_asignados)} litros entre las {_hora(ventana_inicio)} "
        f"y las {_hora(ventana_fin)} del {fecha}, hora de Panamá"
    )
    if tipo == "distribucion":
        return (
            f"Agua para {punto_nombre}: {estimacion}. "
            f"Es una estimación del plan versión {version} y puede cambiar; si cambia, te avisaremos."
        )
    return (
        f"Actualización del plan de agua para {punto_nombre}: ahora {estimacion}. "
        f"Reemplaza el aviso anterior (plan versión {version})."
    )
