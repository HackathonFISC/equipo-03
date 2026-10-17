"""Trabajador V2/V3/V4. Ejecutar --una-vuelta primero; Ctrl+C detiene el sondeo."""
import argparse
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
import time
from pathlib import Path
from uuid import UUID
from agentes.gemini import ConfiguracionGemini, ErrorConfiguracionGemini, ErrorIngesta, ExtractorGemini
from comun.db import get_supabase
from .flujo import avanzar
from agentes.puente_necesidades import preparar_puentes

logger = logging.getLogger('rutaagua.agentes')


def registrar_excepcion(mensaje, error):
    # El mensaje de un SDK puede contener URLs, credenciales o texto ciudadano.
    logger.exception(mensaje, exc_info=(type(error), RuntimeError('Detalle omitido por privacidad'), error.__traceback__))


def una_vuelta(db, extractor, herramientas=None, limite=20, *, planificacion_id=None, detener=None):
    if detener is not None and detener():
        return []
    if planificacion_id is None:
        db.rpc('ra_mantenimiento_v2', {}).execute()
        preparar_puentes(db, limite)
    else:
        db.rpc('ra_mantenimiento_planificacion_v3', {'p_ejecucion_id': str(planificacion_id)}).execute()
    consulta = db.table('ejecuciones').select('ejecucion_id,etapa').eq('estado', 'pendiente').in_(
        'etapa', ['ingesta', 'territorial', 'priorizacion', 'planificacion', 'comunicacion'])
    if planificacion_id is not None:
        consulta = consulta.eq('ejecucion_id', str(planificacion_id)).eq('etapa', 'planificacion')
    filas = consulta.order('creado_en').limit(limite).execute().data
    resultados = []
    for fila in filas:
        if detener is not None and detener():
            break
        trabajador_id = f"{fila['etapa']}:{uuid4()}"
        try:
            resultados.append(avanzar(fila, db, extractor, herramientas, trabajador_id=trabajador_id))
        except Exception as error:
            registrar_excepcion('Error al procesar una ejecución; revisar su reserva.', error)
            try:
                db.rpc('ra_marcar_error_trabajador', dict(p_ejecucion_id=fila['ejecucion_id'],
                    p_trabajador_id=trabajador_id)).execute()
            except Exception as cierre_error:
                registrar_excepcion('No se confirmó la marca de revisión; el mantenimiento vencerá la reserva.', cierre_error)
            # No repetir una llamada incierta; su reserva vencida pasa a revisión.
            resultados.append({'estado': 'requiere_revision', 'ejecucion_id': fila['ejecucion_id']})
    return resultados


def ejecutar_bucle(vuelta, *, detener, intervalo=5, una_sola=False, max_fallos=5,
                   esperar=time.sleep, monotono=time.monotonic, archivo_salud=None):
    """Reintenta la selección/mantenimiento; nunca reenvía una etapa reservada."""
    fallos = 0
    while not detener():
        try:
            resultados = vuelta()
            if archivo_salud is not None:
                temporal = archivo_salud.with_suffix('.tmp')
                temporal.write_text(json.dumps({'ultima_vuelta_exitosa': datetime.now(timezone.utc).isoformat()}))
                temporal.replace(archivo_salud)
            print(json.dumps({'resultados': resultados}, ensure_ascii=False), flush=True)
            fallos = 0
            demora = intervalo
        except ErrorConfiguracionGemini as error:
            print(json.dumps({'estado': 'error_configuracion_proveedor', 'mensaje': str(error)}, ensure_ascii=False))
            return 1
        except Exception as error:
            registrar_excepcion('Falló la vuelta del trabajador.', error)
            fallos += 1
            if una_sola or fallos >= max_fallos:
                return 1
            demora = min(60, intervalo * 2 ** (fallos - 1))
        else:
            if una_sola:
                return 0
        limite = monotono() + demora
        while not detener() and monotono() < limite:
            esperar(min(.2, max(0, limite - monotono())))
    return 0


def main():
    parser = argparse.ArgumentParser(description='Trabajador H2Oeste V2/V3/V4')
    parser.add_argument('--una-vuelta', action='store_true')
    parser.add_argument('--planificacion-id', type=UUID, help='Procesar solo este ensayo V3, sin mantenimiento global de V2')
    parser.add_argument('--intervalo', type=float, default=5)
    parser.add_argument('--archivo-parada', type=Path, help='Señal de cierre del proceso que administra el trabajador')
    parser.add_argument('--archivo-salud', type=Path, help='Última vuelta completada, sin datos ciudadanos')
    parser.add_argument('--max-fallos', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.max_fallos <= 20:
        parser.error('--max-fallos debe estar entre 1 y 20')
    if not 1 <= args.intervalo <= 60:
        parser.error('--intervalo debe estar entre 1 y 60 segundos')
    try:
        extractor = ExtractorGemini(ConfiguracionGemini.cargar())
        db = get_supabase()
        detener = lambda: args.archivo_parada is not None and args.archivo_parada.exists()
        verificado = False
        def vuelta():
            nonlocal verificado
            if not verificado:
                extractor.verificar_modelo()
                # Fallar antes de reservar si PostgREST aún no conoce 0015.
                try:
                    db.table('ejecuciones').select('reintentos_ingesta,proximo_intento_ingesta').limit(0).execute()
                    db.table('puentes_necesidades_v3').select('ejecucion_id').limit(0).execute()
                    db.table('revisiones_lote_v2').select('evento_id').limit(0).execute()
                except Exception:
                    logger.error('No se pudieron consultar columnas de 0015/0016/0017; revisar migración, PostgREST y conexión BD.')
                    raise
                verificado = True
            return una_vuelta(db, extractor, planificacion_id=args.planificacion_id, detener=detener)
        return ejecutar_bucle(vuelta, detener=detener, intervalo=args.intervalo,
            una_sola=args.una_vuelta, max_fallos=args.max_fallos, archivo_salud=args.archivo_salud)
    except KeyboardInterrupt:
        return 0
    except ErrorIngesta as error:
        print(json.dumps({'estado': 'error_configuracion_proveedor', 'mensaje': str(error)}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({'estado': 'error', 'mensaje': 'Revisar configuración y migraciones V2/V3/V4; no se muestran credenciales.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
