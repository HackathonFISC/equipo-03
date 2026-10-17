"""Lote de priorización (V2) armado desde los incidentes reales, para la RPC ra_preparar_priorizacion_v2.

Esta capa ensambla y comprueba; la RPC (de Emilia) decide en una transacción si acepta el lote. Reglas:
- El usuario que confirma sale del token verificado, nunca del cuerpo.
- La política se lee de `politicas_prioridad` con la versión elegida y estado activa; no se elige la primera ni la más reciente.
- El lote cubre TODOS los incidentes del ámbito de `ra_incidentes_contexto_v2`. Si hay dos en el mismo punto, uno sin punto o
  datos de distinto origen, se bloquea para revisión: no se omite, no se suma y no se recorta en silencio.
- Lo que el coordinador no confirma queda pendiente con su motivo; no se inventan demandas, clases ni vulnerabilidades.
- Nada de esto convierte datos reales en sintéticos: el origen del lote es el de la ejecución.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import PrepararPriorizacion, ResultadoPriorizacion, RevisionIncidente
from api.servicios.aclaraciones import _una_fila
from contratos.errores import CodigoError
from contratos.estados import EstadoValidacion
from contratos.modelos import EvaluacionNecesidades, PoliticaPrioridad
from contratos.solicitudes import DemandaDirecta, DemandaPorFormula, SolicitudValidarNecesidad

logger = logging.getLogger("api.priorizacion")

RPC_PREPARAR = "ra_preparar_priorizacion_v2"
RPC_CONTEXTO = "ra_incidentes_contexto_v2"
CAMPOS_POLITICA = frozenset(PoliticaPrioridad.model_fields)
PENDIENTE_CALCULO = "Requiere ejecutar validate_need y score_needs con estos datos revisados."


class EjecucionNoEncontrada(Exception):
    pass


def _lista(datos) -> list[dict]:
    return datos if isinstance(datos, list) else []


def _ejecucion(db, ejecucion_id: UUID) -> dict:
    filas = (
        db.table("ejecuciones")
        .select("ejecucion_id,etapa,estado,origen,entrada_priorizacion")
        .eq("ejecucion_id", str(ejecucion_id))
        .limit(1)
        .execute()
        .data
    )
    if not filas:
        raise EjecucionNoEncontrada
    return filas[0]


def _incidentes(db, ejecucion_id: UUID) -> list[dict]:
    return _lista(db.rpc(RPC_CONTEXTO, {"p_ejecucion_id": str(ejecucion_id)}).execute().data)


def _comprobar_ambito(incidentes: list[dict], origen: str) -> None:
    """Bloquea lo que necesita una decisión humana antes de calcular."""
    if not incidentes:
        raise ErrorApi(CodigoError.DATOS_INSUFICIENTES, "No hay incidentes con reportes vinculados para priorizar.")
    if any(not i.get("punto_atencion_id") for i in incidentes):
        raise ErrorApi(
            CodigoError.DATOS_INSUFICIENTES,
            "Hay incidentes sin punto de atención. Resuélvelos antes de calcular; no se omiten.",
            campos=["incidentes"],
        )
    origenes = {str(i.get("origen")) for i in incidentes} | {origen}
    if len(origenes) > 1:
        raise ErrorApi(
            CodigoError.DATOS_INSUFICIENTES,
            "El ámbito mezcla datos de distinto origen (" + ", ".join(sorted(origenes)) + "). "
            "Requiere revisión: no se recorta en silencio.",
            campos=["incidentes"],
        )
    puntos = [str(i["punto_atencion_id"]) for i in incidentes]
    if len(puntos) != len(set(puntos)):
        raise ErrorApi(
            CodigoError.DATOS_INSUFICIENTES,
            "Hay más de un incidente en el mismo punto. Consolida el episodio o resuelve el conflicto antes de calcular; "
            "no se omite ni se suma ninguno.",
            campos=["incidentes"],
        )


def _politica(db, version: str) -> dict:
    filas = (
        db.table("politicas_prioridad")
        .select("*")
        .eq("politica_version", version)
        .eq("estado", "activa")
        .execute()
        .data
    )
    if not filas:
        raise ErrorApi(
            CodigoError.POLITICA_NO_ACTIVA,
            "La política elegida no existe o no está activa.",
            campos=["politica_version"],
        )
    if len(filas) > 1:
        raise ErrorApi(
            CodigoError.POLITICA_NO_ACTIVA,
            "Hay varias copias activas de esa política; elige una versión inequívoca.",
            campos=["politica_version"],
        )
    # Solo los campos del contrato y tal como están guardados: la RPC compara el contenido exacto con la fila.
    cruda = {k: v for k, v in filas[0].items() if k in CAMPOS_POLITICA}
    try:
        PoliticaPrioridad.model_validate(cruda)
    except ValidationError:
        logger.error("La política %s guardada no cumple el contrato", version)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La política guardada no cumple el contrato; avisa a quien administra los datos.",
        ) from None
    return cruda


def _revisiones(datos: PrepararPriorizacion, incidentes: list[dict]) -> dict[str, RevisionIncidente]:
    por_id = {str(i["incidente_id"]): i for i in incidentes}
    revisiones: dict[str, RevisionIncidente] = {}
    for revision in datos.revisiones:
        clave = str(revision.incidente_id)
        if clave in revisiones:
            raise ErrorApi(CodigoError.CONTRATO_INVALIDO, "Hay dos revisiones del mismo incidente.", campos=["revisiones"])
        if clave not in por_id:
            raise ErrorApi(
                CodigoError.CONTRATO_INVALIDO,
                "Una revisión es de un incidente que no está en el ámbito de esta ejecución.",
                campos=["revisiones"],
            )
        if por_id[clave].get("version") != revision.version_incidente:
            raise ErrorApi(
                CodigoError.VERSION_OBSOLETA,
                "Un incidente cambió desde que lo revisaste. Recarga las necesidades y revísalo de nuevo.",
                campos=["revisiones"],
            )
        revisiones[clave] = revision
    return revisiones


def _datos_version(origen: str, datos: PrepararPriorizacion, incidentes: list[dict], revisiones: dict) -> str:
    """Cambia si cambia cualquier entrada del lote; repetir el mismo envío da la misma versión (idempotente)."""
    entradas = sorted(
        (
            str(i["incidente_id"]),
            i.get("version"),
            revisiones[str(i["incidente_id"])].model_dump(mode="json") if str(i["incidente_id"]) in revisiones else None,
        )
        for i in incidentes
    )
    huella = hashlib.sha256(
        json.dumps(
            {"politica": datos.politica_version, "motivo": datos.motivo, "entradas": entradas},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:20]
    return f"{origen}-priorizacion-{huella}"


def _marca_de_tiempo(ejecucion: dict, datos_version: str) -> datetime:
    """Repetir el mismo lote reutiliza su marca de tiempo, para que la RPC lo reconozca como el mismo."""
    guardado = ejecucion.get("entrada_priorizacion")
    try:
        solicitud = guardado["entradas"][0]["solicitud_demanda"]
        if solicitud["datos_version"] == datos_version:
            return datetime.fromisoformat(str(solicitud["creado_en"]).replace("Z", "+00:00"))
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return datetime.now(timezone.utc)


def _demanda(revision: RevisionIncidente | None, confirmacion: dict):
    if revision is None or revision.demanda is None:
        return DemandaPorFormula(metodo="formula", fuente="Sin revisión del coordinador")
    d = revision.demanda
    if d.metodo == "directa":
        return DemandaDirecta(metodo="directa", litros_declarados=d.litros_declarados, fuente=d.fuente, confirmacion=confirmacion)
    return DemandaPorFormula(
        metodo="formula",
        personas_atendidas=d.personas_atendidas,
        dotacion_litros_persona_dia=d.dotacion_litros_persona_dia,
        dias_cobertura=d.dias_cobertura,
        reserva_utilizable_litros=d.reserva_utilizable_litros,
        fuente=d.fuente,
        confirmacion=confirmacion,
    )


def _faltantes(revision: RevisionIncidente | None) -> list[str]:
    if revision is None:
        return ["Falta la revisión del coordinador: demanda, clase de prioridad y vulnerabilidad."]
    faltan = []
    if revision.demanda is None:
        faltan.append("Falta confirmar la demanda de agua.")
    if revision.clase_prioridad is None:
        faltan.append("Falta confirmar la clase de prioridad.")
    if revision.vulnerabilidad is None:
        faltan.append("Falta confirmar la vulnerabilidad.")
    if revision.horas_sin_agua is None:
        faltan.append("Faltan las horas sin agua.")
    if revision.personas_atendidas is None:
        faltan.append("Falta el número de personas atendidas.")
    return faltan


def _entrada(*, ejecucion_id, origen, datos_version, politica_version, incidente, revision, usuario_id, motivo, ahora):
    confirmacion = {"usuario_id": str(usuario_id), "confirmado_en": ahora.isoformat(), "motivo": f"Revisión del coordinador: {motivo}"}
    contexto = {"ejecucion_id": ejecucion_id, "creado_en": ahora, "origen": origen}
    demanda = _demanda(revision, confirmacion)
    solicitud = SolicitudValidarNecesidad(
        **contexto,
        incidente_id=incidente["incidente_id"],
        punto_atencion_id=incidente["punto_atencion_id"],
        datos_version=datos_version,
        demanda=demanda,
        supuestos=[],
    )
    r = revision
    confirma = lambda valor: confirmacion if valor is not None else None  # noqa: E731
    evaluacion = EvaluacionNecesidades(
        **contexto,
        incidente_id=incidente["incidente_id"],
        punto_atencion_id=incidente["punto_atencion_id"],
        datos_version=datos_version,
        politica_version=politica_version,
        estado_demanda=EstadoValidacion.PENDIENTE,
        metodo_demanda=demanda.metodo,
        confirmacion_demanda=confirma(r.demanda) if r else None,
        clase_prioridad=r.clase_prioridad if r else None,
        confirmacion_clase=confirma(r.clase_prioridad) if r else None,
        ventana_atencion=r.ventana_atencion.model_dump() if r and r.ventana_atencion else None,
        horas_sin_agua=r.horas_sin_agua if r else None,
        personas_atendidas=r.personas_atendidas if r else None,
        vulnerabilidad=r.vulnerabilidad if r else None,
        confirmacion_vulnerabilidad=confirma(r.vulnerabilidad) if r else None,
        ultima_atencion_confirmada_en=r.ultima_atencion_confirmada_en if r else None,
        primera_deteccion_en=incidente["primera_deteccion_en"],
        estado_prioridad="pendiente",
        pendientes=[*_faltantes(revision), PENDIENTE_CALCULO],
        requiere_revision_urgente=bool(incidente.get("requiere_revision_urgente")),
    )
    return {
        "version_incidente": incidente["version"],
        "solicitud_demanda": solicitud.model_dump(mode="json"),
        "evaluacion": evaluacion.model_dump(mode="json"),
        "pendientes": [],
    }


# Texto de la RPC (sin datos de personas) -> (código de dominio, mensaje para quien usa el panel).
ERRORES_RPC = (
    ("Ejecución no disponible", CodigoError.VERSION_OBSOLETA, "La ejecución ya no está en la etapa de priorización."),
    ("Hay un cálculo en curso", CodigoError.VERSION_OBSOLETA, "Hay un cálculo en curso. Espera a que termine antes de cambiar el lote."),
    ("Cambiar datos_version", CodigoError.VERSION_OBSOLETA, "El lote cambió sin cambiar su versión de datos. Vuelve a prepararlo."),
    ("Consolidar un incidente por punto", CodigoError.DATOS_INSUFICIENTES, "Hay más de un incidente en un mismo punto. Consolídalos antes de calcular."),
    ("Faltan incidentes activos", CodigoError.VERSION_OBSOLETA, "Aparecieron incidentes nuevos desde que preparaste el lote. Recarga y revísalos."),
    ("identidad, versión u origen", CodigoError.VERSION_OBSOLETA, "Un incidente cambió o no corresponde a esta ejecución. Recarga y revísalo de nuevo."),
    ("Política sin activar", CodigoError.POLITICA_NO_ACTIVA, "La política no está activa o difiere de la registrada."),
    ("Lote vacío", CodigoError.DATOS_INSUFICIENTES, "No hay incidentes para priorizar."),
)


def traducir_error_rpc(error: APIError) -> ErrorApi | None:
    """Error de dominio si la RPC rechazó con un motivo conocido; None si es otra falla de la base."""
    mensaje = str(getattr(error, "message", "") or "")
    codigo_sql = str(getattr(error, "code", ""))
    if codigo_sql == "42501" or "Sin permiso de coordinador" in mensaje:
        return ErrorApi(CodigoError.SIN_PERMISO, "Solo un coordinador activo puede hacer esto.")
    for fragmento, codigo, texto in ERRORES_RPC:
        if fragmento in mensaje:
            return ErrorApi(codigo, texto)
    if codigo_sql == "22023":
        return ErrorApi(CodigoError.CONTRATO_INVALIDO, "El lote no cumple lo que exige la base de datos.")
    return None


def preparar_lote(db, usuario_id: UUID, ejecucion_id: UUID, datos: PrepararPriorizacion) -> ResultadoPriorizacion:
    ejecucion = _ejecucion(db, ejecucion_id)
    if ejecucion.get("etapa") != "priorizacion":
        raise ErrorApi(CodigoError.VERSION_OBSOLETA, "La ejecución no está en la etapa de priorización.")
    origen = str(ejecucion["origen"])
    incidentes = _incidentes(db, ejecucion_id)
    _comprobar_ambito(incidentes, origen)
    politica = _politica(db, datos.politica_version)
    revisiones = _revisiones(datos, incidentes)
    datos_version = _datos_version(origen, datos, incidentes, revisiones)
    ahora = _marca_de_tiempo(ejecucion, datos_version)
    try:
        entradas = [
            _entrada(
                ejecucion_id=ejecucion_id,
                origen=origen,
                datos_version=datos_version,
                politica_version=datos.politica_version,
                incidente=i,
                revision=revisiones.get(str(i["incidente_id"])),
                usuario_id=usuario_id,
                motivo=datos.motivo,
                ahora=ahora,
            )
            for i in sorted(incidentes, key=lambda x: str(x["incidente_id"]))
        ]
    except ValidationError:
        # Solo el hecho: los detalles de validación podrían incluir datos del incidente.
        raise ErrorApi(
            CodigoError.CONTRATO_INVALIDO,
            "Una revisión no cumple el contrato de necesidades. Revisa la clase, la ventana y las cantidades.",
            campos=["revisiones"],
        ) from None
    lote = {"politica": politica, "entradas": entradas}
    try:
        fila = _una_fila(
            db.rpc(
                RPC_PREPARAR,
                {"p_ejecucion_id": str(ejecucion_id), "p_usuario_id": str(usuario_id), "p_lote": lote},
            )
            .execute()
            .data
        )
    except APIError as error:
        traducido = traducir_error_rpc(error)
        if traducido is None:
            raise
        raise traducido from None
    try:
        if not isinstance(fila, dict):
            raise ValueError
        return ResultadoPriorizacion(
            ejecucion_id=ejecucion_id,
            estado=str(fila["estado"]),
            etapa=str(fila["etapa"]),
            repetido=bool(fila.get("repetido", False)),
            datos_version=datos_version,
            incidentes=len(entradas),
            sin_revisar=sum(1 for i in incidentes if str(i["incidente_id"]) not in revisiones),
        )
    except (ValueError, KeyError, TypeError, ValidationError):
        logger.error("La RPC %s devolvió una forma inesperada", RPC_PREPARAR)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "La base de datos respondió con un formato inesperado.",
        ) from None
