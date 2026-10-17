# Catálogo inicial de geografía

**Dueña: Emilia. Versión: oeste-1.0.**

Emilia confirmó seis puntos totales para la demo: tres en Arraiján y tres en
La Chorrera. Se mantienen dos cisternas y un depósito. Los seis lugares son
candidatos para revisión; aceptar el alcance no autoriza entregas allí.

`puntos.csv` contiene UUID estables, nombre de instalación, sector de referencia,
provincia/distrito/corregimiento, coordenadas y procedencia. `alias.csv` contiene
nombres y variantes de escritura vinculados por UUID. No usa nombres de
corregimientos ni distritos como alias de una sola instalación: «Vista Alegre»
no basta para resolver automáticamente «Junta Comunal de Vista Alegre».

## Fuente y validación

Los nombres, coordenadas y división territorial se transcriben del registro
de puntos de internet de AIG de enero de 2022. PA identifica la fila de AIG,
no una instalación habilitada por IDAAN. Se conservan páginas 27, 28 y 30 y
fecha de consulta 2026-10-16. No se afirma una actualización de la fuente a 2026.

[Fuente AIG en Datos Abiertos](https://datosabiertos.gob.pa/dataset/2e947382-70dd-46a5-9fcb-6fe2f466ca9c/resource/5ba77e85-3b95-4737-bd05-9599da74a320/download/aig-puntos-de-acceso-de-la-rni2.0-vigentes-en-enero2022.pdf).

- `origen=real` describe la referencia documental de la instalación. No demuestra
  desabastecimiento, demanda, población atendida o criticidad actuales.
- `estado_validacion=pendiente`: acceso, autorización del lugar y posición exacta
  de descarga siguen sin comprobarse.
- Precisión en metros, capacidad de recepción y `representa_punto_atencion`
  quedan vacíos en CSV y NULL en SQL. No se convierten a cero, false ni true.
- `activo=true` significa visible en el catálogo, no autorizado para distribuir.
- Las coordenadas son del punto de internet documentado, no del acceso de cisterna.
- Alias adicionales del habla local deben tener fuente y revisión. No se añadieron
  barrios o instalaciones cercanas como equivalencias por suposición.

## Identificadores y compatibilidad

Los UUID se derivan de identidades estables con UUIDv5. El identificador de punto
usa el PA de la fuente; el de sector, distrito y corregimiento. No incluyen la
versión del catálogo ni se generan de nuevo al cargar. Un lugar distinto necesita
otra identidad; no reutilizar los UUID de P1–P6 sintéticos para instalaciones reales.

El sector inicial usa el nombre del corregimiento como zona de referencia para
la demo; no es un polígono ni una delimitación oficial de reparto. Una mención
amplia debe pedir precisión, aunque hoy exista un solo punto en ese sector.

La estructura funciona con los contratos vigentes. El resolvedor Territorial y
la consolidación de V2 ya están implementados; ver [geografía](../../geografia/README.md)
y [flujo V2](../../docs/V2_EMILIA.md). Los CSV son sus datos de referencia; por sí
solos no ejecutan reconocimiento ni validan el lugar para una entrega.

## Cargar y comprobar

1. Revisar `supabase/seed/01_sectores_puntos.sql` y ejecutarlo completo después
   de 0001, con rol administrativo. No es una migración de estructura.
2. Ejecutar `supabase/tests/01_sectores_puntos_smoke.sql`. La comprobación no
   crea necesidades, rutas ni validaciones operativas.
3. La semilla solo inserta ausentes. Reejecutarla conserva coordenadas corregidas,
   validaciones, capacidad de recepción, alias y demás cambios de las filas
   existentes. Una actualización del CSV no actualiza automáticamente esas filas.
4. Un UUID vinculado a otro territorio o un lugar equivalente con otro UUID
   detiene la transacción para revisar la correspondencia; no se fusionan filas.

Regeneración reproducible desde la raíz:

```bash
.venv/bin/python -m geografia.generar_semilla
.venv/bin/python -m pytest geografia/tests/test_catalogo.py -q
```

El generador es para esta entrega inicial pendiente de validación. Cambios de
alcance, fuente o estado operativo necesitan una revisión explícita. Los campos
vacíos no son una forma de ocultar datos conocidos.

## Entrega a José y Noel

José ya preparó los [ensayos 1–3](../escenario/README.md) con estos UUID;
[solver y verificador V3](../../calculo/PLAN_V3.md) están implementados y tienen
pruebas locales. Los depósitos, matrices, demandas y ventanas de esos ensayos
conservan su carácter sintético; no son una validación operativa de los lugares. Los fixtures `escenario-1.0` continúan siendo
sintéticos y no se modifican ni se convierten en datos reales al cargar esta
semilla. No hay equivalencia automática entre P1–P6 y estas instalaciones.

Noel puede listar distrito/corregimiento y estado pendiente. Las suscripciones
de destinos a sectores deben usar los UUID del catálogo elegido. No activar
avisos ni transferir suscripciones de sectores sintéticos por coincidencia de nombre.

La semilla identifica sus seis puntos por UUID; no exige que toda la BD tenga
solo seis filas ni borra otros catálogos. La demo debe seleccionar estos seis
explícitamente y no mezclar sus referencias con el escenario anterior.
