#!/usr/bin/env bash
# Esqueleto inicial de RutaAgua Oeste (equipo-03).
# Uso: dentro del repo clonado, en la rama main:  bash crear_esqueleto.sh
# Funciona en Linux, macOS y Git Bash (Windows).
set -euo pipefail

# carpeta | dueño | qué va ahí
CARPETAS=(
  "contratos|Emilia (COMPARTIDO: cambios con aviso a los tres)|Modelos Pydantic de los 5 contratos, estados y errores"
  "contratos/ejemplos|Emilia|Un JSON de ejemplo por contrato para trabajar con datos simulados"
  "comun|Emilia|Cliente de Supabase del backend y configuración"
  "supabase/migrations|Emilia (0001) y Noel (0002, 0003)|0001_esquema.sql, 0002_politicas_rls.sql, 0003_aprobacion.sql"
  "supabase/seed|Emilia (01) y José (02)|01_sectores_puntos.sql, 02_escenario.sql"
  "geografia|Emilia|catalogo.py, resolver.py (resolve_location), consolidacion.py (link_reports)"
  "geografia/tests|Emilia|Casos 5 a 8"
  "agentes|Emilia|Los 5 agentes, herramientas.py y trazas.py"
  "agentes/tests|Emilia|Casos 1 a 4"
  "orquestador|Emilia|trabajador.py y flujo.py"
  "orquestador/tests|Emilia|Pruebas del flujo y la reanudación"
  "calculo|José|demanda, prioridad, matriz, solver, verificador, orden_llegada"
  "calculo/tests|José|Casos 9 a 17"
  "api|Noel|FastAPI: main.py, auth.py"
  "api/rutas|Noel|reportes, incidentes, propuestas, ejecuciones, planes, aprobaciones, publicacion, paradas, estado_sector"
  "api/servicios|Noel|aprobacion.py (request_approval), bandeja_salida.py (publish_approved_messages)"
  "api/tests|Noel|Casos 18 a 25 (unitarias)"
  "bot|Noel|bot.py (único proceso de recepción), adaptador.py, plantillas.py"
  "frontend|Noel|React + Leaflet"
  "datos/geografia|Emilia|puntos.csv y alias.csv con fuente y verificación"
  "datos/escenario|José|vehiculos.json, demandas.json, politica_v1.json"
  "datos/entradas_prueba|Emilia (territorio.json) y José (necesidades_ataques.json)|Mensajes de prueba; media/ opcional"
  "evals|José|ejecutar.py, metricas.py"
  "evals/independientes|José|Pruebas de caja negra: autorización y operación (18 a 25)"
  "evals/resultados|José|Resultados con entrada, esperado, obtenido, versión y traza"
  "scripts|José (Noel valida)|arrancar.sh, verificar_entorno.py, clonado_limpio.sh"
  "docs|Emilia (arquitectura, guion) y José (infraestructura, decisiones)|Documentación de entrega"
  "docs/bitacora_ia|Cada quien su archivo; José consolida|emilia.md, noel.md, jose.md, BITACORA_IA.md"
)

for linea in "${CARPETAS[@]}"; do
  IFS="|" read -r ruta dueno contenido <<< "$linea"
  mkdir -p "$ruta"
  printf "# %s\n\n**Dueño:** %s\n\n%s\n" "$ruta" "$dueno" "$contenido" > "$ruta/README.md"
done

# Paquetes de Python (para importar entre carpetas desde la raíz del repo)
for pkg in contratos comun geografia agentes orquestador calculo api api/rutas api/servicios bot evals; do
  touch "$pkg/__init__.py"
done

# Bitácoras individuales (cada quien escribe solo la suya)
for nombre in emilia noel jose; do
  printf "# Bitácora de IA: %s\n\n| Fecha y hora | Herramienta | Uso | Salida aprovechada | Cambios y revisión humana |\n| --- | --- | --- | --- | --- |\n" "$nombre" > "docs/bitacora_ia/$nombre.md"
done
printf "| 2026-10-16 | Claude | Esqueleto de carpetas y plan de flujo de trabajo | Estructura del repo | Revisado por Noel |\n" >> "docs/bitacora_ia/noel.md"

cat > .gitignore <<'EOF'
# Secretos
.env
.env.*
!.env.example

# Python
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/

# Node / React
node_modules/
frontend/dist/
frontend/build/

# Sistema
.DS_Store
Thumbs.db
.idea/
.vscode/
EOF

cat > .env.example <<'EOF'
# Copiar a .env y llenar. Nunca subir .env.
# Verificar los nombres exactos que pida cada librería (José mantiene este archivo).

# Supabase
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=      # solo backend

# Modelo (Gemini vía Google AI Studio)
GEMINI_API_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_IDS_PRUEBA=       # chats autorizados para la demo, separados por coma

# General
TZ=America/Panama
EOF

cat > requirements.txt <<'EOF'
# Dependencias de Python. Dueño: José. Agregar líneas nuevas avisando al equipo.
EOF

cat > README.md <<'EOF'
# RutaAgua Oeste

Sistema multiagente que convierte reportes ciudadanos de falta de agua en Panamá Oeste
en un plan de cisternas verificado, aprobado por un coordinador humano y comunicado a cada sector.

Hackatón FISC AI Agents 2026 · Reto 1: Agua · Equipo 03

## Ramas
- `main`: siempre ejecutable; solo cambia por pull request.
- `emilia`, `noel`, `jose`: rama personal de cada integrante.

Instalación, arranque y arquitectura: pendiente (José, Emilia).
EOF

echo "Esqueleto creado. Revisa con: git status"
