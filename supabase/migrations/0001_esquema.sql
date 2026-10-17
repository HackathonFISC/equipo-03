-- RutaAgua Oeste / Emilia / esquema inicial V0 / contratos 1.0.
-- Ejecutar UNA VEZ en un proyecto Supabase vacio, con el rol postgres.
-- No contiene claves, puntos reales, politica activa ni datos operativos.
-- 0002 (Noel): roles y politicas de acceso. 0003 (Noel): aprobacion atomica.
BEGIN;

DO $$
BEGIN
  IF to_regclass('auth.users') IS NULL THEN
    RAISE EXCEPTION 'Se requiere Supabase Auth (auth.users). No crear una tabla sustituta en el proyecto real.';
  END IF;
END $$;

CREATE TYPE public.ra_origen AS ENUM ('real', 'estimado', 'sintetico');
CREATE TYPE public.ra_validacion AS ENUM ('pendiente', 'validada', 'rechazada');
CREATE TYPE public.ra_clase_prioridad AS ENUM ('critico', 'general');
CREATE TYPE public.ra_vulnerabilidad AS ENUM ('sin_condicion_identificada', 'moderada', 'alta');
CREATE TYPE public.ra_estado_ejecucion AS ENUM ('pendiente', 'ejecutando', 'espera_aclaracion', 'espera_validacion', 'espera_revision', 'completada', 'fallida');
CREATE TYPE public.ra_estado_plan AS ENUM ('calculando', 'pendiente_revision', 'aprobado', 'rechazado', 'invalidado');
CREATE TYPE public.ra_estado_aviso AS ENUM ('pendiente', 'enviado', 'fallido', 'incierto', 'cancelado');
CREATE TYPE public.ra_estado_parada AS ENUM ('programada', 'iniciada', 'atendida', 'con_incidencia');
CREATE TYPE public.ra_estado_solver AS ENUM ('factible', 'timeout_sin_solucion', 'inviabilidad_demostrada', 'error');
CREATE TYPE public.ra_agente AS ENUM ('ingesta', 'territorial', 'priorizacion', 'planificacion', 'comunicacion');
CREATE DOMAIN public.ra_cantidad AS numeric CHECK (VALUE >= 0 AND VALUE < 'Infinity'::numeric);
CREATE DOMAIN public.ra_proporcion AS numeric CHECK (VALUE >= 0 AND VALUE <= 1);

CREATE TABLE public.usuarios_operativos (
  usuario_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE RESTRICT,
  rol text NOT NULL CHECK (rol IN ('coordinador', 'conductor', 'consulta')),
  activo boolean NOT NULL DEFAULT false,
  creado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text NOT NULL CHECK (length(btrim(motivo)) > 0)
);

CREATE TABLE public.sectores (
  sector_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL CHECK (length(btrim(nombre)) > 0),
  distrito text NOT NULL DEFAULT 'Arraijan',
  corregimiento text,
  origen public.ra_origen NOT NULL,
  fuente text NOT NULL CHECK (length(btrim(fuente)) > 0),
  estado_informacion text NOT NULL DEFAULT 'sin_informacion'
    CHECK (estado_informacion IN ('sin_informacion', 'pendiente_verificar', 'necesidad_conocida', 'atencion_reciente')),
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text
);

CREATE TABLE public.puntos_atencion (
  punto_atencion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sector_id uuid NOT NULL REFERENCES public.sectores ON DELETE RESTRICT,
  nombre text NOT NULL CHECK (length(btrim(nombre)) > 0),
  alias text[] NOT NULL DEFAULT '{}',
  latitud numeric CHECK (latitud BETWEEN -90 AND 90),
  longitud numeric CHECK (longitud BETWEEN -180 AND 180),
  precision_metros public.ra_cantidad,
  fuente_ubicacion text CHECK (fuente_ubicacion IN ('catalogo', 'compartida', 'coordinador', 'escenario')),
  representa_punto_atencion boolean,
  estado_validacion public.ra_validacion NOT NULL DEFAULT 'pendiente',
  capacidad_recepcion_litros public.ra_cantidad,
  origen public.ra_origen NOT NULL,
  fuente text NOT NULL CHECK (length(btrim(fuente)) > 0),
  activo boolean NOT NULL DEFAULT true,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text,
  UNIQUE (punto_atencion_id, sector_id),
  CHECK ((latitud IS NULL) = (longitud IS NULL)),
  CHECK (estado_validacion <> 'validada' OR
         (latitud IS NOT NULL AND longitud IS NOT NULL AND representa_punto_atencion IS TRUE))
);

