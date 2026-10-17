"""Agente Planificación V3; solver y verificación independientes son herramientas."""
import hashlib
import json
from typing import Literal
from time import perf_counter
from pydantic import BaseModel, ConfigDict, Field
from contratos.modelos import PropuestaDistribucion, InformeVerificacion
from contratos.errores import ExcepcionContrato
from contratos.solicitudes import SolicitudResolverRutas, SolicitudVerificarPlan

BLOQUEO_ENSAYO = 'ENSAYO SINTÉTICO: sin aprobación operativa ni publicación comunitaria.'


class DecisionPlanificacion(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    accion: Literal['calcular', 'presentar_revision', 'solicitar_revision']
    motivo: str = Field(min_length=1, max_length=4000)


class ResultadoPlanificacion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    estado: Literal['espera_validacion', 'espera_revision']
    propuesta: PropuestaDistribucion | None
    informe: InformeVerificacion | None
    trazas: list[dict]


def huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


class HerramientasPlanificacion:
    def solve_routes(self, solicitud):
        from calculo.solver import solve_routes
        return solve_routes(solicitud)

    def verify_plan(self, solicitud):
        from calculo.verificador import verify_plan
        return verify_plan(solicitud)


class DecisorReglas:
    """Modo explícito para ensayos sin red; no se registra como llamada a IA."""
    modo = 'reglas'

    def decidir(self, contexto):
        if contexto['fase'] == 'preparacion':
            return DecisionPlanificacion(accion='calcular', motivo='Escenario recibido; consultar solver y verificador sin alterar restricciones.')
        accion = 'presentar_revision' if contexto['verificacion_valida'] else 'solicitar_revision'
        return DecisionPlanificacion(accion=accion, motivo='Resultado sujeto al verificador independiente y a revisión humana.')


def planificar(solicitud, herramientas=None, decisor=None):
    """No modifica entradas. Ninguna decisión LLM cambia restricciones ni aprueba."""
    datos = solicitud.model_dump(mode='json') if isinstance(solicitud, BaseModel) else solicitud
    s = SolicitudResolverRutas.model_validate(datos)
    if s.origen != 'sintetico':
        raise ValueError('V3 integrada en esta entrega solo admite ensayos sintéticos separados')
    original = s.model_dump(mode='json')
    herramientas = herramientas or HerramientasPlanificacion()
    decisor = decisor or DecisorReglas()
    trazas = []

    def registrar(decision, herramienta=None, **detalles):
        trazas.append(dict(agente='planificacion', decision=decision,
                          herramienta=herramienta, **detalles))

    def decidir(contexto, permitidas):
        inicio = perf_counter()
        try:
            recibida = decisor.decidir(contexto)
            d = DecisionPlanificacion.model_validate(recibida.model_dump(mode='json') if isinstance(recibida, BaseModel) else recibida)
            if d.accion not in permitidas:
                raise ValueError('Acción fuera de fase')
            registrar(d.motivo, 'decidir_planificacion', accion=d.accion,
                      modo=getattr(decisor, 'modo', 'externo'), duracion_ms=round((perf_counter()-inicio)*1000))
            return d
        except Exception:
            # Nunca incluir errores crudos del proveedor (pueden contener datos o claves).
            registrar('Decisor no disponible o salida inválida; revisión sin reintento automático.',
                      'decidir_planificacion', modo=getattr(decisor, 'modo', 'externo'))
            return None

    resumen = dict(fase='preparacion', datos_version=s.datos_version,
                   puntos=len(s.puntos), vehiculos_disponibles=sum(v.disponible for v in s.vehiculos),
                   necesidades_totales=len(s.necesidades),
                   necesidades_sin_datos_para_ranking=sum(n.estado_prioridad != 'calculada' for n in s.necesidades),
                   criticos_confirmados=sum(n.clase_prioridad == 'critico' and n.confirmacion_clase is not None for n in s.necesidades),
                   politica_activa=s.politica.estado == 'activa',
                   insumos_validos_por_contrato=True,
                   origen=s.origen.value)
    decision = decidir(resumen, {'calcular', 'solicitar_revision'})
    if decision is None or decision.accion == 'solicitar_revision':
        return ResultadoPlanificacion(estado='espera_revision', propuesta=None, informe=None, trazas=trazas)
    try:
        argumento = SolicitudResolverRutas.model_validate(original)
        inicio = perf_counter()
        recibida = herramientas.solve_routes(argumento)
        p = PropuestaDistribucion.model_validate(recibida.model_dump(mode='json') if isinstance(recibida, BaseModel) else recibida)
        if argumento.model_dump(mode='json') != original:
            raise ValueError('Solver mutó la solicitud')
        if (p.ejecucion_id, p.plan_id, p.version, p.datos_version, p.politica_version, p.origen) != (
                s.ejecucion_id, s.plan_id, s.version, s.datos_version, s.politica.politica_version, s.origen):
            raise ValueError('Solver devolvió otro contexto')
        if p.estado != 'pendiente_revision' or p.aprobacion is not None:
            raise ValueError('Herramienta intentó aprobar o cambiar estado')
        # Ignorar cualquier informe adjunto; siempre volver a verificar el contenido.
        datos = p.model_dump(mode='json'); datos['verificacion'] = None
        p = PropuestaDistribucion.model_validate(datos)
        registrar('Propuesta calculada; requiere verificación independiente.', 'solve_routes',
                  estado_solver=p.estado_solver.value, solicitud_sha256=huella(original),
                  duracion_ms=round((perf_counter()-inicio)*1000))
        verificacion = SolicitudVerificarPlan(esquema_version=s.esquema_version,
            ejecucion_id=s.ejecucion_id, creado_en=s.creado_en, origen=s.origen,
            solicitud_original=SolicitudResolverRutas.model_validate(original),
            propuesta=PropuestaDistribucion.model_validate(p.model_dump(mode='json')))
        antes = verificacion.model_dump(mode='json')
        inicio = perf_counter()
        recibido = herramientas.verify_plan(verificacion)
        informe = InformeVerificacion.model_validate(recibido.model_dump(mode='json') if isinstance(recibido, BaseModel) else recibido)
        if verificacion.model_dump(mode='json') != antes:
            raise ValueError('Verificador mutó entradas')
        if (informe.ejecucion_id, informe.plan_id, informe.version, informe.datos_version,
            informe.politica_version, informe.origen) != (
                s.ejecucion_id, s.plan_id, s.version, s.datos_version, s.politica.politica_version, s.origen):
            raise ValueError('Informe de otra versión')
        registrar('Verificación independiente ejecutada.', 'verify_plan',
                  valido=informe.valido, violaciones=[v.codigo for v in informe.violaciones],
                  duracion_ms=round((perf_counter()-inicio)*1000))
    except ExcepcionContrato as exc:
        registrar(exc.detalle.mensaje, 'herramientas_planificacion', codigo=exc.detalle.codigo.value, campos=exc.detalle.campos)
        return ResultadoPlanificacion(estado='espera_revision', propuesta=None, informe=None, trazas=trazas)
    except Exception:
        registrar('Fallo de herramienta o contrato; revisar sin alterar datos ni reintentar automáticamente.',
                  'herramientas_planificacion')
        return ResultadoPlanificacion(estado='espera_revision', propuesta=None, informe=None, trazas=trazas)

    decision = decidir(dict(fase='resultado', verificacion_valida=informe.valido,
                           estado_solver=p.estado_solver.value, puntos_atendidos=sum(len(r.paradas) for r in p.rutas),
                           puntos_pendientes=len(p.no_atendidos),
                           violaciones=[v.codigo for v in informe.violaciones]),
                       {'presentar_revision', 'solicitar_revision'})
    estado = 'espera_validacion' if (decision is not None and decision.accion == 'presentar_revision'
              and informe.valido and p.estado_solver == 'factible') else 'espera_revision'
    datos = p.model_dump(mode='json'); datos['verificacion'] = informe.model_dump(mode='json')
    datos['bloqueos_publicacion'] = list(dict.fromkeys([*datos['bloqueos_publicacion'], BLOQUEO_ENSAYO]))
    if not informe.valido:
        datos['bloqueos_publicacion'].append('Verificación inválida; corregir y crear una nueva versión.')
    p = PropuestaDistribucion.model_validate(datos)
    registrar('Esperar revisión humana; no aprobar ni comunicar el plan.', siguiente_estado=estado)
    return ResultadoPlanificacion(estado=estado, propuesta=p, informe=informe, trazas=trazas)


def procesar_planificacion(ejecucion_id, db, trabajador_id, herramientas=None, decisor=None):
    toma = db.rpc('ra_tomar_planificacion_v3', dict(p_ejecucion_id=str(ejecucion_id),
                                                  p_trabajador_id=trabajador_id)).execute().data
    if toma is None:
        return {'estado': 'no_tomada'}
    resultado = planificar(toma['solicitud'], herramientas, decisor)
    return db.rpc('ra_finalizar_planificacion_v3', dict(p_ejecucion_id=str(ejecucion_id),
        p_trabajador_id=trabajador_id, p_snapshot=toma,
        p_resultado=resultado.model_dump(mode='json'))).execute().data
