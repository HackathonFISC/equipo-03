"""Catálogo de instalaciones: no concede permisos ni acredita recepción."""
from dataclasses import dataclass
from uuid import UUID

from contratos.modelos import Ubicacion


@dataclass(frozen=True)
class PuntoCatalogo:
    punto_atencion_id: UUID
    sector_id: UUID
    nombre: str
    alias: tuple[str, ...]
    distrito: str
    corregimiento: str | None
    ubicacion: Ubicacion | None
    estado_validacion: str

    @classmethod
    def desde_fila(cls, fila):
        ubicacion = None
        if fila.get('latitud') is not None and fila.get('longitud') is not None:
            ubicacion = Ubicacion(latitud=float(fila['latitud']), longitud=float(fila['longitud']),
                fuente=fila['fuente_ubicacion'], precision_metros=float(fila['precision_metros']) if fila.get('precision_metros') is not None else None,
                representa_punto_atencion=fila.get('representa_punto_atencion'))
        return cls(UUID(fila['punto_atencion_id']), UUID(fila['sector_id']), fila['nombre'],
                   tuple(fila.get('alias') or []), fila['distrito'], fila.get('corregimiento'),
                   ubicacion, fila['estado_validacion'])
