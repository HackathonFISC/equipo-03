import { useEffect, useMemo, useState } from 'react'
import { obtenerNecesidades, USAR_EJEMPLOS_NECESIDADES } from '../api/necesidades.js'
import './Necesidades.css'

// Urgencia y confianza se muestran por separado (documento de versiones, V2):
// la urgencia sale del puntaje de prioridad; la confianza, de la consolidación del incidente.

const VULNERABILIDAD = {
  sin_condicion_identificada: 'Sin condición identificada',
  moderada: 'Moderada',
  alta: 'Alta',
}

const VALIDACION = {
  pendiente: 'Pendiente de validar',
  validada: 'Validado',
  rechazada: 'Rechazado',
}

// Máximo de cada aporte según la política demo-1.0 (pesos 50/30/20).
const APORTES = [
  { clave: 'aporte_duracion', nombre: 'Tiempo sin agua', maximo: 50 },
  { clave: 'aporte_vulnerabilidad', nombre: 'Vulnerabilidad', maximo: 30 },
  { clave: 'aporte_poblacion', nombre: 'Personas atendidas', maximo: 20 },
]

const numero = new Intl.NumberFormat('es-PA', { maximumFractionDigits: 0 })
const decimales = new Intl.NumberFormat('es-PA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const porcentaje = new Intl.NumberFormat('es-PA', { style: 'percent', maximumFractionDigits: 0 })
const hora = new Intl.DateTimeFormat('es-PA', {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'America/Panama',
})

function plural(n, uno, varios) {
  return `${n} ${n === 1 ? uno : varios}`
}

function noIndicado(valor, formato) {
  return valor === null || valor === undefined ? null : formato(valor)
}

function Dato({ nombre, valor }) {
  return (
    <div className="dato">
      <dt>{nombre}</dt>
      <dd className={valor === null ? 'dato-vacio' : undefined}>{valor ?? 'No indicado'}</dd>
    </div>
  )
}

function Urgencia({ evaluacion }) {
  const calculada = evaluacion.estado_prioridad === 'calculada'
  return (
    <section className="bloque" aria-label="Urgencia">
      <h3>Urgencia</h3>
      {calculada ? (
        <>
          <p className="puntaje">
            <span className="puntaje-valor">{decimales.format(evaluacion.puntaje)}</span>
            <span className="puntaje-escala"> de 100 puntos</span>
          </p>
          <ul className="aportes">
            {APORTES.map((a) => {
              const valor = evaluacion.componentes[a.clave]
              return (
                <li key={a.clave}>
                  <span className="aporte-nombre">{a.nombre}</span>
                  <span className="aporte-barra" aria-hidden="true">
                    <span style={{ width: `${(valor / a.maximo) * 100}%` }} />
                  </span>
                  <span className="aporte-valor">
                    {decimales.format(valor)} de {a.maximo}
                  </span>
                </li>
              )
            })}
          </ul>
        </>
      ) : (
        <p className="sin-puntaje">Sin puntaje: faltan datos para calcular la prioridad.</p>
      )}
      <dl className="datos">
        <Dato nombre="Horas sin agua" valor={noIndicado(evaluacion.horas_sin_agua, (v) => `${numero.format(v)} h`)} />
        <Dato nombre="Personas atendidas" valor={noIndicado(evaluacion.personas_atendidas, numero.format)} />
        <Dato nombre="Vulnerabilidad" valor={noIndicado(evaluacion.vulnerabilidad, (v) => VULNERABILIDAD[v] ?? v)} />
      </dl>
    </section>
  )
}

function Confianza({ incidente }) {
  return (
    <section className="bloque" aria-label="Confianza">
      <h3>Confianza</h3>
      <p className="confianza">
        <span className="puntaje-valor">
          {incidente.confianza === null ? 'Sin dato' : porcentaje.format(incidente.confianza)}
        </span>
        <span className="puntaje-escala"> en la consolidación</span>
      </p>
      <dl className="datos">
        <Dato nombre="Estado del incidente" valor={VALIDACION[incidente.estado_validacion] ?? incidente.estado_validacion} />
        <Dato
          nombre="Reportes"
          valor={`${plural(incidente.reportes_ids.length, 'vinculado', 'vinculados')}, ${plural(
            incidente.reportes_independientes,
            'independiente',
            'independientes',
          )}`}
        />
      </dl>
      {incidente.conflictos.length > 0 && (
        <div className="lista-corta">
          <h4>Conflictos</h4>
          <ul>
            {incidente.conflictos.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {incidente.faltantes.length > 0 && (
        <div className="lista-corta">
          <h4>Falta en el incidente</h4>
          <ul>
            {incidente.faltantes.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function TarjetaNecesidad({ item }) {
  const { punto, incidente, evaluacion } = item
  const clase = evaluacion.clase_prioridad
  const urgente = evaluacion.requiere_revision_urgente || incidente.requiere_revision_urgente
  const ventana = evaluacion.ventana_atencion

  return (
    <li className="necesidad" data-clase={clase ?? 'sin_clase'}>
      <header className="necesidad-cabecera">
        {evaluacion.posicion && (
          <span className="posicion" aria-label={`Posición ${evaluacion.posicion}`}>
            {evaluacion.posicion}
          </span>
        )}
        <div className="necesidad-titulo">
          <h2>{punto?.nombre ?? 'Punto sin nombre'}</h2>
          <p className="necesidad-demanda">
            {evaluacion.demanda_litros === null
              ? 'Demanda por confirmar'
              : `${numero.format(evaluacion.demanda_litros)} litros`}
          </p>
          {ventana && (
            <p className="necesidad-demanda">
              Entrega entre {hora.format(new Date(ventana.inicio))} y {hora.format(new Date(ventana.fin))}
            </p>
          )}
        </div>
        <div className="sellos">
          {clase && <span className="sello-clase">{clase === 'critico' ? 'Crítico' : 'General'}</span>}
          {urgente && <span className="sello-urgente">Revisión urgente</span>}
        </div>
      </header>

      <div className="bloques">
        <Urgencia evaluacion={evaluacion} />
        <Confianza incidente={incidente} />
      </div>

      {evaluacion.pendientes.length > 0 && (
        <div className="pendientes">
          <h3>Qué falta para entrar al orden de atención</h3>
          <ul>
            {evaluacion.pendientes.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {evaluacion.supuestos.length > 0 && (
        <p className="supuestos">Supuestos: {evaluacion.supuestos.join(' ')}</p>
      )}
      <p className="pie">
        Política {evaluacion.politica_version}, datos {evaluacion.datos_version}.
      </p>
    </li>
  )
}

export default function Necesidades() {
  const [items, setItems] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(null)
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    let cancelado = false
    obtenerNecesidades()
      .then((datos) => {
        if (cancelado) return
        setItems(datos)
        setError(null)
        setCargando(false)
      })
      .catch((e) => {
        if (cancelado) return
        setError(e.message)
        setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [intento])

  function reintentar() {
    setCargando(true)
    setError(null)
    setIntento((n) => n + 1)
  }

  // El orden lo decide el cálculo (posición); la página no reordena por su cuenta.
  const { enOrden, pendientes } = useMemo(() => {
    const calculadas = items
      .filter((i) => i.evaluacion.estado_prioridad === 'calculada')
      .sort((a, b) => a.evaluacion.posicion - b.evaluacion.posicion)
    const sinPuntaje = items.filter((i) => i.evaluacion.estado_prioridad !== 'calculada')
    return { enOrden: calculadas, pendientes: sinPuntaje }
  }, [items])

  return (
    <section className="necesidades" aria-labelledby="titulo-necesidades">
      <header className="necesidades-cabecera">
        <h1 id="titulo-necesidades">Necesidades</h1>
        <p>Puntos de atención con falta de agua, en el orden en que se atenderían.</p>
      </header>

      {USAR_EJEMPLOS_NECESIDADES && (
        <p className="aviso-ejemplos" role="note">
          Datos de ejemplo. Estas necesidades son sintéticas y no vienen de la API.
        </p>
      )}

      {cargando && <p className="mensaje">Cargando necesidades…</p>}

      {error && (
        <div className="mensaje mensaje-error" role="alert">
          <p>No se pudieron cargar las necesidades. {error}</p>
          <button type="button" onClick={reintentar}>
            Reintentar
          </button>
        </div>
      )}

      {!cargando && !error && items.length === 0 && (
        <p className="mensaje">
          Todavía no hay necesidades. Aparecerán cuando los reportes se agrupen en incidentes.
        </p>
      )}

      {!cargando && !error && enOrden.length > 0 && (
        <>
          <h2 className="grupo-titulo">Orden de atención</h2>
          <ol className="lista-necesidades">
            {enOrden.map((item) => (
              <TarjetaNecesidad key={item.evaluacion.incidente_id} item={item} />
            ))}
          </ol>
        </>
      )}

      {!cargando && !error && pendientes.length > 0 && (
        <>
          <h2 className="grupo-titulo">Pendientes de revisión</h2>
          <p className="grupo-nota">
            No entran al orden de atención hasta que se confirmen sus datos. Un dato faltante no se
            cuenta como cero.
          </p>
          <ul className="lista-necesidades">
            {pendientes.map((item) => (
              <TarjetaNecesidad key={item.evaluacion.incidente_id} item={item} />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
