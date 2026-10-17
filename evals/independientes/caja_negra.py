"""Ejecutor HTTP para guiones revisados; no importa API, DB ni servicios internos.

No prepara datos ni envía Telegram. Las rutas se acuerdan con Noel en un perfil
local: este módulo no inventa endpoints. No hay reintentos ni redirecciones.
"""
import hashlib
import json
import os
from urllib.parse import urlsplit

import httpx


class FalloComprobacion(ValueError):
    pass


def puntero(documento, ruta):
    """Subconjunto estándar de JSON Pointer; ruta vacía representa el documento."""
    if ruta == '':
        return documento
    if not isinstance(ruta, str) or not ruta.startswith('/'):
        raise FalloComprobacion('Puntero JSON inválido')
    valor = documento
    try:
        for clave in ruta[1:].split('/'):
            clave = clave.replace('~1', '/').replace('~0', '~')
            valor = valor[int(clave)] if isinstance(valor, list) else valor[clave]
    except (KeyError, IndexError, TypeError, ValueError):
        raise FalloComprobacion('Falta un campo esperado en la respuesta') from None
    return valor


def digest(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def validar_guion(guion):
    pasos = guion.get('pasos')
    if not isinstance(pasos, list) or not pasos:
        raise FalloComprobacion('Guion sin pasos: integración pendiente')
    nombres = set()
    for paso in pasos:
        nombre = paso.get('nombre')
        if not isinstance(nombre, str) or not nombre or nombre in nombres:
            raise FalloComprobacion('Cada paso requiere nombre único')
        nombres.add(nombre)
        ruta = paso.get('ruta', '')
        if not isinstance(ruta, str) or not ruta.startswith('/') or ruta.startswith('//') or any(c in ruta for c in ('?', '#', '\\')):
            raise FalloComprobacion('Usar ruta relativa sin parámetros ni credenciales')
        if paso.get('metodo') not in {'GET', 'POST'}:
            raise FalloComprobacion('Método no admitido por este ejecutor')
        esperado = paso.get('esperado', {})
        if not isinstance(esperado.get('http'), int) or esperado['http'] in {404, 405}:
            raise FalloComprobacion('404/405 no demuestran un bloqueo de dominio')
        if not isinstance(esperado.get('json'), dict) or not esperado['json']:
            raise FalloComprobacion('Se requieren comprobaciones del cuerpo, no solo HTTP')
        for comparacion in esperado.values():
            if comparacion is None:
                raise FalloComprobacion('Expectativa incompleta')


def ejecutar_guion(base_url, guion, *, transporte=None):
    validar_guion(guion)  # validar TODO antes de la primera petición
    url = urlsplit(base_url)
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {'', '/'}:
        raise FalloComprobacion('Origen API inválido; no incluir claves ni rutas')
    if url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise FalloComprobacion('HTTP sin cifrar solo se admite en localhost')
    capturas, traza = {}, []
    with httpx.Client(base_url=base_url, timeout=15, follow_redirects=False,
                      transport=transporte, trust_env=False) as cliente:
        for paso in guion['pasos']:
            cabeceras = {}
            for cabecera, referencia in paso.get('cabeceras_entorno', {}).items():
                secreto = os.environ.get(referencia)
                if not secreto:
                    raise FalloComprobacion('Falta una credencial de ensayo en el entorno')
                cabeceras[cabecera] = secreto
            try:
                respuesta = cliente.request(paso['metodo'], paso['ruta'],
                    headers=cabeceras, json=paso.get('cuerpo'))
            except httpx.HTTPError:
                raise FalloComprobacion('Fallo HTTP; no se reintenta una operación incierta') from None
            if respuesta.status_code != paso['esperado']['http']:
                raise FalloComprobacion(f"HTTP inesperado en paso {paso['nombre']}")
            try:
                cuerpo = respuesta.json()
            except ValueError:
                raise FalloComprobacion('Respuesta sin JSON válido') from None
            for ruta, esperado in paso['esperado']['json'].items():
                if puntero(cuerpo, ruta) != esperado:
                    raise FalloComprobacion(f"Contenido inesperado en paso {paso['nombre']}")
            for ruta, captura in paso['esperado'].get('igual_a_captura', {}).items():
                if captura not in capturas or digest(puntero(cuerpo, ruta)) != capturas[captura]:
                    raise FalloComprobacion('Cambió el estado auditado o falta captura anterior')
            for nombre, ruta in paso.get('capturar', {}).items():
                if nombre in capturas:
                    raise FalloComprobacion('No sobrescribir una captura anterior')
                capturas[nombre] = digest(puntero(cuerpo, ruta))
            # No persistir tokens, texto ciudadano, chats, URL ni respuesta cruda.
            traza.append(dict(paso=paso['nombre'], metodo=paso['metodo'],
                              http=respuesta.status_code, comprobaciones=len(paso['esperado']['json'])
                              + len(paso['esperado'].get('igual_a_captura', {}))))
    return traza
