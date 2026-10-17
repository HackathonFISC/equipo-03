# Infraestructura y operación local

Referencia V6 de José basada en d35d80e. Noel valida el arranque integrado y
Emilia confirma las migraciones aplicadas. No se registran cuentas ni claves.

## Componentes

| Componente | Ejecución | Responsabilidad |
| --- | --- | --- |
| API | `python -m uvicorn api.main:app --reload`, puerto 8000 | Noel: HTTP, sesiones verificadas y RPC. |
| Trabajador | Iniciado por lifespan de API | Emilia: ejecuciones, reservas y eventos; arranque automático D015. |
| Bot | `python -m bot.bot`, un proceso por token | Noel: recibe/envía por API, sin acceso directo a Supabase/Gemini. |
| Panel | `npm run dev`, puerto 5173 | Noel: React/Vite, API y login mediante Supabase Auth. |
| Supabase | Servicio remoto del equipo | Postgres/Auth, esquema de Emilia y controles de Noel. |
| Gemini | Proveedor externo de interpretación | Adaptador de Emilia; consume cuota. Cálculo numérico local. |

El bloqueo local evita duplicados administrados en el mismo checkout. Las reservas
SQL son la autoridad sobre ejecuciones; no equivale a alta disponibilidad ni
impide iniciar procesos manuales desde otras copias. Salud local no demuestra
conectividad externa.

## Variables privadas

Copiar `.env.example` a `.env` en la raíz. El cliente común da precedencia al
entorno del proceso. No publicar archivos completados.

| Variable | Consumidor y uso |
| --- | --- |
| `SUPABASE_URL` | Backend y verificación Auth, URL del proyecto. |
| `SUPABASE_SERVICE_ROLE_KEY` | Solo servidor, persistencia privilegiada. |
| `SUPABASE_ANON_KEY` | API, verificación de sesión mediante Auth. |
| `GEMINI_API_KEY` | Interpretación de reportes. |
| `GEMINI_MODEL` | Modelo opcional; confirmar disponibilidad/cuota con Emilia. |
| `TELEGRAM_BOT_TOKEN` | Solo proceso bot. |
| `TELEGRAM_CHAT_IDS_PRUEBA` | Chats autorizados de ensayo; valores privados. |
| `API_SECRETO_BOT` | Compartido API/bot, mínimo 16 caracteres. |
| `API_URL` | Bot, por defecto `http://127.0.0.1:8000`. |
| `TRABAJADOR_AUTOMATICO` | `true` por defecto; `false` para trabajador externo controlado. |
| `TZ` | Referencia `America/Panama`; contratos exigen fechas con zona. |

Crear `frontend/.env` para el navegador:

```dotenv
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

Los valores `VITE_` quedan expuestos en el cliente compilado. Nunca incluir
`service_role`, token Telegram o clave Gemini. CORS permite
`http://localhost:5173`; otra dirección requiere revisión de Noel.

## Base de datos y escenario

Seguir [el orden explícito de migraciones](../supabase/migrations/README.md),
no el orden numérico: 0003 requiere 0009/0011 y precede a 0012; 0013 cubre feedback
de aclaraciones. No ejecutar scripts automáticamente por leer esta guía.
Emilia y Noel registran versiones aplicadas y resultados de los smoke por entorno.
Los smoke con rollback no prueban Telegram. El guion de concurrencia 0003 usa
base desechable y deja fixtures confirmados; no ejecutarlo sobre la base operativa.

El [catálogo](../datos/geografia/README.md) define UUID. El
[ensayo 3](../datos/escenario/oeste-1.0-ensayo-3/README.md) conserva parámetros y
confirmaciones ficticios. Persistencia aislada: [ensayo V2](ENSAYO_PRIORIZACION_V2.md)
y [planificación V3](V3_EMILIA.md). No reasignar fixtures antiguos a UUID nuevos
ni tratar confirmaciones ficticias como autorización de un coordinador real.

## Arranque y recuperación

Comandos en [README](../README.md). Iniciar API, bot y panel. No añadir trabajador
manual con el modo automático activo. Revisar `/salud`, `/salud/agentes` y los
eventos de la ejecución. Plan conserva ejemplos; Aprobación lee API persistida.

| Síntoma | Comprobación y actuación |
| --- | --- |
| Reporte sin interpretar | Revisar trabajador, etapa, estado y cuota Gemini. Un 429 no se reencola solo; Emilia decide recuperación. |
| Espera de aclaración/revisión | Revisar faltantes y respuesta vinculada; no confirmar desconocidos para forzar avance. |
| Plan invalidado | Conservar historial; recalcular y obtener aprobación de nueva versión. |
| Aviso sin salir | Comprobar interruptor, selección por sector, suscripción y destino de ensayo autorizado; Noel decide activación. |
| Envío incierto/reserva vencida | Conservar estado y revisar; no reenviar automáticamente. |
| Trabajador termina | Revisar causa y log; el supervisor registra la salida, sin reinicio ciego. |
| Reinicio planificado | Ctrl+C, esperar cierre, revisar procesos/reservas y reiniciar; comprobar caso 24 real. |

El cierre automático solicita parar entre trabajos, espera hasta 60 s y puede
terminar el proceso si no cierra. No se acredita recuperación ante caída abrupta
ni failover. Mantener un solo receptor de Telegram por token.

## Reproducibilidad y acceso

La auditoría V6 usa una copia sin `.env` y el intérprete existente. Conserva
estado Git, hashes, XML y logs. No instala paquetes ni migra BD. El lock Python
es de restricciones; Node usa `package-lock.json` con `npm ci`.
La instalación desde cero sigue pendiente y debe registrarse con commit,
versiones y comandos en la laptop de exposición. No compartir claves, chat IDs
ni textos personales en evidencias. Ver [entrega V6](ENTREGA_V6.md).
