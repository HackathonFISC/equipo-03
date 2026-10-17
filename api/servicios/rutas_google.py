"""Vista previa vial de reportes localizados, sin inventar demanda o asignar camión."""
from itertools import permutations
from pydantic import ValidationError
from api.errores_http import ErrorApi
from api.servicios.reportes import _localizacion_vigente, _ubicacion_reportada, _leer_interpretacion
from contratos.errores import CodigoError
from contratos.modelos import Ubicacion
from geografia.rutas_google import RutasGoogle, ErrorRutas, enlaces_recorrido


def opciones(db):
    reportes = db.table('reportes').select('reporte_id,interpretacion,localizacion_resuelta,ubicacion_compartida,creado_en,aclaraciones(respuesta_ubicacion,respondida_en)').order('creado_en', desc=True).limit(200).execute().data
    destinos = []
    for fila in reportes:
        localizacion = _localizacion_vigente(fila.get('localizacion_resuelta'))
        ubicacion = _ubicacion_reportada(fila)
        if ubicacion is None and localizacion and localizacion.get('ubicacion'):
            try:
                ubicacion = Ubicacion.model_validate(localizacion['ubicacion'])
            except ValidationError:
                continue
        if ubicacion is None:
            continue
        interpretacion = _leer_interpretacion(fila.get('interpretacion'))
        if interpretacion and interpretacion.fuera_de_alcance:
            continue
        destinos.append({'reporte_id': str(fila['reporte_id']),
            'nombre': (interpretacion.ubicacion_declarada if interpretacion else None) or 'Ubicación compartida',
            'ubicacion': ubicacion.model_dump(mode='json')})
    filas = db.table('depositos').select('deposito_id,nombre,latitud,longitud,activo').eq('activo', True).execute().data
    depositos = []
    for fila in filas:
        try:
            u = Ubicacion(latitud=float(fila['latitud']),longitud=float(fila['longitud']),fuente='catalogo')
        except (ValueError, TypeError, KeyError):
            continue
        depositos.append({'deposito_id':str(fila['deposito_id']),'nombre':fila['nombre'],'ubicacion':u.model_dump(mode='json')})
    return {'destinos':destinos,'depositos':depositos}


def previsualizar(db, datos, proveedor=None):
    # Releer coordenadas y disponibilidad; nunca aceptar las coordenadas del navegador.
    disponibles = opciones(db)
    depositos = {d['deposito_id']:d for d in disponibles['depositos']}
    destinos = {d['reporte_id']:d for d in disponibles['destinos']}
    deposito = depositos.get(str(datos.deposito_id))
    ids = [str(i) for i in datos.reportes_ids]
    if deposito is None or any(i not in destinos for i in ids):
        raise ErrorApi(CodigoError.CONTRATO_INVALIDO, 'El depósito o algún reporte ya no tiene una ubicación vigente. Actualiza los destinos.')
    proveedor = proveedor or RutasGoogle.cargar()
    if proveedor is None:
        raise ErrorApi(CodigoError.PROVEEDOR_NO_DISPONIBLE,'Configura la clave de Google Maps y habilita Routes API en el servidor.',recuperable=True)
    try:
        calculo = proveedor.calcular([datos.deposito_id,*datos.reportes_ids],
            [deposito['ubicacion'],*[destinos[i]['ubicacion'] for i in ids]])
    except ErrorRutas as error:
        raise ErrorApi(CodigoError.PROVEEDOR_NO_DISPONIBLE,str(error),recuperable=True) from None
    matriz = calculo['matriz'].minutos
    mejor = None
    # Hasta 6 destinos: 720 órdenes como máximo, recorrido dirigido con retorno.
    for orden in permutations(range(1,len(ids)+1)):
        nodos = [0,*orden,0]
        tiempos = [matriz[a][b] for a,b in zip(nodos,nodos[1:])]
        if any(t is None for t in tiempos):
            continue
        opcion = (sum(tiempos),orden)
        if mejor is None or opcion < mejor:
            mejor = opcion
    if mejor is None:
        raise ErrorApi(CodigoError.CONTRATO_INVALIDO,'No hay un recorrido vial que visite todos los destinos y regrese al depósito.')
    minutos,orden = mejor
    paradas = [destinos[ids[i-1]] for i in orden]
    nodos = [0,*orden,0]
    distancia = sum(calculo['metros'][a][b] for a,b in zip(nodos,nodos[1:]))
    return {'deposito':deposito,'paradas':paradas,'duracion_minutos':minutos,'distancia_metros':distancia,
        'consultado_en':calculo['consultado_en'],'proveedor':'Google Maps',
        **enlaces_recorrido(deposito['ubicacion'],[p['ubicacion'] for p in paradas])}
