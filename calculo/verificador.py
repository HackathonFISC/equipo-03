"""Verificación independiente: aritmética sobre snapshot y propuesta, sin OR-Tools."""
import hashlib
import json
from decimal import Decimal

from pydantic import ValidationError

from contratos.modelos import InformeVerificacion, PropuestaDistribucion
from contratos.solicitudes import SolicitudResolverRutas, SolicitudVerificarPlan

COMPROBACIONES = ['capacidad', 'horarios', 'ventanas', 'retorno', 'asignacion_unica',
                 'demanda_completa', 'version_entradas', 'cobertura_critica']


def _duracion_microsegundos(delta):
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def verify_plan(entrada: SolicitudVerificarPlan) -> InformeVerificacion:
    """No confía en verificación adjunta, estado aprobado ni ayudas del solver.

    La versión de datos por sí sola no detecta cambios bajo una etiqueta reutilizada;
    comprueba además la huella del snapshot completo emitida en supuestos.
    """
    s = SolicitudResolverRutas.model_validate(entrada.solicitud_original.model_dump(mode='json'))
    p = entrada.propuesta
    violaciones = []

    def fallo(codigo, detalle, referencia=None):
        item = dict(codigo=codigo, detalle=detalle, referencia_id=referencia)
        if item not in violaciones:
            violaciones.append(item)

    def informe(comprobaciones):
        return InformeVerificacion(esquema_version=s.esquema_version, ejecucion_id=s.ejecucion_id,
            creado_en=entrada.creado_en, origen=s.origen, plan_id=s.plan_id, version=s.version,
            datos_version=s.datos_version, politica_version=s.politica.politica_version,
            valido=not violaciones, violaciones=violaciones, comprobaciones=comprobaciones)

    try:
        p = PropuestaDistribucion.model_validate(p.model_dump(mode='json'))
    except ValidationError as error:
        # Defensa ante model_copy/model_construct o listas modificadas tras validar.
        for e in error.errors(include_input=False, include_url=False):
            mensaje = e['msg']
            codigo = 'asignacion' if any(t in mensaje for t in ('repetid', 'dividid', 'pendiente a la vez', 'salida por vehículo')) else 'otro'
            if any(t in mensaje for t in ('versión', 'ejecución')):
                codigo = 'version'
            fallo(codigo, 'Propuesta fuera del contrato: ' + mensaje[:3500])
        return informe([])
    if (p.plan_id, p.version, p.datos_version, p.politica_version, p.ejecucion_id, p.origen) != (
            s.plan_id, s.version, s.datos_version, s.politica.politica_version, s.ejecucion_id, s.origen):
        fallo('version', 'Propuesta y snapshot no comparten plan, versiones, ejecución u origen.')
    if entrada.ejecucion_id != s.ejecucion_id or entrada.origen != s.origen:
        fallo('version', 'El contexto de verificación no corresponde al snapshot.')
    esperada = hashlib.sha256(json.dumps(s.model_dump(mode='json'), ensure_ascii=False,
                                        sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    huellas = [v for v in p.supuestos if v.startswith('HUELLA_ENTRADAS_SHA256=')]
    if huellas != ['HUELLA_ENTRADAS_SHA256=' + esperada]:
        fallo('version', 'Falta huella única del snapshot o cambiaron entradas aun conservando etiquetas de versión.')
    if s.politica.estado != 'activa':
        fallo('version', 'La política del snapshot no está activa.')
    if p.estado_solver != 'factible':
        fallo('otro', 'No hay propuesta factible del solver; el diagnóstico no autoriza un plan.')
    vehiculos = {v.vehiculo_id: v for v in s.vehiculos}
    necesidades = {n.punto_atencion_id: n for n in s.necesidades}
    servicios = {d.punto_atencion_id: d.descarga_minutos for d in s.servicios}
    indices = {pid: i for i, pid in enumerate(s.matriz.nodos_ids)}
    atendidos, pendientes, ids_paradas, usados = set(), set(), set(), set()

    def viaje(a, b):
        if a not in indices or b not in indices:
            return None
        return s.matriz.minutos[indices[a]][indices[b]]

    for ruta in p.rutas:
        vid = ruta.vehiculo_id
        vehiculo = vehiculos.get(vid)
        if vid in usados:
            fallo('asignacion', 'Más de una salida para el mismo vehículo.', vid)
        usados.add(vid)
        if vehiculo is None or not vehiculo.disponible:
            fallo('asignacion', 'Vehículo desconocido o no disponible.', vid)
        if ruta.deposito_id != s.deposito.deposito_id:
            fallo('asignacion', 'La ruta usa otro depósito.', vid)
        if vehiculo and (ruta.salida_estimada < vehiculo.turno.inicio or ruta.retorno_estimado > vehiculo.turno.fin):
            fallo('horario', 'Salida o retorno fuera del turno.', vid)
        anterior, reloj, carga = s.deposito.deposito_id, ruta.salida_estimada, Decimal(0)
        for orden, parada in enumerate(ruta.paradas, 1):
            pid = parada.punto_atencion_id
            n = necesidades.get(pid)
            if pid in atendidos or parada.parada_id in ids_paradas or parada.orden != orden:
                fallo('asignacion', 'Punto/identificador duplicado u orden incorrecto.', pid)
            atendidos.add(pid)
            ids_paradas.add(parada.parada_id)
            carga += Decimal(str(parada.litros_asignados))
            if n is None:
                fallo('asignacion', 'Punto ajeno al snapshot.', pid)
            else:
                if parada.incidente_id != n.incidente_id:
                    fallo('asignacion', 'Incidente distinto del asociado al punto.', pid)
                if (n.estado_demanda != 'validada' or n.estado_prioridad != 'calculada'
                        or n.demanda_litros is None or n.demanda_litros <= 0
                        or Decimal(str(parada.litros_asignados)) != Decimal(str(n.demanda_litros))):
                    fallo('demanda', 'La entrega no coincide con demanda positiva validada e indivisible y prioridad calculada.', pid)
                if n.ventana_atencion is None or parada.inicio_descarga < n.ventana_atencion.inicio or parada.fin_descarga > n.ventana_atencion.fin:
                    fallo('ventana', 'Descarga fuera de la ventana o ventana desconocida.', pid)
            minutos = viaje(anterior, pid)
            if minutos is None:
                fallo('horario', 'Tramo de viaje desconocido o bloqueado en la matriz.', pid)
            elif _duracion_microsegundos(parada.llegada_estimada - reloj) != minutos * 60_000_000:
                fallo('horario', 'Llegada incompatible con viaje desde salida o descarga anterior.', pid)
            if parada.inicio_descarga < parada.llegada_estimada:
                fallo('horario', 'La descarga comienza antes de llegar.', pid)
            if pid in servicios and _duracion_microsegundos(parada.fin_descarga - parada.inicio_descarga) != servicios[pid] * 60_000_000:
                fallo('horario', 'Duración de descarga distinta del servicio acordado.', pid)
            if parada.estado != 'programada':
                fallo('asignacion', 'Una propuesta no acredita entrega física ni inicio del servicio.', pid)
            anterior, reloj = pid, parada.fin_descarga
        if vehiculo and carga > Decimal(str(vehiculo.capacidad_litros)):
            fallo('capacidad', 'Carga total de la ruta superior a capacidad de la cisterna.', vid)
        regreso = viaje(anterior, s.deposito.deposito_id)
        if regreso is None or _duracion_microsegundos(ruta.retorno_estimado - reloj) != regreso * 60_000_000:
            fallo('retorno', 'Retorno incompatible con el viaje desde la última parada o arco bloqueado.', vid)
    for pendiente in p.no_atendidos:
        pid = pendiente.punto_atencion_id
        n = necesidades.get(pid)
        if pid in pendientes or pid in atendidos:
            fallo('asignacion', 'Punto pendiente duplicado o también atendido.', pid)
        pendientes.add(pid)
        if n is None:
            fallo('asignacion', 'Punto pendiente ajeno al snapshot.', pid)
        elif (pendiente.incidente_id != n.incidente_id or pendiente.clase_prioridad != n.clase_prioridad
              or pendiente.demanda_pendiente_litros != n.demanda_litros):
            fallo('demanda', 'Pendiente con identidad, clase o litros distintos del snapshot.', pid)
    if atendidos | pendientes != set(necesidades):
        fallo('asignacion', 'El plan debe contabilizar todos los puntos, atendidos o pendientes, sin añadir otros.')
    for pid, n in necesidades.items():
        if pid not in atendidos and ((n.clase_prioridad == 'critico' and n.demanda_litros != 0)
                or (n.requiere_revision_urgente and n.estado_prioridad == 'pendiente')):
            fallo('cobertura_critica', 'Crítico o posible urgencia sin cubrir: escalar; no aprobar publicación.', pid)
    return informe(COMPROBACIONES)
