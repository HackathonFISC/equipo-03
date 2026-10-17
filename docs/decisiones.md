# Decisiones de H2Oeste

## D001 Aceptación de contratos por el integrante de tools

- Fecha: 16 de octubre de 2026, 18:58 (UTC−05:00).
- Solicitud: el usuario pidió confirmar la aceptación de los contratos desde nuestro rol de integrante 3, José.
- Estado: aceptación técnica de José registrada por instrucción del usuario. La aceptación conjunta de Emilia y Noel no se acredita con este registro.
- Versión revisada: esquema 1.0, carpeta `contratos/` del commit `3f26ba1a2aee2030d095ce99775f3d8ec4296a97`; árbol de contratos `6b62ee43afa970f85260565ff2d64de87f86815f`.
- Alternativas consideradas: consumir los contratos compartidos de Emilia o crear formatos paralelos para cálculo. Se acepta la primera para mantener integración y evitar duplicación.

Se aceptan las firmas síncronas de `HerramientasCalculo`:

| Función | Entrada | Salida |
| --- | --- | --- |
| validate_need | SolicitudValidarNecesidad | ResultadoValidarNecesidad |
| score_needs | SolicitudPriorizarNecesidades | ResultadoPriorizarNecesidades |
| solve_routes | SolicitudResolverRutas | PropuestaDistribucion |
| verify_plan | SolicitudVerificarPlan | InformeVerificacion |

La revisión incluyó modelos auxiliares, estados, errores, ejemplos y reglas documentadas de demanda, prioridad y rutas. Permiten representar litros, ventanas, descarga, flota disponible, matriz dirigida con arcos bloqueados, demanda pendiente, déficit, timeout y versiones. El verificador recibe la solicitud original completa, permitiendo contrastar las restricciones sin depender del resultado del solver.

Evidencia ejecutada: 43 pruebas de contratos y 24 subpruebas aprobadas; verificador local del escenario correcto con Python 3.12.14 y Pydantic 2.14.1. No se encontraron impedimentos de interfaz para implementar las cuatro tools dentro del alcance del MVP. Las pruebas estructurales no sustituyen nuestras pruebas futuras de cálculo, solver ni autorización.

Efecto: estos modelos serán la interfaz de implementación de José. No se modificaron archivos de Emilia ni se crearon modelos alternativos. Todo cambio posterior de interfaz requiere coordinación y actualización de ejemplos.

Límites: aceptar el contrato no activa la política `demo-1.0`, no confirma los valores sintéticos ni concede permisos de coordinador. El cálculo debe rechazar una política no activa y conservar necesidades pendientes y déficit crítico. La versión de Python de las otras laptops y su instalación siguen pendientes de comprobación conjunta. No se declara cerrada V0 del equipo: todavía requiere la aceptación de los otros integrantes y evidencia de esquema, Gemini y API según el plan.

## D002 Ensayo local de solver mínimo V1

- Fecha: 16 de octubre de 2026, 19:31 (UTC−05:00).
- Solicitud: el usuario indicó comenzar V1. Se implementa la parte aislada de José; no se afirma cierre de V0 o V1 del equipo ni se integra automáticamente a main.
- Decisión técnica: `solve_routes_minimo` reutiliza `SolicitudResolverRutas` y `PropuestaDistribucion` sin cambiar contratos. Exige datos sintéticos con demandas y ranking de ensayo completos. Usa el fixture de Emilia con sus confirmaciones explícitamente ficticias; no activa ni altera los archivos pendientes de V0.
- Alternativas: adelantar la selección parcial por prioridad de V3 o resolver primero el conjunto completo del ensayo V1. Se adopta la segunda para probar capacidad, ventanas, descarga, disponibilidad, arcos bloqueados y retorno en un modelo acotado.
- Límites: se rechazan entradas operativas reales y datos pendientes. Si no consigue cobertura completa, todas las necesidades quedan visibles, sin rutas y con motivo; no se declara inviabilidad del reparto parcial. La publicación permanece bloqueada, sin aprobación ni verificación independiente. La función operativa `solve_routes`, la selección por prioridad y `verify_plan` se completarán en V3.
- Evidencia: 15 pruebas del solver y 43 de contratos, con 24 subpruebas, aprobadas en conjunto. Ensayo OR-Tools real con seis puntos, dos rutas y 18 000 L; salidas 08:00 y retornos 09:10 UTC−05:00 del escenario. Entrada, resultado y métricas guardados en evals/resultados/solver_minimo_v1.json; ejecución de pruebas en v1_pruebas.xml. El test de timeout inyecta un estado simulado y no acredita agotamiento real del motor.
- Integración pendiente: Noel revisa el cálculo, Emilia conoce el alcance antes de registrar tools, y el equipo demuestra el recorrido de primer reporte V1. El usuario realiza commit/push manualmente.

