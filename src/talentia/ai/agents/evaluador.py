"""AG-03: relaciona requisitos y verifica toda evidencia en el original."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from talentia.modules.documents.domain.modelos import ReferenciaFuente
from talentia.modules.evaluations.domain.modelos import ResultadoRequisito, Veredicto
from talentia.modules.recruitment.domain.modelos import RequisitoPerfil

TERMINOS_GENERICOS = {
    "anos",
    "conocimiento",
    "experiencia",
    "manejo",
    "nivel",
    "requerido",
}


@dataclass(frozen=True, slots=True)
class ResultadoEvaluacion:
    resultados: tuple[ResultadoRequisito, ...]
    puntaje: Decimal | None
    requiere_revision: bool


def evaluar(
    documento_id: str, texto_original: str, requisitos: tuple[RequisitoPerfil, ...]
) -> ResultadoEvaluacion:
    if not requisitos or not texto_original.strip():
        return ResultadoEvaluacion((), None, True)
    normalizado = texto_original.casefold()
    resultados: list[ResultadoRequisito] = []
    suma = Decimal("0")
    pesos = Decimal("0")
    requiere_revision = False
    for requisito in requisitos:
        terminos = [
            termino
            for termino in re.findall(r"[a-z0-9+#.]+", requisito.descripcion.casefold())
            if len(termino) > 2 and termino not in TERMINOS_GENERICOS
        ]
        presentes = [termino for termino in terminos if termino in normalizado]
        if presentes:
            inicio = min(normalizado.index(termino) for termino in presentes)
            fin = min(len(texto_original), inicio + 180)
            evidencia = ReferenciaFuente(
                documento_id, None, inicio, fin, texto_original[inicio:fin]
            )
            cobertura = Decimal(len(presentes)) / Decimal(max(len(terminos), 1))
            puntaje = (cobertura * 100).quantize(Decimal("0.01"))
            veredicto = (
                Veredicto.COINCIDE if cobertura >= Decimal("0.5") else Veredicto.REVISION_MANUAL
            )
            requiere_revision = requiere_revision or veredicto is Veredicto.REVISION_MANUAL
            resultados.append(
                ResultadoRequisito(
                    requisito.codigo,
                    veredicto,
                    puntaje,
                    (evidencia,),
                    "Coincidencia documental verificada en el CV original.",
                )
            )
            suma += puntaje * requisito.peso
            pesos += requisito.peso
        else:
            resultados.append(
                ResultadoRequisito(
                    requisito.codigo,
                    Veredicto.SIN_EVIDENCIA,
                    None,
                    (),
                    "No se encontro evidencia; BIZ-005 requiere revision humana.",
                )
            )
            requiere_revision = True
    puntaje_total = (suma / pesos).quantize(Decimal("0.01")) if pesos else None
    return ResultadoEvaluacion(tuple(resultados), puntaje_total, requiere_revision)


def verificar_evidencia(texto_original: str, fuente: ReferenciaFuente) -> bool:
    return (
        0 <= fuente.inicio <= fuente.fin <= len(texto_original)
        and texto_original[fuente.inicio : fuente.fin] == fuente.fragmento
    )
