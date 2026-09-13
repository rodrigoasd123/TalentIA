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


def _buscar_linea(documento_id: str, texto: str, patron: str, campo: str) -> CampoExtraido:
    coincidencia = re.search(patron, texto, re.I | re.M)
    if not coincidencia:
        return CampoExtraido(campo, None, 0.0, None)
    valor = coincidencia.group(1).strip()
    inicio, fin = coincidencia.span(1)
    fuente = ReferenciaFuente(documento_id, None, inicio, fin, texto[inicio:fin])
    return CampoExtraido(campo, valor, 0.75, fuente)


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
