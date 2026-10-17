"""Tiempos viales dirigidos de Google; sin fallback a tiempos inventados."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import logging
import os
import re
from urllib.parse import urlencode
import httpx
from contratos.modelos import Ubicacion
from contratos.solicitudes import MatrizTiempos


class ErrorRutas(ValueError):
    """Mensaje controlado que puede mostrarse sin revelar peticiones ni claves."""


def navegacion(origen, destinos):
    def coord(u):
        u = Ubicacion.model_validate(u)
        return f'{u.latitud},{u.longitud}'
    if not destinos:
        return None
    parametros = {'api': 1, 'origin': coord(origen), 'destination': coord(destinos[-1]), 'travelmode': 'driving'}
    if len(destinos) > 1:
        parametros['waypoints'] = '|'.join(coord(u) for u in destinos[:-1])
    return 'https://www.google.com/maps/dir/?' + urlencode(parametros)


def enlaces_recorrido(deposito, paradas):
    """Incluye retorno; enlaces por tramo funcionan también sin soporte multistop."""
    if not paradas:
        return {'navegacion_url': None, 'tramos_navegacion': []}
    nodos = [deposito, *paradas, deposito]
    return {'navegacion_url': navegacion(deposito, nodos[1:]),
            'tramos_navegacion': [navegacion(a, [b]) for a, b in zip(nodos, nodos[1:])]}


@dataclass(frozen=True)
class RutasGoogle:
    clave: str = field(repr=False)
    transporte: object = field(default=None, repr=False)

    @classmethod
    def cargar(cls, *, automatico=False):
        from dotenv import dotenv_values
        from comun.config import RAIZ_PROYECTO
        valores = dotenv_values(RAIZ_PROYECTO / '.env', interpolate=False)
        valores.update(os.environ)
        if automatico and (valores.get('GOOGLE_ROUTES_ACTIVAS') or '').lower() != 'true':
            return None
        clave = (valores.get('GOOGLE_ROUTES_API_KEY') or valores.get('GOOGLE_MAPS_API_KEY') or '').strip()
        if not clave:
            if automatico:
                raise ErrorRutas('Falta GOOGLE_MAPS_API_KEY o GOOGLE_ROUTES_API_KEY para calcular rutas.')
            return None
        return cls(clave)

    def calcular(self, ids, ubicaciones):
        n = len(ids)
        if not 2 <= n <= 7 or len(set(ids)) != n or len(ubicaciones) != n:
            raise ErrorRutas('Se necesita un depósito y entre uno y seis destinos diferentes.')
        nodos = [Ubicacion.model_validate(u) for u in ubicaciones]
        waypoints = [{'waypoint': {'location': {'latLng': {'latitude': u.latitud, 'longitude': u.longitud}}}} for u in nodos]
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        try:
            with httpx.Client(timeout=15, transport=self.transporte, follow_redirects=False) as cliente:
                respuesta = cliente.post('https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix',
                    headers={'X-Goog-Api-Key': self.clave,
                             'X-Goog-FieldMask': 'originIndex,destinationIndex,status,condition,duration,distanceMeters'},
                    json={'origins': waypoints, 'destinations': waypoints, 'travelMode': 'DRIVE',
                          'routingPreference': 'TRAFFIC_UNAWARE', 'languageCode': 'es', 'regionCode': 'pa'})
                respuesta.raise_for_status()
                filas = respuesta.json()
            if not isinstance(filas, list):
                raise ValueError()
            minutos = [[None] * n for _ in range(n)]
            metros = [[None] * n for _ in range(n)]
            vistos = set()
            for fila in filas:
                # protobuf puede omitir los índices cuyo valor es cero.
                a, b = fila.get('originIndex', 0), fila.get('destinationIndex', 0)
                if type(a) is not int or type(b) is not int or not 0 <= a < n or not 0 <= b < n or (a, b) in vistos:
                    raise ValueError()
                vistos.add((a, b))
                if fila.get('status', {}).get('code', 0) != 0:
                    raise ErrorRutas('Google no pudo calcular todos los tramos. Intenta de nuevo más tarde.')
                if fila.get('condition') == 'ROUTE_NOT_FOUND':
                    continue
                if fila.get('condition') != 'ROUTE_EXISTS' or not re.fullmatch(r'\d+(?:\.\d{1,9})?s', fila.get('duration', '')):
                    raise ValueError()
                segundos = Decimal(fila['duration'][:-1])
                distancia = fila.get('distanceMeters', 0)
                if type(distancia) is not int or distancia < 0:
                    raise ValueError()
                minutos[a][b] = int((segundos / 60).to_integral_value(rounding=ROUND_CEILING)) if a != b else 0
                metros[a][b] = distancia if a != b else 0
            if len(vistos) != n * n:
                raise ValueError()
            for i in range(n):
                minutos[i][i] = metros[i][i] = 0
            instante = datetime.now(timezone.utc).isoformat()
            huella = hashlib.sha256(json.dumps([list(map(str, ids)), minutos, instante]).encode()).hexdigest()[:24]
            matriz = MatrizTiempos(matriz_version='google-routes-' + huella, origen='estimado', nodos_ids=ids,
                minutos=minutos, descripcion='Google Maps Routes API; tiempos viales estimados sin tráfico en vivo, redondeados hacia arriba. Consulta: ' + instante)
            return {'matriz': matriz, 'metros': metros, 'consultado_en': instante}
        except ErrorRutas:
            raise
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
            raise ErrorRutas('Google Routes no está disponible o devolvió una matriz incompleta. No se sustituyeron tiempos.') from None

    def para_solicitud(self, solicitud):
        nodos = [solicitud.deposito, *solicitud.puntos]
        ids = [solicitud.deposito.deposito_id, *[p.punto_atencion_id for p in solicitud.puntos]]
        return self.calcular(ids, [n.ubicacion for n in nodos])['matriz']
