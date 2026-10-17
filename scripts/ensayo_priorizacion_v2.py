"""Preparar, registrar y procesar dos casos V2 aislados. Sin Gemini ni rutas."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID
from agentes.ensayo_priorizacion_v2 import preparar_paquetes
from agentes.priorizacion import procesar_priorizacion


def huella(datos):
    return hashlib.sha256(json.dumps(datos,sort_keys=True,default=str).encode()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='modo',required=True)
    crear=sub.add_parser('preparar');crear.add_argument('--coordinador-uid',required=True,type=UUID)
    crear.add_argument('--motivo',required=True);crear.add_argument('--salida',required=True)
    for modo in ['registrar','procesar','verificar']:
        q=sub.add_parser(modo);q.add_argument('--entrada',required=True)
        q.add_argument('--evidencia',required=True)
    a=p.parse_args()
    if a.modo=='preparar':
        data={'motivo':a.motivo,'paquetes':preparar_paquetes(a.coordinador_uid,a.motivo)}
        with open(a.salida,'x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
        print('Archivo revisado preparado; sin escritura en Supabase. Conservarlo para reintentos.')
        return
    data=json.loads(Path(a.entrada).read_text(encoding='utf-8'))
    from comun.db import get_supabase
    db=get_supabase();antes=db.rpc('ra_incidentes_snapshot_v2',{}).execute().data
    evidencia={'modo':a.modo,'casos':[],'snapshot_telegram_antes_sha256':huella(antes)}
    for paquete in data['paquetes']:
        eid=paquete['ejecucion_id']
        fila={'caso':paquete['caso'],'ensayo_id':paquete['ensayo_id'],'ejecucion_id':eid}
        if a.modo=='registrar':
            fila['acuse']=db.rpc('ra_registrar_ensayo_priorizacion_v2',dict(
                p_usuario_id=paquete['revision']['usuario_id'],p_paquete=paquete,p_motivo=data['motivo'])).execute().data
        elif a.modo=='procesar':
            fila['acuse']=procesar_priorizacion(eid,db,'ensayo-v2:'+eid)
        else:
            incidentes=db.rpc('ra_incidentes_contexto_v2',{'p_ejecucion_id':eid}).execute().data
            ev=[i.get('evaluacion_necesidad') for i in incidentes]
            if len(ev)!=6 or not all(ev):raise RuntimeError('Aún no hay seis evaluaciones persistidas')
            fila['evaluaciones']=ev
            pendientes=[n for n in ev if n['estado_prioridad']=='pendiente']
            if paquete['caso']=='calculable':
                assert not pendientes and sum(n['demanda_litros'] for n in ev)==15000
            else:
                assert len(pendientes)==1
                n=pendientes[0]
                assert n['demanda_litros'] is None and n['puntaje'] is None and n['posicion'] is None and n['requiere_revision_urgente']
            fila['resultado']='aprobado'
        evidencia['casos'].append(fila)
    despues=db.rpc('ra_incidentes_snapshot_v2',{}).execute().data
    evidencia['snapshot_telegram_despues_sha256']=huella(despues)
    evidencia['snapshot_telegram_intacto']=antes==despues
    with open(a.evidencia,'x',encoding='utf-8') as f:json.dump(evidencia,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'modo':a.modo,'casos':len(evidencia['casos']),'snapshot_telegram_intacto':antes==despues}))
    if antes!=despues:raise SystemExit('Snapshot ciudadano cambió; revisar posible actividad concurrente.')


if __name__=='__main__':main()
