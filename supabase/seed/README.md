# supabase/seed

**Dueño:** Emilia (01) y José (02)

01_sectores_puntos.sql, 02_escenario.sql


## Semilla 01 de sectores y puntos

`01_sectores_puntos.sql` carga seis instalaciones candidatas del catálogo
`oeste-1.0`: tres en Arraiján y tres en La Chorrera. Requiere 0001. Procedencia
geográfica real AIG 2022; estado operativo pendiente, recepción y precisión NULL.
No registra demanda, criticidad ni confirmaciones de entrega.

Se puede repetir sin sobrescribir cambios humanos. Un conflicto de identidad
aborta la transacción. No elimina otros sectores/puntos ni modifica el escenario
sintético de José. Seleccionar los seis UUID explícitamente para la demo.
Ver `../../datos/geografia/README.md`; comprobar con
`../tests/01_sectores_puntos_smoke.sql`. Probada localmente en PostgreSQL temporal,
no aplicada a Supabase real por esta entrega.


En SQL Editor, copiar y ejecutar TODO `01_sectores_puntos.sql` sin seleccionar
fragmentos. La carga se ejecuta en un único bloque `DO`: creación de tabla
auxiliar, comprobaciones e inserciones comparten una transacción. No crear
`ra_catalogo_oeste` como tabla permanente. Después ejecutar el smoke completo.
Si aparece «current transaction is aborted» tras un intento anterior, ejecutar
`ROLLBACK;` antes de volver a cargar. La semilla conserva las filas existentes.
