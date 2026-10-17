# Escenario territorial oeste-1.0: preparación de V3

> Alcance: este documento describe la preparación y los archivos de este escenario,
> no el estado completo del repositorio. Los bloques 4/5 ya tienen
> [solver y verificador](../../../calculo/PLAN_V3.md). La integración local del
> fixture separado está en [V3 de Emilia](../../../docs/V3_EMILIA.md); aplicación
> en Supabase, panel y cierre integral deben comprobarse por separado.


Dueño: José. Versión de datos: `oeste-1.0-ensayo-1`.

Esta carpeta prepara el bloque 3 con los seis UUID de Emilia. Se conserva el catálogo `datos/geografia/puntos.csv` sin modificarlo. No se reasignan P1–P6 ni se sobrescriben los fixtures históricos V0/V1/V2.

## Archivos y procedencia

- `solicitud_rutas.json`: objeto completo `SolicitudResolverRutas`, todavía pendiente; incluye dos cisternas ficticias, depósito ficticio, seis referencias de puntos reales, necesidades sintéticas, propuesta de política, ventanas, descargas y matriz de siete nodos. Un `plan_id` en una solicitud no significa que exista un plan calculado o persistido.
- `solicitudes_validacion.json`: seis objetos `SolicitudValidarNecesidad` de demanda directa, sin confirmaciones y con recepción desconocida.
- `supuestos.json`: referencia y huella SHA-256 del catálogo normalizado a UTF-8/LF, procedencia documental, parámetros propuestos y decisiones pendientes. Es documentación local del escenario, no un contrato nuevo del equipo.

Las referencias de instalaciones conservan `origen=real`, coordenadas y fuente del catálogo AIG de enero de 2022. Eso no acredita entrega, acceso, recepción, demanda ni desabastecimiento actual. La posición de descarga y la precisión siguen desconocidas; `representa_punto_atencion=null` se conserva.

El contexto de ejecución, vehículos, depósito, matriz y necesidades tienen `origen=sintetico`. Sus UUID de ejecución, incidentes, plan, depósito y vehículos son nuevos y estables para este ensayo; no identifican recursos operativos. Las horas, población y cantidades de necesidad fueron inventadas explícitamente para pruebas; no proceden de reportes ni de sumar mensajes. No hay confirmaciones ficticias de coordinador.

## Seis puntos y cantidades de ensayo

| Distrito | Referencia de instalación | UUID de punto | Demanda sintética |
| --- | --- | --- | ---: |
| Arraiján | Junta Comunal Nuevo Arraiján | `920f8af3-1bfe-5ab6-a4f2-7fbcb323825e` | 2500 L |
| Arraiján | Junta Comunal de Vista Alegre | `1e35ede2-8fc7-51b0-8830-6eec337f6a24` | 3000 L |
| Arraiján | C.E.B.G. Burunga | `66597297-f57e-54ac-b7f1-7a66cc35253f` | 3500 L |
| La Chorrera | Escuela El Coco | `9459ff87-0377-5622-8255-caaf79dc9898` | 2500 L |
| La Chorrera | C.E. Virgen de Guadalupe | `4b89af3e-444a-5103-880c-fe1c886530ed` | 3000 L |
| La Chorrera | Centro Educativo Guillermo Endara | `b2478919-28e8-592d-ae1f-c450057cb229` | 3500 L |

Total: 18 000 L de ensayo. Las seis necesidades quedan pendientes; ninguna entra como demanda validada ni recibe puntaje. No se deduce criticidad por ser escuela o junta comunal.

## Parámetros propuestos, sin aprobación operativa

- Dos cisternas ficticias de 10 000 L cada una; disponibilidad solo de ensayo.
- Turnos y ventanas de 08:00 a 12:00 del 17 de octubre de 2026, UTC−05:00.
- Descarga propuesta de diez minutos por punto, separada del tiempo de viaje.
- Depósito ficticio en 8.9, −79.74: posición arbitraria, sin instalación o capacidad de carga verificada.
- Recepción desconocida (`null`) en los seis puntos; no convertirla a cero ni a una capacidad aprobada.
- Política `oeste-1.0-politica-propuesta-1`: pesos 50/30/20 y topes 168 horas/500 personas heredados del ejemplo solo como propuesta. Estado `propuesta_demo`, sin activación. No son normas oficiales.
- Una salida por cisterna, retorno dentro del turno, sin recargas y sin dividir la demanda de un punto.

## Matriz sintética de siete nodos

La matriz está dentro de `solicitud_rutas.json`, en `matriz`. Su versión es `oeste-1.0-ensayo-1-matriz-1`. `nodos_ids` fija el orden: depósito, Nuevo Arraiján, Vista Alegre, Burunga, El Coco, Virgen de Guadalupe y Guillermo Endara.

Es una tabla manual arbitraria de minutos con diagonal cero; no usa distancias, coordenadas, velocidad, rutas viales, tráfico ni un proveedor externo. No afirma que los trayectos existan o que una cisterna pueda acceder. Las coordenadas documentales no validan esta tabla. El solver debe asociarla por UUID, no por posición en el CSV. Revisar y versionar la matriz al cambiar nodos o tiempos.

## Comprobación local

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe scripts/verificar_escenario_v3.py
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_escenario_territorial_v3.py -q
```

El comprobador verifica los contratos, catálogo, UUID, origen, versiones y coherencia de supuestos, y llama `validate_need` para demostrar que falta confirmación y recepción. No calcula rutas ni sustituye `verify_plan`. No lee secretos ni se conecta a servicios.

La evidencia de esta preparación está en `evals/resultados/escenario_territorial_v3.json` y `bloque3_v3_pruebas.xml`. Para guardar otra ejecución, usar `--salida ruta_nueva.json`; no sobrescribe resultados existentes.

## Qué sigue pendiente

José con Emilia y el usuario deben acordar depósito, flota, demandas, recepción, criticidad, vulnerabilidad, ventanas, descargas, política y aceptación de los tiempos del ensayo. Una decisión nueva requiere actualizar versión y evidencias; el script no confirma datos automáticamente.

El solver mínimo V1 acepta exclusivamente puntos sintéticos y confirmados: este escenario mixto y pendiente no debe enviarse a él ni transformarse para eludir sus comprobaciones. Los bloques 4 y 5 se implementaron después de esta preparación; ver [PLAN_V3](../../../calculo/PLAN_V3.md). Este fixture pendiente no se convirtió automáticamente en uno válido para rutas. Sus archivos no acreditan plan calculado, verificación, aprobación, publicación ni cierre conjunto V3.
