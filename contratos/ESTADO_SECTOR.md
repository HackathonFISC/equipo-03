# Contrato de consulta `estado_sector` (V4)

Emilia define los modelos; Noel implementa la lectura y permisos de la API;
José comprueba la integración. Esta entrega define el intercambio, sin crear
un endpoint ni ejecutar consultas. Los modelos viven en `contratos/consultas.py`.

## Decisiones confirmadas por Emilia

- Mostrar solo la versión aprobada y válida para comunicar a la comunidad.
- Un plan invalidado deja de ser vigente: no mostrar sus litros ni horarios
  históricos como si siguieran autorizados.
- Listar todos los puntos activos del sector, incluidos los que no tienen
  asignación. `sin_asignacion` lleva litros y ventana en `null`, nunca cero.

Los nombres, estructura y comprobaciones siguientes son diseño técnico de
Emilia para revisión de Noel y José; no representan aceptación de los tres.
La ampliación es aditiva y conserva `esquema_version=1.0`: no cambia payloads
existentes ni las cuatro firmas de cálculo.

## Firma e intercambio

```python
from contratos.consultas import SolicitudEstadoSector, EstadoSector

# Firma que implementa Noel:
# estado_sector(entrada: SolicitudEstadoSector) -> EstadoSector
```

| Campo | Significado |
| --- | --- |
| Solicitud `sector_id` | UUID interno del catálogo; nombre libre e ID de Telegram no son identificadores de sector |
| `consultado_en` | Fecha del snapshot de lectura del servidor, con zona horaria |
| `sector` | UUID, nombre, distrito, corregimiento opcional, origen y estado de información del catálogo |
| `estado` | `con_plan_vigente` o `sin_plan_vigente`; indica vigencia de planificación, no disponibilidad del agua |
| `plan_vigente` | Identidad y versión únicas del plan, ejecución, versiones de datos y política, origen, aprobación y fecha; `null` si no existe uno válido |
| `puntos` | Todos los puntos activos de ese sector, una sola vez, aunque no tengan asignación; lista vacía si no hay activos |
| Punto `estado` | `sin_asignacion`, `programada`, `iniciada`, `atendida` o `con_incidencia` |
| Punto `litros_asignados` | Litros positivos del plan vigente; `null` sin asignación. No son litros físicamente entregados |
| Punto `ventana_estimada` | `inicio_descarga` a `fin_descarga` de la parada vigente; no la ventana de disponibilidad del punto ni una llegada garantizada |
| Punto `parada_id` | Referencia de la parada vigente; `null` sin asignación |
| Punto `motivo_sin_asignacion` | Texto obligatorio si no hay asignación: por ejemplo, sin plan vigente o motivo de `no_atendidos`; `null` para una parada asignada |

No se impone el límite de seis puntos de la demo a esta consulta del catálogo.
Los puntos asignados usan el estado persistido de la parada; no se marcan
`atendida` por el transcurso de la ventana ni por enviar un aviso. No se
devuelven remitentes, destinos, chat IDs, datos de usuarios ni claves.

Una consulta no crea una ejecución de agentes. Por eso solicitud y respuesta
heredan `Contrato`, no `Contexto`; `ejecucion_id` se conserva dentro del plan
si hay uno vigente. No fabricar UUID de ejecución para cada lectura.

## Lectura que debe implementar Noel

1. Resolver el sector y comprobar permisos. Un sector inexistente o prohibido
   produce un error de API; no simular un sector sin plan. Noel publica el código
   de dominio y el mapeo HTTP correspondientes antes de cerrar V4.
2. Seleccionar la versión vigente del plan desde el estado autorizado del
   servicio. Exigir `aprobado`, solución factible, verificación válida de esa
   versión, aprobación correspondiente y ausencia de bloqueos de publicación.
   No elegir automáticamente el mayor número de versión o la fila más reciente
   entre planes distintos. Si la selección es ambigua, resolverla o fallar sin
   publicar un snapshot mezclado; un error de BD tampoco equivale a sin plan.
3. Leer sector, puntos activos, plan y paradas de una misma vista consistente.
   Antes de responder, garantizar que la versión no se invalidó o sustituyó
   durante la lectura. El modelo comprueba forma, no vigencia real en la BD.
4. Para cada punto activo, proyectar la parada de **ese mismo plan y versión**.
   Si no existe parada, devolver `sin_asignacion` y su motivo, sin rescatar
   cantidades de versiones anteriores. Un plan vigente puede no asignar ningún
   punto del sector; no equivale por ello a un fallo de consulta.
5. Si no hay plan vigente, devolver `sin_plan_vigente`, `plan_vigente=null`
   y todos los puntos activos como `sin_asignacion`. Un sector conocido vacío
   puede devolver `puntos=[]`; no es un sector inexistente.
6. Validar `EstadoSector` y serializar con `model_dump(mode="json")`.

Los valores `verificado=true` y `estado=aprobado` deben venir de la lectura
validada por el servicio; el modelo no comprueba firmas, permisos ni la
correspondencia del contenido con un informe de verificación. El formato no
incluye una vigencia basada únicamente en horas: Noel debe respetar la regla de
selección/cierre de su servicio, sin inferir que un plan expiró solo por su ETA.

## Origen y ejemplos

Sector, plan y puntos conservan el origen de los datos proyectados. El origen
de cada punto debe considerar tanto el catálogo como su asignación: si alguno
es sintético, el punto es `sintetico`; si ninguno es sintético pero alguno es
estimado, es `estimado`; solo fuentes reales permiten `real`. La misma regla
se valida para el origen global del resumen. Esta clasificación no demuestra
veracidad ni cambia automáticamente el origen de reportes del chat de prueba.

El manifiesto incluye solicitud, respuesta con plan, respuesta sin plan y
sector sin puntos activos. Todos los ejemplos son sintéticos construidos a
mano. Los JSON Schema se generan con `python -m contratos.exportar_esquemas`;
la validación cruzada (duplicados, pertenencia al sector, vigencia y origen)
requiere Pydantic y las comprobaciones del servicio, no solo JSON Schema.

## Revisión antes de V4

- Emilia: dos decisiones funcionales confirmadas; modelos y ejemplos entregados.
- Noel: aceptación de nombres/campos, regla de selección de plan vigente,
  tratamiento de errores, lectura consistente y permisos pendientes.
- José: aceptación del intercambio y pruebas independientes de la API pendientes.

No se modifica la migración 0001. Esta respuesta es una proyección sobre las
tablas existentes, no una nueva tabla. La selección única de plan vigente
entre planes distintos debe resolverse en el servicio de Noel y, si necesita
persistencia adicional, acordarse en una migración nueva.
