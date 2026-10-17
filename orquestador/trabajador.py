"""Trabajador V2. Ejecutar --una-vuelta primero; Ctrl+C detiene el sondeo."""
import argparse
import json
import time
from agentes.gemini import ConfiguracionGemini, ExtractorGemini
from comun.db import get_supabase
from .flujo import avanzar


def una_vuelta(db, extractor, herramientas=None, limite=20):
    db.rpc('ra_mantenimiento_v2', {}).execute()
    filas = db.table('ejecuciones').select('ejecucion_id,etapa').eq('estado', 'pendiente').in_(
        'etapa', ['ingesta', 'territorial', 'priorizacion']).order('creado_en').limit(limite).execute().data
    resultados = []
    for fila in filas:
        try:
            resultados.append(avanzar(fila, db, extractor, herramientas))
        except Exception:
            # No repetir una llamada incierta; su reserva vencida pasa a revisión.
            resultados.append({'estado': 'requiere_revision', 'ejecucion_id': fila['ejecucion_id']})
    return resultados


def main():
    parser = argparse.ArgumentParser(description='Trabajador RutaAgua V2')
    parser.add_argument('--una-vuelta', action='store_true')
    parser.add_argument('--intervalo', type=float, default=5)
    args = parser.parse_args()
    if not 1 <= args.intervalo <= 60:
        parser.error('--intervalo debe estar entre 1 y 60 segundos')
    try:
        db = get_supabase()
        extractor = ExtractorGemini(ConfiguracionGemini.cargar())
        while True:
            print(json.dumps({'resultados': una_vuelta(db, extractor)}, ensure_ascii=False), flush=True)
            if args.una_vuelta:
                return 0
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(json.dumps({'estado': 'error', 'mensaje': 'Revisar configuración y migraciones 0006/0007; no se muestran credenciales.'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
