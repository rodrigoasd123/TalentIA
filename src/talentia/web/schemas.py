"""Contratos Pydantic de entrada y salida HTTP."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credenciales(Estricto):
    correo: str
    contrasena: str


class CambioContrasena(Estricto):
    contrasena_actual: str
    contrasena_nueva: str


class AsignacionRol(Estricto):
    rol: str
    asignar: bool = True


class AsignacionCliente(Estricto):
    cliente_id: str
    asignar: bool = True


class ComprobacionIdentidad(Estricto):
    cliente_id: str
    documento: str | None = None
    correo: str | None = None
    telefono: str | None = None
    nombre_completo: str = ""


class AltaCandidato(Estricto):
    cliente_id: str
    nombres: str = Field(min_length=1, max_length=120)
    apellidos: str = Field(min_length=1, max_length=160)
    tipo_documento: str | None = None
    documento: str | None = None
    correo: str | None = None
    telefono: str | None = None
    fecha_nacimiento: date | None = None
    ubicacion: str | None = None
    fuente: str | None = None
    reclutador: str | None = None
    perfil_solicitado: str | None = None
    conocimiento_tecnico: str | None = None
    disponibilidad: str | None = None
    expectativa_salarial: Decimal | None = Field(default=None, ge=0)
    ctc_rol: Decimal | None = Field(default=None, ge=0)
    bgc: str | None = None
    deuda_equifax: Decimal | None = None
    etiquetas: list[str] = Field(default_factory=list)
    preflight_id: str


class ActualizacionCandidato(Estricto):
    version: int = Field(ge=1)
    cambios: dict[str, object]


class TransicionCandidato(Estricto):
    destino: str
    motivo: str | None = None


class AltaPerfil(Estricto):
    cliente_id: str
    codigo: str
    titulo: str


class AltaVersionPerfil(Estricto):
    requisitos: list[dict[str, object]] = Field(default_factory=list)
    ctc: Decimal | None = Field(default=None, ge=0)
    publicado: bool = False


class AltaPostulacion(Estricto):
    cliente_id: str
    candidato_id: str
    version_perfil_id: str
    fuente: str = "directa"


class SolicitudEvaluacion(Estricto):
    cliente_id: str
    documento_id: str
    version_perfil_id: str
    clave_idempotencia: str | None = None


class CorreccionRevision(Estricto):
    campo: str = Field(min_length=1, max_length=80)
    valor_anterior: object | None = None
    valor_nuevo: object


class RevisionEvaluacion(Estricto):
    decision: Literal["aceptada", "corregida", "rechazada"]
    comentario: str = Field(min_length=3, max_length=2000)
    correcciones: list[CorreccionRevision] = Field(default_factory=list, max_length=50)


class SolicitudReporteExclusion(Estricto):
    cliente_id: str
    filtros: dict[str, object] = Field(default_factory=dict)


class MapeoLote(Estricto):
    columnas: dict[str, str]


class CorreccionFilaLote(Estricto):
    datos: dict[str, object]


class ComprobacionExcolaborador(Estricto):
    cliente_id: str
    documento: str = Field(min_length=1, max_length=100)


class ActualizacionReporteExclusion(Estricto):
    filtros: dict[str, object] = Field(default_factory=dict)
