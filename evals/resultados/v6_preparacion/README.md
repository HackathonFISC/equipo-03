# Evidencia local preparatoria V6

Ejecución del 17 de octubre de 2026 sobre copia candidata de d35d80e más cambios
locales declarados. `informe.json` identifica archivos exactos mediante hashes y
estado Git. Esta ejecución precede al cierre documental de D017 y la última
actualización de la bitácora; no se atribuye a un commit final publicado.

- 715 pruebas Python y 66 subpruebas aprobadas; XML cuenta 781, sin saltos/fallos.
- Cuatro advertencias de dependencias, descritas en `regresion.log`.
- Dependencias, V0, demos V1/V2/V3, comparación V5 y cuatro pruebas Node aprobadas.
- Enlaces de entrada y hashes de bitácoras correctos en el snapshot probado.
- Copia sin entorno privado, dependencias existentes reutilizadas.

Los logs, XML y comparación acompañan al informe. La copia completa y temporales
quedan fuera del repositorio. El primer ensayo fallido por una aserción CRLF/LF
permanece en `tmp/entrega_v6_preparacion_01` del workspace local; fue corregido
antes de producir esta evidencia aprobada.

`cierre_v4`, `cierre_v5` y `cierre_v6` siguen false. No se ejecutaron instalación
nueva, migraciones, Auth remoto, Gemini, Telegram, aprobación/publicación reales,
tag ni envío. Repetir la auditoría para la versión que el equipo decida entregar.