## D003 Acuerdo de integración comunicado por Noel

- Fecha: 16 de octubre de 2026, 20:23 (UTC−05:00).
- Estado: aceptación de los tres integrantes comunicada por Noel, con la aprobación de José (indicada por Noel) a las 20:33 (UTC−05:00). La confirmación escrita de Emilia no consta en este registro.
- Aceptado sin cambios: contrato `estado_sector` (`ESTADO_SECTOR.md`); clave de idempotencia de avisos con `punto_atencion_id`; identidad de remitentes con `mensaje_externo_id = "<chat_id>:<message_id>"` (`supabase/IDENTIDAD_REPORTES.md`).
- Aceptado como propuesta de Noel: todos los reportes de V1 se guardan con origen `"sintetico"`; errores de dominio a HTTP: 422 (`contrato_invalido`, `datos_insuficientes`, `ubicacion_ambigua`, `fuera_de_area`), 403 (`sin_permiso`), 409 (`politica_no_activa`, `version_obsoleta`, `plan_no_verificado`, `cobertura_critica_pendiente`), 503 (`proveedor_no_disponible`), 502 (`envio_incierto`), con el `ErrorDominio` completo como cuerpo.
- Python: sin impedimento declarado; no se fija una versión obligatoria.

## D004 Implementación local de demanda y prioridad V2

- Fecha: 16 de octubre de 2026, 21:55 (UTC−05:00).
- Solicitud: el usuario indicó comenzar V2. Se implementa la parte de cálculo de José sobre los contratos existentes, sin modificar agentes, API, esquema ni política compartida.
- Resultado: `calculo.demanda.validate_need` y `calculo.prioridad.score_needs` disponibles como funciones puras síncronas. Demanda directa y fórmula, recepción, confirmaciones, faltantes, criticidad, puntaje configurable, escalas fijas y desempate según política de demo.
- Alternativas: rellenar ausencias para producir un ranking completo o conservar las necesidades pendientes. Se conserva la segunda conforme al plan. Los motivos de revisión existentes no se eliminan salvo el marcador técnico del ejemplo compartido que indica cálculo aún no ejecutado; el integrador retira observaciones resueltas de forma explícita.
- Límites: el formato de una confirmación no verifica permisos humanos. Política no activa produce `ExcepcionContrato`/`politica_no_activa`; Noel adapta el error al HTTP acordado al integrar las tools. Ninguna cifra por encima del tope del puntaje se rechaza automáticamente: solo se satura el componente, se preserva el dato y se alerta para revisión. No se añaden umbrales operativos de rechazo.
- Origen (implementación inicial; ajustado por D009): el contrato actual solo define políticas sintéticas. Inicialmente se etiquetaban también las evaluaciones como sintéticas. D009 conserva la procedencia individual y conserva también el origen de la ejecución, con advertencia explícita de política sintética y ensayo.
- Evidencia: 43 pruebas nuevas de V2; regresión de 204 pruebas y 57 subpruebas aprobadas, pip check correcto. Demo: 2500 L directos, 1500 L por fórmula, demanda desconocida sin reserva, seis puntos priorizados con confirmaciones ficticias y seis necesidades originales V0 conservadas pendientes. Entrada/salida y métricas en `evals/resultados/necesidades_v2.json`; ejecución de pruebas en `v2_pruebas.xml`.
- Supuesto exclusivo del ensayo: recepción sintética de 5000 L por punto para probar las seis demandas del fixture. No se incorpora a los archivos compartidos de escenario ni se considera aprobado para operación.
- Pendiente para cierre conjunto: Emilia integra tools, territorio, incidentes y reanudación; Noel conecta aclaraciones y errores. Acordar parámetros/activación de política del escenario. La regresión de repetición de quejas cubre cálculo e invariancia de factores; el recorrido real de duplicados/consolidación sigue siendo prueba de integración del equipo. No se declara cerrada V2 del sistema.

## D005 Reducir espera inicial del solver mínimo

- Fecha: 16 de octubre de 2026, 22:20 (UTC−05:00).
- Origen: el usuario trasladó una revisión de solve_routes_minimo que detectó salida a 06:00 y espera innecesaria hasta 08:00 cuando el turno comienza dos horas antes.
- Decisión: primero minimizar los finales de todos los vehículos y después maximizar sus inicios. No maximizar solo las salidas, porque pospondría el recorrido hacia el final del turno. El ajuste afecta al solver V1, no a validate_need ni score_needs de V2.
- Evidencia: prueba añadida reproduce el fallo antes del cambio; después pasan 17 pruebas del solver. Caso temprano: salida 07:50, primera descarga 08:00, retorno 09:00. Demo base: mismas rutas y horas 08:00–09:10. Regresión completa: 206 pruebas y 57 subpruebas aprobadas.
- Alcance V3 conservado: selección de cobertura parcial por criticidad/prioridad y diagnóstico por punto. La demanda de cada punto sigue indivisible; si excede toda cisterna disponible debe quedar pendiente con motivo demanda_supera_vehiculo. No autoriza dividir esa demanda entre camiones ni introducir recargas.

