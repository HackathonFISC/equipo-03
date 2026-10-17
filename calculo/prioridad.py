"""Ranking configurable por clase y puntaje, con pendientes explícitos."""
from contratos.errores import CodigoError, ErrorDominio, ExcepcionContrato
from contratos.modelos import EvaluacionNecesidades
from contratos.solicitudes import SolicitudPriorizarNecesidades, ResultadoPriorizarNecesidades

# Marcadores técnicos del ejemplo compartido y del adaptador de Emilia.
# No representan observaciones ni faltantes de datos.
CALCULO_PENDIENTE = 'Cálculo de prioridad todavía no ejecutado.'
MARCADORES_CALCULO_PENDIENTE = frozenset({CALCULO_PENDIENTE, 'prioridad_por_calcular'})


def score_needs(entrada: SolicitudPriorizarNecesidades) -> ResultadoPriorizarNecesidades:
    entrada = SolicitudPriorizarNecesidades.model_validate(entrada.model_dump(mode='json'))
    politica = entrada.politica
    if politica.estado != 'activa':
        raise ExcepcionContrato(ErrorDominio(
            esquema_version=entrada.esquema_version, ejecucion_id=entrada.ejecucion_id,
            creado_en=entrada.creado_en, origen=entrada.origen,
            codigo=CodigoError.POLITICA_NO_ACTIVA, mensaje='La política debe activarse antes de calcular prioridades.',
            recuperable=True, campos=['politica.estado'],
        ))
    calculadas, pendientes = [], []
    alertas = [f'Ranking de ensayo con política sintética {politica.politica_version}; '
               'se conserva el origen de cada necesidad. No constituye autorización operativa.']
    for necesidad in sorted(entrada.necesidades, key=lambda n: str(n.incidente_id)):
        datos = necesidad.model_dump(mode='json')
        motivos = [m for m in necesidad.pendientes if m not in MARCADORES_CALCULO_PENDIENTE]
        if necesidad.estado_demanda != 'validada':
            motivos.append('La demanda no está validada.')
        for campo in ('horas_sin_agua', 'personas_atendidas', 'vulnerabilidad',
                      'confirmacion_vulnerabilidad', 'clase_prioridad', 'confirmacion_clase'):
            if getattr(necesidad, campo) is None:
                motivos.append(f'Falta {campo}.')
        if necesidad.clase_prioridad == 'critico' and necesidad.ventana_atencion is None:
            motivos.append('Falta ventana_atencion del punto crítico.')
        # La procedencia de los datos se conserva; el ranking declara por separado
        # el origen de la política mediante su versión y la alerta de ensayo.
        datos.update(puntaje=None, componentes=None, posicion=None)
        if motivos:
            datos.update(estado_prioridad='pendiente', pendientes=list(dict.fromkeys(motivos)),
                         requiere_revision_urgente=(necesidad.requiere_revision_urgente
                                                   or necesidad.clase_prioridad == 'critico'))
            pendientes.append(datos)
            if datos['requiere_revision_urgente']:
                alertas.append(f'{necesidad.punto_atencion_id}: posible urgencia pendiente de revisión.')
            continue
        duracion = min(necesidad.horas_sin_agua, politica.tope_horas) / politica.tope_horas
        poblacion = min(necesidad.personas_atendidas, politica.tope_personas) / politica.tope_personas
        vulnerabilidad = {'sin_condicion_identificada': 0.0,
                         'moderada': politica.vulnerabilidad_moderada, 'alta': 1.0}[necesidad.vulnerabilidad]
        componentes = dict(duracion_normalizada=duracion, poblacion_normalizada=poblacion,
                           vulnerabilidad_normalizada=vulnerabilidad,
                           aporte_duracion=100 * politica.peso_duracion * duracion,
                           aporte_poblacion=100 * politica.peso_poblacion * poblacion,
                           aporte_vulnerabilidad=100 * politica.peso_vulnerabilidad * vulnerabilidad)
        puntaje = sum(componentes[k] for k in ('aporte_duracion', 'aporte_poblacion', 'aporte_vulnerabilidad'))
        # Pesos que suman uno con tolerancia pueden generar una desviación ínfima de 100.
        if puntaje > 100:
            if puntaje - 100 > 1e-6:
                raise ValueError('La política produce un puntaje fuera del rango permitido.')
            puntaje = 100.0
        datos.update(estado_prioridad='calculada', puntaje=puntaje, componentes=componentes, pendientes=[])
        calculadas.append(datos)
        excedidos = [nombre for nombre, valor, tope in (
            ('horas_sin_agua', necesidad.horas_sin_agua, politica.tope_horas),
            ('personas_atendidas', necesidad.personas_atendidas, politica.tope_personas)) if valor > tope]
        if excedidos:
            alertas.append(f'{necesidad.punto_atencion_id}: revisar factores sobre la escala de demo '
                           f'({", ".join(excedidos)}); se conserva la cantidad original y se satura solo el componente.')
        if necesidad.requiere_revision_urgente:
            alertas.append(f'{necesidad.punto_atencion_id}: conserva alerta de revisión urgente.')

    ordenadas = []
    for clase in ('critico', 'general'):
        clase_ordenada = sorted((n for n in calculadas if n['clase_prioridad'] == clase),
                               key=lambda n: (-n['puntaje'], n['incidente_id']))
        cursor = 0
        while cursor < len(clase_ordenada):
            referencia = clase_ordenada[cursor]['puntaje']
            fin = cursor + 1
            while fin < len(clase_ordenada) and referencia - clase_ordenada[fin]['puntaje'] <= 1e-9:
                fin += 1
            grupo = clase_ordenada[cursor:fin]
            # Comparar instantes, no cadenas ISO con offsets diferentes.
            modelos = {n['incidente_id']: EvaluacionNecesidades.model_validate(
                {**n, 'posicion': 1}) for n in grupo}
            historial_completo = all(n.ultima_atencion_confirmada_en is not None for n in modelos.values())

            def desempate(n):
                modelo = modelos[n['incidente_id']]
                base = (modelo.primera_deteccion_en, str(modelo.incidente_id))
                return (modelo.ultima_atencion_confirmada_en, *base) if historial_completo else base

            ordenadas.extend(sorted(grupo, key=desempate))
            cursor = fin
    for posicion, datos in enumerate(ordenadas, 1):
        datos['posicion'] = posicion
    return ResultadoPriorizarNecesidades.model_validate(dict(
        esquema_version=entrada.esquema_version, ejecucion_id=entrada.ejecucion_id,
        creado_en=entrada.creado_en, origen=entrada.origen, datos_version=entrada.datos_version,
        politica_version=politica.politica_version, evaluaciones=ordenadas + pendientes,
        alertas_revision=alertas,
    ))
