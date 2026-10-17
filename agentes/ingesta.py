"""Ingesta V1 manual: contratos puros y adaptador de persistencia transaccional."""
import argparse
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4, uuid5

from pydantic import ValidationError

from contratos.errores import CodigoError, ErrorDominio
from contratos.estados import EstadoEjecucion
from contratos.modelos import Evidencia, EventoTraza, ExtraccionReporteLLM, ReporteInterpretado, ReporteRegistrado
from .gemini import ConfiguracionGemini, ErrorConfiguracionGemini, ErrorIngesta, ExtractorGemini
from .trazas import traza_ingesta
from .evidencia_textual import fragmento_original, cantidades_explicitas

MAX_REINTENTOS_INGESTA = 2


class Extractor(Protocol):
    def extraer(self, texto: str) -> ExtraccionReporteLLM: ...


@dataclass(frozen=True)
class ResultadoIngesta:
    reporte: ReporteInterpretado
    evento: EventoTraza
    siguiente_etapa: str


def interpretar_reporte(reporte: ReporteRegistrado, extractor: Extractor, *, intento_ref: str = 'manual', aclaraciones=()) -> ResultadoIngesta:
    """No persiste ni envía mensajes. Solo V1 texto; IDs y origen del backend."""
    reporte = ReporteRegistrado.model_validate(reporte.model_dump(mode='json'))
    if reporte.entrada.modalidad != 'texto':
        raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Ingesta V1 admite solo reportes de texto.')
    fuentes = [reporte.entrada.texto]
    fuentes += [a['respuesta_texto'] for a in aclaraciones if a.get('respuesta_texto')]
    texto = '\n\nRespuesta de aclaración:\n'.join(fuentes)
    inicio = time.monotonic()
    try:
        propuesta = extractor.extraer(texto)
        salida = ExtraccionReporteLLM.model_validate(propuesta.model_dump(mode='json'))
    except (ValidationError, AttributeError, TypeError):
        raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Extracción incompatible con el contrato.') from None
    citas = [fragmento_original(fragmento, fuentes) for fragmento in salida.evidencia_textual]
    if any(cita is None for cita in citas):
        raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'La evidencia citada no pertenece al texto original.')
    datos = salida.model_dump(mode='json')
    datos['evidencia_textual'] = citas
    for contenedor, campo in [(datos, 'ubicacion_declarada'), (datos['campos'], 'institucion_declarada'),
                              (datos['campos'], 'vulnerabilidad_declarada')]:
        valor = contenedor[campo]
        if valor is not None:
            original = fragmento_original(valor, fuentes)
            if original is None:
                raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Se declaró un dato textual que no está en el reporte.')
            contenedor[campo] = original
    horas, personas = cantidades_explicitas(fuentes)
    respaldos = {'horas_sin_agua': horas, 'personas_afectadas': personas}
    for campo, valores in respaldos.items():
        valor = datos['campos'][campo]
        coincide = any(math.isclose(valor, v, rel_tol=0, abs_tol=1e-9) for v in valores) if valor is not None else True
        if not coincide:
            datos['campos'][campo] = None
            if not datos['fuera_de_alcance']:
                datos['faltantes'] = list(dict.fromkeys([*datos['faltantes'], campo]))
                datos['requiere_aclaracion'] = True
    salida = ExtraccionReporteLLM.model_validate(datos)
    if salida.fuera_de_alcance and salida.requiere_aclaracion:
        raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Una entrada fuera de alcance no debe pedir aclaración de agua.')
    if not salida.fuera_de_alcance and not salida.evidencia_textual:
        raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Un reporte interpretado de agua requiere evidencia textual.')
    evidencia = Evidencia(
        evidencia_id=uuid5(reporte.reporte_id, 'texto_original'), reporte_id=reporte.reporte_id,
        tipo={'transcripcion_audio': 'audio', 'descripcion_imagen': 'foto'}.get(reporte.entrada.fuente_texto, 'texto'), referencia=f'reportes/{reporte.reporte_id}/texto',
        descripcion=('Descripción automática de foto y texto adjunto persistidos; no se conserva la foto original ni se verifican visualmente los hechos.'
                     if reporte.entrada.fuente_texto == 'descripcion_imagen' else
                     'Transcripción automática persistida; citas cotejadas contra la transcripción, no contra el audio original.'
                     if reporte.entrada.fuente_texto == 'transcripcion_audio' else
                     'Texto original persistido; las citas se cotejaron ignorando solo acentos, mayúsculas y espacios, conservando el fragmento original.'),
        campos_respaldados=['entrada.texto'],
    )
    evidencias = [evidencia]
    ubicacion_compartida = reporte.entrada.ubicacion_compartida
    for aclaracion in aclaraciones:
        tipo = ('ubicacion' if aclaracion.get('respuesta_ubicacion') else
                {'transcripcion_audio': 'audio', 'descripcion_imagen': 'foto'}.get(aclaracion.get('respuesta_fuente_texto'), 'texto'))
        evidencias.append(Evidencia(evidencia_id=uuid5(reporte.reporte_id, 'aclaracion:' + str(aclaracion['aclaracion_id'])),
            reporte_id=reporte.reporte_id, tipo=tipo, referencia='aclaraciones/' + str(aclaracion['aclaracion_id']),
            descripcion=('Descripción automática de foto y texto adjunto en respuesta; identidad y pregunta verificadas; no se conserva la foto original.'
                         if tipo == 'foto' else 'Transcripción automática de respuesta de audio; identidad y pregunta verificadas; no se conserva el audio original.'
                         if tipo == 'audio' else 'Respuesta aceptada con identidad y pregunta verificadas; se conserva separada del texto original.'),
            campos_respaldados=['ubicacion_compartida' if tipo == 'ubicacion' else 'interpretacion']))
        if tipo == 'ubicacion':
            from contratos.modelos import Ubicacion
            ubicacion_compartida = Ubicacion.model_validate(aclaracion['respuesta_ubicacion'])
    if ubicacion_compartida is not None and salida.requiere_aclaracion and salida.faltantes:
        faltantes = [f for f in salida.faltantes
                     if not re.search(r'ubicaci|lugar|direcci|sector|punto', f, re.I)]
        salida = salida.model_copy(update={'requiere_aclaracion': bool(faltantes), 'faltantes': faltantes})
    interpretado = ReporteInterpretado(
        esquema_version=reporte.esquema_version, ejecucion_id=reporte.ejecucion_id,
        creado_en=datetime.now(timezone.utc), origen=reporte.origen, reporte_id=reporte.reporte_id,
        modalidad='texto', interpretacion=salida, evidencias=evidencias,
        ubicacion_compartida=ubicacion_compartida,
    )
    if salida.fuera_de_alcance:
        estado, etapa, decision = EstadoEjecucion.COMPLETADA, 'terminada', 'Cerrar entrada fuera del alcance de agua.'
    elif salida.requiere_aclaracion:
        estado, etapa, decision = EstadoEjecucion.ESPERA_ACLARACION, 'ingesta', 'Pausar para aclarar datos del reporte.'
    else:
        estado, etapa, decision = EstadoEjecucion.PENDIENTE, 'territorial', 'Entregar interpretación a Territorial.'
    evento = traza_ingesta(reporte, intento_ref=intento_ref, siguiente_estado=estado,
                          duracion_ms=round((time.monotonic()-inicio)*1000), decision=decision,
                          resultado='Extracción validada y citas cotejadas; no se autorizó distribución.')
    return ResultadoIngesta(interpretado, evento, etapa)


