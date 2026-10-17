"""Agente de Comunicación V4: crea avisos autorizados, no aprueba ni envía Telegram.

La herramienta transaccional vuelve a comprobar vigencia, destino y versión.
El bot de Noel reserva/envía la bandeja; crear un aviso no significa entregarlo.
"""
from uuid import UUID


def procesar_comunicacion(ejecucion_id, db, trabajador_id):
    return db.rpc('ra_comunicar_plan_v4', {
        'p_ejecucion_id': str(UUID(str(ejecucion_id))),
        'p_trabajador_id': trabajador_id,
    }).execute().data
