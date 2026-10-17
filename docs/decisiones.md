# Decisiones de RutaAgua Oeste

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

## D004 Alcance de geografía de la demo

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

## D005 Aclaraciones y caducidad de V2

- Fecha de registro: 2026-10-16T22:47-05:00.
- Usuario comunicó acuerdo con Noel: aclaración creada por orquestador, máximo una activa por ejecución; bot llama API y API ejecuta RPC con service_role.
- Reply válido: chat de origen, mensaje de pregunta y autor original, también en grupos. Deduplicar chat:message_id; no sobrescribir respuesta aceptada.
- Se acepta texto o ubicación estática compartida como reply. Ubicación no crea ni valida un lugar de entrega.
- Usuario aprobó 30 minutos desde envío confirmado, configurable. Al vencer pasa a espera_revision, conserva evidencia y genera alerta; resultado vencida no reactiva nada.
- Reservas vencidas y envíos inciertos requieren revisión, sin reenvío automático. Fallidos también se dejan visibles para revisión.
- Implementación local: migraciones 0006/0007 y docs/V2_EMILIA.md. No acredita aplicación remota ni integración del bot de Noel.
