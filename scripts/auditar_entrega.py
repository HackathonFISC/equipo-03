"""Auditoría V6 sin red: copia declarada sin secretos, regresión y manifiesto.

Usa el Python instalado, NO instala dependencias ni demuestra un clonado fresco.
Salida 0: controles locales aprobados; 1: fallo; 2: control local pendiente.
Nunca acredita cierre V4/V5/V6 ni arranca procesos del producto.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from time import perf_counter
from xml.etree import ElementTree as ET

RAIZ = Path(__file__).resolve().parents[1]
CARPETAS = ('contratos/tests', 'calculo/tests', 'comun/tests', 'api/tests',
            'bot/tests', 'agentes/tests', 'geografia/tests', 'orquestador/tests',
            'evals/independientes')
DOCUMENTOS = ('README.md', 'docs/infraestructura.md', 'docs/ENTREGA_V6.md',
              'docs/decisiones.md', 'docs/bitacora_ia/BITACORA_IA.md',
              '.env.example', 'requirements.txt', 'requirements-lock.txt',
              'frontend/package-lock.json')


def sha(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def git_ejecutar(git, *argumentos):
    return subprocess.check_output([git, '-C', str(RAIZ), *argumentos])


def ruta_publicable(nombre):
    """Rechaza escapes, enlaces y archivos privados aun si Git los declarase."""
    relativa = PurePosixPath(nombre)
    if relativa.is_absolute() or '..' in relativa.parts or '\\' in nombre or ':' in nombre:
        raise ValueError('Ruta no publicable')
    for parte in relativa.parts:
        if (parte in {'.git', '.venv', 'venv', 'node_modules', '.runtime', '__pycache__'}
                or parte == '.env' or parte.startswith('.env.') and parte != '.env.example'
                or parte.lower().endswith(('.pem', '.key', '.p12', '.pfx'))):
            raise ValueError('Archivo privado o generado declarado en Git')
    ruta = RAIZ.joinpath(*relativa.parts)
    if any(p.is_symlink() for p in (ruta, *ruta.parents)):
        raise ValueError('No se exportan enlaces simbólicos')
    if not ruta.resolve().is_relative_to(RAIZ.resolve()) or not ruta.is_file():
        raise ValueError('Archivo inexistente o fuera del repositorio')
    return ruta


def consolidar_bitacoras(destino):
    partes = ['# Bitácora de IA consolidada', '',
              'Copia literal de las bitácoras de cada integrante. Las declaraciones de uso y revisión',
              'son de sus autores; esta consolidación no certifica pruebas remotas ni revisión humana.',
              'Cada fuente conserva sus filas y su huella SHA-256. Regenerar antes de la entrega.', '']
    for nombre in ('emilia', 'jose', 'noel'):
        ruta = RAIZ/'docs'/'bitacora_ia'/f'{nombre}.md'
        partes.extend([f'## Fuente: {nombre}.md', '', f'SHA-256: `{sha(ruta)}`', '',
                       ruta.read_text(encoding='utf-8').rstrip(), ''])
    with destino.open('x', encoding='utf-8', newline='\n') as archivo:
        archivo.write('\n'.join(partes))


def revisar_documentos():
    """Enlaces de entrada y vigencia de las fuentes consolidadas, sin consultar web."""
    rotos = []
    for nombre in ('README.md', 'docs/infraestructura.md', 'docs/ENTREGA_V6.md', 'scripts/README.md'):
        ruta = RAIZ/nombre
        for enlace in re.findall(r'\]\(([^)]+)\)', ruta.read_text(encoding='utf-8')):
            if enlace.startswith(('https://', 'http://', '#')):
                continue
            destino = (ruta.parent/enlace.split('#', 1)[0]).resolve()
            if not destino.is_relative_to(RAIZ.resolve()) or not destino.exists():
                rotos.append(dict(documento=nombre, enlace=enlace))
    consolidada = (RAIZ/'docs/bitacora_ia/BITACORA_IA.md').read_text(encoding='utf-8')
    vigentes = all(sha(RAIZ/f'docs/bitacora_ia/{n}.md') in consolidada
                   for n in ('emilia', 'jose', 'noel'))
    return [dict(id='enlaces_documentacion', estado='fallido' if rotos else 'aprobado', rotos=rotos),
            dict(id='bitacoras_vigentes', estado='aprobado' if vigentes else 'fallido')]


def correr(nombre, comando, cwd, salida, entorno, limite=180):
    inicio = perf_counter()
    try:
        resultado = subprocess.run(comando, cwd=cwd, env=entorno, capture_output=True,
                                   timeout=limite, encoding='utf-8', errors='replace')
        codigo = resultado.returncode
        texto = resultado.stdout + resultado.stderr
    except subprocess.TimeoutExpired:
        codigo, texto = None, 'Tiempo límite excedido; revisar antes de repetir.'
    registro = salida/f'{nombre}.log'
    registro.write_text(texto, encoding='utf-8')
    return dict(id=nombre, estado='aprobado' if codigo == 0 else 'fallido',
                codigo_salida=codigo, duracion_ms=round((perf_counter()-inicio)*1000),
                registro=registro.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, help='Carpeta NUEVA fuera del repositorio')
    parser.add_argument('--git', default=shutil.which('git'), help='Ejecutable Git local')
    parser.add_argument('--node', default=shutil.which('node'), help='Node para sondeo local')
    parser.add_argument('--consolidar-bitacoras', type=Path,
                        help='Solo crea un archivo NUEVO con las tres fuentes literales')
    args = parser.parse_args()
    if args.consolidar_bitacoras:
        consolidar_bitacoras(args.consolidar_bitacoras)
        return 0
    if not args.salida or not args.git:
        parser.error('Se necesitan --salida y Git local; no se descarga nada')
    salida = args.salida.resolve()
    if salida.is_relative_to(RAIZ.resolve()):
        parser.error('La salida debe quedar fuera del repositorio para evitar autoexportación')
    salida.mkdir(parents=True, exist_ok=False)
    informe = dict(esquema='jose-v6-1', registrado_en=datetime.now(timezone.utc).isoformat(),
                   cierre_v4=False, cierre_v5=False, cierre_v6=False,
                   alcance='Copia candidata sin .env; dependencias Python instaladas reutilizadas; sin red.',
                   instalacion_desde_cero='pendiente', recorridos_reales='pendiente',
                   controles=[], archivos={})
    try:
        informe['commit_base'] = git_ejecutar(args.git, 'rev-parse', 'HEAD').decode().strip()
        informe['estado_git'] = git_ejecutar(args.git, 'status', '--porcelain=v1').decode('utf-8', errors='replace')
        # Incluye cambios nuevos de V6: una exportación exclusiva de HEAD los omitiría.
        # No es un commit ni un clon. El manifiesto identifica esta copia candidata.
        nombres = sorted(set(git_ejecutar(args.git, 'ls-files', '-z', '--cached',
                                         '--others', '--exclude-standard').decode('utf-8').rstrip('\0').split('\0')))
        fuentes = [(n, ruta_publicable(n)) for n in nombres]
        faltantes = sorted(set(DOCUMENTOS)-set(nombres))
        if faltantes:
            raise ValueError('Faltan documentos de entrega: ' + ', '.join(faltantes))
        informe['controles'].extend(revisar_documentos())
        copia = salida/'candidato'
        copia.mkdir()
        for nombre, fuente in fuentes:
            destino = copia/nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fuente, destino)
            informe['archivos'][nombre] = sha(destino)
        entorno = os.environ.copy()
        # Los controles locales no heredan credenciales de servicios ni cargan .env.
        for clave in list(entorno):
            if (clave.startswith(('SUPABASE_', 'GEMINI_', 'GOOGLE_', 'TELEGRAM_', 'VITE_', 'LOGFIRE_', 'OPENAI_'))
                    or clave in {'API_SECRETO_BOT', 'API_URL'}):
                entorno.pop(clave)
        temporal = salida/'temporales'
        temporal.mkdir()
        entorno.update(TEMP=str(temporal), TMP=str(temporal), TRABAJADOR_AUTOMATICO='false',
                       PYTHONPATH=str(copia), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        comandos = [
            ('dependencias', [sys.executable, '-m', 'pip', 'check']),
            ('entorno_v0', [sys.executable, 'scripts/verificar_entorno.py']),
            ('regresion', [sys.executable, '-m', 'pytest', *CARPETAS, '-q', '-p', 'no:cacheprovider',
                           f'--junitxml={salida / "regresion.xml"}']),
            ('demo_v1', [sys.executable, '-m', 'calculo.demo_v1']),
            ('demo_v2', [sys.executable, '-m', 'calculo.demo_v2']),
            ('demo_v3', [sys.executable, '-m', 'calculo.demo_plan_v3']),
            ('comparacion_v5', [sys.executable, '-m', 'evals.comparar_v5', '--repeticiones', '3',
                                '--salida', str(salida/'comparacion_v5.json')]),
        ]
        for nombre, comando in comandos:
            informe['controles'].append(correr(nombre, comando, copia, salida, entorno))
        if args.node:
            informe['controles'].append(correr('sondeo_frontend', [args.node, '--test', 'tests/sondeo.test.mjs'],
                                              copia/'frontend', salida, entorno))
        else:
            informe['controles'].append(dict(id='sondeo_frontend', estado='pendiente', motivo='Node no disponible'))
        xml = salida/'regresion.xml'
        if xml.exists():
            raiz = ET.parse(xml).getroot()
            suites = [raiz] if raiz.tag == 'testsuite' else list(raiz.iter('testsuite'))
            conteos = {c: sum(int(s.get(c, 0)) for s in suites)
                       for c in ('tests', 'errors', 'failures', 'skipped')}
            informe['junit_incluye_subpruebas'] = conteos
            if not conteos['tests'] or conteos['errors'] or conteos['failures'] or conteos['skipped']:
                informe['controles'].append(dict(id='integridad_junit', estado='fallido'))
        else:
            informe['controles'].append(dict(id='integridad_junit', estado='fallido'))
        # Evita atribuir los resultados a fuentes cambiadas durante la ejecución.
        intactos = all(f.exists() and sha(f) == informe['archivos'][n] for n, f in fuentes)
        actuales = set(git_ejecutar(args.git, 'ls-files', '-z', '--cached', '--others',
                                  '--exclude-standard').decode('utf-8').rstrip('\0').split('\0'))
        informe['controles'].append(dict(id='fuentes_estables',
            estado='aprobado' if intactos and actuales == set(nombres) else 'fallido'))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # No volcar excepciones de procesos con posibles datos privados.
        informe['controles'].append(dict(id='auditoria', estado='fallido', tipo_error=type(error).__name__))
    estados = {c['estado'] for c in informe['controles']}
    informe['estado_local'] = 'fallido' if 'fallido' in estados else 'pendiente' if 'pendiente' in estados else 'aprobado'
    (salida/'informe.json').write_text(json.dumps(informe, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(estado_local=informe['estado_local'], cierre_v6=False, informe=str(salida/'informe.json')),
                     ensure_ascii=False))
    return {'aprobado': 0, 'fallido': 1, 'pendiente': 2}[informe['estado_local']]


if __name__ == '__main__':
    raise SystemExit(main())
