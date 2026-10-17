# geografia

**Dueño:** Emilia

catalogo.py, resolver.py (resolve_location), consolidacion.py (link_reports)


## Catálogo inicial oeste-1.0

El usuario confirmó seis puntos totales: tres por distrito entre Arraiján y
La Chorrera, conservando dos camiones y un depósito. CSV y alias con UUID
estables en `datos/geografia/`. Ver su README para fuente y validación pendiente.
`python -m geografia.generar_semilla` regenera semilla y smoke desde los CSV.
El resolvedor y la consolidación de V2 están implementados en `resolver.py` y
`consolidacion.py`, integrados por `agentes/territorial.py`. El catálogo no
convierte una mención amplia del corregimiento en una instalación por defecto.
La validación operativa del acceso y la descarga sigue pendiente; es distinta
del estado de implementación del código.

## Implementación V2

Catálogo, resolve_location y link_reports disponibles. La corrección conserva historial mediante RPC backend (interfaz autorizada en V4); sin geocodificación externa ni asignación automática por cercanía. Ver [V2](../docs/V2_EMILIA.md).
