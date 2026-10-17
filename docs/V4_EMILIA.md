# V4: Comunicación, vigencia por sector y lectura consistente

Entrega backend de Emilia. Noel mantiene exclusivamente `api/`, `bot/` y
`frontend/`; esas carpetas no se modifican aquí. José mantiene solver y verificador.
No se aplica SQL ni se envían mensajes al ejecutar pruebas locales.

## Flujo y límite de alcance

1. Noel verifica el token de Supabase y deriva usuario_id de esa identidad.
2. `ra_aprobar_plan` de Noel valida la propuesta persistida y su revisión humana;
   deja la ejecución `pendiente/comunicacion`. No aceptar snapshot, rol o usuario
   del navegador como autoridad. El JSON `planes.propuesta` conserva la propuesta
   histórica; el estado aprobado y su aprobación se leen de las filas autorizadas.
3. La coordinadora selecciona explícitamente el plan aprobado por sector mediante
   `ra_seleccionar_plan_sector_v4`. Esta selección única resuelve la ambigüedad entre
   planes diferentes; no se elige el mayor número ni la fecha más reciente.
   Noel puede incorporar esta operación a su recorrido de revisión. Sin selección
   de todos los sectores que tienen paradas, Comunicación espera validación.
4. El trabajador llama al agente `agentes/comunicacion.py`. Su herramienta
   `ra_comunicar_plan_v4` comprueba vigencia y crea avisos en una transacción.
   La clave única sigue siendo `plan:versión:sector:punto:destino:tipo`.
5. El bot de Noel reserva la bandeja y envía. Se conserva la firma de su reserva,
   con comprobación adicional de snapshot, plan seleccionado y destino de ensayo.
   El acuse de Telegram no acredita entrega de agua. Comunicación completada
   significa bandeja creada; consultar estado_envio por separado.
6. `ra_estado_sector_v4` proyecta el contrato EstadoSector desde una lectura
   consistente: todos los puntos activos, litros/ventanas null sin asignación,
   sin cantidades de un plan invalidado y sin datos de remitentes o chats.

Comunicación es un agente con reglas explícitas y herramienta que escribe en BD.
No necesita que un LLM vuelva a redactar cantidades aprobadas. Ingesta y
Planificación conservan su intervención de Gemini. Esta entrega no conecta por
sí sola las necesidades ciudadanas V2 con un escenario operativo de V3.

## Sintéticos y destinos

Decisión de Emilia: demo exclusivamente en chat de prueba autorizado. Un plan
sintético nunca se comunica a una suscripción comunitaria ordinaria.

La autorización previa en `destinos` y suscripción activa no bastan para un
sintético: `destinos_ensayo_v4` exige habilitación explícita por coordinador activo.
La migración no crea ni habilita filas. No se infiere un chat de prueba por nombre.
`ra_configurar_destino_ensayo_v4` exige que el destino Telegram ya esté autorizado;
el UID viene del token de Noel o de una operación administrativa revisada.

El texto guardado y el nombre proyectado hacia la plantilla actual del bot llevan
`ENSAYO SINTÉTICO, SIN ENTREGA REAL`. No se modifica el nombre del catálogo ni se
introducen campos incompatibles en AvisoPorEnviar. El reconocimiento humano de
los bloqueos admitidos por 0003 aprueba exclusivamente la demostración sintética;
no valida datos de campo, agua, infraestructura ni una operación comunitaria.

Si falta un destino permitido en cualquier sector con parada, la ejecución queda
`espera_validacion/comunicacion`, sin generar una bandeja parcial. Al habilitar el
chat de ensayo se reanudan las ejecuciones que esperaban ese destino; no se
reactivan cierres completados. Tras configurar destinos reales fuera del ensayo,
la reanudación exige operación backend explícita; no hay reintento de envíos.

## SQL y orden

No reinstalar migraciones existentes. Orden de dependencias:
0009 Planificación → 0010 ensayo V2 → 0011 bandeja de Noel → 0003 aprobación de
Noel → **0012_comunicacion_v4.sql** → smoke completo 0012 con ROLLBACK.
Los archivos históricos `0009_bandeja_salida.sql` y `0010_bandeja_salida.sql`
no se aplican junto con 0011. Consultar el README existente de migraciones.

0012 crea tres tablas con RLS y RPC exclusivas de service_role. No añade políticas
públicas ni modifica cuentas. Añade comprobaciones a `ra_reservar_aviso` manteniendo
parámetros y forma de salida; Noel debe revisar esta extensión de su interfaz.
**No sustituye ni modifica ra_aprobar_plan o el archivo 0003 de Noel.**

