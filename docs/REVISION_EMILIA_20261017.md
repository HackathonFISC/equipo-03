# Revisión de Emilia del 17 de octubre

Actualización A1 del 17/10: ver [puente de necesidades persistidas](A1_PUENTE_NECESIDADES.md)
y [relevo a Noel](HANDOFF_NOEL_A1.md). La nueva 0016 conserva la procedencia del
reporte y conecta la misma ejecución con un escenario de ensayo usando recursos
ficticios. El cuerpo histórico siguiente describe la entrega anterior; no acredita
aplicación remota ni resuelve los ajustes de captura/recepción de Noel.

Base inspeccionada: rama `Emilia`, commit `1875234`, árbol limpio. Hora inicial confirmada por el usuario: 06:14 de Panamá. Cierre de funciones previsto: 11:30; entrega interna: 12:30. Los Word son referencias del plan del 16 de octubre; las decisiones posteriores del repositorio precisan su alcance. Este documento no activa políticas ni valida supuestos operativos.

## Respuestas documentadas sobre el escenario

- Plan maestro, secciones 2, 4 y 5: seis lugares, dos cisternas y un depósito; demanda estimada, litros asignados y litros entregados separados. Recomienda aprobar seis demandas sintéticas fijas. No fija capacidades, reservas ni ventanas. 40 % duración, 30 % población y 30 % vulnerabilidad es una hipótesis pendiente de adopción.
- Versiones de implementación, V2/V3 y sección 12: exige decisiones explícitas de política y escenario. Sus afirmaciones de piezas todavía no implementadas describen el momento de redacción, no el estado actual del código.
- D007 en `docs/decisiones.md`: ya consta aprobación del alcance de tres puntos de Arraiján y tres de La Chorrera. Los lugares son referencias documentales AIG 2022; acceso, posición de descarga, precisión y capacidad operativa siguen pendientes. No volver a pedir aprobación del alcance 3+3 como si no existiera ese registro.
- D011/D012 y `docs/politica_prioridad_oeste.md`: propuesta posterior de 40 % vulnerabilidad, 40 % duración y 20 % personas; críticos confirmados primero, escalas de 168 horas y 500 personas. `politica_apoyo_panama_v1.json` está en `propuesta_demo`, con confirmación nula. El fixture 3 activa solo su copia con identidad ficticia. No hay evidencia nueva de cuál está activa en Supabase.
- `datos/escenario/oeste-1.0-ensayo-3/escenario_fixture.json`: origen sintético; dos vehículos de 10 000 L, turno 08:00–12:00 UTC−05:00, depósito ficticio en 8.9, −79.74. Matriz manual de siete nodos. Demandas de grupos ficticios: 860 personas, 17 200 L brutos menos 2200 L de reserva = 15 000 L netos. Hipótesis de 20 L/persona por un día, cinco personas por familia y descarga de 300 L/min más cinco minutos. No son mediciones de las instalaciones.

| Referencia documental | Demanda sintética |
| --- | ---: |
| Junta Comunal Nuevo Arraiján | 3000 L |
| Junta Comunal de Vista Alegre | 3000 L |
| C.E.B.G. Burunga | 2000 L |
| Escuela El Coco | 2500 L |
| C.E. Virgen de Guadalupe | 3000 L |
| Centro Educativo Guillermo Endara | 1500 L |

Los ensayos anteriores se conservan: V0 contiene 18 000 L y política 50/30/20 propuesta; no mezclarlos con el ensayo 3. Tener una copia activa para pruebas no acredita aprobación humana ni política operativa. El escenario disponible permite seguir pruebas sintéticas sin inventar valores nuevos.

## Diseño A1 para coordinar con Noel

1. Una ruta autenticada de coordinador, propiedad de Noel, deriva el UID del token. Recibe una revisión consolidada y versionada, nunca un UID o aprobación como autoridad del navegador.
2. Servicio backend obtiene ejecución, ámbito completo de `ra_incidentes_contexto_v2` y política activa seleccionada por versión desde `politicas_prioridad`. No elige porcentajes ni activa una fila. Si hay varias políticas activas, exige selección explícita; si no hay una compatible, conserva el bloqueo.
3. Construye entradas revisadas por incidente: `version_incidente`, `solicitud_demanda` y `evaluacion`. Conserva desconocidos, evidencia y confirmaciones humanas; no deriva demanda, clase o vulnerabilidad del número de reportes. No introduce automáticamente los números del fixture en incidentes ciudadanos.
4. Un incidente por punto y todos los incidentes del ámbito, sin mezclar orígenes. Dos episodios de un punto bloquean hasta revisión. Invoca `ra_preparar_priorizacion_v2`; la RPC vuelve a validar rol, política, versiones, ámbito e idempotencia en transacción. Un cambio exige nueva `datos_version`.
5. Trabajador ejecuta `validate_need` y `score_needs`; persiste también los pendientes con motivos. No aprueba.
6. El puente hacia rutas debe tomar las evaluaciones persistidas vigentes, infraestructura revisada, servicios y matriz del mismo escenario. Requiere una RPC nueva: `ra_preparar_ensayo_v3` actual inserta incidentes nuevos y política exclusiva; reutilizarla duplicaría o separaría la historia. Preservar la misma ejecución y referencias en los cinco agentes exige diseñar ese registro, su snapshot y sus guardas de vigencia conjuntamente con Noel.
7. La implementación vigente permite planificación sintética solamente. Para la demo puede mantenerse un ensayo sintético completo con chat autorizado; un reporte real no se convierte en sintético para eludir esta guarda. Origen estimado/real termina en revisión controlada. Aún no existe evidencia del recorrido continuo Telegram → necesidad revisada → plan bajo una sola ejecución.

