# H2Oeste — Contexto del producto y diseño UI/UX aprobado

Fecha: 17 de octubre de 2026, hora de Panamá.
Destinatario: otra IA, diseñador o desarrollador que continúe la interfaz.
Propietario del frontend: Noel, integrante 2.

## 1. Propósito de este documento

Transferir el contexto del proyecto, las decisiones visuales aprobadas y el estado de la primera implementación. Distinguir siempre:

- Alcance del producto: comportamiento establecido en la planificación.
- Diseño aprobado: solución visual elegida por el usuario.
- Implementación existente: código presente, que no equivale por sí solo a integración validada.
- Pendientes: trabajo todavía necesario, sin presentarlo como terminado.

Este documento no cambia contratos, políticas de prioridad ni permisos. Antes de continuar, revisar el código actual y el diff porque otros integrantes pueden haber avanzado desde esta fecha.

## 2. Fuentes y decisiones del usuario

La propuesta se elaboró a partir de estos documentos adjuntos:

1. RutaAgua_Oeste_Plan_Maestro(2).docx.
2. RutaAgua_Oeste_Flujo_de_Trabajo(1).docx.
3. RutaAgua_Oeste_Versiones_Implementacion(1).docx.

Se contrastaron con el frontend y sus clientes de API. Las decisiones visuales siguientes fueron aceptadas expresamente por el usuario:

- Identidad de centro de operaciones institucional serio, con tecnología moderna y cercanía a las personas.
- Cubrir tres experiencias: coordinador, actividad interna de agentes y residente mediante el bot.
- Diseño responsivo para distintos dispositivos.
- Paleta A: Agua institucional.
- Aceptación del resto del blueprint: tipografía, estructura, componentes y reglas de interacción.
- Autorización para iniciar la implementación en el repositorio.

La paleta alternativa B, Territorio cercano, se presentó pero NO fue elegida. No volver a abrir esta decisión sin una necesidad concreta.

## 3. Problema, propuesta y usuarios

H2Oeste es un prototipo de coordinación de distribución de agua mediante cisternas, con referencia territorial en Panamá Oeste y un escenario acotado en Arraiján.

Transforma reportes ciudadanos en incidentes consolidados, necesidades justificadas y una propuesta verificable de distribución. El coordinador revisa una versión concreta y autoriza la comunicación. El residente puede reportar, aclarar datos y consultar un estado autorizado.

El sistema busca mejorar coordinación y transparencia. Una simulación no demuestra impacto real sobre la crisis de agua ni integración oficial con instituciones.

### Usuarios

| Usuario | Necesidad |
| --- | --- |
| Coordinador, usuario principal del panel | Entender prioridades, recursos, cobertura, déficit y decisiones que puede autorizar. |
| Residente, mediante Telegram | Reportar, resolver aclaraciones y conocer información autorizada en lenguaje claro. |
| Conductor o coordinador, según alcance implementado | Registrar hechos de ejecución física; un agente no puede declararlos por su cuenta. |
| Jurado | Observar decisiones trazables, herramientas y una consecuencia comprobable. |

### Recorrido principal

Reporte de texto → interpretación → ubicación y consolidación → validación de necesidad y prioridad → planificación y verificación → revisión humana → comunicación autorizada → seguimiento.

Una aclaración o revisión humana pausa el trabajo persistido. La interfaz muestra la espera real; no inventa progreso.

### Escenario y límites

- Escenario documentado: seis puntos, dos cisternas y un depósito.
- Capacidades, demandas y tiempos del ensayo deben identificarse según su origen real, estimado o sintético.
- No deducir población atendida a partir de toda la población del corregimiento.
- El diferenciador previsto es retirar una cisterna antes de salir, recalcular, mostrar déficit y obtener una nueva aprobación.
- Voz, fotos y audio de salida son extensiones opcionales, sujetas al núcleo estable.
- Tráfico en vivo, OSRM, múltiples depósitos, recargas, reparto parcial y WhatsApp están fuera del MVP acordado.
- No agregar GPS en vivo, analíticas inventadas, porcentajes de mejora ni promesas de entrega.

## 4. Arquitectura y agentes

