"""AG-05: exclusion deterministica y conservadora a nivel persona."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

ESTADOS_PROTEGIDOS = {"apto", "en_proceso", "contratado"}


@dataclass(frozen=True, slots=True)
class EntradaExclusion:
    persona_id: str
    documento: str
    motivo_generico: str


def clasificar_exclusiones(registros: list[dict[str, object]]) -> tuple[EntradaExclusion, ...]:
    protegidas = {
        str(registro["persona_id"])
        for registro in registros
        if str(registro.get("estado", "")) in ESTADOS_PROTEGIDOS
    }
    resultado: dict[str, EntradaExclusion] = {}
    for registro in registros:
        persona_id = str(registro["persona_id"])
        if persona_id in protegidas:
            continue
        if registro.get("vigente") is not True:
            continue
        documento = str(registro.get("documento", "")).strip()
        motivo = str(registro.get("motivo_generico", "")).strip()
        if documento and motivo:
            resultado[persona_id] = EntradaExclusion(persona_id, documento, motivo)
    return tuple(sorted(resultado.values(), key=lambda item: item.documento))


def generar_csv(entradas: tuple[EntradaExclusion, ...]) -> tuple[bytes, str]:
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida)
    escritor.writerow(["documento", "motivo"])
    for entrada in entradas:
        escritor.writerow([entrada.documento, entrada.motivo_generico])
    contenido = ("\ufeff" + salida.getvalue()).encode("utf-8")
    return contenido, hashlib.sha256(contenido).hexdigest()
