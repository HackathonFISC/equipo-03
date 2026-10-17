"""Demo de solve_routes y verify_plan: completo, parcial y déficit crítico."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from contratos.solicitudes import SolicitudResolverRutas, SolicitudVerificarPlan
from .demo_escenario_v3 import construir
from .solver import solve_routes
from .verificador import verify_plan


def ejecutar_casos():
    base = construir()['solicitud_rutas']
    completo = copy.deepcopy(base)
    completo['version'] = 4
    parcial = copy.deepcopy(base)
    parcial['version'] = 5
    parcial['vehiculos'][1]['disponible'] = False
    deficit = copy.deepcopy(base)
    deficit['version'] = 6
    next(n for n in deficit['necesidades'] if n['clase_prioridad'] == 'critico')['demanda_litros'] = 12000.0
    casos = []
    for nombre, datos, esperado in (
            ('completo', completo, dict(atendidos=6, pendientes=0, litros_asignados=15000, verificacion_valida=True)),
            ('una_cisterna', parcial, dict(atendidos=4, pendientes=2, litros_asignados=9000, verificacion_valida=True)),
            ('critico_supera_cisterna', deficit, dict(atendidos=5, pendientes=1, litros_asignados=12000, verificacion_valida=False))):
        datos['datos_version'] += '-' + nombre
        for n in datos['necesidades']:
            n['datos_version'] = datos['datos_version']
        entrada = SolicitudResolverRutas.model_validate(datos)
        inicio = perf_counter()
        propuesta = solve_routes(entrada)
        informe = verify_plan(SolicitudVerificarPlan(esquema_version=entrada.esquema_version,
            ejecucion_id=entrada.ejecucion_id, creado_en=entrada.creado_en, origen=entrada.origen,
            solicitud_original=entrada, propuesta=propuesta))
        obtenido = dict(atendidos=sum(len(r.paradas) for r in propuesta.rutas),
            pendientes=len(propuesta.no_atendidos),
            litros_asignados=sum(p.litros_asignados for r in propuesta.rutas for p in r.paradas),
            verificacion_valida=informe.valido)
        if obtenido != esperado:
            raise AssertionError(f'{nombre}: resultado distinto del esperado: {obtenido}')
        casos.append(dict(caso=nombre, entrada=entrada.model_dump(mode='json'), esperado=esperado,
            obtenido=obtenido, coincide=True, propuesta=propuesta.model_dump(mode='json'),
            verificacion=informe.model_dump(mode='json'),
            metricas=dict(duracion_ms=round((perf_counter() - inicio) * 1000, 3),
                litros_pendientes_conocidos=sum(n.demanda_pendiente_litros for n in propuesta.no_atendidos
                                               if n.demanda_pendiente_litros is not None),
                necesidades_con_litros_desconocidos=sum(n.demanda_pendiente_litros is None for n in propuesta.no_atendidos))))
    return casos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, help='Guardar nueva evidencia sin sobrescribir.')
    args = parser.parse_args()
    casos = ejecutar_casos()
    zona = timezone(timedelta(hours=-5))
    print('ENSAYO SINTÉTICO V3 - sin autorización operativa ni publicación')
    for caso in casos:
        r = caso['obtenido']
        print(f"{caso['caso']}: {r['atendidos']} atendidos; {r['pendientes']} pendientes; "
              f"{r['litros_asignados']:g} L; verificación {r['verificacion_valida']}")
        for i, ruta in enumerate(caso['propuesta']['rutas'], 1):
            salida = datetime.fromisoformat(ruta['salida_estimada'].replace('Z', '+00:00')).astimezone(zona)
            retorno = datetime.fromisoformat(ruta['retorno_estimado'].replace('Z', '+00:00')).astimezone(zona)
            print(f"  Cisterna {i}: {sum(p['litros_asignados'] for p in ruta['paradas']):g} L; "
                  f"{salida:%H:%M}-{retorno:%H:%M} UTC-05:00")
        for n in caso['propuesta']['no_atendidos']:
            print(f"  Pendiente {n['punto_atencion_id']}: {n['codigo']}; {n['demanda_pendiente_litros']} L")
    print('Verificar restricciones no acredita calidad del agua, aprobación humana ni entrega física.')
    if args.salida:
        directorio = Path(__file__).parent
        evidencia = dict(version='v3-bloques-4-5', origen='sintetico',
            registrado_en=datetime.now(timezone.utc).isoformat(),
            traza=dict(herramientas=['solve_routes', 'verify_plan'],
                sha256_codigo={nombre: hashlib.sha256((directorio / nombre).read_bytes()).hexdigest()
                               for nombre in ('solver_v3.py', 'verificador.py')}),
            casos=casos, metricas=dict(casos=len(casos), coincidentes=len(casos)))
        with args.salida.open('x', encoding='utf-8') as archivo:
            json.dump(evidencia, archivo, ensure_ascii=False, indent=2)
            archivo.write('\n')


if __name__ == '__main__':
    main()
