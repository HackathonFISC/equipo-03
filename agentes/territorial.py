"""Territorial V2: catálogo y episodio mediante herramientas, sin coordenadas LLM."""
from contratos.modelos import ExtraccionReporteLLM, Ubicacion
from geografia.catalogo import PuntoCatalogo
from geografia.resolver import resolve_location
from geografia.consolidacion import periodo_reportado, link_reports


def resolver_reporte(filas):
    reporte = filas['reporte']
    extraccion = ExtraccionReporteLLM.model_validate(reporte['interpretacion'])
    respuestas = filas.get('aclaraciones', [])
    textos = [extraccion.ubicacion_declarada, reporte['texto']]
    textos += [a.get('respuesta_texto') for a in respuestas]
    ubicaciones = [a['respuesta_ubicacion'] for a in respuestas if a.get('respuesta_ubicacion')]
    ubicacion = Ubicacion.model_validate(ubicaciones[-1]) if ubicaciones else None
    catalogo = [PuntoCatalogo.desde_fila(p) for p in filas['catalogo']]
    # Una aclaración explícita prevalece sobre las alternativas del reporte original.
    # Respuestas sobre otros campos no borran una ubicación ya identificada.
    for aclaracion in reversed(respuestas):
        texto_respuesta = aclaracion.get('respuesta_texto')
        if texto_respuesta and resolve_location([texto_respuesta], catalogo).candidatos:
            textos = [texto_respuesta]
            break
    resolucion = resolve_location(textos, catalogo, ubicacion)
    salida = {'estado': resolucion.estado, 'motivo': resolucion.motivo,
              'candidatos': [str(p.punto_atencion_id) for p in resolucion.candidatos]}
    if resolucion.punto:
        inicio, fin = periodo_reportado(reporte['creado_en'], extraccion.campos.horas_sin_agua)
        salida.update(punto_atencion_id=str(resolucion.punto.punto_atencion_id),
                      periodo_inicio=inicio.isoformat(), periodo_fin=fin.isoformat(),
                      episodio_establecido=extraccion.campos.horas_sin_agua is not None,
                      tipo_problema=extraccion.campos.tipo_problema)
    return salida


def procesar_territorial(ejecucion_id, db, trabajador_id):
    filas = db.rpc('ra_tomar_etapa_v2', {'p_ejecucion_id': str(ejecucion_id),
        'p_trabajador_id': trabajador_id, 'p_etapa': 'territorial'}).execute().data
    if filas is None:
        return {'estado': 'no_tomada'}
    salida = resolver_reporte(filas)
    return link_reports(ejecucion_id, db, trabajador_id, filas, salida)
