"""Geocoding v4 del servidor: una petición acotada, sin claves en URLs ni logs."""
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import httpx
from dotenv import dotenv_values
from pydantic import ValidationError
from contratos.modelos import Ubicacion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeocodificadorGoogle:
    clave: str = field(repr=False)
    transporte: object = field(default=None, repr=False)

    @classmethod
    def cargar(cls):
        valores = dotenv_values(Path(__file__).resolve().parents[1] / '.env', interpolate=False)
        clave = (os.environ.get('GOOGLE_MAPS_API_KEY', valores.get('GOOGLE_MAPS_API_KEY')) or '').strip()
        return cls(clave) if clave else None

    def resolver(self, direccion):
        if not direccion or len(direccion) > 1000:
            return None
        # HTTPX registra las direcciones en la URL; HTTPcore puede registrar detalles de transporte.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        try:
            with httpx.Client(timeout=5, transport=self.transporte, follow_redirects=False) as cliente:
                respuesta = cliente.get('https://geocode.googleapis.com/v4/geocode/address',
                    params={'address.addressLines': direccion, 'address.regionCode': 'PA',
                            'languageCode': 'es', 'regionCode': 'pa'},
                    headers={'X-Goog-Api-Key': self.clave,
                             'X-Goog-FieldMask': 'results.placeId,results.location,results.granularity,results.types,results.postalAddress.regionCode'})
                respuesta.raise_for_status()
                datos = respuesta.json()
            resultados = datos.get('results', [])
            # Una localidad/centroide no ubica una vivienda. Pedir pin al remitente.
            if len(resultados) != 1:
                return None
            lugar = resultados[0]
            if (lugar.get('postalAddress', {}).get('regionCode') != 'PA'
                    or lugar.get('granularity') not in {'ROOFTOP', 'RANGE_INTERPOLATED'}
                    or not set(lugar.get('types', [])) & {'street_address', 'premise', 'subpremise', 'establishment', 'point_of_interest', 'plus_code'}
                    or not isinstance(lugar.get('placeId'), str) or not lugar['placeId']):
                return None
            coord = lugar['location']
            ubicacion = Ubicacion(latitud=coord['latitude'], longitud=coord['longitude'],
                                  fuente='geocodificada', representa_punto_atencion=None)
            return {'ubicacion': ubicacion.model_dump(mode='json'), 'place_id': lugar['placeId']}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, ValidationError):
            # No incluir excepciones, URLs, direcciones, respuestas ni credenciales.
            logger.warning('Geocodificación no disponible o sin resultado utilizable; solicitar pin.')
            return None
