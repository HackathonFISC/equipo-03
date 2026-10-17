"""Resolución determinista de nombres. No usa distancia para adivinar un destino."""
from dataclasses import dataclass
import re
import unicodedata

from .catalogo import PuntoCatalogo


def normalizar(texto):
    sin_acentos = ''.join(c for c in unicodedata.normalize('NFD', texto.casefold()) if unicodedata.category(c) != 'Mn')
    return ' '.join(re.findall(r'[^\W_]+', sin_acentos))


@dataclass(frozen=True)
class Resolucion:
    estado: str
    candidatos: tuple[PuntoCatalogo, ...]
    motivo: str

    @property
    def punto(self):
        return self.candidatos[0] if self.estado == 'resuelta' else None


def resolve_location(textos, catalogo, ubicacion_compartida=None):
    """Nombres/alias completos con límites de palabra; zonas amplias no son alias.

    Una coincidencia de nombre identifica una referencia, no valida su operación.
    Coordenadas sin nombre compatible requieren revisión humana de correspondencia.
    """
    textos = [normalizar(t) for t in textos if t]
    catalogo = list(catalogo)
    zonas = {normalizar(z) for p in catalogo for z in (p.distrito, p.corregimiento, 'Panamá Oeste') if z}
    candidatos = []
    for punto in catalogo:
        nombres = {normalizar(n) for n in (punto.nombre, *punto.alias)} - zonas - {''}
        if any(f' {nombre} ' in f' {texto} ' for nombre in nombres for texto in textos):
            candidatos.append(punto)
    if len(candidatos) == 1:
        if ubicacion_compartida is not None:
            # No existe una tolerancia de distancia aprobada: una ubicación enviada
            # por el ciudadano necesita confirmar qué representa antes de asociarla.
            return Resolucion('revision', tuple(candidatos), 'Confirmar correspondencia de la ubicación compartida con la instalación nombrada.')
        return Resolucion('resuelta', tuple(candidatos), 'Nombre o alias de instalación reconocido en catálogo.')
    if len(candidatos) > 1:
        return Resolucion('ambigua', tuple(candidatos), 'Se mencionan varias instalaciones; precisar a cuál corresponde el reporte.')
    if ubicacion_compartida is not None:
        return Resolucion('revision', (), 'Ubicación recibida fuera de correspondencia conocida; revisar sin crear un punto.')
    return Resolucion('desconocida', (), 'Falta identificar una instalación; no equivale a fuera de cobertura.')
