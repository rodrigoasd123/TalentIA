"""Puertos de aplicacion; no conocen ORM ni transporte."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from talentia.modules.candidates.domain.modelos import Candidato


class DatosTalentIA(Protocol):
    def buscar_usuario(self, correo: str) -> dict[str, object] | None: ...

    def registrar_intento_autenticacion(
        self, usuario_id: str, exitoso: bool, maximos_intentos: int, minutos_bloqueo: int
    ) -> dict[str, object]: ...

    def sesion_valida(self, usuario_id: str, sesion_version: int) -> bool: ...

    def revocar_sesiones(self, usuario_id: str) -> int: ...

    def actualizar_contrasena(self, usuario_id: str, hash_nuevo: str) -> int: ...

    def crear_usuario(
        self,
        correo: str,
        nombre: str,
        hash_contrasena: str,
        rol: str,
        cliente_id: str | None,
    ) -> dict[str, object]: ...

    def listar_accesos(self) -> dict[str, object]: ...

    def asignar_rol(self, usuario_id: str, rol: str, asignar: bool) -> dict[str, object]: ...

    def asignar_cliente(
        self, usuario_id: str, cliente_id: str, asignar: bool
    ) -> dict[str, object]: ...

    def sincronizar_clientes_usuario(
        self, usuario_id: str, clientes_ids: list[str]
    ) -> None: ...

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

    def traza_candidato(
        self,
        candidato_id: str,
        limite: int,
        tipo: str | None = None,
        desde: datetime | None = None,
    ) -> list[dict[str, object]]: ...

    def crear_perfil(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_perfil(self, perfil_id: str) -> dict[str, object] | None: ...

    def crear_version_perfil(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_version_perfil(self, version_id: str) -> dict[str, object] | None: ...

    def obtener_versiones_perfil(self, perfil_id: str) -> list[dict[str, object]]: ...

    def listar_postulaciones_perfil(self, perfil_id: str) -> list[dict[str, object]]: ...

    def crear_convocatoria(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_convocatoria(self, convocatoria_id: str) -> dict[str, object] | None: ...

    def listar_convocatorias(
        self,
        clientes: frozenset[str],
        cliente_id: str | None = None,
        limite: int = 100,
        cursor: str | None = None,
    ) -> list[dict[str, object]]: ...

    def obtener_o_crear_convocatoria_compatibilidad(
        self, cliente_id: str, version_perfil_id: str
    ) -> dict[str, object]: ...

    def asignar_reclutador_convocatoria(
        self, convocatoria_id: str, usuario_id: str, asignado_por: str, asignar: bool
    ) -> dict[str, object]: ...

    def usuario_asignado_cliente(self, usuario_id: str, cliente_id: str) -> bool: ...

    def transicionar_postulacion(
        self,
        postulacion_id: str,
        destino: str,
        motivo: str | None,
        version_esperada: int,
    ) -> dict[str, object]: ...

    def listar_postulaciones_convocatoria(
        self, convocatoria_id: str
    ) -> list[dict[str, object]]: ...

    def vista_previa_cierre(self, convocatoria_id: str) -> dict[str, object]: ...

    def cerrar_convocatoria(
        self, convocatoria_id: str, version_esperada: int, motivo: str
    ) -> dict[str, object]: ...

    def crear_postulacion(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_postulacion(self, postulacion_id: str) -> dict[str, object] | None: ...

    def obtener_postulacion_activa_candidato(
        self, candidato_id: str, documento_normalizado: str | None = None
    ) -> dict[str, object] | None: ...

    def guardar_documento(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_documento(self, documento_id: str) -> dict[str, object] | None: ...

    def buscar_documento_por_hash(
        self, candidato_id: str, hash_sha256: str
    ) -> dict[str, object] | None: ...

    def obtener_extraccion_documento(self, documento_id: str) -> dict[str, object] | None: ...

    def guardar_extraccion_documento(
        self,
        datos: dict[str, object],
        sugerencias: list[dict[str, object]],
    ) -> dict[str, object]: ...

    def validar_solicitud_evaluacion(
        self,
        cliente_id: str,
        postulacion_id: str,
        documento_id: str,
        version_perfil_id: str,
    ) -> bool: ...

    def crear_trabajo(self, datos: dict[str, object]) -> dict[str, object]: ...

    def obtener_trabajo(self, trabajo_id: str) -> dict[str, object] | None: ...

    def obtener_evaluacion(self, evaluacion_id: str) -> dict[str, object] | None: ...

    def registrar_revision(
        self,
        evaluacion_id: str,
        revisor_id: str,
        decision: str,
        comentario: str,
        correcciones: list[dict[str, object]],
    ) -> dict[str, object]: ...

    def metricas(
        self,
        clientes: frozenset[str],
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> dict[str, object]: ...

    def registrar_metrica(
        self,
        cliente_id: str,
        nombre: str,
        valor: int | float | Decimal,
        unidad: str,
        dimensiones: dict[str, object],
        clave_idempotencia: str | None = None,
    ) -> None: ...

    def crear_lote(
        self, datos: dict[str, object], filas: list[dict[str, object]]
    ) -> dict[str, object]: ...

    def obtener_lote(self, lote_id: str) -> dict[str, object] | None: ...

    def aplicar_mapeo_lote(self, lote_id: str, mapeo: dict[str, str]) -> dict[str, object]: ...

    def corregir_fila_lote(
        self, lote_id: str, numero: int, datos: dict[str, object]
    ) -> dict[str, object]: ...

    def confirmar_lote(self, lote_id: str) -> dict[str, object]: ...

    def cancelar_lote(self, lote_id: str) -> dict[str, object]: ...

    def verificar_excolaborador(
        self, cliente_id: str, documento_hash: str
    ) -> dict[str, object]: ...

    def candidatos_para_exclusion(
        self, cliente_id: str, filtros: dict[str, object]
    ) -> list[dict[str, object]]: ...

    def guardar_reporte_exclusion(
        self,
        cliente_id: str,
        filtros: dict[str, object],
        entradas: list[dict[str, str]],
        hash_contenido: str,
    ) -> dict[str, object]: ...

    def obtener_reporte_exclusion(self, reporte_id: str) -> dict[str, object] | None: ...

    def actualizar_reporte_exclusion(
        self,
        reporte_id: str,
        filtros: dict[str, object],
        entradas: list[dict[str, str]],
        hash_contenido: str,
    ) -> dict[str, object]: ...

    def listar_panel_operativo(
        self, modulo: str, clientes: frozenset[str], limite: int
    ) -> list[dict[str, object]]: ...

    def listar_opciones_operativas(
        self, clientes: frozenset[str]
    ) -> dict[str, list[dict[str, object]]]: ...


class UnidadTrabajo(Protocol, AbstractContextManager["UnidadTrabajo"]):
    datos: DatosTalentIA

    def confirmar(self) -> None: ...

    def revertir(self) -> None: ...


class FabricaUnidadTrabajo(Protocol):
    def __call__(self) -> UnidadTrabajo: ...


def iterar_unidad(fabrica: FabricaUnidadTrabajo) -> Iterator[UnidadTrabajo]:
    with fabrica() as unidad:
        yield unidad