Stack: React + Vite en frontend; FastAPI y lógica Python en backend; persistencia y autenticación con Supabase; Telegram como canal ciudadano. El cálculo y verificación se realizan mediante código, con OR-Tools para rutas según la planificación.

| Agente | Responsabilidad | Salida conceptual |
| --- | --- | --- |
| Ingesta | Extraer datos respaldados y detectar faltantes o entradas fuera de alcance. | ReporteInterpretado |
| Territorial | Resolver ubicación y consolidar reportes con asociaciones reversibles. | IncidenteConsolidado |
| Priorización | Gestionar evidencia insuficiente y solicitar cálculo conforme a la política versionada. | EvaluacionNecesidades |
| Planificación | Solicitar solver y verificación; proponer, recalcular o escalar. | PropuestaDistribucion |
| Comunicación | Preparar aclaraciones, consultas y avisos autorizados, preservando los datos aprobados. | AvisoComunidad |

Herramientas previstas: resolve_location, link_reports, validate_need, score_needs, solve_routes, verify_plan, request_approval y publish_approved_messages. Verificar nombres y disponibilidad en el código antes de conectarlas a controles.

No mostrar pensamiento interno del modelo. Mostrar decisiones observables, herramienta, referencias de entrada/salida, resultado, hora y duración.

## 5. Reglas de negocio que el diseño debe conservar

1. Urgencia y confianza son dimensiones diferentes y se muestran por separado.
2. Más reportes no significan más necesidad ni más prioridad. Fuentes independientes y mensajes repetidos no son equivalentes.
3. Un dato desconocido se muestra como no indicado o pendiente; nunca se transforma silenciosamente en cero.
4. Una necesidad sin atender permanece visible con su motivo.
5. Los pesos y escalas se leen de la política vigente; no fijar una fórmula histórica en la UI.
6. Verificado no significa óptimo, aprobado, comunicado ni físicamente entregado.
7. Aprobación, envío, recepción y entrega física son hechos distintos.
8. La aprobación depende del rol, la vigencia, las versiones y la verificación del backend.
9. Una casilla de reconocimiento no puede levantar restricciones duras de seguridad o factibilidad.
10. Un plan invalidado u obsoleto no puede presentarse como disponible para aprobar.
11. Un timeout de envío conserva incertidumbre; no inducir un reenvío ciego.
12. Las consultas ciudadanas usan el plan vigente autorizado.
13. Cantidades en litros y fechas con zona horaria; presentación de horarios en America/Panama.
14. Mostrar el origen sintético de los ejemplos de manera visible.

## 6. Dirección gráfica aprobada

Concepto: centro de coordinación claro y sobrio, navegación azul profundo, superficies claras y lenguaje humano.

La modernidad proviene de trazabilidad, jerarquía y respuesta estable. La cercanía proviene de mensajes comprensibles y del contexto de las necesidades. Evitar decoración futurista, brillos excesivos, interfaces de ciencia ficción y gráficos sin utilidad operativa.

### Paleta A: Agua institucional

| Token | HEX | Uso |
| --- | --- | --- |
| Primario | #075985 | Acciones principales y enlaces. |
| Secundario | #102A43 | Navegación y marca. |
| Acento | #0E7490 | Foco y detalles de selección. |
| Fondo | #F4F7FA | Fondo general. |
| Superficie | #FFFFFF | Tarjetas y formularios. |
| Texto | #172B4D | Contenido principal. |
| Texto secundario | #526477 | Ayudas y metadatos. |
| Borde | #D8E2EC | Separadores y bordes decorativos. |
| Éxito | #166534 | Texto e indicador de éxito. |
| Fondo de éxito | #F0FDF4 | Superficie semántica. |
| Error | #B91C1C | Error, bloqueo o criticidad explícita. |
| Fondo de error | #FEF2F2 | Superficie semántica. |
| Advertencia | #92400E | Pendientes o advertencias. |
| Fondo de advertencia | #FFFBEB | Superficie semántica. |
| Información | #075985 | Información contextual. |
| Fondo de información | #EFF6FF | Superficie semántica. |