## D006 Circuito de aclaración de V2 (Noel y Emilia)

Referencia del acuerdo recibido: D004. Se registra como D006 para no duplicar el identificador D004 ya utilizado en este archivo.

- Fecha: 16 de octubre de 2026, 22:35 (UTC−05:00). Acordado entre Noel y Emilia.
- Creación: el orquestador de Emilia crea la aclaración (plantilla según faltantes) y pasa la ejecución a `espera_aclaracion` en una sola operación. Máximo una aclaración activa por ejecución.
- Destino: el `POST /reportes` de Noel registra el chat de origen en `destinos` y lo guarda en `reportes.destino_origen_id` (columna en la migración de Emilia). Las aclaraciones solo van al chat de origen y no requieren autorización de coordinador; los avisos de V4 sí.
- Envío: el bot consulta cada 5–10 s; la API de Noel reserva la aclaración y registra `enviado`, `fallido` o `incierto` mediante RPC de Emilia. Sin reenvío automático de envíos inciertos ni de reservas vencidas: pasan a revisión. El bot no tiene acceso a Supabase.
- Respuesta: solo un reply a la pregunta, en el mismo chat, del mismo remitente del reporte original, también en grupos. Deduplicada por el identificador externo del reply. Texto o ubicación estática (contrato `Ubicacion`, fuente `"compartida"`, sin validar punto de entrega).
- Reanudación: una RPC de Emilia, llamada por la API, valida, guarda la respuesta, cierra la aclaración, registra la traza y devuelve la ejecución a `pendiente/ingesta` de forma atómica. Un reply repetido no sobrescribe ni reactiva.
- Caducidad: 30 minutos desde `enviado_en`, configurable. Al vencer, la ejecución pasa a `espera_revision`. Una respuesta tardía se rechaza con el resultado `"vencida"`.
- Resultados de la RPC de respuesta: `aceptada`, `repetida`, `ya_respondida`, `autor_distinto`, `no_encontrada`, `vencida`.
## D007 Alcance de geografía de la demo

Referencia de la versión recibida de main: D004. Se registra como D007 para conservar el identificador local de la implementación V2 sin perder este acuerdo.

- Fecha: 2026-10-16 22:08 EST.
- Decisión del usuario: confirmó «seis puntos totales, tres por distrito» para
  Arraiján y La Chorrera, autorizando preparar catálogo y semilla.
- Se conservan dos cisternas y un depósito. No se amplía el número máximo de
  puntos por solicitud de rutas ni se modifican contratos.
- Catálogo documental inicial: oeste-1.0, con seis instalaciones candidatas y
  nuevas identidades estables. Fuente AIG enero 2022 con coordenadas, páginas y PA.
- El alcance está aprobado; acceso, lugar de descarga, autorización, precisión,
  capacidad de recepción y demanda operativa siguen pendientes. Las referencias
  geográficas no se presentan como un ranking IDAAN ni como necesidad actual.
- Efecto: `datos/geografia/puntos.csv`, `alias.csv` y semilla 01. José debe
  coordinar el siguiente escenario y matriz con estos UUID antes de calcular
  rutas para el nuevo catálogo. Los fixtures sintéticos V0/V1 no se reasignan.
- Comprobación local: siete pruebas Python; semilla y smoke ejecutados en
  PostgreSQL temporal, reejecución conservadora, alias y correspondencia CSV/SQL,
  guardas de identidad y conservación de otras filas. No se aplicó SQL a Supabase real.

## D008 Aclaraciones y caducidad de V2

Referencia de la versión recibida de main: D005. Se registra como D008 para conservar el identificador local de la corrección del solver. Complementa el circuito D006; ambos registros del acuerdo se conservan con sus fechas y procedencia.

- Fecha de registro: 2026-10-16T22:47-05:00.
- Usuario comunicó acuerdo con Noel: aclaración creada por orquestador, máximo una activa por ejecución; bot llama API y API ejecuta RPC con service_role.
- Reply válido: chat de origen, mensaje de pregunta y autor original, también en grupos. Deduplicar chat:message_id; no sobrescribir respuesta aceptada.
- Se acepta texto o ubicación estática compartida como reply. Ubicación no crea ni valida un lugar de entrega.
- Usuario aprobó 30 minutos desde envío confirmado, configurable. Al vencer pasa a espera_revision, conserva evidencia y genera alerta; resultado vencida no reactiva nada.
- Reservas vencidas y envíos inciertos requieren revisión, sin reenvío automático. Fallidos también se dejan visibles para revisión.
- Implementación local: migraciones 0006/0007 y docs/V2_EMILIA.md. No acredita aplicación remota ni integración del bot de Noel.

