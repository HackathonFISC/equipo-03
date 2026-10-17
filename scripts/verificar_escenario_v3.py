"""Comprueba el escenario territorial de ensayo sin calcular ni autorizar rutas."""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calculo.demanda import validate_need
from contratos.solicitudes import SolicitudResolverRutas, SolicitudValidarNecesidad

CARPETA = ROOT / 'datos/escenario/oeste-1.0-ensayo-1'
CATALOGO = ROOT / 'datos/geografia/puntos.csv'


def exigir(condicion, mensaje):
    if not condicion:
        raise ValueError(mensaje)


def verificar(carpeta=CARPETA, catalogo=CATALOGO):
    carpeta, catalogo = Path(carpeta), Path(catalogo)

    def leer(nombre):
        return json.loads((carpeta / nombre).read_text(encoding='utf-8-sig'))

    solicitud = SolicitudResolverRutas.model_validate(leer('solicitud_rutas.json'))
    solicitudes = [SolicitudValidarNecesidad.model_validate(n)
                   for n in leer('solicitudes_validacion.json')]
    supuestos = leer('supuestos.json')
    if 'politica_fuente' in supuestos:
        politica_fuente = json.loads((ROOT / supuestos['politica_fuente']).read_text(encoding='utf-8-sig'))
        exigir(solicitud.politica.model_dump(mode='json') == politica_fuente,
               'La política del escenario difiere de su archivo fuente.')
    texto_catalogo = catalogo.read_text(encoding='utf-8-sig')
    filas = list(csv.DictReader(texto_catalogo.splitlines()))
    exigir(hashlib.sha256(texto_catalogo.encode('utf-8')).hexdigest()
           == supuestos['sha256_catalogo_lf'], 'El catálogo cambió; revisar y versionar el escenario.')
    exigir(len(filas) == 6 and Counter(f['distrito'] for f in filas)
           == {'Arraiján': 3, 'La Chorrera': 3}, 'Se requieren seis puntos, tres por distrito.')
    exigir({f['catalogo_version'] for f in filas} == {supuestos['catalogo_version']},
           'Versión del catálogo incompatible.')
    puntos = {str(p.punto_atencion_id): p for p in solicitud.puntos}
    exigir(set(puntos) == {f['punto_atencion_id'] for f in filas}, 'UUID de puntos distintos del catálogo.')
    referencias = {f['punto_atencion_id']: f for f in supuestos['referencias']}
    exigir(len(supuestos['referencias']) == 6 and set(referencias) == set(puntos),
           'Referencias incompletas o duplicadas.')
    for fila in filas:
        punto = puntos[fila['punto_atencion_id']]
        exigir(str(punto.sector_id) == fila['sector_id'] and punto.nombre == fila['nombre']
               and punto.origen == fila['origen'], 'Identidad o procedencia del catálogo alterada.')
        exigir(punto.ubicacion.latitud == float(fila['latitud'])
               and punto.ubicacion.longitud == float(fila['longitud'])
               and punto.ubicacion.fuente == fila['fuente_ubicacion']
               and punto.ubicacion.precision_metros is None
               and punto.ubicacion.representa_punto_atencion is None,
               'Coordenadas o validación del lugar alteradas.')
        exigir(all(referencias[fila['punto_atencion_id']][k] == fila[k]
                   for k in referencias[fila['punto_atencion_id']]),
               'Procedencia documental incompatible.')
    exigir(solicitud.datos_version == supuestos['datos_version'], 'Versión de escenario incompatible.')
    exigir(supuestos['estado'] == 'preparacion_sintetica_pendiente_confirmacion'
           and supuestos['pendientes_confirmacion'], 'Falta declarar confirmaciones pendientes.')
    exigir(solicitud.origen == 'sintetico' and solicitud.matriz.origen == 'sintetico'
           and solicitud.deposito.origen == 'sintetico', 'El ensayo debe conservar su origen sintético.')
    exigir(solicitud.deposito.ubicacion.representa_punto_atencion is None,
           'El depósito ficticio no está validado como lugar de entrega.')
    exigir(solicitud.politica.estado == 'propuesta_demo'
           and solicitud.politica.confirmacion_activacion is None, 'No activar la política del ensayo.')
    parametros = supuestos['parametros_propuestos']
    exigir(len(solicitud.vehiculos) == 2 and all(
        v.origen == 'sintetico' and v.disponible
        and v.capacidad_litros == parametros['capacidad_por_cisterna_litros']
        and v.turno.model_dump(mode='json') == parametros['turno'] for v in solicitud.vehiculos),
        'Flota o turno distintos de los supuestos declarados.')
    exigir(len(solicitud.matriz.nodos_ids) == 7, 'La matriz debe tener siete nodos.')
    exigir(all(s.descarga_minutos == parametros['descarga_por_punto_minutos']
               for s in solicitud.servicios), 'Descargas distintas de los supuestos declarados.')
    peticiones = {str(n.punto_atencion_id): n for n in solicitudes}
    exigir(len(solicitudes) == 6 and set(peticiones) == set(puntos),
           'Solicitudes de demanda incompletas o duplicadas.')
    resultados = []
    for n in solicitud.necesidades:
        pid = str(n.punto_atencion_id)
        p = peticiones[pid]
        exigir((p.ejecucion_id, p.incidente_id, p.datos_version, p.origen)
               == (solicitud.ejecucion_id, n.incidente_id, solicitud.datos_version, 'sintetico'),
               'Demanda con identidad, origen o versión incompatible.')
        exigir(n.origen == 'sintetico' and n.estado_demanda == 'pendiente'
               and n.estado_prioridad == 'pendiente' and n.confirmacion_demanda is None
               and n.clase_prioridad is None and n.confirmacion_clase is None
               and n.vulnerabilidad is None and n.confirmacion_vulnerabilidad is None,
               'No introducir confirmaciones ni clasificación en el ensayo pendiente.')
        exigir(p.demanda.metodo == 'directa' and p.demanda.confirmacion is None
               and p.capacidad_recepcion_litros is None
               and n.demanda_litros == p.demanda.litros_declarados
               == parametros['demandas_litros_por_punto'][pid],
               'Demanda, recepción o confirmación distinta de los supuestos declarados.')
        exigir(n.ventana_atencion is not None and n.ventana_atencion.model_dump(mode='json')
               == parametros['ventana_por_punto'], 'Ventana distinta del supuesto declarado.')
        resultado = validate_need(p)
        exigir(resultado.estado == 'pendiente' and resultado.demanda_litros == n.demanda_litros,
               'Una demanda sin confirmación ni recepción debe conservarse pendiente.')
        resultados.append(resultado.model_dump(mode='json'))
    return dict(datos_version=solicitud.datos_version, catalogo_version=supuestos['catalogo_version'],
                puntos=6, vehiculos=2, nodos_matriz=7,
                demanda_ensayo_litros=sum(n.demanda_litros for n in solicitud.necesidades),
                necesidades_pendientes=len(resultados), politica_estado=solicitud.politica.estado,
                autorizacion_operativa=False, validaciones_demanda=resultados,
                pendientes_confirmacion=supuestos['pendientes_confirmacion'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--carpeta', type=Path, default=CARPETA, help='Carpeta del escenario a comprobar.')
    parser.add_argument('--salida', type=Path, help='Guardar evidencia nueva sin sobrescribir.')
    args = parser.parse_args()
    resultado = verificar(args.carpeta)
    print('ESCENARIO TERRITORIAL DE ENSAYO - sin autorización operativa')
    print(f"Catálogo {resultado['catalogo_version']}: 6 puntos, 2 cisternas, matriz de 7 nodos.")
    print(f"Demanda sintética: {resultado['demanda_ensayo_litros']:g} L; 6 necesidades pendientes.")
    print('Política propuesta; recepción desconocida. No se ejecutaron solver, BD ni publicación.')
    if args.salida:
        evidencia = dict(registrado_en=datetime.now(timezone.utc).isoformat(), origen='sintetico',
                         entrada={nombre: json.loads((args.carpeta / nombre).read_text(encoding='utf-8'))
                                  for nombre in ('solicitud_rutas.json', 'solicitudes_validacion.json', 'supuestos.json')},
                         esperado=dict(puntos=6, vehiculos=2, nodos_matriz=7,
                                       necesidades_pendientes=6, politica_estado='propuesta_demo'),
                         obtenido=resultado, traza=dict(herramientas=['validate_need'],
                                                       verificacion='Contratos, catálogo y coherencia de escenario; no verify_plan.'))
        with args.salida.open('x', encoding='utf-8') as archivo:
            json.dump(evidencia, archivo, ensure_ascii=False, indent=2)
            archivo.write('\n')


if __name__ == '__main__':
    main()