Las asociaciones de color son intenciones de marca, no efectos psicológicos universales. La consistencia y el contraste son los criterios operativos.

No depender solo del color. Etiquetar los estados. Reservar colores de rutas distintos de los estados; por ejemplo, azul/violeta con C1/C2. Verificar contraste de cada combinación utilizada: objetivo 4,5:1 para texto normal y 3:1 para texto grande.

### Tipografía y estilo

- Familia elegida: Inter. Public Sans se mencionó como alternativa, no como segunda fuente obligatoria.
- Inter se carga actualmente desde Google Fonts con display=swap y fallback a fuentes del sistema.
- Títulos de página: 28–32 px, peso 600; adaptar a móvil.
- Secciones: 20 px, peso 600.
- Cuerpo y formularios: 16 px.
- Tablas: 14–15 px; metadatos 13–14 px como objetivo de refinamiento.
- Indicadores: 28–36 px, peso 600; números tabulares.
- Interlineado: 1,5 en cuerpo y 1,2 en títulos.
- Espaciado: 4, 8, 12, 16, 24 y 32 px.
- Radios: tarjetas 12 px; campos y botones 8 px; paneles superpuestos 16 px.
- Sombra de tarjeta: 0 1px 3px rgb(16 42 67 / 6%).
- Sombra de superposición prevista: 0 12px 32px rgb(16 42 67 / 16%).
- Controles habituales: altura mínima de 44 px.
- Transiciones cortas de 120–180 ms cuando aporten claridad; respetar movimiento reducido.

## 7. Jerarquía de información y pantallas objetivo

### Tres prioridades del coordinador

1. Necesidades que requieren atención: criticidad, orden y casos pendientes de validar.
2. Cobertura y déficit de la propuesta seleccionada: puntos atendidos sobre total, litros asignados y pendientes con motivo.
3. Estado y vigencia: versión, verificación, aprobación y bloqueos.

Acción principal propuesta: Revisar propuesta. Dentro de la revisión: Aprobar versión, solo cuando corresponda. No mezclar indicadores de distintas versiones ni datos sintéticos de Plan con datos actuales de Necesidades.

### Estructura objetivo

- Sidebar de 232 px en escritorio.
- Header de al menos 64 px, adaptable al contenido.
- Área principal de 12 columnas, separación y padding habituales de 24 px.
- Resumen de tres bloques equivalentes.
- Plan: cuerpo 8+4 para rutas/mapa y revisión/pendientes; detalle inferior completo.
- Secciones: Reportes, Necesidades, Plan, Aprobación y Actividad de agentes (Eventos).

El patrón de lectura en F orienta la ubicación de contexto y listas; no es una regla universal. Reducir decisiones simultáneas mediante una acción principal por contexto y detalles progresivos.

### Reportes

Lista con hora, lugar declarado, resumen, origen y estado. Detalle con texto original, campos extraídos, evidencia, faltantes y seguimiento. Estados actuales: interpretado, necesita aclaración, sin interpretar y fuera de alcance. El blueprint propone detalle lateral en escritorio; actualmente se conserva el desplegable por reporte.

### Necesidades

Separar orden de atención de pendientes de revisión. Mostrar criticidad, demanda, puntaje y componentes de la política. La confianza, los vínculos y los conflictos tienen su propio bloque. No reordenar en frontend contra el orden calculado por backend.

### Plan

Versión, origen y estado; cobertura y déficit; rutas por cisterna con capacidad, asignación, paradas y ventanas; pendientes visibles; verificación y supuestos. El mapa futuro debe identificar recorridos esquemáticos y tiempos sintéticos. Las líneas entre puntos no equivalen a rutas viales ni GPS.

### Aprobación

Revisión de versión concreta, restricciones, supuestos, motivo y confirmación. Diferenciar advertencias reconocibles de bloqueos duros. La comunicación por sector es un paso separado: no suponer que aprobar equivale automáticamente a publicar o entregar.

### Actividad de agentes

Vista independiente prevista con línea temporal vertical por ejecución y detalle de eventos. Campos: agente, estado, decisión observable, herramienta, evidencia, hora/duración y siguiente estado o espera. Revisión humana como hito separado. No inventar porcentaje de progreso.