## D009 Compatibilidad de priorización y conservación del origen V2

- Fecha: 16 de octubre de 2026 (UTC−05:00).
- Solicitud: José autorizó trabajar los pendientes de prioridad y origen detectados tras el pull de main 2815e91. Es una corrección local de nuestras tools; no atribuye aceptación a los otros integrantes.
- Problemas reproducidos: el adaptador añade `prioridad_por_calcular`, que nuestra tool conservaba como una falta real; además, cambiar el origen de cada evaluación a sintético provocaba rechazo por modificar datos consolidados cuando la entrada era real o estimada.
- Decisión: reconocer exactamente ese marcador y el del ejemplo compartido como preparación de cálculo. Conservar los demás motivos y ejecutar las comprobaciones habituales de demanda y factores; retirar el marcador no valida información incompleta.
- Origen: conservar `EvaluacionNecesidades.origen` por necesidad, también en lotes mixtos y pendientes. El contexto del resultado conserva `entrada.origen`, tal como exige la RPC `ra_finalizar_priorizacion_v2` en la migración 0007. Una alerta identifica la política sintética y su versión y aclara que el ensayo no constituye autorización operativa. El campo origen expresa procedencia de datos, no aprobación de la política. Sustituye la interpretación inicial de D004 sin ampliar el contrato.
- Integración: probar el adaptador existente con `HerramientasJose` y nuestras funciones reales, para los tres orígenes y con confirmación u observación pendientes. Los fixtures con campo origen real son casos de prueba, no evidencia de datos reales. No se modifican archivos de Emilia o Noel, política, parámetros, permisos o servicios remotos.
- Evidencia: `evals/resultados/integracion_prioridad_v2.json` y `v2_integracion_prioridad_pruebas.xml`. La integración persistida, activación de aclaraciones, panel y cierre conjunto V2 siguen pendientes.

## D010 Preparación del escenario territorial para V3

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José autorizó trabajar el bloque 3 y comprobar catálogo/UUID de Emilia. Se prepara `datos/escenario/oeste-1.0-ensayo-1/` sin importar cambios del ZIP de Noel.
- Alcance: seis puntos de oeste-1.0 (tres por distrito), dos cisternas ficticias, depósito ficticio, demanda directa de ensayo, ventanas/descargas propuestas y matriz manual sintética de siete nodos. Se conservan íntegros catálogo, contratos y fixtures históricos.
- Procedencia: puntos reales solo como referencia documental AIG 2022, sin validar recepción o descarga. Necesidades y demás parámetros de prueba sintéticos, con nuevas identidades de ensayo salvo los UUID de punto/sector del catálogo. No se atribuyen demandas actuales a esas instalaciones.
- Cantidades propuestas: 18 000 L totales, dos capacidades de 10 000 L, turno/ventanas 08:00–12:00 UTC−05:00, descargas de diez minutos. Depósito y tiempos de viaje arbitrarios, sin geometría vial ni estimación física. Estos valores no quedan aprobados por crear los archivos.
- Pendientes conservados: seis demandas sin confirmación, recepción desconocida, clase/vulnerabilidad sin confirmar y política propuesta sin activación. No se añaden confirmaciones de coordinador ni se modifica Supabase.
- Comprobación: script local valida estructura y coherencia contra catálogo, y ejecuta validate_need; no es verify_plan ni acredita factibilidad. Evidencias separadas en `escenario_territorial_v3.json` y `bloque3_v3_pruebas.xml`.
- Límite: preparación técnica del bloque 3; confirmación de parámetros, solver completo, verificador e integración del equipo siguen pendientes. El solver mínimo V1 no admite este escenario mixto y pendiente; no se eluden sus guardas para fabricar rutas.