class PersistenciaIngesta:
    def __init__(self, db):
        self.db = db

    def tomar(self, ejecucion_id: UUID, trabajador_id: str):
        return self.db.rpc('ra_tomar_ingesta', {'p_ejecucion_id': str(ejecucion_id),
                                             'p_trabajador_id': trabajador_id}).execute().data

    def finalizar(self, *, ejecucion_id, trabajador_id, snapshot, resultado=None, evento=None, error=None):
        return self.db.rpc('ra_finalizar_ingesta', {
            'p_ejecucion_id': str(ejecucion_id), 'p_trabajador_id': trabajador_id,
            'p_reporte_snapshot': snapshot,
            'p_resultado': resultado.model_dump(mode='json') if resultado else None,
            'p_evento': evento.model_dump(mode='json'),
            'p_error': error.model_dump(mode='json') if error else None,
        }).execute().data


def reconstruir_reporte(filas: dict) -> ReporteRegistrado:
    e, r = filas['ejecucion'], filas['reporte']
    if e['reporte_id'] != r['reporte_id'] or e['origen'] != r['origen']:
        raise ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Reporte y ejecución no comparten referencia y origen.')
    return ReporteRegistrado.model_validate({
        'esquema_version': r['esquema_version'], 'ejecucion_id': e['ejecucion_id'],
        'creado_en': r['creado_en'], 'origen': r['origen'], 'reporte_id': r['reporte_id'],
        'entrada': {**{k: r.get(k) for k in ('canal', 'mensaje_externo_id', 'remitente_ref', 'modalidad', 'texto', 'ubicacion_compartida')},
                    'fuente_texto': r.get('fuente_texto', 'escrito')},
    })


