# Política de prioridad de RutaAgua Oeste: apoyo panameño, versión 1

Fecha: 17 de octubre de 2026. Archivo de política: `datos/escenario/politica_apoyo_panama_v1.json`; identificador `oeste-prioridad-apoyo-pa-1`.

El usuario solicitó construir ponderaciones con apoyo en fuentes oficiales. Esta política es una decisión técnica del proyecto para ensayo y revisión; no es una fórmula emitida o aprobada por IDAAN, MINSA o ASEP. Conserva estado `propuesta_demo`, origen sintético y confirmación de activación nula. El contrato vigente no admite todavía una política de origen operativo real.

## Requisitos previos y prioridad crítica

Las condiciones sanitarias de fuente, cisterna y agua se tratan fuera del puntaje. La [Resolución ASEP AN 1480-Agua](https://asep.gob.pa/an-no-1480-agua-de-15-02-2008/) regula vehículos de prestadores sujetos a ASEP. La [DGNTI-COPANIT 21-2019 y su reforma 122/2021](https://infojuridica.procuraduria-admon.gob.pa/norma_screen?numsec=57329) deben considerarse para calidad. Son referencias para requisitos de operación; no justifican puntos adicionales por cumplir lo obligatorio.

El operador debe comprobar esas condiciones, recepción y acceso antes de autorizar reparto. No están implementadas como certificación sanitaria en score_needs ni verify_plan. El integrador debe conservar sus observaciones pendientes y bloquear el uso operativo cuando corresponda, sin inventar estados favorables. Los contratos y servicios necesarios se coordinan con Emilia/Noel.

Primero se atiende la clase crítica confirmada; después, la general. La propuesta considera para revisión crítica la interrupción que comprometa un servicio sanitario esencial o una persona dependiente sin alternativa suficiente. El [operativo IDAAN de Semana Santa 2026 publicado por SERTV](https://sertv.gob.pa/idaan-activa-operativo-de-semana-santa-2026/) prioriza hospitales, centros médicos y personas encamadas en Azuero; es apoyo operativo, no una clasificación legal automática para Panamá Oeste.

El nombre de una escuela, institución o barrio no confirma por sí solo criticidad. Un caso sospechoso sin evidencia queda pendiente con alerta urgente para revisión humana. Si faltan recursos para críticos, se debe mostrar déficit y escalar; la selección y verificación de cobertura corresponden a los siguientes bloques V3.

## Ponderaciones dentro de cada clase

| Factor | Peso | Decisión del proyecto |
| --- | ---: | --- |
| Vulnerabilidad confirmada | 40 % | Aumenta su influencia frente al ensayo anterior para representar dependencia y barreras de acceso documentadas. No equivale a diagnóstico médico. |
| Tiempo confirmado sin suministro | 40 % | Mantiene una medida de espera y evita relegar indefinidamente comunidades. No representa consumo acumulado. |
| Personas efectivamente atendidas | 20 % | Considera alcance sin permitir que el tamaño del grupo desplace automáticamente a un crítico. No usa población total del corregimiento por defecto. |

La fuente oficial no fija estos porcentajes. El cambio respecto de 50/30/20 es una elección técnica solicitada para el proyecto, pendiente de validación del operador antes de usarla en una intervención real. No se calibra como modelo estadístico ni se afirma optimalidad.

El puntaje es `40 × V + 40 × min(horas / 168, 1) + 20 × min(personas / 500, 1)`.

- `V=0`: sin condición identificada, solo cuando esa clasificación está confirmada; ausencia de información no significa cero.
- `V=0.5`: vulnerabilidad moderada confirmada; por ejemplo, barreras documentadas con una alternativa de acceso disponible. Es una propuesta de clasificación a revisar por el operador.
- `V=1`: vulnerabilidad alta confirmada; por ejemplo, dependencia para obtener agua sin alternativa suficiente. Un caso que comprometa salud esencial requiere además revisar clase crítica.
- Las escalas de 168 horas y 500 personas y el valor moderado 0.5 se conservan para comparar ensayos; son parámetros técnicos del proyecto, no umbrales legales, sanitarios ni máximos de atención. Cambiarlos exige versionar y recalcular.

Ejemplo puramente sintético: 84 horas, 250 personas y vulnerabilidad moderada aportan 20 + 10 + 20 = 50 puntos. Un crítico confirmado con menor puntaje sigue antes que un general con mayor puntaje.

## Pendientes, desempate y límites

Demanda sin validar, recepción insuficiente/desconocida, factores sin confirmar u observaciones no resueltas permanecen pendientes. No se rellena información para producir un ranking. La cantidad de mensajes repetidos no aumenta población, demanda ni prioridad.

En un empate dentro de la misma clase se usa última atención confirmada más antigua cuando todo el grupo tiene historial; si falta historial en alguno, todo el grupo usa primera detección. Después se usa primera detección e ID estable según corresponda. Se conserva la tolerancia numérica ya implementada; no se redondea antes de ordenar.

Las normas de diseño de acueductos no determinan automáticamente litros de emergencia. Esta política no cambia demanda, capacidad de recepción, horarios, descarga o calidad del agua. Tampoco activa la política ni confirma datos: esas acciones requieren identidad y actuación del coordinador autorizado.

La nueva versión se incorpora en `datos/escenario/oeste-1.0-ensayo-2/`. El escenario anterior y sus evidencias se conservan. Referencias y límites de vigencia: `docs/referencias_normativas_panama.md`.

Para continuar el desarrollo con datos completamente sintéticos, `oeste-1.0-ensayo-3/` ejercita una copia de esta política activada exclusivamente por un coordinador ficticio identificado como fixture. Sus demandas y recepciones proceden de hipótesis explícitas, no de confirmaciones reales. Esa simulación no modifica el estado de la política compartida ni satisface requisitos de operación real.
