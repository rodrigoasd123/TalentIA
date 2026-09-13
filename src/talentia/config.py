"""Configuracion segura por ambiente para el nuevo runtime."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Ambiente(StrEnum):
    DESARROLLO = "desarrollo"
    PRUEBAS = "pruebas"
    PILOTO = "piloto"


class ConfiguracionError(RuntimeError):
    """La configuracion no permite un arranque seguro."""


@dataclass(frozen=True, slots=True)
class Configuracion:
    ambiente: Ambiente
    url_base_datos: str
    secreto_sesion: str
    proveedor_ia: str | None
    ruta_documentos: Path
    tamano_maximo_mb: int = 10
    tiempo_sesion_minutos: int = 30
    intentos_trabajo: int = 3
    timeout_ia_segundos: int = 60

    @property
    def modo_manual(self) -> bool:
        return not self.proveedor_ia

    def validar(self) -> None:
        if self.ambiente is Ambiente.PILOTO and len(self.secreto_sesion) < 32:
            raise ConfiguracionError(
                "TALENTIA_SESSION_SECRET debe tener al menos 32 caracteres en piloto"
            )
        if self.tamano_maximo_mb < 1 or self.tamano_maximo_mb > 25:
            raise ConfiguracionError("El limite de archivos debe estar entre 1 y 25 MB")
        if not self.url_base_datos.startswith("sqlite:///"):
            raise ConfiguracionError("El piloto solo admite SQLite local")


def cargar_configuracion() -> Configuracion:
    ambiente = Ambiente(os.getenv("TALENTIA_ENV", Ambiente.DESARROLLO.value))
    secreto = os.getenv("TALENTIA_SESSION_SECRET", "")
    if not secreto and ambiente is not Ambiente.PILOTO:
        secreto = secrets.token_urlsafe(32)
    configuracion = Configuracion(
        ambiente=ambiente,
        url_base_datos=os.getenv(
            "TALENTIA_GREENFIELD_DATABASE_URL", "sqlite:///./talentia_greenfield.db"
        ),
        secreto_sesion=secreto,
        proveedor_ia=os.getenv("TALENTIA_LLM_PROVIDER") or None,
        ruta_documentos=Path(os.getenv("TALENTIA_DOCUMENT_STORAGE", "storage/greenfield")),
        tamano_maximo_mb=int(os.getenv("TALENTIA_MAX_UPLOAD_MB", "10")),
        tiempo_sesion_minutos=int(os.getenv("TALENTIA_SESSION_MINUTES", "30")),
        intentos_trabajo=int(os.getenv("TALENTIA_JOB_ATTEMPTS", "3")),
        timeout_ia_segundos=int(os.getenv("TALENTIA_LLM_TIMEOUT_SECONDS", "60")),
    )
    configuracion.validar()
    return configuracion
