"""Trabajador V2/V3. Ejecutar --una-vuelta primero; Ctrl+C detiene el sondeo."""
import argparse
import json
import time
from uuid import UUID
from agentes.gemini import ConfiguracionGemini, ExtractorGemini
from comun.db import get_supabase
from .flujo import avanzar


def una_vuelta(db, extractor, herramientas=None, limite=20, *, planificacion_id=None):
    if planificacion_id is None:
        db.rpc('ra_mantenimiento_v2', {}).execute()
    else:
        db.rpc('ra_mantenimiento_planificacion_v3', {'p_ejecucion_id': str(planificacion_id)}).execute()
    consulta = db.table('ejecuciones').select('ejecucion_id,etapa').eq('estado', 'pendiente').in_(
        'etapa', ['ingesta', 'territorial', 'priorizacion', 'planificacion'])
    if planificacion_id is not None:
        consulta = consulta.eq('ejecucion_id', str(planificacion_id)).eq('etapa', 'planificacion')
    filas = consulta.order('creado_en').limit(limite).execute().data
    resultados = []
    for fila in filas:
        try:
            resultados.append(avanzar(fila, db, extractor, herramientas))
        except Exception:
            # No repetir una llamada incierta; su reserva vencida pasa a revisión.
            resultados.append({'estado': 'requiere_revision', 'ejecucion_id': fila['ejecucion_id']})
    return resultados


def main():
    parser = argparse.ArgumentParser(description='Trabajador RutaAgua V2/V3')
    parser.add_argument('--una-vuelta', action='store_true')
    parser.add_argument('--planificacion-id', type=UUID, help='Procesar solo este ensayo V3, sin mantenimiento global de V2')
    parser.add_argument('--intervalo', type=float, default=5)
    args = parser.parse_args()
    if not 1 <= args.intervalo <= 60:
        parser.error('--intervalo debe estar entre 1 y 60 segundos')
    try:
        db = get_supabase()
        class ExtractorPerezoso:
            def extraer(self, texto):
                return ExtractorGemini(ConfiguracionGemini.cargar()).extraer(texto)
        extractor = ExtractorPerezoso()
        while True:
            print(json.dumps({'resultados': una_vuelta(db, extractor, planificacion_id=args.planificacion_id)}, ensure_ascii=False), flush=True)
            if args.una_vuelta:
                return 0
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(json.dumps({'estado': 'error', 'mensaje': 'Revisar configuración y migraciones 0006–0009; no se muestran credenciales.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