## D011 Ponderaciones del proyecto con apoyo en referencias panameñas

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José pidió construir políticas/ponderaciones apoyadas en las fuentes oficiales investigadas. Se define una propuesta técnica del proyecto; no se atribuye aprobación a IDAAN, ASEP, MINSA ni a un coordinador.
- Selección técnica: clase crítica confirmada antes de general; dentro de cada clase, 40 % vulnerabilidad, 40 % duración y 20 % personas atendidas. Se aumenta vulnerabilidad frente al ensayo 50/30/20. Se conservan las escalas técnicas de 168 horas y 500 personas, valor moderado 0.5 y desempate existente. Estos números no vienen impuestos por las normas consultadas ni son resultado de calibración empírica.
- Apoyo: antecedente operativo IDAAN/SERTV de 2026 para atención sanitaria prioritaria; ASEP AN 1480-Agua y DGNTI-COPANIT 21-2019 con reforma 122/2021 para requisitos sanitarios separados del puntaje. El cálculo no certifica su cumplimiento ni clasifica instalaciones automáticamente por nombre.
- Entrega: `politica_apoyo_panama_v1.json`, fundamento en `docs/politica_prioridad_oeste.md`, escenario nuevo `oeste-1.0-ensayo-2`. Se conservan ensayo 1 y fixtures anteriores. Cambian versiones de política, datos, solicitud y referencia de matriz; no se reutiliza una propuesta calculada anterior.
- Estado: propuesta sintética sin activación ni confirmaciones inventadas. Demandas, recepción y lugares siguen pendientes. Para uso operativo se requiere validación del operador y coordinación del contrato de política con Emilia. No se modifica código ajeno ni Supabase.
- Evidencia: seis pruebas específicas, incluida criticidad antes de puntaje, ejemplos 30/50/70 y rechazo de política no activa; regresión de 344 pruebas y 66 subpruebas aprobadas. Resultados en `politica_apoyo_panama_v1.json` y `politica_apoyo_panama_v1_pruebas.xml` dentro de `evals/resultados/`.

## D012 Ensayo sintético con demanda, recepción y política calculables

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José pidió generar datos sintéticos plausibles para Panamá Oeste, construir demanda/recepción y continuar con la nueva política. Se construye `oeste-1.0-ensayo-3`, conservando catálogos, contratos, ensayos anteriores y política compartida sin activar.
- Modelo: seis grupos vecinales ficticios, 860 personas; hipótesis de cinco personas por familia, cobertura de un día a 20 L/persona/día y reservas explícitas. Demanda bruta 17 200 L, reserva 2200 L y demanda neta 15 000 L. No son consumos institucionales de las instalaciones del catálogo ni mediciones locales.
- Recepción: tanque nominal de 5000 L o banco equivalente de dos, menos agua almacenada y margen arbitrario del 5 %. Caudal de descarga de ensayo 300 L/min más cinco minutos de preparación. Referencias OMS y ejemplo MINSA de tanque panameño aportan contexto; no prescriben capacidades de los seis lugares.
- Política: copia del 40/40/20 y dos grupos críticos ficticios para probar precedencia; no se infiere criticidad por el nombre de las instalaciones. Identidad y confirmaciones de coordinador ficticias marcadas como fixture; activación solo en esa copia. No se crean usuarios/roles ni se escribe en Supabase.
- Estado: preparación del bloque 3 utilizable para pruebas sintéticas con seis demandas validadas y prioridades calculadas; no equivale a validación de campo ni cierre integrado V3. La propuesta incluye bloqueos de publicación fuera de los contratos de solicitud; no hay plan calculado ni verificación.
- Pruebas: casos de recepción desconocida/insuficiente, reserva desconocida, separación de reserva utilizable y volumen almacenado, población incoherente, exceso de tanque, clasificación/ranking y reproducibilidad. Evidencia separada en `escenario_oeste_sintetico_v3.json` y `escenario_oeste_sintetico_v3_pruebas.xml` dentro de `evals/resultados/`.

## D013 Solver completo y verificador independiente de V3

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José autorizó continuar bloques 4 y 5. Se implementan solve_routes y verify_plan con contratos actuales, preservando solver mínimo V1, fixtures y módulos de los otros integrantes.
- Objetivo del MVP: máximo número de críticos cubiertos, después cobertura lexicográfica según ranking y finalmente duración total mínima. Un crítico no cubierto bloquea validación/publicación aunque la selección parcial sea la mejor disponible. No se amplía a recargas ni entregas divididas.
- Método: enumeración exacta de rutas admisibles para hasta seis puntos y dos cisternas; OR-Tools CP-SAT combina rutas disjuntas. Se conserva mejor ruta por vehículo/subconjunto; no se promete escalabilidad fuera del límite. Se usa la biblioteca OR-Tools ya instalada, sin nuevas dependencias.
- Entrada: vuelve a comprobar puntajes, componentes y orden frente a la política/factores; conserva pendientes, ceros validados y cantidades desconocidas. Capacidad en mililitros exactos, tiempos en microsegundos; límites técnicos y errores documentados en calculo/PLAN_V3.md.
- Diagnóstico: motivo por punto, separando datos, capacidad, demanda indivisible excesiva, accesibilidad, ventana, timeout y selección conjunta. Inviabilidad demostrada solo cuando no existe servicio positivo validado posible; timeout nunca demuestra inviabilidad. Factible sin óptimo se identifica explícitamente.
- Verificación: implementación sin importar OR-Tools/solver y sin confiar en informes adjuntos. Recalcula cargas, viajes, descargas, retorno, ventanas, identidades, demanda completa, versiones y cobertura crítica. SHA-256 del snapshot en supuestos permite detectar cambios de entradas bajo versiones reutilizadas; no sustituye permisos ni vigencia de BD.
- Evidencia: calculo/tests/test_plan_v3.py y demo_plan_v3; casos completos, una cisterna y crítico de 12 000 L. Resultados de V3 en plan_v3_bloques_4_5.json y plan_v3_pruebas.xml dentro de evals/resultados. Estados de timeout/óptimo parcial comprobados con simulaciones identificadas.
- Límite: bloques 4/5 locales; registro por Emilia, persistencia, API/panel por Noel y recorrido integrado siguen pendientes en bloque 6. Propuestas pendientes de revisión, publicación bloqueada, sin activaciones ni aprobaciones reales. Verificación válida solo acredita restricciones del modelo.

