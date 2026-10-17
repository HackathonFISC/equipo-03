"""Ejecutar desde la raíz: python -m calculo.demo_v1 [--salida ruta.json]."""
import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from contratos.solicitudes import SolicitudResolverRutas
from .solver import solve_routes_minimo


def main():
    parser = argparse.ArgumentParser(description='Ensayo sintético V1; no publica ni aprueba planes.')
    parser.add_argument('--salida', type=Path, help='Guardar evidencia de entrada y resultado, sin sobrescribir.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    # Este fixture contiene confirmaciones ficticias explícitas para pruebas.
    # No se activan los archivos pendientes de datos/escenario/ de V0.
    fixture = root / 'contratos/ejemplos/solicitud_resolver_rutas.json'
    entrada = SolicitudResolverRutas.model_validate_json(fixture.read_text(encoding='utf-8-sig'))
    inicio = perf_counter()
    plan = solve_routes_minimo(entrada)
    duracion_ms = round((perf_counter() - inicio) * 1000, 3)
    print('ENSAYO SINTETICO V1 - no representa reparto real ni autorizacion')
    print(f'Estado: {plan.estado_solver.value}; rutas: {len(plan.rutas)}; pendientes: {len(plan.no_atendidos)}')
    nombres = {p.punto_atencion_id: p.nombre.split()[0] for p in entrada.puntos}
    zona = entrada.vehiculos[0].turno.inicio.tzinfo
    hora = lambda fecha: fecha.astimezone(zona).strftime('%H:%M')
    for numero, ruta in enumerate(plan.rutas, 1):
        litros = sum(p.litros_asignados for p in ruta.paradas)
        print(f'Cisterna {numero} ({ruta.vehiculo_id}): {litros:g} L; '
              f'{hora(ruta.salida_estimada)} a {hora(ruta.retorno_estimado)} (UTC-05:00 en el fixture)')
        for p in ruta.paradas:
            print(f'  {nombres[p.punto_atencion_id]}: {p.litros_asignados:g} L; '
                  f'descarga {hora(p.inicio_descarga)}-{hora(p.fin_descarga)}')
    print('Publicación bloqueada. Verificador independiente y selección parcial se implementan en V3.')
    if args.salida:
        evidencia = dict(escenario='fixture_sintetico_v1',
                         registrado_en=datetime.now(timezone.utc).isoformat(),
                         esperado='Cobertura de los seis puntos sin exceder capacidad, ventanas o turnos.',
                         metricas=dict(puntos_atendidos=sum(len(r.paradas) for r in plan.rutas),
                                       puntos_elegibles=len(entrada.puntos),
                                       litros_asignados=sum(p.litros_asignados for r in plan.rutas for p in r.paradas),
                                       puntos_pendientes=len(plan.no_atendidos)),
                         traza=dict(herramienta='solve_routes_minimo', version='v1-minimo',
                                    ortools=version('ortools'), duracion_ms=duracion_ms),
                         entrada=entrada.model_dump(mode='json'), obtenido=plan.model_dump(mode='json'))
        with args.salida.open('x', encoding='utf-8') as f:
            json.dump(evidencia, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'Evidencia guardada: {args.salida}')
    return 0 if plan.estado_solver == 'factible' else 1


if __name__ == '__main__':
    raise SystemExit(main())
