# Ensayo territorial 2: nueva política de prioridad

Versión de datos: `oeste-1.0-ensayo-2`. Conserva los seis UUID y referencias del catálogo de Emilia.

Esta versión conserva las demandas, flota, depósito, ventanas, descargas y tiempos sintéticos del ensayo 1; cambia la política a `oeste-prioridad-apoyo-pa-1`, con pesos 40 % duración, 40 % vulnerabilidad y 20 % población. Se incrementan versión de solicitud y datos; ninguna propuesta anterior queda reutilizada como si empleara la nueva política.

La copia de política incluida en `solicitud_rutas.json` debe coincidir con `../politica_apoyo_panama_v1.json`. `supuestos.json` identifica su archivo fuente y política previa. La matriz conserva valores y nodos; su identificador queda asociado a esta versión de escenario. Los incidentes y recursos conservan sus identidades de ensayo.

Los documentos oficiales apoyan requisitos sanitarios y revisión de casos críticos; no establecen esos porcentajes. Leer `docs/politica_prioridad_oeste.md` para fundamento, fórmula, clasificación y límites. Se mantienen topes técnicos de 168 horas y 500 personas, sin carácter normativo.

Las seis demandas permanecen pendientes, recepción desconocida y política sin activar. No hay confirmaciones de coordinador, plan calculado ni autorización operativa. Las condiciones sanitarias no son comprobadas por el cálculo del puntaje. Los datos sintéticos no describen necesidades actuales de las instalaciones.

Comprobar desde la raíz:

```powershell
.\.venv\Scripts\python.exe scripts/verificar_escenario_v3.py --carpeta datos/escenario/oeste-1.0-ensayo-2
.\.venv\Scripts\python.exe -m pytest calculo/tests/test_politica_apoyo_panama.py -q
```

La evidencia específica está en `evals/resultados/politica_apoyo_panama_v1.json` y `politica_apoyo_panama_v1_pruebas.xml`. El comprobador sigue usando por defecto el ensayo 1 para conservar su comando histórico; indicar `--carpeta` para el ensayo 2.