## D014 Preparación independiente de evaluaciones V4

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José autorizó desarrollar nuestra parte V4 mientras el equipo cierra la integración anterior. Se limita a evals y documentación propios; no implementa aprobación o publicación ajenas ni declara V3/V4 cerradas.
- Entrega: evals/ejecutar.py reúne las pruebas del equipo, metricas.py separa ejecutados/pendientes, y evals/independientes contiene regresiones locales y un ejecutor HTTP configurable sin importar servicios internos.
- Numeración de la fuente: 18 inyección, 19 usuario sin rol, 20 versión obsoleta y 21 cambio durante aprobación. V4 prepara 18/20/21; la comprobación local del secreto del bot no acredita el rol coordinador del caso 19.
- Veracidad: pruebas locales de contratos/herramientas y sondeos HTTP se contabilizan aparte de los casos oficiales integrados. HTTP 404/405, un error de dominio distinto, rechazo con efectos secundarios, timeout o salida con integración pendiente no son compuerta aprobada. Informe y XML se guardan en carpeta nueva; salida 2 indica pendiente y 1 fallo/error.
- Caso 21: diseño de intercalado de transacciones pendiente de backend de ensayo con Noel; no se sustituye por sleep, llamadas secuenciales o un resultado simulado. Los escenarios reales de aprobación/vigencia, evidencia de Telegram y revisión del equipo siguen pendientes.
- Seguridad de ensayo: credenciales HTTP solo por referencia al entorno, sin persistir respuestas/cuerpos/tokens en el informe; sin reintentos o redirecciones. Los guiones son perfiles de ensayo revisados, no nuevos contratos compartidos. No se ejecutó un perfil HTTP real, Gemini, SQL remoto, trabajador ni envío.
- Evidencia preparatoria: evals/resultados/v4_preparacion/informe.json y regresion.xml; alcance e interfaces pendientes en evals/V4.md. El total de pruebas de JUnit incluye subpruebas; no confundir ese contador con casos oficiales de evaluación.

## D015 Arranque automático de agentes y actualización de reportes

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José confirmó que arrancaba API, bot e interfaz sin trabajador y pidió que los agentes trabajaran sin activación separada. Autoriza esta integración de arranque en API/orquestador y actualización del panel; no cambia propietarios permanentes.
- Decisión: el ciclo de vida de FastAPI administra un subprocess de orquestador.trabajador con el mismo intérprete. Activo por defecto; TRABAJADOR_AUTOMATICO=false permite un trabajador externo. Importar módulos no inicia procesos. Bloqueo local de archivo para hijos administrados; reservas de BD siguen controlando cada ejecución.
- Cierre: señal para dejar de tomar trabajo entre etapas, espera de hasta 60 segundos y terminación si se excede. Reservas inciertas conservan controles de revisión existentes. No se implementa recuperación ante caída abrupta ni reinicio ciego del proceso.
- Visibilidad: GET /salud/agentes informa estado del proceso local; no acredita éxito de servicios externos. Reportes y trazas abiertas se consultan sin solapar peticiones y cancelan su sondeo al cerrar; ya no necesitan F5.
- Pruebas: conftest desactiva el trabajador real en pytest y los tests del arranque usan procesos ficticios. No se procesó la cola ni se llamó a Gemini, Supabase o Telegram para verificar este cambio. Configuración/migraciones y revisión del equipo siguen siendo necesarias.
- Evidencia: evals/resultados/arranque_automatico/informe.json y regresion.xml. 527 pruebas Python y 66 subpruebas, cuatro pruebas de sondeo, lint y build aprobados. El arranque automático no concede permisos, confirma demanda/política, aprueba planes ni cierra V4 integrada.
- Aceptación de Noel (dueño de api/): acepta que el ciclo de vida de FastAPI arranque el trabajador de agentes, activo por defecto. Queda registrado que ese trabajador consume cuota de Gemini mientras la API está encendida; para ensayar sin gastarla se usa TRABAJADOR_AUTOMATICO=false. La API no cambia por esto sus rutas ni sus permisos. Fecha: 17 de octubre de 2026 (UTC−05:00).