CREATE TABLE public.depositos (
  deposito_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL CHECK (length(btrim(nombre)) > 0),
  latitud numeric NOT NULL CHECK (latitud BETWEEN -90 AND 90),
  longitud numeric NOT NULL CHECK (longitud BETWEEN -180 AND 180),
  fuente_ubicacion text NOT NULL CHECK (fuente_ubicacion IN ('catalogo', 'compartida', 'coordinador', 'escenario')),
  precision_metros public.ra_cantidad,
  origen public.ra_origen NOT NULL,
  fuente text NOT NULL CHECK (length(btrim(fuente)) > 0),
  activo boolean NOT NULL DEFAULT true,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text
);

CREATE TABLE public.vehiculos (
  vehiculo_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL CHECK (length(btrim(nombre)) > 0),
  capacidad_litros public.ra_cantidad NOT NULL CHECK (capacidad_litros > 0),
  disponible boolean NOT NULL DEFAULT false,
  turno_inicio timestamptz NOT NULL,
  turno_fin timestamptz NOT NULL,
  deposito_id uuid NOT NULL REFERENCES public.depositos ON DELETE RESTRICT,
  origen public.ra_origen NOT NULL,
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text,
  CHECK (turno_fin > turno_inicio)
);

CREATE TABLE public.politicas_prioridad (
  politica_version text PRIMARY KEY CHECK (length(btrim(politica_version)) > 0),
  estado text NOT NULL DEFAULT 'propuesta_demo' CHECK (estado IN ('propuesta_demo', 'activa')),
  origen public.ra_origen NOT NULL CHECK (origen = 'sintetico'),
  peso_duracion public.ra_proporcion NOT NULL,
  peso_vulnerabilidad public.ra_proporcion NOT NULL,
  peso_poblacion public.ra_proporcion NOT NULL,
  tope_horas public.ra_cantidad NOT NULL CHECK (tope_horas > 0),
  tope_personas integer NOT NULL CHECK (tope_personas > 0),
  vulnerabilidad_moderada public.ra_proporcion NOT NULL CHECK (vulnerabilidad_moderada > 0 AND vulnerabilidad_moderada < 1),
  criticos_obligatorios boolean NOT NULL DEFAULT true CHECK (criticos_obligatorios),
  faltantes_fuera_ranking boolean NOT NULL DEFAULT true CHECK (faltantes_fuera_ranking),
  orden_desempate text NOT NULL DEFAULT 'ultima_atencion_luego_incidente_luego_id'
    CHECK (orden_desempate = 'ultima_atencion_luego_incidente_luego_id'),
  fundamento text NOT NULL CHECK (length(btrim(fundamento)) > 0),
  confirmacion_activacion jsonb CHECK (confirmacion_activacion IS NULL OR jsonb_typeof(confirmacion_activacion) = 'object'),
  creado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  CHECK (abs(peso_duracion + peso_vulnerabilidad + peso_poblacion - 1) < 0.000000001),
  CHECK (estado <> 'activa' OR (confirmacion_activacion IS NOT NULL AND confirmacion_activacion ?& ARRAY['usuario_id','confirmado_en','motivo']))
);

CREATE TABLE public.remitentes (
  remitente_ref uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canal text NOT NULL CHECK (canal IN ('telegram', 'panel')),
  identificador_externo text NOT NULL CHECK (length(btrim(identificador_externo)) > 0),
  creado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (canal, identificador_externo)
);

CREATE TABLE public.destinos (
  destino_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canal text NOT NULL CHECK (canal IN ('telegram', 'panel')),
  identificador_externo text NOT NULL CHECK (length(btrim(identificador_externo)) > 0),
  remitente_ref uuid REFERENCES public.remitentes ON DELETE RESTRICT,
  autorizado boolean NOT NULL DEFAULT false,
  autorizado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  autorizado_en timestamptz,
  motivo text,
  creado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (canal, identificador_externo),
  CHECK (NOT autorizado OR (autorizado_por IS NOT NULL AND autorizado_en IS NOT NULL AND motivo IS NOT NULL AND length(btrim(motivo)) > 0))
);