Se serializan de forma conservadora lecturas, autorizaciones y escrituras de
entradas mediante un bloqueo transaccional común. Es adecuado para el MVP, no una
solución de alto volumen. Cambios de entradas invalidan planes aprobados y cancelan
avisos pendientes aún no reservados; cambios de asignación también invalidan.
Actualizar solo el estado de una parada no cambia su asignación. Un envío ya
reservado puede haber sido autorizado antes del cambio: se conserva esa historia,
la incertidumbre y el resultado del proveedor; no se promete retirar un mensaje.

### Ajuste que corresponde a Noel antes de cerrar concurrencia

La RPC 0003 actual lee las entradas antes de adquirir el bloqueo común. Para
serializar también la aprobación, Noel debe añadir como primera operación del
BEGIN de `ra_aprobar_plan` y de `ra_rechazar_plan`, una vez disponible 0012:

```sql
PERFORM public.ra_bloqueo_v4();
```

Antes de devolver una aprobación repetida, comprobar
`ra_plan_valido_v4(pl.plan_id, pl.version)`; si es false, devolver
`version_obsoleta`. Un plan invalidado también debe mapearse a `version_obsoleta`
cuando se intente aprobarlo. No se cambian esas RPC ajenas aquí. Con 0012 vigente,
Comunicación/consulta/reserva ya rechazan el plan obsoleto aunque falte este ajuste,
pero **no está acreditado el rechazo concurrente de aprobación del caso 21**.
Aplicar ambas piezas coordinadamente y probar los dos órdenes de confirmación en
PostgreSQL con dos sesiones. PGlite local no acredita esa concurrencia.

## Firmas para Noel

- `ra_seleccionar_plan_sector_v4(p_usuario_id uuid, p_sector_id uuid, p_plan_id uuid,
  p_version integer, p_motivo text)` → sector_id, plan_id/version en selección nueva,
  repetido. Selección sin aprobación vigente se rechaza.
- `ra_estado_sector_v4(p_sector_id uuid)` → JSON compatible con EstadoSector.
  Noel conserva permisos y transporte HTTP; sector inexistente es
  `contrato_invalido`, no un sector sin plan.
- `ra_configurar_destino_ensayo_v4(p_usuario_id uuid, p_destino_id uuid,
  p_habilitado boolean, p_motivo text)` → destino_id, habilitado.
- `ra_comunicar_plan_v4(p_ejecucion_id uuid, p_trabajador_id text)` → cierre con
  estado, etapa, avisos_creados, plan_id/version, repetido, o espera con código.
  Solo el trabajador la llama. No se suministran litros ni horarios desde el cliente.
- `ra_plan_valido_v4(p_plan_id uuid, p_version integer)` → boolean; uso backend.
- `ra_reservar_aviso(p_trabajador_id text)` conserva la firma y JSON de 0011.

El adaptador Python `agentes.estado_sector.consultar_estado_sector` valida el
JSON con Pydantic y propaga errores de BD: no los convierte a sin_plan_vigente.
Las escrituras deben mapear `sin_permiso` a 403 y `version_obsoleta` a 409 según
D003. Los motivos de espera de Comunicación son estados operativos, no nuevos
valores del enum CodigoError compartido.

## Operación administrativa en macOS

Con el venv activo y desde la raíz:

```bash
python -m scripts.operar_v4 estado-sector --sector-id UUID
python -m scripts.operar_v4 seleccionar-plan --coordinador-uid UUID --sector-id UUID --plan-id UUID --version 1 --motivo 'Plan revisado para este sector'
python -m scripts.operar_v4 destino-ensayo --coordinador-uid UUID --destino-id UUID --habilitar --motivo 'Solo chat autorizado de ensayo'
```

No incluyen aprobación automática ni Telegram. En el entorno local administrado
la identidad se pasa explícitamente; estas órdenes no son un mecanismo de login.
La API debe obtener siempre esa identidad del token verificado. No activar un
trabajador adicional si la API de Noel ya administra uno.

## Verificación y pendientes de cierre

Pruebas Python de despacho, consulta y errores; smoke SQL transaccional de
permisos, selección, puntos sin asignación, aislamiento sintético, deduplicación,
reserva, incertidumbre e invalidación. Recorrido local con solver/verificador
reales, persistencia V3, aprobación simulada, seis avisos y seis acuses simulados.
Los acuses de ese ensayo **no son mensajes recibidos en Telegram**. No se usa
Gemini real en esta verificación V4 (decisor de reglas explícito).

Pendientes externos: integración API/panel de Noel, ajuste de concurrencia de sus
RPC, aplicar SQL en Supabase, seleccionar el destino de prueba por UUID y probar
el recorrido con mensaje recibido. José comprueba los casos oficiales 18/20/21
según evals/V4.md. No dar V4 integrada por cerrada solo por estos tests locales.
