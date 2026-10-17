"""Métricas de evaluación: un pendiente nunca cuenta como aprobado."""
from collections import Counter


def resumir(resultados):
    estados = Counter(r['estado'] for r in resultados)
    permitidos = {'aprobado', 'fallido', 'pendiente', 'error'}
    if set(estados) - permitidos:
        raise ValueError('Estado de evaluación desconocido')
    total = len(resultados)
    ejecutados = estados['aprobado'] + estados['fallido'] + estados['error']
    return dict(total=total, ejecutados=ejecutados,
                **{e: estados[e] for e in sorted(permitidos)},
                cobertura_ejecucion=ejecutados / total if total else None,
                tasa_exito_ejecutados=estados['aprobado'] / ejecutados if ejecutados else None,
                proporcion_aprobada_total=estados['aprobado'] / total if total else None)
