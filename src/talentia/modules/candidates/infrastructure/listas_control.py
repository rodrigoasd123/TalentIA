"""Cruce local de identidad contra las listas sinteticas de control TCS."""

from __future__ import annotations

import csv
from pathlib import Path

from talentia.modules.candidates.domain.modelos import normalizar_documento, tokens_nombre


class ListasControlTCS:
    def __init__(
        self,
        excolaboradores: Path,
        vetados: Path,
        clientes_tcs: frozenset[str],
    ) -> None:
        self._clientes_tcs = clientes_tcs
        self._registros = self._leer(excolaboradores, "ex_tcs") + self._leer(vetados, "vetado")

    @staticmethod
    def _leer(ruta: Path, tipo: str) -> list[dict[str, str]]:
        if not ruta.is_file():
            return []
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            return [{**fila, "tipo_lista": tipo} for fila in csv.DictReader(archivo)]

    def comprobar(
        self,
        cliente_id: str,
        documento: str | None,
        nombre_completo: str,
    ) -> list[dict[str, str]]:
        if cliente_id not in self._clientes_tcs:
            return []
        documento_normalizado = normalizar_documento(documento)
        nombre_tokens = tokens_nombre(nombre_completo)
        alertas: list[dict[str, str]] = []
        for registro in self._registros:
            documento_lista = normalizar_documento(registro.get("documento"))
            nombre_lista = " ".join(
                parte
                for parte in (registro.get("nombres", ""), registro.get("apellidos", ""))
                if parte
            )
            coincide_documento = bool(
                documento_normalizado and documento_normalizado == documento_lista
            )
            coincide_nombre = bool(
                not documento_normalizado
                and len(nombre_tokens) >= 2
                and nombre_tokens == tokens_nombre(nombre_lista)
            )
            if not (coincide_documento or coincide_nombre):
                continue
            criterio = "documento" if coincide_documento else "nombre"
            if registro["tipo_lista"] == "ex_tcs":
                elegible = registro.get("elegible_reingreso", "").strip().casefold() in {"si", "sí"}
                alertas.append(
                    {
                        "tipo": "ex_tcs",
                        "nivel": "informativa" if elegible else "alta",
                        "estado": "elegible" if elegible else "revision_requerida",
                        "criterio": criterio,
                        "mensaje": (
                            "Coincidencia con excolaborador TCS elegible para reingreso. "
                            "Validar el historial con RR. HH."
                            if elegible
                            else "Coincidencia con excolaborador TCS no elegible. "
                            "Revision de RR. HH. obligatoria."
                        ),
                    }
                )
            else:
                estado = registro.get("estado_restriccion", "desconocida").strip() or "desconocida"
                vigente = estado.casefold() in {"activa", "permanente"}
                alertas.append(
                    {
                        "tipo": "vetado",
                        "nivel": "alta" if vigente else "media",
                        "estado": estado,
                        "criterio": criterio,
                        "mensaje": (
                            "Coincidencia con una restriccion vigente. "
                            "Revision de RR. HH. obligatoria."
                            if vigente
                            else "Coincidencia historica con la lista de restricciones. "
                            "Validar vigencia con RR. HH."
                        ),
                    }
                )
        return alertas