def procesar_ejecucion(ejecucion_id: UUID, persistencia: PersistenciaIngesta, extractor: Extractor, *, trabajador_id=None) -> dict:
    trabajador_id = trabajador_id or f'ingesta:{uuid4()}'
    filas = persistencia.tomar(ejecucion_id, trabajador_id)
    if filas is None:
        return {'estado': 'no_tomada', 'ejecucion_id': str(ejecucion_id)}
    inicio = time.monotonic()
    r = filas['reporte']
    # Este contexto permite registrar un error de entrada aunque falle su contrato.
    contexto = dict(esquema_version='1.0', ejecucion_id=ejecucion_id,
                    creado_en=datetime.now(timezone.utc), origen=r['origen'])
    try:
        reporte = reconstruir_reporte(filas)
        resultado = interpretar_reporte(reporte, extractor, intento_ref=trabajador_id, aclaraciones=filas.get('aclaraciones', []))
    except (ErrorIngesta, ValidationError) as error:
        fallo = error if isinstance(error, ErrorIngesta) else ErrorIngesta(CodigoError.CONTRATO_INVALIDO, 'Reporte persistido incompatible con el contrato.')
        detalle = ErrorDominio(**contexto, codigo=fallo.codigo, mensaje=str(fallo), recuperable=fallo.recuperable, campos=fallo.campos)
        if fallo.recuperable:
            estado_error = ('espera_revision' if isinstance(fallo, ErrorConfiguracionGemini)
                            or filas['ejecucion'].get('reintentos_ingesta', 0) >= MAX_REINTENTOS_INGESTA
                            else 'espera_validacion')
        else:
            estado_error = 'fallida'
        decision = ('Esperar reintento acotado del proveedor.' if estado_error == 'espera_validacion'
                    else 'Dejar Ingesta en revisión.' if estado_error == 'espera_revision'
                    else 'Detener Ingesta y registrar error controlado.')
        evento = EventoTraza(**contexto, evento_id=uuid5(ejecucion_id, f'ingesta:{trabajador_id}'),
                            agente='ingesta', decision=decision,
                            herramienta='gemini.generateContent', entrada_ids=[r['reporte_id']], salida_ids=[],
                            resultado=str(fallo), duracion_ms=round((time.monotonic()-inicio)*1000), siguiente_estado=estado_error)
        return persistencia.finalizar(ejecucion_id=ejecucion_id, trabajador_id=trabajador_id,
                                     snapshot=r, evento=evento, error=detalle)
    # Un fallo de persistencia no se convierte en error del LLM ni se reintenta
    # ciegamente: la RPC pudo haber confirmado antes de perderse la respuesta.
    return persistencia.finalizar(ejecucion_id=ejecucion_id, trabajador_id=trabajador_id,
                                 snapshot=r, resultado=resultado.reporte, evento=resultado.evento)


def main():
    parser = argparse.ArgumentParser(description='Ejecutar Ingesta V1 para un reporte de texto.')
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('--ejecucion-id', type=UUID, help='Procesar y persistir una ejecución pendiente concreta.')
    grupo.add_argument('--reporte-json', type=Path, help='ReporteRegistrado local: llama a Gemini sin usar BD.')
    parser.add_argument('--salida', type=Path, help='Guardar resultado local, sin claves; solo con --reporte-json.')
    args = parser.parse_args()
    if args.salida and not args.reporte_json:
        parser.error('--salida solo se permite con --reporte-json')
    try:
        extractor = ExtractorGemini(ConfiguracionGemini.cargar())
        extractor.verificar_modelo()
        if args.reporte_json:
            reporte = ReporteRegistrado.model_validate_json(args.reporte_json.read_text())
            resultado = interpretar_reporte(reporte, extractor)
            if args.salida:
                args.salida.write_text(json.dumps({'reporte': resultado.reporte.model_dump(mode='json'),
                                                 'evento': resultado.evento.model_dump(mode='json'),
                                                 'siguiente_etapa': resultado.siguiente_etapa}, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps({'estado': 'ok', 'modo': 'sin_bd', 'siguiente_estado': resultado.evento.siguiente_estado.value,
                              'siguiente_etapa': resultado.siguiente_etapa}, ensure_ascii=False))
            return 0
        from comun.db import get_supabase
        resultado = procesar_ejecucion(args.ejecucion_id, PersistenciaIngesta(get_supabase()), extractor)
        print(json.dumps(resultado, ensure_ascii=False))
        return 1 if resultado.get('estado') == 'fallida' else 0
    except ErrorIngesta as error:
        print(json.dumps({'estado': 'error', 'codigo': error.codigo.value, 'mensaje': str(error)}, ensure_ascii=False))
    except Exception:
        # No imprimir excepciones crudas del SDK, URLs, entrada ni claves.
        print(json.dumps({'estado': 'error', 'mensaje': 'No se completó Ingesta. Revisa configuración, migración 0005, entrada y estado de ejecución; no reintentes un cierre sin comprobar su resultado.'}, ensure_ascii=False))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
