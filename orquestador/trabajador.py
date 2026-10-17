"""Trabajador V2/V3/V4. Ejecutar --una-vuelta primero; Ctrl+C detiene el sondeo."""
import argparse
import json
import time
from pathlib import Path
from uuid import UUID
from agentes.gemini import ConfiguracionGemini, ExtractorGemini
from comun.db import get_supabase
from .flujo import avanzar


def una_vuelta(db, extractor, herramientas=None, limite=20, *, planificacion_id=None, detener=None):
    if detener is not None and detener():
        return []
    if planificacion_id is None:
        db.rpc('ra_mantenimiento_v2', {}).execute()
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
        try:
            resultados.append(avanzar(fila, db, extractor, herramientas))
        except Exception:
            # No repetir una llamada incierta; su reserva vencida pasa a revisión.
            resultados.append({'estado': 'requiere_revision', 'ejecucion_id': fila['ejecucion_id']})
    return resultados


def main():
    parser = argparse.ArgumentParser(description='Trabajador H2Oeste V2/V3/V4')
    parser.add_argument('--una-vuelta', action='store_true')
    parser.add_argument('--planificacion-id', type=UUID, help='Procesar solo este ensayo V3, sin mantenimiento global de V2')
    parser.add_argument('--intervalo', type=float, default=5)
    parser.add_argument('--archivo-parada', type=Path, help='Señal de cierre del proceso que administra el trabajador')
    args = parser.parse_args()
    if not 1 <= args.intervalo <= 60:
        parser.error('--intervalo debe estar entre 1 y 60 segundos')
    try:
        db = get_supabase()
        class ExtractorPerezoso:
            def extraer(self, texto):
                return ExtractorGemini(ConfiguracionGemini.cargar()).extraer(texto)
        extractor = ExtractorPerezoso()
        detener = lambda: args.archivo_parada is not None and args.archivo_parada.exists()
        while not detener():
            print(json.dumps({'resultados': una_vuelta(db, extractor, planificacion_id=args.planificacion_id, detener=detener)}, ensure_ascii=False), flush=True)
            if args.una_vuelta:
                return 0
            # Responder al cierre sin esperar todo el intervalo de sondeo.
            limite_espera = time.monotonic() + args.intervalo
            while not detener() and time.monotonic() < limite_espera:
                time.sleep(min(.2, max(0, limite_espera-time.monotonic())))
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(json.dumps({'estado': 'error', 'mensaje': 'Revisar configuración y migraciones V2/V3/V4; no se muestran credenciales.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
