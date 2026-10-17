# V6: preparación y cierre de entrega

José prepara documentación, auditoría y consolidación. El cierre requiere
evidencia del equipo: V4/V5 integradas siguen pendientes en la revisión d35d80e.
Estos archivos no habilitan publicación ni convierten ensayos locales en cierre.

## Preparación propia

- [README](../README.md): problema, arquitectura, cuatro tools, instalación y uso.
- [Infraestructura](infraestructura.md): procesos, variables, migraciones y recuperación.
- [Bitácora consolidada](bitacora_ia/BITACORA_IA.md): tres fuentes literales con hashes.
- `scripts/auditar_entrega.py`: copia candidata, regresión, demos y manifiesto.
- [V4](../evals/V4.md) y [V5](../evals/V5.md): casos y límites de evidencia.

[Evidencia preparatoria ejecutada](../evals/resultados/v6_preparacion/README.md):
715 pruebas y 66 subpruebas aprobadas, demos y comparación correctas. Sus hashes
identifican el snapshot probado; no son una declaración de cierre integrado.

## Auditoría local sin servicios externos

Desde raíz, con salida nueva fuera del repositorio:

```powershell
.\.venv\Scripts\python.exe scripts/auditar_entrega.py --salida ../tmp/entrega_v6_01
```

Git y Node deben estar disponibles, o indicarse con `--git "ruta/al/git.exe"`
y `--node "ruta/al/node.exe"`. No se descargan herramientas.

| Salida | Contenido |
| --- | --- |
| `candidato/` | Archivos versionados y nuevos no ignorados, incluyendo V6; sin `.git`, `.env`, `.venv` ni `node_modules`. |
| `informe.json` | Commit base, estado Git, hashes de archivos, controles y pendientes. |
| XML y logs | Regresión y demos locales; JUnit incluye subpruebas en su total. |
| `comparacion_v5.json` | Cinco casos sintéticos, tres repeticiones por método, snapshots y verificación. |

Usa Python/paquetes instalados fuera de la copia, sin credenciales de servicios
en los controles y con trabajador desactivado. HTTP usa dobles explícitos. No
inicia API/bot/agentes reales. Comprueba sondeo Node sin instalar el frontend;
lint/build e instalación nueva se comprueban por separado.
Código 0: éxito local; 1: fallo; 2: control pendiente. Siempre `cierre_v6=false`.

Rechaza rutas fuera del repositorio, enlaces, archivos de entorno privados y
extensiones de claves. No certifica ausencia de secretos incrustados en código;
la revisión humana sigue necesaria. Si las fuentes cambian durante la auditoría,
el resultado falla. Cambios posteriores exigen repetirla para la versión final.

Regenerar consolidación tras actualizar fuentes:

```powershell
.\.venv\Scripts\python.exe scripts/auditar_entrega.py --consolidar-bitacoras ../tmp/BITACORA_IA_nueva.md
```

El destino debe ser nuevo. Revisar y sustituir la consolidación publicada,
manteniendo intactas las fuentes. La copia literal no certifica hechos ajenos.

## Pendientes para cerrar V6

| Comprobación | Responsable | Evidencia pendiente |
| --- | --- | --- |
| Clonado e instalación nuevos | José y Noel | Commit concreto, Python/Node, instalación de requirements y npm ci; la copia candidata no lo reemplaza. |
| Migraciones y concurrencia | Emilia y Noel; José revisa | Versiones aplicadas y smoke por entorno; intercalado real del caso 21. |
| Tres recorridos seguidos, uno adverso | Equipo | Misma versión entregable, trazas y resultados; registrar fallos y repetir la serie estable. |
| Robustez V5 | Noel y Emilia; José evalúa | Casos 19/22/23/24/25 reales, incluida nueva aprobación y aviso tras retiro. |
| Dos correcciones del panel notificadas | Noel | Respuestas tardías por sector y origen visible; revisar siguiente pull. |
| Datos/autorización de demo | Equipo | Origen sintético visible, destinatarios autorizados, coordinador real; sin rellenar desconocidos. |
| Acceso y laptop | Noel y equipo | Prueba desde entorno de exposición y acceso de evaluadores. |
| Exposición y respaldo | Equipo; guion de Emilia | Ensayo 6 min 30 s, máximo siete; respaldo identificado como grabación. |
| Git y envío final | José verifica; Noel envía | Tag final-24h sobre commit validado, acceso y comprobante de envío/acuse. La auditoría no publica ni crea tags. |

## Registro de recorridos reales

Completar con evidencias sanitizadas, sin tokens, chat IDs ni datos personales:

| Recorrido | Caso | Resultado y evidencia |
| --- | --- | --- |
| 1 | Reporte → interpretación/aclaración → incidente → necesidad/prioridad → plan verificado → aprobación vigente → aviso recibido | Pendiente: ejecución, plan/versión, datos/política, eventos y recepción. |
| 2 | Otro caso válido sobre la misma versión entregable | Pendiente: identidades nuevas e inexistencia de duplicados indebidos. |
| 3 | Retiro de cisterna antes de salida | Pendiente: invalidación, déficit, recálculo, nueva versión/aprobación/aviso, conservando historial. |

Registrar recepción→propuesta y aprobación→envío con fechas reales y zona horaria;
no sustituirlas por tiempo de funciones. Si queda un crítico sin cubrir, registrar
el bloqueo esperado y demostrar después un escenario autorizable, sin relajar
restricciones para conseguir un aviso.

Revisar documentos y evidencia contra el commit final. Un resultado local no
autoriza afirmar proyecto completo ni realizar reparto operativo de agua.