CREATE TABLE public.suscripciones_sector (
  destino_id uuid NOT NULL REFERENCES public.destinos ON DELETE RESTRICT,
  sector_id uuid NOT NULL REFERENCES public.sectores ON DELETE RESTRICT,
  activa boolean NOT NULL DEFAULT false,
  creado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text,
  PRIMARY KEY (destino_id, sector_id)
);

CREATE TABLE public.reportes (
  reporte_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  esquema_version text NOT NULL DEFAULT '1.0' CHECK (esquema_version = '1.0'),
  remitente_ref uuid NOT NULL REFERENCES public.remitentes ON DELETE RESTRICT,
  canal text NOT NULL CHECK (canal IN ('telegram', 'panel')),
  mensaje_externo_id text NOT NULL CHECK (length(btrim(mensaje_externo_id)) > 0),
  modalidad text NOT NULL CHECK (modalidad IN ('texto', 'voz', 'foto', 'ubicacion')),
  texto text,
  ubicacion_compartida jsonb CHECK (ubicacion_compartida IS NULL OR jsonb_typeof(ubicacion_compartida) = 'object'),
  interpretacion jsonb CHECK (interpretacion IS NULL OR jsonb_typeof(interpretacion) = 'object'),
  evidencias jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidencias) = 'array'),
  requiere_aclaracion boolean,
  fuera_de_alcance boolean,
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (canal, remitente_ref, mensaje_externo_id),
  CHECK (modalidad <> 'texto' OR (texto IS NOT NULL AND length(btrim(texto)) > 0)),
  CHECK (modalidad <> 'ubicacion' OR ubicacion_compartida IS NOT NULL)
);

CREATE TABLE public.adjuntos (
  adjunto_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporte_id uuid REFERENCES public.reportes ON DELETE RESTRICT,
  remitente_ref uuid REFERENCES public.remitentes ON DELETE RESTRICT,
  procedencia text NOT NULL DEFAULT 'ciudadano' CHECK (procedencia IN ('ciudadano','sistema')),
  tipo text NOT NULL CHECK (tipo IN ('audio', 'foto')),
  bucket text NOT NULL CHECK (length(btrim(bucket)) > 0),
  ruta_privada text NOT NULL CHECK (length(btrim(ruta_privada)) > 0),
  mime_type text NOT NULL,
  tamano_bytes bigint CHECK (tamano_bytes >= 0),
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  UNIQUE (bucket, ruta_privada),
  CHECK (procedencia <> 'ciudadano' OR remitente_ref IS NOT NULL)
);

