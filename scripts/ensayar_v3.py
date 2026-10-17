"""Ensayo V3 local, preparación revisada o registro explícito en Supabase."""
import argparse
import json
from pathlib import Path
from uuid import UUID
from agentes.escenario_v3 import preparar_escenario
from agentes.planificacion import planificar
from contratos.solicitudes import SolicitudResolverRutas


def guardar(path, datos):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='modo', required=True)
    local = sub.add_parser('local')
    local.add_argument('--con-ia', action='store_true')
    local.add_argument('--salida', required=True)
    preparar = sub.add_parser('preparar')
    preparar.add_argument('--coordinador-uid', required=True, type=UUID)
    preparar.add_argument('--motivo', required=True)
    preparar.add_argument('--salida', required=True)
    registrar = sub.add_parser('registrar')
    registrar.add_argument('--coordinador-uid', required=True, type=UUID)
    registrar.add_argument('--motivo', required=True)
    registrar.add_argument('--entrada', required=True)
    args = parser.parse_args()
    if args.modo == 'local':
        solicitud = preparar_escenario()
        decisor = None
        if args.con_ia:
            from agentes.planificacion_gemini import DecisorGeminiPlanificacion
            decisor = DecisorGeminiPlanificacion()
        resultado = planificar(solicitud, decisor=decisor)
        guardar(args.salida, dict(solicitud=solicitud.model_dump(mode='json'),
                                 resultado=resultado.model_dump(mode='json'),
                                 autorizacion_operativa=False))
        print(json.dumps({'estado': resultado.estado, 'valido': bool(resultado.informe and resultado.informe.valido),
                          'modo': 'gemini' if args.con_ia else 'reglas', 'publicacion': 'bloqueada'}))
    elif args.modo == 'preparar':
        s = preparar_escenario(coordinador_id=args.coordinador_uid, motivo=args.motivo)
        guardar(args.salida, s.model_dump(mode='json'))
        print('Escenario revisable guardado; sin escritura en Supabase. Conservar este archivo para reintentos.')
    else:
        s = SolicitudResolverRutas.model_validate_json(Path(args.entrada).read_text(encoding='utf-8'))
        from comun.db import get_supabase
        respuesta = get_supabase().rpc('ra_preparar_ensayo_v3', dict(
            p_usuario_id=str(args.coordinador_uid), p_solicitud=s.model_dump(mode='json'),
            p_motivo=args.motivo)).execute().data
        print(json.dumps(respuesta))


if __name__ == '__main__':
    main()
