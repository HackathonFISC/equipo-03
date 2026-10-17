# Relevo para Noel del puente A1

El usuario confirmó el flujo que recibe quejas y calcula escenarios usando
recursos ficticios por falta de datos verificados de IDAAN. Conservar la procedencia
de cada hecho y separar el modo ensayo. No se requiere convertir incidentes reales
a sintéticos para construir el escenario. Las cuatro herramientas y sus contratos
se conservan; la nueva persistencia va en 0016, después de 0015.

## Captura de origen y estado de la revisión

1. **Captura y conservación de origen.** En api/servicios/reportes.py sigue
   ORIGEN='sintetico' para todos los reportes. Una situación simulada sigue siendo
   sintética; una queja sobre hechos declarados reales conserva origen real.
   El chat de prueba y el modo ensayo no deciden por sí solos esa procedencia.
   Definir una clasificación explícita en la captura/metadata del adaptador;
   no inferirla de instrucciones en texto ni conceder permisos por origen.
   Al reutilizar un reporte o crear su ejecución, derivar el origen del registro
   persistido; la respuesta también debe devolver ese valor. No cambiar masivamente
   filas históricas. Si una clasificación fue incorrecta, revisar evidencia y
   registrar su corrección, versiones y cálculos afectados.
2. **Recepción revisada: resuelto por Noel en f1fe718.** RevisionIncidente ya
   incluye capacidad_recepcion_litros y _entrada la pasa a SolicitudValidarNecesidad;
   el panel incorpora el formulario. Se conservó íntegro ese commit al integrar A1.
   Para datos hipotéticos, seguir declarando fuente/supuesto del ensayo; una cantidad
   confirmada en el formulario no acredita recepción física en campo.

La integración local de Emilia usó revisiones completas de fixture para comprobar
el puente; no sustituye el recorrido integrado con el formulario nuevo de tu ruta/panel. No se editaron
tus archivos para anticipar el acuerdo.

## Cómo se conecta tu ruta

Conservar POST /ejecuciones/{id}/priorizacion, la sesión y la política activa
seleccionada. Una vez calculadas y persistidas las necesidades, 0016 encola el
puente y el trabajador lo procesa automáticamente. No necesitas llamar a
ra_preparar_ensayo_v3 ni crear otra ejecución. La misma ejecución conserva ingesta,
territorial, priorización, planificación y comunicación.

ra_incidentes_contexto_v2 conserva su firma, pero ahora el ámbito se divide por
origen de la ejecución y ensayo. Se sigue exigiendo el ámbito completo, un incidente
por punto. No sumar ni elegir entre episodios conflictivos. Las otras procedencias
no se borran ni se reclasifican.

Las nuevas RPC de puente son backend/service_role. No exponer un endpoint que
admita un snapshot, un UID libre o una solicitud de plan como autorización.
La API de revisión sigue siendo la entrada humana; el trabajador no aprueba.

## Qué muestra y qué comunica

- Reporte/incidente/necesidad y ejecución: procedencia original.
- Escenario y plan de este puente: origen sintético y modo ensayo por recursos
  ficticios, aunque haya antecedentes reales. Mostrar «Reporte real declarado ·
  Recursos sintéticos · Propuesta de ensayo» cuando corresponda.
- Sigue vigente la restricción de 0012: aprobación humana de la versión y snapshot,
  selección por sector, suscripción activa y destino de ensayo autorizado.
  No se amplía aprobación o envío operativo real. No hace falta debilitar las
  guardas existentes para que un reporte real participe en este ensayo.
- Aviso de prueba, sin prometer asignación de IDAAN ni entrega física. Su contenido
  permanece ligado a litros, ventana, plan y versión aprobados.
- AVISOS_ACTIVOS permanece false hasta los controles conjuntos; la activación
  temporal de la prueba final sigue a tu cargo.

## Estado de validación

0014/0015 y sus smoke: confirmados por el usuario en Supabase. 0016 y su smoke:
probados localmente; aplicación remota pendiente. Suite candidata final sobre f1fe718: 846 pruebas y
66 subpruebas. Integración local de cinco agentes, 15 000 L y seis avisos preparada
con proveedor y aprobación simulados. No hay acuse real de Telegram acreditado.

Antes de las 10:00 comprobar juntos al menos un recorrido real en el chat de prueba.
El recorrido corto aprobación→aviso sigue siendo un respaldo rotulado si falta
el enlace de captura/revisión. Las 11:30 son referencia interna pendiente de
confirmación organizativa; no se presenta esa hora como regla nueva del evento.