Antes de implementar el puente: confirmar con Noel la ruta, la identidad autenticada y la estrategia transaccional que conserva ejecución e historial; verificar la política activa del entorno. No se modificaron `api/` ni los contratos para anticipar ese acuerdo.

## Hallazgos y estado del lote de correcciones

| Elemento | Evidencia local | Estado |
| --- | --- | --- |
| A1 lote revisado | RPC 0010 existe; no hay llamada Python/API productiva a `ra_preparar_priorizacion_v2` | Diseño, implementación e integración pendientes |
| A2 trabajador | Mantenimiento/selección fuera del bucle protegido; excepciones de etapa silenciadas | Corrección preparada: recuperación acotada, marca por propietario y señal de última vuelta; exposición HTTP pendiente de Noel |
| A3 Comunicación | Mantenimiento de 0009 excluye Comunicación | Nueva 0014 y smoke preparados; ejecución SQL pendiente |
| A4 Ingesta | Regresiones reproducidas y corregidas; evidencia normalizada y cantidades conservadoras | Implementado con 0015 y smoke aprobados localmente; aplicación remota pendiente |
| A5 origen | `planificar` lanzaba ValueError | Revisión controlada con traza; solver y decisor no se invocan |
| A6 entornos | Código no acredita migraciones, roles o destino remoto | Pendiente con Noel; avisos permanecen desactivados |
| B1 traza única | V2 y fixture V3 separados; V4 documenta ese límite | Parcial; falta recorrido persistido bajo una ejecución |
| B2 retiro | `calculo/replanificacion.py` simula snapshot; D016 declara que no invalida BD | Persistencia e integración pendientes; no editar cálculo ajeno |
| B3 pruebas | Suite base 737 y 66 subpruebas aprobadas | No equivale a 25 casos integrados ejecutados |
| B4 catálogo | CSV con seis puntos, fuente, coordenadas y validación pendiente | Alcance 3+3 registrado; verificación operativa pendiente |
| B5 documentación | Arquitectura, guion y V4 existen | Parcial; no declarar cierre integrado |
| B6 entrega | D017 y ENTREGA_V6 distinguen auditoría local y ejecución real | Clonado limpio, tres recorridos, auditoría final y tag pendientes |
| B7 multimodal | V4 integrada sin acreditar | Posponer extensión |

## HANDOFF para Noel y José

- Noel: integrar el servicio revisado de A1 con sesión de coordinador; acordar puente V2→V3 que conserve ejecución e historial. No se tocaron sus rutas.
- Noel: en `/salud/agentes`, conservar estado y añadir `ultima_vuelta_exitosa` usando `servicio.ultima_vuelta_exitosa()` o null si no existe servicio. Cambiar el tipo de retorno a `dict[str, str | None]`; pruebas de API para null y marca recibida. No interpretar la marca como salud de Telegram/Gemini/Supabase.
- Noel: autenticación ausente confirmada en GET `/incidentes` y GET `/ejecuciones/{id}`; revisar `_vinculados` y su `.in_()` grande. CORS fijo en `api/main.py`.
- Noel: `AVISOS_ACTIVOS = False` confirmado en `bot/bandeja.py`. Propuesta para su módulo: `os.getenv('AVISOS_ACTIVOS', 'false').strip().lower() in {'true','1'}`. Mantener false hasta comprobar migraciones, roles efectivos, selección de sector y destino de ensayo autorizado. No activar desde esta revisión.
- Noel: revisar comparación UUID y texto de origen de Comunicación, null en componentes de Necesidades y datos de ejemplo en Plan. Estos puntos requieren revisión del dueño; no se contabilizan aquí como corregidos.
- Noel/José: retiro antes de salida debe invalidar y versionar en transacción antes de recalcular; revisión humana y nuevo aviso, preservando avisos enviados/inciertos e historial. No llamar una simulación local «replanificación persistida».
- José: regenerar bitácora consolidada tras cambiar la fuente de Emilia; la consolidación pertenece a sus archivos. Repetir auditoría sobre el commit final efectivo.
- Equipo: aplicar 0014 una sola vez tras revisar dependencias; ejecutar smoke en entorno aislado. No editar migraciones históricas. Confirmar efectos con roles reales; no inferir ausencia de RLS porque falte un nombre de archivo 0002.

## Verificación

Base: 737 pruebas + 66 subpruebas, cuatro advertencias de dependencias. Pruebas específicas del candidato: 36 aprobadas. Suite completa del candidato: 743 pruebas + 66 subpruebas, cuatro advertencias de dependencias. SQL 0014, Supabase remoto, Gemini/Telegram reales, roles efectivos, concurrencia, tres recorridos y recepción de avisos no ejecutados en esta revisión. No hay despliegue, activación, aprobación ni entrega física acreditados. La preparación y pruebas se hicieron en copia aislada. El estado Git del repositorio determina si se integró después el candidato; este informe no acredita commit ni despliegue.