CREATE TABLE public.ejecuciones (
  ejecucion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporte_id uuid REFERENCES public.reportes ON DELETE RESTRICT,
  estado public.ra_estado_ejecucion NOT NULL DEFAULT 'pendiente',
  etapa text NOT NULL DEFAULT 'ingesta' CHECK (etapa IN ('ingesta','territorial','priorizacion','planificacion','comunicacion','terminada')),
  origen public.ra_origen NOT NULL,
  datos_version text,
  clave_idempotencia text UNIQUE,
  intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
  bloqueada_hasta timestamptz,
  trabajador_id text,
  ultimo_error jsonb CHECK (ultimo_error IS NULL OR jsonb_typeof(ultimo_error) = 'object'),
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.incidentes (
  incidente_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  sector_id uuid REFERENCES public.sectores ON DELETE RESTRICT,
  punto_atencion_id uuid,
  estado_validacion public.ra_validacion NOT NULL DEFAULT 'pendiente',
  ubicacion jsonb CHECK (ubicacion IS NULL OR jsonb_typeof(ubicacion) = 'object'),
  confianza public.ra_proporcion,
  reportes_independientes integer NOT NULL DEFAULT 0 CHECK (reportes_independientes >= 0),
  conflictos text[] NOT NULL DEFAULT '{}',
  faltantes text[] NOT NULL DEFAULT '{}',
  requiere_revision_urgente boolean NOT NULL DEFAULT false,
  periodo_inicio timestamptz NOT NULL,
  periodo_fin timestamptz NOT NULL,
  primera_deteccion_en timestamptz NOT NULL,
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text,
  FOREIGN KEY (punto_atencion_id, sector_id) REFERENCES public.puntos_atencion(punto_atencion_id, sector_id) ON DELETE RESTRICT,
  UNIQUE (incidente_id, punto_atencion_id),
  CHECK (periodo_fin > periodo_inicio),
  CHECK (punto_atencion_id IS NULL OR sector_id IS NOT NULL),
  CHECK (estado_validacion <> 'validada' OR (sector_id IS NOT NULL AND punto_atencion_id IS NOT NULL AND ubicacion IS NOT NULL))
);

CREATE TABLE public.vinculos_reportes (
  vinculo_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incidente_id uuid NOT NULL REFERENCES public.incidentes ON DELETE RESTRICT,
  reporte_id uuid NOT NULL REFERENCES public.reportes ON DELETE RESTRICT,
  vinculado_en timestamptz NOT NULL DEFAULT now(),
  vinculado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  desvinculado_en timestamptz,
  desvinculado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text NOT NULL CHECK (length(btrim(motivo)) > 0),
  CHECK (desvinculado_en IS NULL OR desvinculado_en >= vinculado_en)
);
-- Un mensaje solo pertenece a un incidente activo; al corregir se conserva el vinculo anterior.
CREATE UNIQUE INDEX vinculos_reporte_activo ON public.vinculos_reportes(reporte_id) WHERE desvinculado_en IS NULL;

CREATE TABLE public.necesidades (
  necesidad_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  incidente_id uuid NOT NULL,
  punto_atencion_id uuid NOT NULL,
  datos_version text NOT NULL CHECK (length(btrim(datos_version)) > 0),
  politica_version text NOT NULL REFERENCES public.politicas_prioridad ON DELETE RESTRICT,
  estado_demanda public.ra_validacion NOT NULL DEFAULT 'pendiente',
  demanda_litros public.ra_cantidad,
  metodo_demanda text NOT NULL CHECK (metodo_demanda IN ('directa','formula')),
  entrada_demanda jsonb NOT NULL CHECK (jsonb_typeof(entrada_demanda) = 'object'),
  resultado_demanda jsonb CHECK (resultado_demanda IS NULL OR jsonb_typeof(resultado_demanda) = 'object'),
  confirmacion_demanda jsonb CHECK (confirmacion_demanda IS NULL OR jsonb_typeof(confirmacion_demanda) = 'object'),
  clase_prioridad public.ra_clase_prioridad,
  confirmacion_clase jsonb CHECK (confirmacion_clase IS NULL OR jsonb_typeof(confirmacion_clase) = 'object'),
  ventana_inicio timestamptz,
  ventana_fin timestamptz,
  horas_sin_agua public.ra_cantidad,
  personas_atendidas integer CHECK (personas_atendidas >= 0),
  vulnerabilidad public.ra_vulnerabilidad,
  confirmacion_vulnerabilidad jsonb CHECK (confirmacion_vulnerabilidad IS NULL OR jsonb_typeof(confirmacion_vulnerabilidad) = 'object'),
  ultima_atencion_confirmada_en timestamptz,
  primera_deteccion_en timestamptz NOT NULL,
  estado_prioridad text NOT NULL DEFAULT 'pendiente' CHECK (estado_prioridad IN ('pendiente','calculada')),
  puntaje numeric CHECK (puntaje BETWEEN 0 AND 100),
  componentes jsonb CHECK (componentes IS NULL OR jsonb_typeof(componentes) = 'object'),
  posicion integer CHECK (posicion > 0),
  pendientes text[] NOT NULL DEFAULT '{}',
  supuestos text[] NOT NULL DEFAULT '{}',
  requiere_revision_urgente boolean NOT NULL DEFAULT false,
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text,
  FOREIGN KEY (incidente_id, punto_atencion_id) REFERENCES public.incidentes(incidente_id, punto_atencion_id) ON DELETE RESTRICT,
  UNIQUE (ejecucion_id, datos_version, politica_version, punto_atencion_id),
  CHECK ((ventana_inicio IS NULL) = (ventana_fin IS NULL)),
  CHECK (ventana_fin IS NULL OR ventana_fin > ventana_inicio),
  CHECK (estado_demanda <> 'validada' OR (demanda_litros IS NOT NULL AND confirmacion_demanda IS NOT NULL)),
  CHECK (clase_prioridad IS NULL OR confirmacion_clase IS NOT NULL),
  CHECK (clase_prioridad IS DISTINCT FROM 'critico' OR ventana_inicio IS NOT NULL),
  CHECK ((estado_prioridad = 'pendiente' AND puntaje IS NULL AND componentes IS NULL AND posicion IS NULL AND cardinality(pendientes) > 0)
    OR (estado_prioridad = 'calculada' AND estado_demanda = 'validada' AND horas_sin_agua IS NOT NULL
      AND personas_atendidas IS NOT NULL AND vulnerabilidad IS NOT NULL AND confirmacion_vulnerabilidad IS NOT NULL
      AND clase_prioridad IS NOT NULL AND puntaje IS NOT NULL AND componentes IS NOT NULL AND posicion IS NOT NULL
      AND cardinality(pendientes) = 0))
);

CREATE TABLE public.planes (
  plan_id uuid NOT NULL DEFAULT gen_random_uuid(),
  version integer NOT NULL CHECK (version > 0),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  datos_version text NOT NULL CHECK (length(btrim(datos_version)) > 0),
  politica_version text NOT NULL REFERENCES public.politicas_prioridad ON DELETE RESTRICT,
  estado public.ra_estado_plan NOT NULL DEFAULT 'calculando',
  estado_solver public.ra_estado_solver,
  deposito_id uuid NOT NULL REFERENCES public.depositos ON DELETE RESTRICT,
  solicitud_snapshot jsonb NOT NULL CHECK (jsonb_typeof(solicitud_snapshot) = 'object'),
  no_atendidos jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(no_atendidos) = 'array'),
  supuestos text[] NOT NULL DEFAULT '{}',
  bloqueos_publicacion text[] NOT NULL DEFAULT '{}',
  verificado boolean NOT NULL DEFAULT false,
  verificacion jsonb CHECK (verificacion IS NULL OR jsonb_typeof(verificacion) = 'object'),
  aprobacion_id uuid,
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  creado_por uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  motivo text,
  PRIMARY KEY (plan_id, version),
  UNIQUE (plan_id, version, datos_version, politica_version),
  CHECK (NOT verificado OR ((verificacion ->> 'valido') = 'true') IS TRUE),
  CHECK (estado = 'calculando' OR estado_solver IS NOT NULL),
  CHECK (estado <> 'aprobado' OR (estado_solver = 'factible' AND verificado AND aprobacion_id IS NOT NULL AND cardinality(bloqueos_publicacion) = 0)),
  CHECK (aprobacion_id IS NULL OR estado IN ('aprobado','invalidado')),
  CHECK (NOT jsonb_path_exists(no_atendidos, '$[*] ? (@.clase_prioridad == "critico")') OR cardinality(bloqueos_publicacion) > 0)
);

