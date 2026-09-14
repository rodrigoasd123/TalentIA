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
    maximos_intentos_login: int = 5
    minutos_bloqueo_login: int = 15
    dias_vigencia_contrasena: int = 90

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
        if self.maximos_intentos_login < 3 or self.maximos_intentos_login > 20:
            raise ConfiguracionError("Los intentos de login deben estar entre 3 y 20")
        if self.minutos_bloqueo_login < 1 or self.minutos_bloqueo_login > 1440:
            raise ConfiguracionError("El bloqueo de login debe estar entre 1 y 1440 minutos")
        if self.dias_vigencia_contrasena < 1 or self.dias_vigencia_contrasena > 365:
            raise ConfiguracionError("La vigencia de contrasena debe estar entre 1 y 365 dias")


RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


def cargar_configuracion() -> Configuracion:
    ambiente = Ambiente(os.getenv("TALENTIA_ENV", Ambiente.DESARROLLO.value))
    secreto = os.getenv("TALENTIA_SESSION_SECRET", "")
    if not secreto and ambiente is not Ambiente.PILOTO:
        secreto = secrets.token_urlsafe(32)

    db_env = os.getenv("TALENTIA_GREENFIELD_DATABASE_URL")
    if not db_env:
        db_path = (RAIZ_PROYECTO / "talentia_greenfield.db").resolve()
        url_base_datos = f"sqlite:///{db_path.as_posix()}"
    else:
        url_base_datos = db_env

    doc_env = os.getenv("TALENTIA_DOCUMENT_STORAGE")
    ruta_documentos = (
        Path(doc_env).resolve() if doc_env else (RAIZ_PROYECTO / "storage" / "greenfield").resolve()
    )

    configuracion = Configuracion(
        ambiente=ambiente,
        url_base_datos=url_base_datos,
        secreto_sesion=secreto,
        proveedor_ia=os.getenv("TALENTIA_LLM_PROVIDER") or None,
        ruta_documentos=ruta_documentos,
        tamano_maximo_mb=int(os.getenv("TALENTIA_MAX_UPLOAD_MB", "10")),
        tiempo_sesion_minutos=int(os.getenv("TALENTIA_SESSION_MINUTES", "30")),
        intentos_trabajo=int(os.getenv("TALENTIA_JOB_ATTEMPTS", "3")),
        timeout_ia_segundos=int(os.getenv("TALENTIA_LLM_TIMEOUT_SECONDS", "60")),
        maximos_intentos_login=int(os.getenv("TALENTIA_LOGIN_MAX_ATTEMPTS", "5")),
        minutos_bloqueo_login=int(os.getenv("TALENTIA_LOGIN_LOCK_MINUTES", "15")),
        dias_vigencia_contrasena=int(os.getenv("TALENTIA_PASSWORD_MAX_AGE_DAYS", "90")),
    )
    configuracion.validar()
    return configuracion
