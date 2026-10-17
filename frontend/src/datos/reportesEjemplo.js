// Reportes de ejemplo para desarrollar la página sin la API.
// Son sintéticos: no corresponden a personas ni a lugares reales.
// La forma sigue a ReporteRegistrado y ReporteInterpretado (contratos/modelos.py),
// con solo los campos que usa la página. El primero es el ejemplo de los contratos.

export const reportesEjemplo = [
  {
    registrado: {
      reporte_id: 'bc815641-f5cc-5c37-aaf5-e85bf7d84f23',
      ejecucion_id: 'efdae7d9-3aac-5cd8-ab6d-fdba9e663f4e',
      creado_en: '2026-10-16T18:00:00-05:00',
      origen: 'sintetico',
      entrada: {
        canal: 'telegram',
        modalidad: 'texto',
        texto: 'Llevamos tres días sin agua en P1; somos unas 120 personas.',
      },
    },
    interpretado: {
      interpretacion: {
        resumen: 'El remitente declara tres días sin agua en el punto de demo P1.',
        ubicacion_declarada: 'Punto de demo P1',
        campos: {
          horas_sin_agua: 72,
          personas_afectadas: 120,
          vulnerabilidad_declarada: 'personas con barreras para recoger agua',
          institucion_declarada: null,
          tipo_problema: 'sin_suministro',
        },
        evidencia_textual: ['Llevamos tres días sin agua en P1; somos unas 120 personas.'],
        faltantes: [],
        requiere_aclaracion: false,
        fuera_de_alcance: false,
      },
    },
  },
  {
    registrado: {
      reporte_id: '00000000-0000-4000-8000-000000000002',
      ejecucion_id: '00000000-0000-4000-8000-0000000000a2',
      creado_en: '2026-10-16T18:12:00-05:00',
      origen: 'sintetico',
      entrada: {
        canal: 'telegram',
        modalidad: 'texto',
        texto: 'No tenemos agua desde ayer en mi sector.',
      },
    },
    interpretado: {
      interpretacion: {
        resumen: 'El remitente reporta falta de agua desde ayer, sin indicar el punto de atención.',
        ubicacion_declarada: null,
        campos: {
          horas_sin_agua: null,
          personas_afectadas: null,
          vulnerabilidad_declarada: null,
          institucion_declarada: null,
          tipo_problema: 'sin_suministro',
        },
        evidencia_textual: ['No tenemos agua desde ayer en mi sector.'],
        faltantes: ['Punto de atención', 'Cantidad de personas', 'Horas sin agua'],
        requiere_aclaracion: true,
        fuera_de_alcance: false,
      },
    },
  },
  {
    registrado: {
      reporte_id: '00000000-0000-4000-8000-000000000003',
      ejecucion_id: '00000000-0000-4000-8000-0000000000a3',
      creado_en: '2026-10-16T18:25:00-05:00',
      origen: 'sintetico',
      entrada: {
        canal: 'telegram',
        modalidad: 'texto',
        texto: 'Hace dos días no llega agua a la escuela de P2.',
      },
    },
    interpretado: null,
  },
  {
    registrado: {
      reporte_id: '00000000-0000-4000-8000-000000000004',
      ejecucion_id: '00000000-0000-4000-8000-0000000000a4',
      creado_en: '2026-10-16T18:40:00-05:00',
      origen: 'sintetico',
      entrada: {
        canal: 'telegram',
        modalidad: 'texto',
        texto: 'Se rompió un tubo en la avenida principal y sale mucha agua.',
      },
    },
    interpretado: {
      interpretacion: {
        resumen:
          'El remitente avisa de una fuga en la vía pública, no de una falta de suministro en un punto de atención.',
        ubicacion_declarada: 'Avenida principal',
        campos: {
          horas_sin_agua: null,
          personas_afectadas: null,
          vulnerabilidad_declarada: null,
          institucion_declarada: null,
          tipo_problema: 'otro',
        },
        evidencia_textual: ['Se rompió un tubo en la avenida principal y sale mucha agua.'],
        faltantes: [],
        requiere_aclaracion: false,
        fuera_de_alcance: true,
      },
    },
  },
  {
    registrado: {
      reporte_id: '00000000-0000-4000-8000-000000000005',
      ejecucion_id: '00000000-0000-4000-8000-0000000000a5',
      creado_en: '2026-10-16T18:52:00-05:00',
      origen: 'sintetico',
      entrada: {
        canal: 'telegram',
        modalidad: 'texto',
        texto: 'Llevamos una semana con agua solo unas horas al día en el centro de salud de P4.',
      },
    },
    interpretado: {
      interpretacion: {
        resumen:
          'El remitente reporta una semana de suministro intermitente en el centro de salud de P4.',
        ubicacion_declarada: 'Centro de salud de P4',
        campos: {
          horas_sin_agua: 168,
          personas_afectadas: null,
          vulnerabilidad_declarada: null,
          institucion_declarada: 'Centro de salud',
          tipo_problema: 'intermitencia',
        },
        evidencia_textual: [
          'Llevamos una semana con agua solo unas horas al día en el centro de salud de P4.',
        ],
        faltantes: [],
        requiere_aclaracion: false,
        fuera_de_alcance: false,
      },
    },
  },
]
