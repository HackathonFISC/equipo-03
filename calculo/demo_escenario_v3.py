"""Demanda, recepción y prioridad del ensayo 3; sin solver, BD ni publicación."""
import argparse
import copy
import json
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from pydantic import TypeAdapter

from contratos.modelos import Cantidad, CantidadPositiva, EnteroPositivo, Proporcion
from contratos.solicitudes import SolicitudPriorizarNecesidades, SolicitudResolverRutas, SolicitudValidarNecesidad
from .demanda import validate_need
from .prioridad import CALCULO_PENDIENTE, score_needs

ROOT = Path(__file__).resolve().parents[1]
CARPETA = ROOT / 'datos/escenario/oeste-1.0-ensayo-3'


def recepcion_libre(nominal, almacenada, margen):
    """Espacio libre tras margen de ensayo; no acredita capacidad real del lugar."""
    if nominal is None or almacenada is None:
        return None
    nominal = TypeAdapter(CantidadPositiva).validate_python(nominal)
    almacenada = TypeAdapter(Cantidad).validate_python(almacenada)
    margen = TypeAdapter(Proporcion).validate_python(margen)
    if almacenada > nominal:
        raise ValueError('Agua almacenada superior a capacidad nominal.')
    libre = Decimal(str(nominal)) * (1 - Decimal(str(margen))) - Decimal(str(almacenada))
    return float(max(Decimal(0), libre))


def simular(parametros, base, politica):
    """Construye objetos nuevos a partir de hipótesis explícitas de un fixture."""
    if parametros['modo'] != 'fixture_sintetico':
        raise ValueError('Esta demo solo construye fixtures sintéticos.')
    confirmacion = parametros['confirmacion_fixture']
    if not confirmacion['motivo'].startswith('FIXTURE SINTÉTICO:'):
        raise ValueError('La confirmación debe identificarse como ficticia.')
    s = copy.deepcopy(base)
    perfiles = parametros['perfiles']
    ids = {p['punto_atencion_id'] for p in s['puntos']}
    if len(perfiles) != 6 or {p['punto_atencion_id'] for p in perfiles} != ids:
        raise ValueError('Se requiere un perfil único para cada uno de los seis puntos.')
    personas_por_familia = TypeAdapter(EnteroPositivo).validate_python(parametros['personas_por_familia'])
    s['datos_version'] = parametros['datos_version']
    s['version'] = 3
    s['politica'] = copy.deepcopy(politica)
    s['politica'].update(politica_version=politica['politica_version'] + '-fixture-3',
                         estado='activa', confirmacion_activacion=confirmacion)
    s['politica']['fundamento'] += ' Copia activa exclusivamente en fixture local con identidad ficticia.'
    s['matriz']['matriz_version'] = parametros['datos_version'] + '-matriz-1'
    contexto = {k: s[k] for k in ('esquema_version', 'ejecucion_id', 'creado_en', 'origen')}
    anteriores = {n['punto_atencion_id']: n for n in s['necesidades']}
    servicios = {n['punto_atencion_id']: n for n in s['servicios']}
    solicitudes, validaciones, necesidades, resumen = [], [], [], []
    for p in perfiles:
        familias = TypeAdapter(EnteroPositivo).validate_python(p['familias_sinteticas'])
        if p['personas_atendidas'] is not None and p['personas_atendidas'] != familias * personas_por_familia:
            raise ValueError('Población incompatible con los grupos sintéticos declarados.')
        pid = p['punto_atencion_id']
        recepcion = recepcion_libre(p['tanque_nominal_litros'], p['agua_almacenada_litros'],
                                   p['margen_tanque_proporcion'])
        reserva = p['reserva_utilizable_litros']
        if reserva is not None and p['agua_almacenada_litros'] is not None and reserva > p['agua_almacenada_litros']:
            raise ValueError('Reserva utilizable superior al agua almacenada.')
        supuestos = [*parametros['supuestos'], p['supuesto_clasificacion'], parametros['limite']]
        peticion = SolicitudValidarNecesidad.model_validate(dict(
            **contexto, incidente_id=anteriores[pid]['incidente_id'], punto_atencion_id=pid,
            datos_version=s['datos_version'], capacidad_recepcion_litros=recepcion,
            demanda=dict(metodo='formula', personas_atendidas=p['personas_atendidas'],
                         dotacion_litros_persona_dia=p['dotacion_litros_persona_dia'],
                         dias_cobertura=p['dias_cobertura'], reserva_utilizable_litros=reserva,
                         fuente='Hipótesis domésticas sintéticas de parametros.json; no demanda institucional medida.',
                         confirmacion=confirmacion), supuestos=supuestos))
        resultado = validate_need(peticion)
        necesidad = dict(**contexto, incidente_id=peticion.incidente_id, punto_atencion_id=pid,
            datos_version=s['datos_version'], politica_version=s['politica']['politica_version'],
            estado_demanda=resultado.estado, demanda_litros=resultado.demanda_litros,
            metodo_demanda='formula', confirmacion_demanda=resultado.confirmacion,
            clase_prioridad=p['clase_prioridad'], confirmacion_clase=confirmacion,
            ventana_atencion=anteriores[pid]['ventana_atencion'], horas_sin_agua=p['horas_sin_agua'],
            personas_atendidas=p['personas_atendidas'], vulnerabilidad=p['vulnerabilidad'],
            confirmacion_vulnerabilidad=confirmacion, ultima_atencion_confirmada_en=None,
            primera_deteccion_en=anteriores[pid]['primera_deteccion_en'], estado_prioridad='pendiente',
            pendientes=[*resultado.faltantes, *resultado.motivos, CALCULO_PENDIENTE],
            supuestos=supuestos, requiere_revision_urgente=False)
        necesidades.append(necesidad)
        if resultado.demanda_litros is not None:
            caudal = TypeAdapter(CantidadPositiva).validate_python(p['caudal_descarga_litros_minuto'])
            preparacion = TypeAdapter(Cantidad).validate_python(p['preparacion_descarga_minutos'])
            minutos = Decimal(str(resultado.demanda_litros)) / Decimal(str(caudal)) + Decimal(str(preparacion))
            servicios[pid]['descarga_minutos'] = max(1, int(minutos.to_integral_value(rounding=ROUND_CEILING)))
        else:
            necesidad['pendientes'].append('Descarga todavía basada en supuesto previo; falta demanda calculable.')
        solicitudes.append(peticion.model_dump(mode='json'))
        validaciones.append(resultado.model_dump(mode='json'))
        resumen.append(dict(punto_atencion_id=pid, nombre=p['nombre_referencia'],
                            personas=p['personas_atendidas'], demanda_litros=resultado.demanda_litros,
                            recepcion_litros=recepcion, estado_demanda=resultado.estado.value,
                            descarga_minutos=servicios[pid]['descarga_minutos']))
    entrada_prioridad = SolicitudPriorizarNecesidades.model_validate(dict(
        **contexto, datos_version=s['datos_version'], politica=s['politica'], necesidades=necesidades))
    ranking = score_needs(entrada_prioridad)
    s['necesidades'] = [n.model_dump(mode='json') for n in ranking.evaluaciones]
    s['servicios'] = list(servicios.values())
    solicitud_rutas = SolicitudResolverRutas.model_validate(s)
    return dict(modo='fixture_sintetico', limite=parametros['limite'],
                autorizacion_operativa=False,
                bloqueos_publicacion=['Confirmaciones e identidad ficticias; sin autorización real.',
                    'Ubicaciones, fuente potable, vehículos, acceso y recepción operativa no verificados.',
                    'Sin solver completo, verificador independiente ni aprobación de plan.'],
                parametros=copy.deepcopy(parametros), resumen=resumen,
                solicitudes_validacion=solicitudes, validaciones_demanda=validaciones,
                solicitud_prioridad=entrada_prioridad.model_dump(mode='json'),
                resultado_prioridad=ranking.model_dump(mode='json'),
                solicitud_rutas=solicitud_rutas.model_dump(mode='json'))


