# evals/independientes

**Dueño:** José

Pruebas de autorización y operación (18 a 25). Preparación actual: V4.

- `test_v4_local.py`: 19 regresiones independientes sobre interfaces públicas.
  Ingesta y Planificación reales con extractores/decisores controlados, contratos
  reales y solver/verificador reales; API en memoria con secreto ficticio y BD
  centinela. No importa pruebas ni utilidades privadas de Noel.
- `caja_negra.py`: guiones HTTP configurables, sin importar la aplicación o sus
  servicios. Verifica cuerpo y estado HTTP; puede comparar una lectura de
  auditoría antes/después mediante capturas SHA-256, sin guardar contenido.
- `test_ejecutor_v4.py`: comprueba que el evaluador detecte estado cambiado,
  errores incorrectos, timeout, redirecciones y credenciales mal ubicadas.
  Sus peticiones utilizan transporte simulado; no son evidencia de la API viva.

```powershell
.\.venv\Scripts\python.exe -m pytest evals/independientes -q
```

Casos oficiales: **18 inyección, 19 usuario sin rol, 20 versión obsoleta,
21 cambio durante aprobación**, según el plan maestro. V4 inicia 18, 20 y 21;
el perímetro del secreto del bot no sustituye la prueba 19 del coordinador.

El caso 21 no se representa con una prueba secuencial ni con un sleep. Requiere
un intercalado controlado en un backend de ensayo y evidencia de transacciones,
pendiente de acordar con Noel. No está implementado en el ejecutor HTTP
secuencial. Consultar [V4](../V4.md).
