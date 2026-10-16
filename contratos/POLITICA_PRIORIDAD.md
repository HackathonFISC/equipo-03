# Política de prioridad para la demo

Versión `demo-1.0`. Diseño solicitado por el usuario. Los parámetros están propuestos para el escenario sintético; el coordinador registra su activación antes de usarlos. No es una política oficial del IDAAN ni una regla clínica de triaje.

## Decisiones aprobadas por el usuario

- Clases **crítico** y **general**, confirmadas por el coordinador.
- Un punto crítico necesita ventana de atención. La falta de cobertura crítica bloquea publicación y exige revisión; el sistema no omite ese punto ni simula cobertura.
- Datos faltantes: pendiente, sin puntaje ni posición y sin imputarlos como cero. Una posible urgencia genera alerta visible de revisión.
- En empate: atención confirmada más antigua; si falta historial, antigüedad del incidente y luego ID. Mensajes repetidos no cambian antigüedad ni prioridad.

La clasificación de un centro de salud, escuela, albergue o sector no se deduce automáticamente de su nombre. La confirma el coordinador con motivo y evidencia. Una afirmación de criticidad no confirmada queda pendiente con alerta, no se vuelve general por defecto. Tampoco se permite que un ciudadano se declare coordinador por texto.

## Fundamento y límite de los pesos

La OMS recomienda considerar explícitamente los grupos que sufren desventajas sociales, económicas, demográficas o geográficas al planificar el agua. Sphere sitúa el acceso equitativo y la evaluación contextual de necesidades y recursos entre sus principios de respuesta. Estas referencias justifican considerar vulnerabilidad y necesidad, pero **no proporcionan una fórmula 50/30/20 ni los topes de este prototipo**.

- OMS, *A guide to equitable water safety planning*, 2019: https://www.who.int/publications/i/item/9789241515313
- Sphere, *The Sphere Handbook*, edición 2018: https://spherestandards.org/handbook/

Los pesos siguientes son una heurística de ingeniería explicable para probar la demo. Deben evaluarse y ajustarse con actores operativos antes de una aplicación real. No se afirma que sean óptimos o que garanticen equidad.

| Factor | Peso | Motivo de diseño |
| --- | --- | --- |
| Duración sin agua | 50 % | Da mayor influencia al tiempo de espera que a la magnitud del sector. |
| Vulnerabilidad validada | 30 % | Hace visibles barreras para conseguir agua por otros medios; una ausencia de información no se considera ausencia de vulnerabilidad. |
| Personas atendidas | 20 % | Considera alcance de la atención, con influencia limitada para reducir el dominio de los sectores grandes. |

La clase crítica precede al puntaje. Un general con 100 puntos no desplaza a un crítico confirmado con 10 puntos. Las restricciones de capacidad, acceso, servicio y turnos nunca se relajan porque un puntaje sea alto.

## Fórmula estable

```text
D = min(horas_sin_agua / 168, 1)
V = 0 si sin_condicion_identificada está validado
    0.5 si moderada está validada
    1 si alta está validada
P = min(personas_atendidas / 500, 1)
puntaje = 100 × (0.50 × D + 0.30 × V + 0.20 × P)
```

168 horas y 500 personas son escalas fijas **del ensayo**, no umbrales sanitarios ni cifras obtenidas del máximo del lote. Se eligieron para explorar diferencias en un escenario pequeño y evitar que la llegada de un valor extremo renormalice a todos los demás. El tope de duración no significa que esperar más de una semana sea aceptable; los empates requieren aplicar la regla acordada.

La vulnerabilidad moderada representa barreras de acceso parcialmente compensadas; alta representa barreras importantes sin alternativa confirmada. El coordinador documenta el motivo. Las categorías no son diagnósticos y no requieren almacenar historias médicas. Si no se conoce el nivel o no fue validado, `vulnerabilidad=null`: queda pendiente.

Las personas atendidas corresponden al punto de entrega y deben estar respaldadas. La dotación, cantidad de litros solicitada, confianza y número de mensajes no forman parte de este puntaje.

No redondear antes de comparar puntajes. Mostrar dos decimales en la interfaz sin alterar el valor utilizado. Para estos factores, comparar valores calculados con tolerancia técnica de 1e-9 y aplicar el desempate de grupo; las sumas del contrato toleran 1e-6 por serialización.

## Desempate determinístico

1. Agrupar por clase y puntaje empatado. Para evitar comparaciones no transitivas, construir grupos estables a partir de puntajes descendentes comparando con el primer puntaje del grupo.
2. Si **todos** los integrantes del grupo tienen historial, ordenar por fecha de última atención confirmada ascendente; después, primera detección e ID.
3. Si **alguno** carece de historial, usar para **todo el grupo** primera detección ascendente y luego ID. Un dato ausente no significa que nunca haya recibido agua.
4. El ID se compara como su cadena UUID canónica para que el resultado sea reproducible.

Esta precisión implementa la regla de ausencia de historial sin producir un orden que cambie según la secuencia de comparaciones. La primera detección solo puede cambiar por una corrección explícita auditada, no al añadir reportes duplicados.

## Ejemplo de sensibilidad

Comparación matemática sintética dentro de la misma clase, con todos los datos validados:

| Caso | Horas | Personas | Vulnerabilidad | 50/30/20 | Hipótesis anterior 40/30/30 por duración población vulnerabilidad |
| --- | --- | --- | --- | --- | --- |
| A | 72 | 120 | Alta | 56.23 | 54.34 |
| B | 24 | 500 | Sin condición identificada | 27.14 | 35.71 |

La reducción del peso poblacional reduce la ventaja del caso B. Esto ilustra una elección de diseño; no demuestra equidad ni impacto real. Cambiar los pesos siempre crea una nueva versión y obliga a recalcular y verificar los planes afectados.

## Comprobaciones que José debe implementar

- Duplicar mensajes sin cambiar hechos no cambia puntaje ni posición.
- Aumentar horas o vulnerabilidad, manteniendo lo demás igual, no reduce el puntaje.
- Un factor ausente produce pendiente; no debe calcularse un puntaje con cero implícito.
- Añadir un sector extremo no cambia el puntaje numérico de los existentes.
- Una clase crítica no se desplaza por puntaje general.
- El desempate funciona con historial completo, incompleto y mensajes duplicados.
- Con recursos insuficientes, el solver refleja prioridad y obligaciones críticas; no maximiza viaje corto a costa de ocultar déficit.

El contrato comprueba forma y algunos invariantes, pero estas pruebas del cálculo y su conexión al solver siguen siendo trabajo de José. El archivo `politica_prioridad.json` está en estado `propuesta_demo`. Los ejemplos de solicitudes de herramientas contienen una activación ficticia identificada como sintética; no habilitan una operación real.