CREATE TABLE public.rutas (
  ruta_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id uuid NOT NULL,
  version integer NOT NULL,
  vehiculo_id uuid NOT NULL REFERENCES public.vehiculos ON DELETE RESTRICT,
  deposito_id uuid NOT NULL REFERENCES public.depositos ON DELETE RESTRICT,
  salida_estimada timestamptz NOT NULL,
  retorno_estimado timestamptz NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (plan_id, version) REFERENCES public.planes ON DELETE RESTRICT,
  UNIQUE (plan_id, version, vehiculo_id),
  UNIQUE (ruta_id, plan_id, version),
  CHECK (retorno_estimado > salida_estimada)
);

CREATE TABLE public.paradas (
  parada_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ruta_id uuid NOT NULL,
  plan_id uuid NOT NULL,
  version integer NOT NULL,
  incidente_id uuid NOT NULL,
  punto_atencion_id uuid NOT NULL,
  orden integer NOT NULL CHECK (orden > 0),
  litros_asignados public.ra_cantidad NOT NULL CHECK (litros_asignados > 0),
  llegada_estimada timestamptz NOT NULL,
  inicio_descarga timestamptz NOT NULL,
  fin_descarga timestamptz NOT NULL,
  estado public.ra_estado_parada NOT NULL DEFAULT 'programada',
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (ruta_id, plan_id, version) REFERENCES public.rutas(ruta_id, plan_id, version) ON DELETE RESTRICT,
  FOREIGN KEY (incidente_id, punto_atencion_id) REFERENCES public.incidentes(incidente_id, punto_atencion_id) ON DELETE RESTRICT,
  UNIQUE (plan_id, version, punto_atencion_id),
  UNIQUE (ruta_id, orden),
  CHECK (llegada_estimada <= inicio_descarga AND inicio_descarga < fin_descarga)
);

