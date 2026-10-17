# Ensayo 3: demanda, recepción y prioridad sintéticas calculadas

> Alcance: este documento describe la preparación y los archivos de este escenario,
> no el estado completo del repositorio. Los bloques 4/5 ya tienen
> [solver y verificador](../../../calculo/PLAN_V3.md). La integración local del
> fixture separado está en [V3 de Emilia](../../../docs/V3_EMILIA.md); aplicación
> en Supabase, panel y cierre integral deben comprobarse por separado.


Este escenario permite continuar V3 sin esperar datos de campo. Modelo doméstico de emergencia con grupos vecinales ficticios asociados a los seis UUID del catálogo de Emilia. No describe la población, tanques, usuarios, funcionamiento o desabastecimiento actuales de esas instalaciones; tampoco estima su demanda institucional. No es un modelo calibrado con mediciones de Panamá Oeste.

## Referencias y decisiones del ensayo

- La [OMS](https://www.who.int/teams/environment-climate-change-and-health/water-sanitation-and-health/environmental-health-in-emergencies/humanitarian-emergencies) describe unos 20 L/persona/día para necesidades básicas de higiene y alimentos en emergencia. Se usa ese valor para un día de cobertura doméstica básica. No se presenta como cuota legal de Panamá ni como cobertura de todos los usos.
- [MINSA documenta un tanque de 5000 L en Atalaya](https://www.minsa.gob.pa/noticia/centro-de-salud-de-atalaya-cuenta-con-nuevo-tanque-de-reserva-de-agua). Sirve de referencia de escala panameña, sin demostrar tanques en nuestras seis ubicaciones. El ensayo usa un tanque de 5000 L o un banco equivalente de dos.
- Cinco personas por familia es una hipótesis de grupo inspirada en un [parámetro de diseño del IDAAN, página 14](https://monitoreo.antai.gob.pa/api/submissions/146052/files/39526/download); no un promedio censal ni conteo real local.
- Reserva, familias, horas sin agua y categorías son inventadas. El margen de tanque del 5 %, caudal de descarga de 300 L/min y preparación de cinco minutos son decisiones técnicas arbitrarias del ensayo, sin carácter normativo.

## Demanda y recepción

`demanda = max(0, personas × 20 L/persona/día × 1 día − reserva utilizable)`.

`recepción libre = max(0, capacidad nominal × 0.95 − agua almacenada)`.

La reserva utilizable y el agua almacenada se declaran por separado: en el caso base se suponen iguales, pero una reserva que no sea utilizable sigue ocupando espacio. La recepción es espacio disponible para esta entrega, no capacidad nominal. La descarga propuesta es `ceil(demanda / 300 + 5)` minutos, incluyendo preparación. Las horas sin agua influyen en prioridad, no multiplican días de consumo.

| Referencia del catálogo | Familias ficticias | Personas | Reserva / agua almacenada | Tanque nominal | Demanda neta | Recepción libre |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Junta Comunal Nuevo Arraiján | 32 | 160 | 200 L | 5000 L | 3000 L | 4550 L |
| Junta Comunal de Vista Alegre | 36 | 180 | 600 L | 10 000 L | 3000 L | 8900 L |
| C.E.B.G. Burunga | 24 | 120 | 400 L | 5000 L | 2000 L | 4350 L |
| Escuela El Coco | 28 | 140 | 300 L | 5000 L | 2500 L | 4450 L |
| C.E. Virgen de Guadalupe | 32 | 160 | 200 L | 10 000 L | 3000 L | 9300 L |
| Centro Educativo Guillermo Endara | 20 | 100 | 500 L | 5000 L | 1500 L | 4250 L |

Son 860 personas, 17 200 L de necesidad bruta para un día, 2200 L de reserva y 15 000 L netos. Las demandas se derivan de estos perfiles, no se recortan para ajustarlas a la flota. Las dos cisternas de 10 000 L y el depósito siguen siendo ficticios. La matriz de siete nodos conserva los tiempos manuales del ensayo 2; no acredita recorridos físicos ni tiempos realistas de carretera.

## Política 40/40/20 y confirmaciones del fixture

Se conserva la política definida en `docs/politica_prioridad_oeste.md`: críticos antes de generales y, dentro de cada clase, 40 % vulnerabilidad, 40 % duración y 20 % personas. Escalas técnicas: 168 horas y 500 personas. Porcentajes y escalas no son normas oficiales.

Dos grupos se declaran críticos **solo por hipótesis ficticia de dependencia sin alternativa**, asociados a las referencias Burunga y Virgen de Guadalupe. No se deduce criticidad por tratarse de escuelas ni se afirma la existencia de pacientes o usuarios dependientes allí. Las clasificaciones de los otros cuatro grupos también son sintéticas.

Para ejercitar los contratos se incluye una identidad de coordinador ficticia y motivos que empiezan por `FIXTURE SINTÉTICO`. Se valida demanda y se activa exclusivamente una copia de política `oeste-prioridad-apoyo-pa-1-fixture-3`. No se activa `politica_apoyo_panama_v1.json`, no se crea un rol real ni se escribe en Supabase. Esto permite probar aritmética y ranking sin atribuir aprobación humana real.

Orden obtenido: Virgen de Guadalupe, Burunga, El Coco, Nuevo Arraiján, Guillermo Endara y Vista Alegre. Son prioridades de grupos ficticios, no una recomendación de reparto actual a esos lugares.

## Archivos y ejecución

- `parametros.json`: hipótesis explícitas, referencias y perfiles; fuente para regenerar el ensayo.
- `escenario_fixture.json`: envoltorio local con solicitudes y resultados de demanda/prioridad, resumen y `SolicitudResolverRutas` preparada. Sus objetos internos usan los contratos existentes; el envoltorio no es un contrato nuevo ni un endpoint.
- `calculo/demo_escenario_v3.py`: cálculo reproducible con nuestras funciones reales, sin red ni BD. Reutiliza como plantilla las referencias, matriz y flota del ensayo 2, sin modificarlo.

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m calculo.demo_escenario_v3
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_demo_escenario_v3.py -q
```

Para conservar otra salida, añadir `--salida ruta_nueva.json`; no sobrescribe archivos. La evidencia de validación se guarda en `evals/resultados/escenario_oeste_sintetico_v3.json` y `escenario_oeste_sintetico_v3_pruebas.xml`. El comprobador de ensayos pendientes 1/2 sigue separado y no acepta este fixture como si estuviese pendiente.

## Alcance del cierre

El bloque 3 queda preparado para desarrollo y pruebas sintéticas: cantidades y recepción calculadas, demandas validadas y ranking calculado con confirmaciones ficticias. Para uso real siguen faltando operador autorizado, calidad del agua, flota, depósito, acceso, recepción y evidencias de campo.

La salida de esta demo de demanda/prioridad no incluye rutas calculadas ni informe de `verify_plan`, aprobación o publicación. El resultado declara `autorizacion_operativa=false` y bloqueos explícitos. El solver mínimo V1 no admite referencias reales mezcladas con este ensayo; no se eluden sus guardas. Los bloques 4/5 ya están implementados en [PLAN_V3](../../../calculo/PLAN_V3.md). El bloque 6 tiene integración local de Planificación en [V3 de Emilia](../../../docs/V3_EMILIA.md); eso no acredita despliegue, API/panel ni cierre conjunto.
