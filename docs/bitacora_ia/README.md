# Bitácoras de IA

Cada integrante mantiene su fuente: [Emilia](emilia.md), [José](jose.md) y
[Noel](noel.md). [BITACORA_IA.md](BITACORA_IA.md) contiene las tres fuentes
literales con sus huellas SHA-256; no suma recuentos históricos de pruebas ni
convierte declaraciones en evidencia remota. José coordina la consolidación;
Emilia solicitó esta actualización conjunta.

La [revisión del 17 de octubre](REVISION_2026-10-17.md) identifica omisiones
recuperadas, comprobaciones y pendientes. Las entradas describen el estado en su
fecha: «sin commit» o «sin aplicar» no significa que continúe así tras una entrega
posterior. Consultar evidencia posterior sin borrar el registro histórico.

Para regenerar, desde la raíz del repositorio:

```sh
python -m scripts.auditar_entrega --consolidar-bitacoras /tmp/bitacora-ia-nueva.md
```

Usar una ruta nueva: el generador rechaza sobrescribir. Revisar el resultado y
reemplazar `docs/bitacora_ia/BITACORA_IA.md`. Cada cambio de fuente requiere
regenerarla; conservar las fuentes de los demás sin atribuirles revisiones nuevas.
