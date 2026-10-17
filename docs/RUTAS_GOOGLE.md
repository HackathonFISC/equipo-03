# Rutas viales con Google Maps

La extensión añade tiempos de conducción por carretera a la planificación existente,
enlaces de navegación por cisterna y una vista previa para reportes localizados
fuera del diccionario. No necesita crear incidentes ni puntos ficticios para esa vista.

## Activar

1. En el proyecto de Google Cloud, habilitar **Routes API**, con facturación.
   La clave del servidor debe tener acceso tanto a Geocoding como a Routes API,
   o usar una clave independiente en `GOOGLE_ROUTES_API_KEY`.
2. Aplicar `supabase/migrations/0018_localizacion_automatica.sql` y luego
   `0019_matriz_vial_planificacion.sql` si no están aplicadas. 0019 solo modifica
   la matriz de una planificación reservada y aún sin resultado; no cambia
   capacidades, destinos, cantidades, aprobaciones ni planes calculados.
3. En `.env` del backend:

   ```dotenv
   GOOGLE_MAPS_API_KEY=tu_clave_del_servidor
   GOOGLE_ROUTES_ACTIVAS=true
   # GOOGLE_ROUTES_API_KEY=opcional_clave_separada
   ```

4. Reiniciar API/trabajador y reconstruir el frontend.
5. En **Plan**, abrir «Recorrido de reportes localizados», cargar destinos,
   elegir depósito activo y hasta seis reportes, y pulsar «Calcular recorrido».
   Los reportes deben tener coordenadas compartidas o una localización Google
   vigente. El depósito debe existir con coordenadas correctas; no se inventa uno.

La vista previa funciona con una clave configurada incluso si el uso automático
está desactivado. Se calcula solo al pulsar el botón, sin sondeo que consuma cuota.
La página muestra el orden sugerido, minutos de conducción, kilómetros y enlaces
por tramo, incluido el retorno. Es un recorrido previo: no asigna litros ni camión.
Las cantidades, ventanas de descarga y capacidades se consideran en la planificación
completa, con el optimizador y el verificador existentes.

## Planificación completa

Con `GOOGLE_ROUTES_ACTIVAS=true`, antes de calcular una nueva planificación el
trabajador consulta Compute Route Matrix para el depósito y los puntos de esa
solicitud. Actualiza el snapshot de manera atómica, con reserva y comparación
contra cambios concurrentes. Solver y verificador reciben exactamente la misma
matriz dirigida. La procedencia de los tiempos es `estimado`, no `sintetico`.
No se replanifican silenciosamente planes guardados, aprobados o en curso.

Los planes existentes conservan sus restricciones y su modo de ensayo. Esta mejora
no convierte los escenarios sintéticos en operaciones reales ni incorpora demandas
no confirmadas al optimizador. Los reportes recién geocodificados están disponibles
en la vista previa; su distribución completa requiere el circuito de necesidades.

Los enlaces de cada cisterna salen de las coordenadas congeladas en el snapshot del
plan, no del catálogo actual. El enlace completo incluye regreso al depósito. Los
enlaces individuales evitan límites de paradas de algunos navegadores móviles.
Abrir Google Maps puede recalcular indicaciones y tiempos de acuerdo con las
condiciones vigentes; no modifica el plan guardado.

## Cálculo y fallos

- Máximo siete nodos: depósito y seis destinos. Una consulta genera hasta 49 elementos.
  Google factura por elementos según la modalidad habilitada; no se asume gratuidad.
- Se utiliza DRIVE y TRAFFIC_UNAWARE: tiempos viales estimados sin tráfico en vivo.
  No se anuncia como una predicción de tráfico para la hora exacta de salida.
- Se respetan sentidos de circulación: A→B puede diferir de B→A.
- Segundos fraccionarios se redondean hacia arriba a minutos para el solver.
- Tramos ROUTE_NOT_FOUND se conservan como inaccesibles. Una matriz incompleta,
  malformada o con errores no se rellena con ceros ni con el fixture sintético.
- Un fallo de Google al planificar evita ejecutar el solver con tiempos sustituidos;
  la ejecución conserva un motivo de revisión. La vista previa muestra un error.
- La clave viaja en un header del backend, nunca al navegador ni en enlaces.
- El modo DRIVE no certifica restricciones particulares de peso/altura para cisternas.

## Pruebas y CLI

`python -m pytest geografia/tests api/tests agentes/tests -q` usa Google simulado,
sin cuota ni datos reales. El harness PostgreSQL efímero puede verificar la cadena
completa, incluido cierre y verificación independiente:

```sh
RA_PROBAR_RUTAS_GOOGLE=1 RA_EVIDENCIA=/tmp/rutas_evidencia.json \
RA_PGLITE_PACKAGE=/ruta/temporal/package.json \
node supabase/tests/0016_integracion_local.mjs
```

Para un ensayo local con llamadas reales a Google y sin escritura en Supabase:

```sh
python -m scripts.ensayar_v3 local --rutas-google --salida /tmp/ensayo-rutas.json
```

`preparar --rutas-google` también permite guardar un escenario con matriz vial
antes de registrarlo. No colocar claves en la línea de comandos ni subir salidas
con coordenadas personales al repositorio.

Referencias: [Compute Route Matrix](https://developers.google.com/maps/documentation/routes/compute_route_matrix),
[Maps URLs](https://developers.google.com/maps/documentation/urls/get-started).
