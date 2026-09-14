"""Almacenamiento local privado para el piloto de TalentIA."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


class AlmacenLocal:
    """Guarda documentos fuera de los estáticos y bloquea escapes de ruta."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz.resolve()
        self._raiz.mkdir(parents=True, exist_ok=True)

    def guardar(self, nombre: str, contenido: bytes) -> str:
        if not contenido:
            raise ValueError("El documento no puede estar vacío")
        if not nombre or Path(nombre).name != nombre or nombre in {".", ".."}:
            raise ValueError("Nombre de documento inválido")

        destino = (self._raiz / nombre).resolve()
        if self._raiz not in destino.parents:
            raise ValueError("La ruta del documento sale del almacenamiento permitido")
        if destino.exists():
            raise FileExistsError("El documento ya existe")

        temporal = self._raiz / f".{nombre}.{uuid4().hex}.tmp"
        try:
            temporal.write_bytes(contenido)
            os.replace(temporal, destino)
        finally:
            temporal.unlink(missing_ok=True)
        return str(destino)
