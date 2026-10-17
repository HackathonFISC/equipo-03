"""Soporte de integración local 0016; fixtures explícitos, nunca reportes reales."""
import json
import sys
from agentes.ensayo_priorizacion_v2 import preparar_paquetes
from agentes.ingesta import interpretar_reporte, reconstruir_reporte
from agentes.territorial import resolver_reporte
from agentes.priorizacion import evaluar_lote, HerramientasJose
from agentes.puente_necesidades import infraestructura_ensayo, construir_solicitud
from agentes.planificacion import planificar, DecisorReglas
from contratos.modelos import ExtraccionReporteLLM


def ejecutar(datos):
    accion=datos['accion']
    if accion=='fixture':
        paquete=preparar_paquetes(datos['usuario_id'],'FIXTURE: prueba local de procedencia, no datos reales')[0]
        return dict(paquete=paquete,infraestructura=infraestructura_ensayo())
    if accion=='ingesta':
        r=reconstruir_reporte(datos['toma'])
        class Simulado:
            def extraer(self,texto):
                return ExtraccionReporteLLM(resumen='FIXTURE: reporte controlado de agua',ubicacion_declarada=datos['nombre'],
                    campos=dict(horas_sin_agua=datos['horas'],personas_afectadas=datos['personas'],tipo_problema='sin_suministro'),
                    evidencia_textual=[texto],faltantes=[],requiere_aclaracion=False,fuera_de_alcance=False)
        salida=interpretar_reporte(r,Simulado(),intento_ref='integracion-a1-simulado')
        return dict(resultado=salida.reporte.model_dump(mode='json'),evento=salida.evento.model_dump(mode='json'))
    if accion=='territorial': return resolver_reporte(datos['toma'])
    if accion=='priorizacion':
        t=datos['toma']; e=t['ejecucion'];validaciones={}
        resultado=evaluar_lote(dict(esquema_version='1.0',ejecucion_id=e['ejecucion_id'],creado_en=e['creado_en'],origen=e['origen']),
            t['lote_calculo']['entradas'],t['lote_calculo']['politica'],HerramientasJose(),validaciones=validaciones)
        return dict(resultado=resultado.model_dump(mode='json'),validaciones=validaciones)
    if accion=='puente':return construir_solicitud(datos['snapshot'])
    if accion=='planificacion':return planificar(datos['solicitud'],decisor=DecisorReglas()).model_dump(mode='json')
    raise ValueError('Acción de ensayo desconocida')


if __name__=='__main__':
    print(json.dumps(ejecutar(json.load(sys.stdin)),ensure_ascii=False))
