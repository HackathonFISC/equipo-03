"""Demo local V2: python -m calculo.demo_v2 [--salida ruta.json]."""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from contratos.solicitudes import SolicitudValidarNecesidad, SolicitudPriorizarNecesidades
from .demanda import validate_need
from .prioridad import CALCULO_PENDIENTE, score_needs


def main():
    parser = argparse.ArgumentParser(description='Demanda y prioridad sintéticas V2 sin red ni BD.')
    parser.add_argument('--salida', type=Path, help='Guardar entrada y resultados sin sobrescribir.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]

    def leer(nombre):
        return json.loads((root / 'contratos/ejemplos' / nombre).read_text(encoding='utf-8'))

    inicio = perf_counter()
    casos = []
    print('ENSAYO SINTETICO V2 - las confirmaciones del fixture no son permisos reales')
    for nombre in ('solicitud_validar_directa.json', 'solicitud_validar_formula.json',
                   'solicitud_validar_formula_pendiente.json'):
        entrada = SolicitudValidarNecesidad.model_validate(leer(nombre))
        resultado = validate_need(entrada)
        litros = 'desconocida' if resultado.demanda_litros is None else f'{resultado.demanda_litros:g} L'
        print(f'{entrada.demanda.metodo}: {resultado.estado.value}; demanda {litros}')
        casos.append(dict(caso=nombre, esperado='pendiente' if 'pendiente' in nombre else 'validada',
                          entrada=entrada.model_dump(mode='json'), obtenido=resultado.model_dump(mode='json')))

    # Construye solicitudes de validación reales desde cantidades sintéticas del fixture.
    rutas = leer('solicitud_resolver_rutas.json')
    prioridad = leer('solicitud_priorizar.json')
    prioridad['necesidades'] = copy.deepcopy(rutas['necesidades'])
    plantilla = leer('solicitud_validar_directa.json')
    solicitudes = []
    for necesidad in prioridad['necesidades']:
        peticion = copy.deepcopy(plantilla)
        peticion.update(incidente_id=necesidad['incidente_id'], punto_atencion_id=necesidad['punto_atencion_id'])
        peticion['demanda']['litros_declarados'] = necesidad['demanda_litros']
        peticion['capacidad_recepcion_litros'] = 5000.0
        peticion['supuestos'] = ['Recepción de 5000 L propuesta exclusivamente para este ensayo sintético V2.']
        validada = validate_need(SolicitudValidarNecesidad.model_validate(peticion))
        necesidad.update(estado_demanda=validada.estado.value, demanda_litros=validada.demanda_litros,
                         confirmacion_demanda=validada.confirmacion.model_dump(mode='json'),
                         estado_prioridad='pendiente', puntaje=None, componentes=None, posicion=None,
                         pendientes=[CALCULO_PENDIENTE], supuestos=necesidad['supuestos'] + validada.supuestos)
        solicitudes.append(dict(entrada=peticion, obtenido=validada.model_dump(mode='json')))
    resultado = score_needs(SolicitudPriorizarNecesidades.model_validate(prioridad))
    nombres = {p['punto_atencion_id']:p['nombre'].split()[0] for p in rutas['puntos']}
    print('Ranking calculado con politica activa SOLO en el fixture sintetico:')
    for n in resultado.evaluaciones:
        print(f'  {n.posicion}. {nombres[str(n.punto_atencion_id)]}: {n.clase_prioridad.value}, '
              f'{n.demanda_litros:g} L, puntaje {n.puntaje:.2f}')
    # Demuestra que las seis necesidades originales V0 continúan pendientes.
    pendientes = copy.deepcopy(prioridad)
    pendientes['necesidades'] = json.loads((root / 'datos/escenario/demandas.json').read_text(encoding='utf-8'))['necesidades']
    revision = score_needs(SolicitudPriorizarNecesidades.model_validate(pendientes))
    print(f'Escenario V0 original: {sum(n.estado_prioridad == "pendiente" for n in revision.evaluaciones)} '
          'necesidades pendientes, sin inventar confirmaciones.')
    print('Sin planes, aprobaciones, mensajes ni cambios en politica_v1.json.')
    if args.salida:
        evidencia = dict(version='v2-necesidades', registrado_en=datetime.now(timezone.utc).isoformat(),
                         origen='sintetico', traza=dict(herramientas=['validate_need','score_needs'],
                                                      duracion_ms=round((perf_counter()-inicio)*1000,3)),
                         esperado='Demanda validada o pendiente; criticidad antes de puntaje; desconocidos fuera del ranking.',
                         validaciones=casos, solicitudes_escenario=solicitudes,
                         priorizacion=dict(entrada=prioridad, obtenido=resultado.model_dump(mode='json')),
                         escenario_v0=dict(entrada=pendientes, obtenido=revision.model_dump(mode='json')),
                         metricas=dict(necesidades_ensayo=6, necesidades_priorizadas=len(resultado.evaluaciones),
                                       necesidades_v0=6, pendientes_v0=sum(n.estado_prioridad=='pendiente' for n in revision.evaluaciones)))
        with args.salida.open('x',encoding='utf-8') as archivo:
            json.dump(evidencia,archivo,ensure_ascii=False,indent=2)
            archivo.write('\n')
        print(f'Evidencia guardada: {args.salida}')


if __name__ == '__main__':
    main()
