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
