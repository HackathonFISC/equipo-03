# Resultados de escritorio PED

Entradas: [dataset de treinta casos](../../../datos/entradas_prueba/escritorio_v1/README.md).
El informe conserva sus hashes y los del código de cálculo, con finales de línea
normalizados a LF. Cada PED tiene su esperado, obtenido y alcance separado.

- 30 casos válidos en el conjunto.
- 18 comprobaciones locales ejecutadas y aprobadas, sin fallos ni errores.
- 12 casos de integración pendientes: PED-07–12 y PED-25–30.
- No se ejecutó extracción con Gemini, Auth/BD ni Telegram reales.
- Cero publicación o autorización operativa; `cierre_integrado=false`.

PED-01–06 comprueban las entradas estructuradas y sus cantidades/prioridades,
no la interpretación de los mensajes por el modelo. Los rechazos esperados de
casos adversos no se presentan como planes publicables.

`regresion.xml`: 852 pruebas y 66 subpruebas aprobadas (918 JUnit), cuatro
advertencias de dependencias conocidas. Incluye seis pruebas nuevas del dataset:
sin red/inmutabilidad, oráculo falso, edición de caso, generación determinista,
checkout CRLF y snapshot obsoleto. pip check correcto.

Los primeros ajustes del ejecutor (estado de prioridad era texto, no enum) se
corrigieron antes de esta evidencia. Los resultados de desarrollo están en el
temporal externo del workspace; esta carpeta conserva el resultado final.

No sobrescribir esta evidencia. Para repetir, usar `--salida` con carpeta nueva;
las entradas mantienen `obtenido=no_ejecutado` para que cada ejecución tenga su
propio registro. Las pruebas locales no cierran los casos oficiales integrados.