def construir():
    def leer(ruta):
        return json.loads((ROOT / ruta).read_text(encoding='utf-8'))
    parametros = leer('datos/escenario/oeste-1.0-ensayo-3/parametros.json')
    return simular(parametros, leer('datos/escenario/oeste-1.0-ensayo-2/solicitud_rutas.json'),
                   leer(parametros['politica_fuente']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, help='Guardar fixture reproducible sin sobrescribir.')
    args = parser.parse_args()
    r = construir()
    print('ENSAYO SINTÉTICO V3: confirmaciones ficticias; política activa SOLO en este fixture.')
    for n in r['resumen']:
        demanda = 'desconocida' if n['demanda_litros'] is None else f"{n['demanda_litros']:g} L"
        recepcion = 'desconocida' if n['recepcion_litros'] is None else f"{n['recepcion_litros']:g} L"
        print(f"{n['nombre']}: demanda {demanda}; recepción libre {recepcion}; {n['estado_demanda']}.")
    print('Ranking del ensayo:')
    nombres = {n['punto_atencion_id']: n['nombre'] for n in r['resumen']}
    for n in r['resultado_prioridad']['evaluaciones']:
        puntaje = 'pendiente' if n['puntaje'] is None else f"{n['puntaje']:.2f}"
        print(f"  {n['posicion']}. {nombres[n['punto_atencion_id']]}: {n['clase_prioridad']}; {puntaje}")
    print('Publicación bloqueada; sin rutas calculadas ni cambios en Supabase.')
    if args.salida:
        with args.salida.open('x', encoding='utf-8') as archivo:
            json.dump(r, archivo, ensure_ascii=False, indent=2)
            archivo.write('\n')


if __name__ == '__main__':
    main()
