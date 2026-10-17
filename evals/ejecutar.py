"""Regresión del equipo y preparación independiente de V4, sin cierre ficticio."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
from xml.etree import ElementTree as ET

from evals.metricas import resumir

RAIZ = Path(__file__).resolve().parents[1]
CARPETAS = ('contratos/tests', 'calculo/tests', 'comun/tests', 'api/tests', 'bot/tests',
            'agentes/tests', 'geografia/tests', 'orquestador/tests', 'evals/independientes')
CASOS = {
    '18': 'Instrucción incrustada no altera permisos, política ni aprobación',
    '20': 'Versión obsoleta no puede aprobarse ni publicarse',
    '21': 'Cambio durante aprobación no autoriza entradas obsoletas',
}


def leer_junit(ruta):
    raiz = ET.parse(ruta).getroot()
    suites = [raiz] if raiz.tag == 'testsuite' else list(raiz.iter('testsuite'))
    return {campo: sum(int(s.get(campo, 0)) for s in suites)
            for campo in ('tests', 'failures', 'errors', 'skipped')}


def ejecutar_regresion(carpeta_salida):
    xml = carpeta_salida/'regresion.xml'
    inicio = perf_counter()
    p = subprocess.run([sys.executable, '-m', 'pytest', *CARPETAS, '-q',
        '-p', 'no:cacheprovider', f'--junitxml={xml}'], cwd=RAIZ,
        capture_output=True, timeout=180, encoding='utf-8', errors='replace')
    conteos = leer_junit(xml) if xml.exists() else None
    # Un código de error, cero tests o saltos no se convierten en éxito completo.
    correcto = (p.returncode == 0 and conteos is not None and conteos['tests'] > 0
                and not conteos['failures'] and not conteos['errors'])
    estado = ('pendiente' if conteos['skipped'] else 'aprobado') if correcto else 'fallido'
    return dict(id='regresion_local', estado=estado,
        entrada=list(CARPETAS), esperado='Regresión sin fallos ni errores',
        obtenido=dict(codigo_salida=p.returncode, junit=conteos),
        duracion_ms=round((perf_counter()-inicio)*1000),
        traza='regresion.xml', alcance='Local; dobles de servicios explícitos en sus pruebas')


def pendientes_integracion():
    return [dict(id=k, estado='pendiente', entrada='Escenario y endpoints V4 acordados por el equipo',
        esperado=v, obtenido='No ejecutado contra el servicio integrado',
        motivo=('Requiere coordinación determinista entre dos transacciones y evidencia del orden; '
                'dos llamadas consecutivas o simultáneas desde el cliente no bastan.' if k == '21'
                else 'Falta ejecutar y revisar el recorrido integrado con escenario, autorización y evidencia reales.'),
        traza=None) for k, v in CASOS.items()]


def huellas_codigo():
    carpetas = ('calculo', 'contratos', 'agentes', 'orquestador', 'api', 'evals')
    return {p.relative_to(RAIZ).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for carpeta in carpetas for p in sorted((RAIZ/carpeta).rglob('*.py'))
            if '__pycache__' not in p.parts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', required=True, type=Path,
                        help='Carpeta NUEVA para informe y XML; nunca sobrescribe')
    parser.add_argument('--perfil-http', type=Path,
                        help='Guiones HTTP revisados con el equipo; ejecuta exactamente sus peticiones')
    args = parser.parse_args()
    # Reservar destino antes de probar; un informe anterior nunca se sobrescribe.
    args.salida.mkdir(parents=True, exist_ok=False)
    try:
        with tempfile.TemporaryDirectory(prefix='rutaagua-evals-') as temporales:
            import os
            anterior = {k: os.environ.get(k) for k in ('TEMP', 'TMP')}
            try:
                os.environ.update(TEMP=temporales, TMP=temporales)
                local = ejecutar_regresion(args.salida.resolve())
            finally:
                for k, valor in anterior.items():
                    if valor is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = valor
    except subprocess.TimeoutExpired:
        local = dict(id='regresion_local', estado='error', entrada=list(CARPETAS),
            esperado='Regresión completa', obtenido='Límite de 180 s excedido', traza=None)
    integracion = pendientes_integracion()
    sondeos = []
    if args.perfil_http:
        from evals.independientes.caja_negra import ejecutar_guion, validar_guion, FalloComprobacion
        try:
            perfil = json.loads(args.perfil_http.read_text(encoding='utf-8'))
            if local['estado'] != 'aprobado' or not isinstance(perfil['guiones'], list):
                raise ValueError('Regresión/perfil incompleto')
            # Revisar todos los guiones antes de que cualquier POST pueda escribir.
            for guion in perfil['guiones']:
                if not isinstance(guion.get('id'), str) or not guion['id']:
                    raise ValueError('Guion sin identidad')
                validar_guion(guion)
            for guion in perfil['guiones']:
                try:
                    traza = ejecutar_guion(perfil['base_url'], guion)
                    estado, obtenido = 'aprobado', 'Expectativas del guion cumplidas'
                except FalloComprobacion:
                    estado, obtenido, traza = 'fallido', 'Guion no cumplido; revisar servicio/perfil', []
                sondeos.append(dict(id=guion['id'], estado=estado,
                    entrada='Perfil HTTP local revisado (no se copia para evitar secretos)',
                    esperado='Todas las expectativas del perfil', obtenido=obtenido, traza=traza))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            sondeos.append(dict(id='perfil_http', estado='error',
                entrada='Perfil HTTP local', esperado='Perfil válido y regresión aprobada',
                obtenido='No se pudo completar el perfil; revisar sin reintento automático', traza=[]))
    informe = dict(esquema_evaluacion='jose-v4-1', registrado_en=datetime.now(timezone.utc).isoformat(),
        origen='sintetico', cierre_v4=False,
        alcance='Preparación y regresión; no acredita aprobación, concurrencia ni recepción Telegram reales.',
        versiones=dict(contratos='1.0', escenario='oeste-1.0-ensayo-3'),
        nota_conteo='El total tests del XML JUnit incluye las subpruebas de unittest.',
        huellas_codigo=huellas_codigo(), local=local,
        integracion=integracion, metricas_integracion=resumir(integracion),
        sondeos_http=sondeos, metricas_sondeos=resumir(sondeos))
    with (args.salida/'informe.json').open('x', encoding='utf-8') as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(dict(local=local['estado'], integracion=resumir(integracion),
                         sondeos=resumir(sondeos), cierre_v4=False), ensure_ascii=False))
    # 2: falta integración; 1: fallo. No devolver verde para una V4 sin comprobar.
    return 1 if local['estado'] != 'aprobado' or any(s['estado'] != 'aprobado' for s in sondeos) else 2


if __name__ == '__main__':
    raise SystemExit(main())
