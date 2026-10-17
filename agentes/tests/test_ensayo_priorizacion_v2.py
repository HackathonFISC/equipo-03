from agentes.ensayo_priorizacion_v2 import preparar_paquetes
from agentes.priorizacion import evaluar_lote, HerramientasJose


def test_dos_casos_con_funciones_reales_y_usuario_revisado():
    uid='00000000-0000-4000-8000-000000001001'
    paquetes=preparar_paquetes(uid,'Revisión sintética de prueba')
    resultados=[]
    for p in paquetes:
        f=p['lote']['entradas'][0]['solicitud_demanda']
        ctx={k:f[k] for k in ['esquema_version','ejecucion_id','creado_en','origen']}
        r=evaluar_lote(ctx,p['lote']['entradas'],p['lote']['politica'],HerramientasJose())
        resultados.append(r)
        assert all(n.confirmacion_clase.usuario_id.__str__()==uid for n in r.evaluaciones)
    assert sum(n.demanda_litros for n in resultados[0].evaluaciones)==15000
    assert all(n.estado_prioridad=='calculada' for n in resultados[0].evaluaciones)
    pendientes=[n for n in resultados[1].evaluaciones if n.estado_prioridad=='pendiente']
    assert len(pendientes)==1
    n=pendientes[0]
    assert n.demanda_litros is None and n.puntaje is None and n.posicion is None
    assert n.requiere_revision_urgente
    assert any('reserva_utilizable_litros' in x for x in n.pendientes)
    assert {x['solicitud_demanda']['incidente_id'] for x in paquetes[0]['lote']['entradas']}.isdisjoint(
        x['solicitud_demanda']['incidente_id'] for x in paquetes[1]['lote']['entradas'])
