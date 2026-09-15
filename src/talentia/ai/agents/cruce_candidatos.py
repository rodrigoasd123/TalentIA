"""AG-04: consolida el cruce de CV sin tomar decisiones sobre personas."""

from __future__ import annotations


def construir_reporte_cruce(resultados: list[dict[str, object]]) -> dict[str, object]:
    """Resume una carga de CV para control del proveedor y revision de RR. HH."""

    def alertas_de(resultado: dict[str, object]) -> list[dict[str, object]]:
        valor = resultado.get("alertas", [])
        return [item for item in valor if isinstance(item, dict)] if isinstance(valor, list) else []

    total = len(resultados)
    repetidos = sum(resultado.get("estado") == "reutilizado" for resultado in resultados)
    cvs_repetidos = sum(bool(resultado.get("cv_reutilizado")) for resultado in resultados)
    ex_tcs = sum(
        any(alerta.get("tipo") == "ex_tcs" for alerta in alertas_de(resultado))
        for resultado in resultados
    )
    restringidos = sum(
        any(alerta.get("tipo") == "vetado" for alerta in alertas_de(resultado))
        for resultado in resultados
    )
    revision = sum(
        resultado.get("estado") == "requiere_revision" or bool(resultado.get("error"))
        for resultado in resultados
    )
    return {
        "total": total,
        "nuevos": sum(resultado.get("estado") == "registrado" for resultado in resultados),
        "ya_procesados": repetidos,
        "cvs_repetidos": cvs_repetidos,
        "ex_tcs": ex_tcs,
        "restringidos": restringidos,
        "revision": revision,
        "porcentaje_repetidos": round(repetidos * 100 / total, 1) if total else 0.0,
        "resultados": resultados,
    }
