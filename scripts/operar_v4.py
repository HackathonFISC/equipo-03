"""Operaciones backend V4 explícitas; no aprueba planes ni inicia Telegram.

Uso administrativo con credenciales backend locales. Las rutas de Noel deben
obtener el usuario del token verificado, no copiarlo del cuerpo del navegador.
"""
import argparse
import json
from uuid import UUID
from comun.db import get_supabase
from contratos.consultas import SolicitudEstadoSector
from agentes.estado_sector import consultar_estado_sector


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='accion',required=True)
    estado=sub.add_parser('estado-sector');estado.add_argument('--sector-id',type=UUID,required=True)
    seleccionar=sub.add_parser('seleccionar-plan')
    seleccionar.add_argument('--coordinador-uid',type=UUID,required=True)
    seleccionar.add_argument('--sector-id',type=UUID,required=True)
    seleccionar.add_argument('--plan-id',type=UUID,required=True)
    seleccionar.add_argument('--version',type=int,required=True)
    seleccionar.add_argument('--motivo',required=True)
    destino=sub.add_parser('destino-ensayo')
    destino.add_argument('--coordinador-uid',type=UUID,required=True)
    destino.add_argument('--destino-id',type=UUID,required=True)
    grupo=destino.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--habilitar',action='store_true');grupo.add_argument('--deshabilitar',action='store_true')
    destino.add_argument('--motivo',required=True)
    a=p.parse_args();db=get_supabase()
    if a.accion=='estado-sector':
        print(consultar_estado_sector(db,SolicitudEstadoSector(sector_id=a.sector_id)).model_dump_json());return 0
    if not a.motivo.strip() or len(a.motivo)>4000:p.error('Motivo entre 1 y 4000 caracteres')
    if a.accion=='seleccionar-plan':
        if a.version<1:p.error('Versión positiva requerida')
        rpc='ra_seleccionar_plan_sector_v4'
        params=dict(p_usuario_id=str(a.coordinador_uid),p_sector_id=str(a.sector_id),
                    p_plan_id=str(a.plan_id),p_version=a.version,p_motivo=a.motivo)
    else:
        rpc='ra_configurar_destino_ensayo_v4'
        params=dict(p_usuario_id=str(a.coordinador_uid),p_destino_id=str(a.destino_id),
                    p_habilitado=a.habilitar,p_motivo=a.motivo)
    print(json.dumps(db.rpc(rpc,params).execute().data,ensure_ascii=False));return 0


if __name__=='__main__':
    raise SystemExit(main())
