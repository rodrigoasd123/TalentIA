"""Puertos de aplicacion; no conocen ORM ni transporte."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Protocol

from talentia.modules.candidates.domain.modelos import Candidato


class DatosTalentIA(Protocol):
    def buscar_usuario(self, correo: str) -> dict[str, object] | None: ...

    def listar_accesos(self) -> dict[str, object]: ...

    def asignar_rol(self, usuario_id: str, rol: str, asignar: bool) -> dict[str, object]: ...

    def asignar_cliente(
        self, usuario_id: str, cliente_id: str, asignar: bool
    ) -> dict[str, object]: ...

    def buscar_identidad(
        self,
        cliente_id: str,
        documento: str | None,
        correo: str | None,
        telefono: str | None,
        tokens: tuple[str, ...],
    ) -> list[dict[str, object]]: ...

    def agregar_candidato(self, candidato: Candidato) -> Candidato: ...

    def obtener_candidato(self, candidato_id: str) -> Candidato | None: ...

    def buscar_candidatos(
        self, clientes: frozenset[str], texto: str, limite: int, cursor: str | None
    ) -> list[Candidato]: ...

    def actualizar_candidato(
        self, candidato: Candidato, version_esperada: int, campos: set[str]
    ) -> Candidato: ...

    def registrar_evento(
        self,
        *,
        cliente_id: str | None,
        actor_id: str | None,
        accion: str,
        recurso_tipo: str,
        recurso_id: str | None,
        detalle: dict[str, object],
        correlacion_id: str,
    ) -> str: ...

    def traza_candidato(self, candidato_id: str, limite: int) -> list[dict[str, object]]: ...

    def crear_perfil(self, datos: dict[str, object]) -> dict[str, object]: ...

    def crear_version_perfil(self, datos: dict[str, object]) -> dict[str, object]: ...

    def crear_postulacion(self, datos: dict[str, object]) -> dict[str, object]: ...

    def guardar_documento(self, datos: dict[str, object]) -> dict[str, object]: ...

    def crear_trabajo(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_trabajo(self, trabajo_id: str) -> dict[str, object] | None: ...

    def metricas(self, clientes: frozenset[str]) -> dict[str, object]: ...

    def crear_lote(
        self, datos: dict[str, object], filas: list[dict[str, object]]
    ) -> dict[str, object]: ...

    def obtener_lote(self, lote_id: str) -> dict[str, object] | None: ...

    def confirmar_lote(self, lote_id: str) -> dict[str, object]: ...

    def candidatos_para_exclusion(self, cliente_id: str) -> list[dict[str, object]]: ...

    def guardar_reporte_exclusion(
        self,
        cliente_id: str,
        filtros: dict[str, object],
        entradas: list[dict[str, str]],
        hash_contenido: str,
    ) -> dict[str, object]: ...

    def obtener_reporte_exclusion(self, reporte_id: str) -> dict[str, object] | None: ...


class UnidadTrabajo(Protocol, AbstractContextManager["UnidadTrabajo"]):
    datos: DatosTalentIA

    def confirmar(self) -> None: ...

    def revertir(self) -> None: ...


class FabricaUnidadTrabajo(Protocol):
    def __call__(self) -> UnidadTrabajo: ...


def iterar_unidad(fabrica: FabricaUnidadTrabajo) -> Iterator[UnidadTrabajo]:
    with fabrica() as unidad:
        yield unidad