## D016 Comparación controlada y preparación de robustez V5

- Fecha: 17 de octubre de 2026 (UTC−05:00).
- Solicitud: José autorizó empezar nuestra parte V5 mientras el equipo cierra la validación real de V4. Se trabaja en cálculo, evals y documentación propios; no se cambian agentes, API, bot, contratos, migraciones ni datos compartidos.
- Comparador: orden de llegada significa primera detección del incidente consolidado, con desempate UUID. Optimiza sus rutas sobre el mismo motor/región factible de V3; solo cambia el objetivo de selección, sin usar criticidad/puntaje como preferencia. No es una quinta tool ni se registra en agentes. La firma y objetivo públicos de solve_routes se conservan mediante un refactor privado comprobado por regresión.
- Método: mismo snapshot completo y huella para ambos; mismas cantidades, disponibilidad, turnos, ventanas, servicios, matriz, precisión y presupuesto. Ambos pasan por verify_plan independiente. Se alterna orden de ejecución y se conserva reproducibilidad, tiempo por muestra y resultados desfavorables. No se afirma mejora general ni diferencia estadística por cinco fixtures sintéticos.
- Retiro: simulación antes de salida, nueva versión de plan/datos/ejecución, preservando el snapshot previo. No invalida filas reales ni aprueba o publica. Variantes de exceso/ausencia se construyen con validate_need y score_needs reales y confirmaciones ficticias explícitas. Exceso crítico de 12 000 L con recepción ficticia suficiente de 18 000 L; reserva desconocida permanece null.
- Métricas: cobertura con denominadores, clase crítica calculable y total separadas, litros/déficit conocidos frente a total desconocido, viaje con retorno, servicio/espera, salidas y latencias locales. Recepción→propuesta y aprobación→envío integrados quedan null. Cero críticos en denominador no se declara cobertura 100 %.
- Resultado del retiro adverso: prioridad cubre 2/2 críticos y 9000 L; FIFO cubre 0/2 y 10 000 L. Ambos cuatro puntos; déficit conocido 6000 frente a 5000 L. Se conserva el rechazo del verificador para FIFO, sin presentarlo como plan publicable.
- Fronteras: pruebas independientes HTTP en memoria del rol coordinador y errores de proveedor/acuse que atraviesan bot→API; Auth, RPC y Telegram simulados. El control positivo impide confundir token mal formado con rechazo por rol. Casos oficiales 19/22/23/24/25 siguen pendientes de evidencia integrada; 22/24 no se dan por ejecutados.
- Validación local: 666 pruebas y 66 subpruebas aprobadas, cuatro advertencias de dependencias y pip check correcto. 38 nuevas pruebas V5; evidencia en evals/resultados/comparacion_v5.json y v5_pruebas.xml. Guía evals/V5.md. Sin servicios externos, cambios de política operativa, commit ni push.

## D017 Preparación documental y auditoría de entrega V6

- Fecha: 17 de octubre de 2026 (UTC−05:00). José solicita continuar V6 tras trasladar dos hallazgos del panel a Noel.
- Alcance propio: completar README e infraestructura, lista de evidencias/propietarios, consolidación literal de bitácoras y auditoría local reproducible. No se modifican módulos de Noel/Emilia ni se activan avisos.
- Auditoría: copia candidata de archivos versionados y nuevos no ignorados; rechaza rutas externas, enlaces y archivos privados por nombre/extensión. Usa el intérprete existente, retira credenciales de servicios del entorno de los controles y conserva manifiesto SHA-256, estado Git, XML, logs y comparación V5. No instala dependencias ni accede a servicios remotos. No es un clonado ni instalación desde cero; revisión de secretos incrustados y dependencias nuevas siguen pendientes.
- Códigos: 0 aprueba controles locales; 1 falla; 2 indica control pendiente. Ninguno acredita cierre integrado V4/V5/V6. Fuentes cambiadas durante la ejecución y bitácoras consolidadas desactualizadas impiden éxito local completo.
- Evidencia de preparación: 715 pruebas Python y 66 subpruebas aprobadas (781 en JUnit), cuatro advertencias conocidas; dependencias, demos V1/V2/V3, comparación V5 y cuatro pruebas Node aprobadas en copia sin .env. El informe conserva las huellas exactas de esa ejecución anterior al cierre documental de esta decisión, no afirma corresponder a un commit final ya publicado.
- Pendientes conjuntos: instalación nueva, migraciones/permisos y concurrencia comprobados, casos V5 reales, tres recorridos consecutivos con uno adverso, revisión de acceso, ensayo y comprobante de entrega. El equipo valida estos hechos; José no los da por ejecutados ni crea tag/commit/push. Guía: docs/ENTREGA_V6.md.

