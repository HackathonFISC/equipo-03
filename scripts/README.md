# scripts

**Dueño:** José (Noel valida)

Desde la raíz del repositorio:

| Script | Uso y límites |
| --- | --- |
| `verificar_entorno.py` | Dependencias, contratos y fixture V0 sin red. |
| `verificar_escenario_v3.py` | Comprobación del escenario territorial. |
| `auditar_entrega.py` | Copia candidata, regresión y manifiesto; ver [V6](../docs/ENTREGA_V6.md). |
| `ensayo_priorizacion_v2.py` | Ensayo persistido; revisar guía/entorno antes de ejecutarlo. |
| `ensayar_v3.py`, `evaluar_planificacion_v3.py` | Ensayos de Planificación, con modos que usan servicios externos. |
| `operar_v4.py` | Selección por sector/destinos de ensayo; operación administrativa ajena a la auditoría local. |

No hay instalador automático de BD ni script general de arranque. Los comandos
revisados de API, bot y panel están en [README](../README.md).
