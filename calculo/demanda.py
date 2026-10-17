"""Validación determinística de demanda. Sin red, BD ni autorización de personas."""
from decimal import Decimal, localcontext
from math import isfinite

from contratos.solicitudes import SolicitudValidarNecesidad, ResultadoValidarNecesidad


def validate_need(entrada: SolicitudValidarNecesidad) -> ResultadoValidarNecesidad:
    entrada = SolicitudValidarNecesidad.model_validate(entrada.model_dump(mode='json'))
    demanda = entrada.demanda
    faltantes, motivos = [], []
    litros = None
    if demanda.metodo == 'directa':
        litros = demanda.litros_declarados
        if litros is None:
            faltantes.append('demanda.litros_declarados')
    else:
        factores = ('personas_atendidas', 'dotacion_litros_persona_dia',
                    'dias_cobertura', 'reserva_utilizable_litros')
        faltantes.extend(f'demanda.{k}' for k in factores if getattr(demanda, k) is None)
        if not faltantes:
            # Evita overflow en productos intermedios y conserva cero explícito.
            with localcontext() as contexto:
                contexto.prec = 50
                personas, dotacion, dias, reserva = (Decimal(str(getattr(demanda, k))) for k in factores)
                calculada = max(Decimal(0), personas * dotacion * dias - reserva)
                litros = float(calculada)
            if not isfinite(litros):
                litros = None
                motivos.append('La demanda calculada excede la representación numérica; revisar parámetros.')
    if demanda.confirmacion is None:
        faltantes.append('demanda.confirmacion')
    if entrada.capacidad_recepcion_litros is None:
        faltantes.append('capacidad_recepcion_litros')
    elif litros is not None and litros > entrada.capacidad_recepcion_litros:
        motivos.append('La demanda supera la capacidad de recepción; requiere ajuste explícito, sin recorte automático.')
    if faltantes:
        motivos.append('Falta información o confirmación: ' + ', '.join(faltantes) + '.')
    contexto = {k: getattr(entrada, k) for k in (
        'esquema_version', 'ejecucion_id', 'creado_en', 'origen',
        'incidente_id', 'punto_atencion_id', 'datos_version')}
    return ResultadoValidarNecesidad(
        **contexto, metodo=demanda.metodo,
        estado='pendiente' if motivos else 'validada', demanda_litros=litros,
        fuente=demanda.fuente, confirmacion=demanda.confirmacion,
        faltantes=faltantes, motivos=motivos, supuestos=entrada.supuestos,
    )