## D018 Robustez de Ingesta y recuperación acotada

- Fecha: 17 de octubre de 2026, 06:50 America/Panama. Usuario encarga el punto 3 mientras aplica 0014 y su smoke en Supabase.
- Alternativas: rechazar diferencias tipográficas o cotejar con normalización conservando el fragmento original; fallar definitivamente, reintentar sin límite o conservar dos reintentos persistidos.
- Decisión técnica: ignorar solo acentos, mayúsculas y espacios; ampliar unidades explícitas y convertir cantidades sin respaldo a null con aclaración. No convertir familias a personas. Dos reintentos adicionales de extracción, separados por cinco y diez segundos, luego revisión. Configuración inválida no consume ese presupuesto.
- Motivo: conservar hechos respaldados y recuperar disponibilidad transitoria sin duplicar cierres ni volver a llamar al modelo tras un resultado incierto de persistencia. El límite es de recuperación técnica, no una política de prioridad o reparto.
- Efecto: nueva 0015 posterior a 0014; contador/fecha en ejecuciones, cierre idempotente y mantenimiento. Contratos y cuatro herramientas sin cambios; reportes fallidos históricos no se reactivan. El preflight de Gemini/columnas ocurre antes de reservar.
- Evidencia: 773 pruebas y 66 subpruebas aprobadas en el candidato, cuatro advertencias conocidas; SQL 0015 y regresiones de aclaraciones/reservas en PostgreSQL temporal PGlite. Metadatos reales del modelo predeterminado: HTTP 200, generateContent disponible. Sin generación real corregida, SQL remoto ni Telegram. Ver docs/INGESTA_A4.md.

## D019 Procedencia de reportes y recursos de ensayo en A1

- Fecha: 17 de octubre de 2026, America/Panama. El usuario confirmó escenario existente; luego precisó que la queja puede describir hechos reales y los recursos son sintéticos porque no hay datos verificados de IDAAN. Autorizó preparar el cambio de alcance y reafirmó el recorrido completo con devolución del resultado.
- Alternativas: mantener todo sintético, habilitar programación operativa real o conservar la procedencia de los hechos y calcular exclusivamente un escenario de ensayo con recursos ficticios. Se adopta la tercera para A1; real no acredita veracidad del reporte y ensayo no acredita reparto.
- Decisión: reporte/incidente/necesidad/ejecución conservan origen. Escenario/propuesta de asignación origen sintético y modo ensayo; flota, depósito y tiempos ficticios explícitos. No se convierten los hechos ni se atribuyen recursos a IDAAN. Política activa seleccionada por coordinador, sin nuevos pesos.
- Efecto: nueva 0016, cola transaccional y puente sobre la misma ejecución, fuente de necesidades en snapshot e invalidación. Ámbito completo por origen y ensayo; no mezcla ni borra otras procedencias. Contratos y cuatro tools sin cambios. Aprobación humana y destino de ensayo existentes se conservan; no se habilita operación real ni se activa AVISOS_ACTIVOS.
- Coordinación: api/servicios/reportes.py todavía usa origen sintético constante; Noel debe distinguir procedencia al capturar y conservar filas existentes. Su revisión necesita recepción y fuente/supuesto explícitos. Relevo concreto en docs/HANDOFF_NOEL_A1.md; no se modifican sus módulos ni los de José.
- Evidencia local: base 825 y candidata 843 pruebas + 66 subpruebas, cuatro advertencias conocidas. Smoke 0016 y regresiones SQL aprobados en PGlite. Fixture con campo origen real conservado, cuatro tools reales, cinco agentes bajo una ejecución, 15 000 L y seis avisos; proveedor y aprobación simulados, sin Telegram. SQL remoto y recorrido conjunto pendientes. Usuario confirmó 0014/0015 y sus smoke en Supabase; Codex no los repitió allí.

Actualización de integración: durante el cierre llegó f1fe718 de Noel con formulario y capacidad de recepción. Se conservaron sus archivos completos; queda pendiente clasificar la procedencia en captura de Telegram. Base nueva: 828 pruebas, candidato final: 846 pruebas + 66 subpruebas, cuatro advertencias conocidas.