### Residente mediante Telegram

Diseñar textos, botones y secuencia, respetando que Telegram controla su interfaz nativa. Reporte → acuse tras persistir → aclaración concreta si hace falta → consulta autorizada → aviso con punto, cantidad, fecha y ventana estimada → actualización si cambia el plan. Evitar tecnicismos, promesas de hora exacta y afirmaciones de lectura o entrega no demostradas.

## 8. Responsividad y accesibilidad

Objetivo: contenido general utilizable desde 320 CSS px, sin desplazamiento horizontal de toda la página. Mapas o tablas bidimensionales requieren tratamiento específico.

- Escritorio amplio: sidebar y columnas.
- Tablet: navegación compacta y bloques apilados cuando sea necesario.
- Móvil: una columna, menú desplegable, tarjetas y detalles completos.
- Mostrar lista de paradas antes del mapa en móvil.
- No depender de hover.
- Foco visible, navegación por teclado, controles etiquetados y enlace de salto.
- No ocultar déficit, origen sintético o incertidumbre para simplificar la pantalla.
- Conservar datos previos si falla una actualización, indicando desactualización: objetivo pendiente de revisar por página.

La primera fase usa un breakpoint de 900 px para el menú; no confundirlo con los anchos orientativos del blueprint.

## 9. Estado real de la implementación al redactar

### Implementado en la primera fase visual

- Tokens de la paleta A en src/index.css.
- Carga de Inter y theme-color en index.html.
- Sidebar, menú móvil desplegable, Escape para cerrarlo y salto al contenido.
- Enlaces hash existentes conservados y título del navegador por sección.
- Aplicación visual común a Reportes, Necesidades, Plan, Aprobación y comunicación por sector.
- Tarjetas, formularios, sellos, rutas y verificación con apariencia consistente.
- Trazas existentes estilizadas como línea temporal dentro de cada reporte.
- Adaptación de la pantalla de acceso al mismo lenguaje visual y eliminación de su animación de fondo.
- Ajustes de distribución y tamaños para pantallas pequeñas.

### Archivos principales