CREATE TABLE public.aprobaciones (
  aprobacion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id uuid NOT NULL,
  version integer NOT NULL,
  datos_version text NOT NULL,
  politica_version text NOT NULL,
  usuario_id uuid NOT NULL REFERENCES public.usuarios_operativos ON DELETE RESTRICT,
  confirmado_en timestamptz NOT NULL DEFAULT now(),
  motivo text NOT NULL CHECK (length(btrim(motivo)) > 0),
  FOREIGN KEY (plan_id, version, datos_version, politica_version)
    REFERENCES public.planes(plan_id, version, datos_version, politica_version) ON DELETE RESTRICT,
  UNIQUE (plan_id, version),
  UNIQUE (aprobacion_id, plan_id, version)
);
-- La transaccion de Noel inserta aprobacion y actualiza plan en una misma operacion.
ALTER TABLE public.planes ADD CONSTRAINT planes_aprobacion_fk
  FOREIGN KEY (aprobacion_id, plan_id, version)
  REFERENCES public.aprobaciones(aprobacion_id, plan_id, version)
  DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE public.avisos (
  aviso_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  aprobacion_id uuid NOT NULL,
  plan_id uuid NOT NULL,
  version integer NOT NULL,
  sector_id uuid NOT NULL,
  punto_atencion_id uuid NOT NULL,
  destino_id uuid NOT NULL,
  tipo text NOT NULL CHECK (tipo IN ('distribucion','actualizacion')),
  ventana_inicio timestamptz NOT NULL,
  ventana_fin timestamptz NOT NULL,
  litros_asignados public.ra_cantidad NOT NULL CHECK (litros_asignados > 0),
  texto text NOT NULL CHECK (length(btrim(texto)) > 0),
  audio_adjunto_id uuid REFERENCES public.adjuntos ON DELETE RESTRICT,
  estado_envio public.ra_estado_aviso NOT NULL DEFAULT 'pendiente',
  proveedor_mensaje_id text,
  enviado_en timestamptz,
  ultimo_error text,
  intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (aprobacion_id, plan_id, version) REFERENCES public.aprobaciones(aprobacion_id, plan_id, version) ON DELETE RESTRICT,
  FOREIGN KEY (punto_atencion_id, sector_id) REFERENCES public.puntos_atencion(punto_atencion_id, sector_id) ON DELETE RESTRICT,
  FOREIGN KEY (destino_id, sector_id) REFERENCES public.suscripciones_sector(destino_id, sector_id) ON DELETE RESTRICT,
  UNIQUE (plan_id, version, sector_id, punto_atencion_id, destino_id, tipo),
  CHECK (ventana_fin > ventana_inicio),
  CHECK ((estado_envio = 'enviado' AND proveedor_mensaje_id IS NOT NULL AND enviado_en IS NOT NULL)
    OR (estado_envio <> 'enviado' AND proveedor_mensaje_id IS NULL AND enviado_en IS NULL)),
  CHECK (estado_envio NOT IN ('fallido','incierto') OR (ultimo_error IS NOT NULL AND length(btrim(ultimo_error)) > 0))
);

