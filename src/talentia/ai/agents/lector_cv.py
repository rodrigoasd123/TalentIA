"""AG-02: extraccion local con fuentes; un proveedor opcional solo propone."""

from __future__ import annotations

import re
from dataclasses import dataclass

from talentia.ai.guardrails.privacidad import TextoSanitizado, sanitizar
from talentia.modules.documents.domain.modelos import ReferenciaFuente


@dataclass(frozen=True, slots=True)
class CampoExtraido:
    campo: str
    valor: str | None
    confianza: float
    fuente: ReferenciaFuente | None


@dataclass(frozen=True, slots=True)
class ResultadoLectura:
    texto: TextoSanitizado
    campos: tuple[CampoExtraido, ...]
    requiere_revision: bool


PatronCampo = str | tuple[str, ...]


def _coincidencia(texto: str, patrones: PatronCampo) -> re.Match[str] | None:
    opciones = (patrones,) if isinstance(patrones, str) else patrones
    return next(
        (
            coincidencia
            for patron in opciones
            if (coincidencia := re.search(patron, texto, re.I | re.M))
        ),
        None,
    )


def _buscar_linea(documento_id: str, texto: str, patron: PatronCampo, campo: str) -> CampoExtraido:
    coincidencia = _coincidencia(texto, patron)
    if not coincidencia:
        return CampoExtraido(campo, None, 0.0, None)
    valor = coincidencia.group(1).strip()
    inicio, fin = coincidencia.span(1)
    fuente = ReferenciaFuente(documento_id, None, inicio, fin, texto[inicio:fin])
    return CampoExtraido(campo, valor, 0.75, fuente)


def _buscar_linea_con_fuente(
    documento_id: str,
    texto_sanitizado: str,
    paginas_originales: tuple[tuple[int, str], ...],
    patron: PatronCampo,
    campo: str,
) -> CampoExtraido:
    coincidencia = _coincidencia(texto_sanitizado, patron)
    if not coincidencia:
        return CampoExtraido(campo, None, 0.0, None)
    valor = coincidencia.group(1).strip()
    for pagina, original in paginas_originales:
        ubicada = re.search(re.escape(valor), original, re.I)
        if not ubicada and "[DOCUMENTO_RETIRADO]" in valor:
            patron_original = re.escape(valor).replace(re.escape("[DOCUMENTO_RETIRADO]"), r".+?")
            ubicada = re.search(patron_original, original, re.I)
        if ubicada:
            inicio, fin = ubicada.span()
            return CampoExtraido(
                campo,
                valor,
                0.75,
                ReferenciaFuente(documento_id, pagina, inicio, fin, original[inicio:fin]),
            )
    return CampoExtraido(campo, valor, 0.5, None)


def extraer_cv(documento_id: str, texto_original: str) -> ResultadoLectura:
    limpio = sanitizar(texto_original)
    campos = (
        _buscar_linea(documento_id, limpio.texto, r"(?:skills|habilidades)\s*:\s*(.+)", "skills"),
        _buscar_linea(
            documento_id,
            limpio.texto,
            r"(?:experiencia|experience)\s*:\s*(.+)",
            "experiencia",
        ),
        _buscar_linea(
            documento_id,
            limpio.texto,
            r"(?:educacion|education)\s*:\s*(.+)",
            "educacion",
        ),
        _buscar_linea(
            documento_id,
            limpio.texto,
            r"(?:empresa reciente|ultima empresa)\s*:\s*(.+)",
            "empresa_reciente",
        ),
    )
    return ResultadoLectura(limpio, campos, any(campo.valor is None for campo in campos))


def extraer_cv_paginas(documento_id: str, paginas: tuple[tuple[int, str], ...]) -> ResultadoLectura:
    originales = tuple((numero, texto) for numero, texto in paginas if texto.strip())
    texto_original = "\n".join(texto for _, texto in originales)
    limpio = sanitizar(texto_original)
    patrones = (
        (
            (
                r"(?:skills|habilidades)\s*:\s*(.+)",
                r"(?:^|\n)\s*(?:\d+\.\s*)?(?:competencias\s+y\s+)?habilidades\s+t[eé]cnicas\s*\n\s*[•\-]?\s*(?:(?:skills\s+principales|especialidad)\s*:\s*)?(.+)",
            ),
            "skills",
        ),
        (
            (
                r"(?:experiencia|experience)\s*:\s*(.+)",
                r"(?:^|\n)\s*(?:\d+\.\s*)?experiencia(?:\s+laboral)?(?:\s+relevante)?\s*\n\s*[•\-]?\s*(.+)",
            ),
            "experiencia",
        ),
        (
            (
                r"(?:educacion|education)\s*:\s*(.+)",
                r"(?:^|\n)\s*(?:\d+\.\s*)?educaci[oó]n(?:\s+y\s+(?:certificaciones|\[DOCUMENTO_RETIRADO\]))?\s*\n\s*[•\-]?\s*(.+)",
            ),
            "educacion",
        ),
        (
            (
                r"(?:empresa reciente|ultima empresa)\s*:\s*(.+)",
                r"(?:^|\n)\s*(?:\d+\.\s*)?experiencia(?:\s+laboral)?(?:\s+relevante)?\s*\n[^\n]*?[|\-\u2013\u2014]\s*(.+?)\s*\(",
            ),
            "empresa_reciente",
        ),
    )
    campos = tuple(
        _buscar_linea_con_fuente(documento_id, limpio.texto, originales, patron, campo)
        for patron, campo in patrones
    )
    requiere_revision = any(campo.valor is None or campo.fuente is None for campo in campos)
    return ResultadoLectura(limpio, campos, requiere_revision)
