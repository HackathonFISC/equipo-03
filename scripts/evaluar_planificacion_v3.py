"""15 evals reproducibles del agente V3; sin red, Supabase ni autorización operativa."""
import argparse
import json
from datetime import datetime, timedelta, timezone
from time import perf_counter
from agentes.escenario_v3 import preparar_escenario
from agentes.planificacion import planificar, HerramientasPlanificacion, DecisionPlanificacion


class DecisorSimulado:
    modo='simulado_eval'
    def __init__(self, accion=None, falla=False):
        self.accion=accion; self.falla=falla
    def decidir(self,c):
        if self.falla: raise RuntimeError('Proveedor simulado no disponible')
        return {'accion':self.accion or ('calcular' if c['fase']=='preparacion' else 'presentar_revision'),
                'motivo':'Decisión simulada explícita del eval'}


class InformeAjeno(HerramientasPlanificacion):
    def verify_plan(self,s):
        return super().verify_plan(s).model_copy(update={'version':s.propuesta.version+1})


class SolverMutante(HerramientasPlanificacion):
    def solve_routes(self,s):
        p=super().solve_routes(s); s.vehiculos[0].capacidad_litros=1
        return p


def ejecutar():
    base=preparar_escenario(escenario_id='d60b7afd-c6a5-4786-a989-f83ba30ae015')
    def demanda(d,clase,cantidad):
        next(n for n in d['necesidades'] if n['clase_prioridad']==clase)['demanda_litros']=cantidad
    def aislar(d):
        indice=next(i for i,n in enumerate(d['matriz']['nodos_ids']) if n==d['necesidades'][-1]['punto_atencion_id'])
        # Escoger explícitamente Vista Alegre (general) sin depender del orden del ranking.
        pid=next(p['punto_atencion_id'] for p in d['puntos'] if 'Vista Alegre' in p['nombre'])
        indice=d['matriz']['nodos_ids'].index(pid)
        for i in range(len(d['matriz']['minutos'])):
            if i!=indice:d['matriz']['minutos'][i][indice]=None;d['matriz']['minutos'][indice][i]=None
    def ventana(d):
        n=next(n for n in d['necesidades'] if n['clase_prioridad']=='critico')
        inicio=datetime.fromisoformat(n['ventana_atencion']['inicio'])
        n['ventana_atencion']['fin']=(inicio+timedelta(minutes=1)).isoformat()
    casos=[
      ('completo',lambda d:None,'espera_validacion',6,None,None),
      ('una_cisterna',lambda d:d['vehiculos'][1].update(disponible=False),'espera_validacion',4,None,None),
      ('sin_flota',lambda d:[v.update(disponible=False) for v in d['vehiculos']],'espera_revision',0,None,None),
      ('critico_excede_capacidad',lambda d:demanda(d,'critico',12000),'espera_revision',5,None,None),
      ('general_excede_capacidad',lambda d:demanda(d,'general',12000),'espera_validacion',5,None,None),
      ('general_sin_acceso',aislar,'espera_validacion',5,None,None),
      ('critico_ventana_insuficiente',ventana,'espera_revision',5,None,None),
      ('general_cero_validado',lambda d:demanda(d,'general',0),'espera_validacion',5,None,None),
      ('cantidad_negativa',lambda d:demanda(d,'general',-1),'contrato_rechazado',None,None,None),
      ('punto_duplicado',lambda d:d['puntos'].append(d['puntos'][0]),'contrato_rechazado',None,None,None),
      ('matriz_incompleta',lambda d:d['matriz']['nodos_ids'].pop(),'contrato_rechazado',None,None,None),
      ('llm_intenta_aprobar',lambda d:None,'espera_revision',None,None,DecisorSimulado('aprobar')),
      ('proveedor_no_disponible',lambda d:None,'espera_revision',None,None,DecisorSimulado(falla=True)),
      ('informe_otra_version',lambda d:None,'espera_revision',None,InformeAjeno(),None),
      ('solver_muta_entrada',lambda d:None,'espera_revision',None,SolverMutante(),None),
    ]
    resultados=[]
    for nombre,mutar,esperado,atendidos,tools,decisor in casos:
        d=base.model_dump(mode='json');mutar(d);inicio=perf_counter()
        try:
            r=planificar(d,tools,decisor)
            obtenido=r.estado
            cantidad=sum(len(x.paradas) for x in r.propuesta.rutas) if r.propuesta else None
            valido=bool(r.informe and r.informe.valido)
            sin_aprobar=r.propuesta is None or (r.propuesta.aprobacion is None and r.propuesta.estado=='pendiente_revision' and bool(r.propuesta.bloqueos_publicacion))
        except ValueError:
            obtenido='contrato_rechazado';cantidad=None;valido=False;sin_aprobar=True
        coincide=obtenido==esperado and (atendidos is None or cantidad==atendidos) and sin_aprobar
        resultados.append(dict(caso=nombre,esperado=esperado,obtenido=obtenido,
            atendidos_esperados=atendidos,atendidos_obtenidos=cantidad,verificacion_valida=valido,
            sin_aprobacion_automatica=sin_aprobar,coincide=coincide,
            decisor='simulado_eval' if decisor else 'reglas',
            duracion_ms=round((perf_counter()-inicio)*1000,3)))
    aprobados=sum(x['coincide'] for x in resultados)
    return dict(registrado_en=datetime.now(timezone.utc).isoformat(),origen='sintetico',
        alcance='15 evals locales V3: herramientas reales salvo fallos inyectados e identificados; no prueba LLM real ni concurrencia de servidores.',
        metricas=dict(casos=len(resultados),aprobados=aprobados,tasa_exito=aprobados/len(resultados),
            aprobaciones_indebidas=sum(not x['sin_aprobacion_automatica'] for x in resultados)),casos=resultados)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--salida',required=True);a=p.parse_args()
    r=ejecutar()
    with open(a.salida,'x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(r['metricas']))
    if r['metricas']['aprobados']!=r['metricas']['casos']:raise SystemExit(1)

if __name__=='__main__':main()