CREATE TABLE public.aclaraciones (
  aclaracion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  reporte_id uuid NOT NULL REFERENCES public.reportes ON DELETE RESTRICT,
  destino_id uuid NOT NULL REFERENCES public.destinos ON DELETE RESTRICT,
  campos_solicitados text[] NOT NULL CHECK (cardinality(campos_solicitados) > 0),
  pregunta text NOT NULL CHECK (length(btrim(pregunta)) > 0),
  estado_envio public.ra_estado_aviso NOT NULL DEFAULT 'pendiente',
  proveedor_mensaje_id text,
  enviado_en timestamptz,
  ultimo_error text,
  respuesta_texto text,
  respuesta_ubicacion jsonb CHECK (respuesta_ubicacion IS NULL OR jsonb_typeof(respuesta_ubicacion) = 'object'),
  respondida_en timestamptz,
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK ((estado_envio = 'enviado' AND proveedor_mensaje_id IS NOT NULL AND enviado_en IS NOT NULL)
    OR (estado_envio <> 'enviado' AND proveedor_mensaje_id IS NULL AND enviado_en IS NULL)),
  CHECK (estado_envio NOT IN ('fallido','incierto') OR (ultimo_error IS NOT NULL AND length(btrim(ultimo_error)) > 0)),
  CHECK (respondida_en IS NULL OR (respuesta_texto IS NOT NULL OR respuesta_ubicacion IS NOT NULL))
);

CREATE TABLE public.eventos (
  evento_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  agente public.ra_agente,
  actor_tipo text NOT NULL CHECK (actor_tipo IN ('agente','coordinador','conductor','sistema')),
  usuario_id uuid REFERENCES auth.users(id) ON DELETE RESTRICT,
  decision text NOT NULL CHECK (length(btrim(decision)) > 0),
  herramienta text,
  entrada_ids uuid[] NOT NULL DEFAULT '{}',
  salida_ids uuid[] NOT NULL DEFAULT '{}',
  resultado text NOT NULL,
  duracion_ms integer NOT NULL CHECK (duracion_ms >= 0),
  siguiente_estado public.ra_estado_ejecucion,
  detalles jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detalles) = 'object'),
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now(),
  CHECK (actor_tipo <> 'agente' OR agente IS NOT NULL)
);

CREATE TABLE public.confirmaciones_entrega (
  confirmacion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ejecucion_id uuid NOT NULL REFERENCES public.ejecuciones ON DELETE RESTRICT,
  parada_id uuid NOT NULL UNIQUE REFERENCES public.paradas ON DELETE RESTRICT,
  usuario_id uuid NOT NULL REFERENCES public.usuarios_operativos ON DELETE RESTRICT,
  rol text NOT NULL CHECK (rol IN ('conductor','coordinador')),
  litros_entregados public.ra_cantidad NOT NULL,
  atendida_en timestamptz NOT NULL,
  observaciones text,
  origen public.ra_origen NOT NULL,
  creado_en timestamptz NOT NULL DEFAULT now()
);

-- Indices de FK y consultas operativas del MVP.
CREATE INDEX puntos_sector_idx ON public.puntos_atencion(sector_id);
CREATE INDEX vehiculos_deposito_idx ON public.vehiculos(deposito_id);
CREATE INDEX destinos_remitente_idx ON public.destinos(remitente_ref);
CREATE INDEX suscripciones_sector_idx ON public.suscripciones_sector(sector_id);
CREATE INDEX reportes_creados_idx ON public.reportes(creado_en DESC);
CREATE INDEX reportes_remitente_idx ON public.reportes(remitente_ref);
CREATE INDEX adjuntos_reporte_idx ON public.adjuntos(reporte_id);
CREATE INDEX ejecuciones_reporte_idx ON public.ejecuciones(reporte_id);
CREATE INDEX ejecuciones_cola_idx ON public.ejecuciones(estado, creado_en) WHERE estado IN ('pendiente','ejecutando');
CREATE INDEX incidentes_punto_idx ON public.incidentes(punto_atencion_id);
CREATE INDEX incidentes_ejecucion_idx ON public.incidentes(ejecucion_id);
CREATE INDEX vinculos_incidente_idx ON public.vinculos_reportes(incidente_id) WHERE desvinculado_en IS NULL;
CREATE INDEX necesidades_incidente_idx ON public.necesidades(incidente_id);
CREATE INDEX necesidades_politica_idx ON public.necesidades(politica_version);
CREATE INDEX necesidades_ranking_idx ON public.necesidades(ejecucion_id, datos_version, politica_version, posicion);
CREATE INDEX planes_ejecucion_idx ON public.planes(ejecucion_id);
CREATE INDEX planes_estado_idx ON public.planes(estado, creado_en DESC);
CREATE INDEX rutas_vehiculo_idx ON public.rutas(vehiculo_id);
CREATE INDEX paradas_incidente_idx ON public.paradas(incidente_id);
CREATE INDEX avisos_cola_idx ON public.avisos(estado_envio, creado_en) WHERE estado_envio IN ('pendiente','fallido','incierto');
CREATE INDEX avisos_destino_idx ON public.avisos(destino_id, sector_id);
CREATE INDEX aclaraciones_ejecucion_idx ON public.aclaraciones(ejecucion_id);
CREATE INDEX aclaraciones_reporte_idx ON public.aclaraciones(reporte_id);
CREATE INDEX eventos_ejecucion_idx ON public.eventos(ejecucion_id, creado_en);