| Archivo relativo a frontend/ | Responsabilidad |
| --- | --- |
| src/App.jsx | Navegación y composición de cuatro páginas existentes. |
| src/App.css | Shell, sidebar, menú y encabezado. |
| src/index.css | Tokens y estilos globales. |
| src/design-system.css | Capa compartida cargada después de los estilos de páginas. |
| index.html | Fuente y metadatos. |
| src/paginas/*.jsx y *.css | Lógica y estilos particulares existentes. |
| src/api/planes.js | Plan sigue usando ejemplos. |
| src/api/aprobacion.js | Consulta y decisiones sobre planes con sesión. |
| README.md | Descripción y límites de esta fase. |

No se añadió una biblioteca de componentes. package.json contiene React/React DOM y las herramientas de Vite/ESLint. No se instalaron Tailwind, Material UI, shadcn/ui ni Leaflet en esta fase.

### Pendientes explícitos

- Revisión visual real en escritorio, tablet y móvil.
- Página independiente Actividad de agentes/Eventos.
- Mapa Leaflet y su conexión con catálogo y rutas.
- Unificación de Plan con datos reales: USAR_EJEMPLOS_PLANES sigue en true.
- Adaptador entre el formato consumido por Plan y el formato de GET /planes usado por Aprobación. No basta cambiar el booleano.
- Selectores de sector/destino con nombres cuando existan endpoints de catálogo; hoy hay formularios con UUID.
- Componentes reutilizables extraídos: AppShell, StatusBadge, MetricCard, RouteCard, VerificationPanel y AgentTimeline son propuestas, no archivos ya creados.
- Distribución final 8+4 y resumen operacional completo de una versión seleccionada.
- Refinamiento de textos y botones del bot según la propuesta: no se implementó como parte del cambio visual.
- Revisión de estados vacíos, carga y datos desactualizados en todas las páginas.

Nota: un comentario de src/api/planes.js dice que GET /planes no existe, pero la consulta sí está presente en el cliente de Aprobación. Tratar ese comentario como desactualizado; verificar el contrato real.

## 10. Validación realizada y límites

En la fase visual anterior:

- npm run lint: aprobado.
- npm run build -- --configLoader native: aprobado.
- node --test --test-isolation=none tests/sondeo.test.mjs, desde frontend/: cuatro pruebas aprobadas.
- git diff --check: sin errores de formato; hubo avisos de conversión LF/CRLF.

Los comandos habituales de build y pruebas encontraron spawn EPERM en este entorno. Los modos indicados evitaron necesitar esos subprocesos. No se cambió la configuración persistente de Vite para ello.

La herramienta del navegador falló por un error de sesión. No se comprobó visualmente la apariencia, el overflow ni el funcionamiento táctil. No afirmar que la responsividad está validada solo porque compila.

No se validaron con estos cambios una aprobación real, publicación ni entrega física. El servidor de desarrollo llegó a iniciarse en 127.0.0.1:5174 porque 5173 estaba ocupado; no asumir que continúa activo.

## 11. Continuación recomendada

1. Leer git status y preservar cambios ajenos. En la revisión para este documento apareció bot/adaptador.py modificado; no atribuir ese cambio al rediseño ni sobrescribirlo.
2. Abrir la app y revisar 320/390 px, tablet y escritorio, incluidos acceso, errores y planes con datos largos.
3. Corregir overflow, foco y jerarquía antes de ampliar alcance.
4. Extraer componentes compartidos gradualmente, sin reescribir la lógica de negocio.
5. Implementar Actividad de agentes reutilizando las consultas de ejecución.
6. Unificar Plan y Aprobación sobre una versión coherente y un adaptador explícito.
7. Añadir mapa sobre el recorrido funcional, con etiquetas de sus limitaciones.
8. Refinar la interacción ciudadana preservando las plantillas y datos autorizados.
9. Repetir lint/build y pruebas relevantes, ensayar el recorrido y registrar resultados en la bitácora.

## 12. Instrucción de relevo para otra IA

Continúa H2Oeste sobre este repositorio. Conserva la identidad Agua institucional ya aprobada y el alcance del plan maestro. Antes de editar, inspecciona el estado actual y los contratos de las pantallas afectadas. No inventes datos ni conviertas el diseño objetivo en una afirmación de implementación. Preserva prioridades calculadas, evidencia, déficit, versiones, autorización y separación entre aprobación, comunicación y entrega. Trabaja por componentes sobre React + Vite y CSS existente. Informa qué cambiaste, qué verificaste y qué sigue pendiente. No cambies la paleta ni agregues funciones fuera del MVP sin una razón acordada con el usuario.

## Actualización: acceso separado de Aprobación

Por indicación del usuario, la cuenta se ubica en el encabezado, junto a un avatar,
fuera de la navegación operativa. `#acceso` usa `src/paginas/Acceso.jsx` para iniciar
sesión o cerrar la sesión actual. Aprobación conserva la revisión de planes y, sin
sesión, muestra un enlace al acceso; ya no contiene el formulario de credenciales.
El estado local de sesión se comparte desde App; los permisos siguen comprobándose
en backend. Lint y build con configLoader native aprobaron tras el cambio.

El usuario proporcionó un nuevo logo en dos imágenes. Su descarga falló en esta
sesión y NO se incorporó; la gota provisional sigue presente. No reconstruir el
logo ni afirmar que se revisó visualmente hasta disponer de sus bytes.

## Refinamiento posterior del diseño

El usuario solicitó diferenciar las pantallas y reducir la repetición de tarjetas.
Se incorporó `src/editorial.css`: Reportes como bandeja, Necesidades como ranking y
Aprobación como expediente. Los títulos editoriales usan Georgia y los controles
conservan Inter. La paleta A se mantiene. Los resúmenes nuevos derivan de datos
cargados correctamente; no presentan métricas ficticias. El código actual usa
H2Oeste como marca, y se conservó ese cambio existente. Lint y compilación aprobados;
la revisión visual continúa pendiente. Las tres imágenes adjuntas de esta iteración
no pudieron descargarse y no se integraron.