CREATE FUNCTION public.ra_actualizar_fecha() RETURNS trigger
LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  NEW.actualizado_en := now();
  RETURN NEW;
END $$;

-- Los eventos, aprobaciones y hechos de entrega conservan su historial.
-- Una correccion se registra con otro evento o una nueva version del plan.
CREATE FUNCTION public.ra_rechazar_cambio_historial() RETURNS trigger
LANGUAGE plpgsql SET search_path = '' AS $$
BEGIN
  RAISE EXCEPTION 'Historial de % solo admite INSERT; registrar correccion o nueva version', TG_TABLE_NAME
    USING ERRCODE = '55000';
END $$;

DO $$
DECLARE nombre text;
BEGIN
  FOREACH nombre IN ARRAY ARRAY['eventos','aprobaciones','confirmaciones_entrega'] LOOP
    EXECUTE format('CREATE TRIGGER ra_historial_solo_insert BEFORE UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.ra_rechazar_cambio_historial()', nombre);
  END LOOP;
END $$;

DO $$
DECLARE nombre text;
BEGIN
  FOREACH nombre IN ARRAY ARRAY['sectores','puntos_atencion','depositos','vehiculos','reportes','ejecuciones','incidentes','planes','paradas','avisos'] LOOP
    EXECUTE format('CREATE TRIGGER ra_actualizar_fecha BEFORE UPDATE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.ra_actualizar_fecha()', nombre);
  END LOOP;
END $$;

-- Cierre inicial: ninguna tabla se expone al navegador ni a usuarios autenticados
-- hasta 0002. service_role SOLO backend; su permiso no equivale a validar al coordinador.
DO $$
DECLARE nombre text;
BEGIN
  FOREACH nombre IN ARRAY ARRAY[
    'usuarios_operativos','sectores','puntos_atencion','depositos','vehiculos',
    'politicas_prioridad','remitentes','destinos','suscripciones_sector','reportes',
    'adjuntos','ejecuciones','incidentes','vinculos_reportes','necesidades','planes',
    'rutas','paradas','aprobaciones','avisos','aclaraciones','eventos','confirmaciones_entrega'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', nombre);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', nombre);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role', nombre);
  END LOOP;
END $$;
REVOKE ALL ON FUNCTION public.ra_actualizar_fecha() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ra_rechazar_cambio_historial() FROM PUBLIC, anon, authenticated;
COMMENT ON TABLE public.planes IS 'PK plan_id/version. Nueva version por cambio relevante; 0003 implementa aprobacion atomica y vigencia.';
COMMENT ON TABLE public.necesidades IS 'Snapshot por ejecucion/datos_version/politica_version/punto. JSON y columnas se validan con contratos antes de persistir.';
COMMENT ON TABLE public.remitentes IS 'Identificadores privados del adaptador. Nunca exponer chat IDs en vistas publicas.';
COMMENT ON TABLE public.avisos IS 'Bandeja de salida de Noel. Unicidad por plan/version/sector/punto/destino/tipo; no demuestra entrega fisica.';
COMMIT;
