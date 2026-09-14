"""Ensamblaje de dependencias y migracion del runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from talentia.config import Ambiente, Configuracion, cargar_configuracion
from talentia.modules.access.domain.modelos import PERMISOS_POR_ROL, Rol
from talentia.modules.documents.infrastructure.extractores import extraer_documento
from talentia.modules.providers.infrastructure.lector_lotes import leer_filas
from talentia.platform.document_store.local import AlmacenLocal
from talentia.platform.security.contrasenas import hash_contrasena
from talentia.shared.application.puertos import FabricaUnidadTrabajo
from talentia.shared.application.servicio_principal import ServicioTalentIA
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    AsignacionUsuarioClienteModelo,
    ClienteModelo,
    RolModelo,
    UsuarioModelo,
    UsuarioRolModelo,
)
from talentia.shared.infrastructure.repositorio_sqlalchemy import (
    FabricaUnidadTrabajoSqlalchemy,
)

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


def migrar(configuracion: Configuracion) -> None:
    config = Config(str(RAIZ_PROYECTO / "alembic_greenfield.ini"))
    config.set_main_option("script_location", str(RAIZ_PROYECTO / "migrations_greenfield"))
    config.set_main_option("sqlalchemy.url", configuracion.url_base_datos.replace("%", "%%"))
    command.upgrade(config, "head")


def preparar_acceso(configuracion: Configuracion, fabrica: FabricaSesiones) -> None:
    correo = os.getenv("TALENTIA_ADMIN_EMAIL", "").strip().casefold()
    contrasena = os.getenv("TALENTIA_ADMIN_PASSWORD", "")
    with fabrica.sesion() as sesion:
        roles: dict[Rol, RolModelo] = {}
        for rol, permisos in PERMISOS_POR_ROL.items():
            modelo = sesion.scalar(select(RolModelo).where(RolModelo.codigo == rol))
            if modelo is None:
                modelo = RolModelo(id=nuevo_id(), codigo=rol, permisos=sorted(permisos))
                sesion.add(modelo)
            roles[Rol(rol)] = modelo
        cliente = sesion.scalar(select(ClienteModelo).where(ClienteModelo.codigo == "TCS"))
        if cliente is None:
            cliente = ClienteModelo(id=nuevo_id(), codigo="TCS", nombre="TCS", activo=True)
            sesion.add(cliente)
        sesion.flush()

        usuarios_laboratorio = [
            ("admin@ejemplo.local", "Administrador del Sistema", Rol.ADMINISTRADOR),
            ("reclutador@ejemplo.local", "Reclutador Principal", Rol.RECLUTADOR),
            ("gestor@ejemplo.local", "Gestor de Contratación", Rol.GESTOR_CONTRATACION),
            ("auditor@ejemplo.local", "Auditor de Cumplimiento", Rol.AUDITOR),
            ("entrevistador@ejemplo.local", "Entrevistador Técnico", Rol.ENTREVISTADOR),
            ("importador@ejemplo.local", "Operador de Importación", Rol.IMPORTADOR),
        ]
        clave_lab = "Laboratorio-TalentIA-2026!"
        hash_lab = hash_contrasena(clave_lab)

        for correo_lab, nombre_lab, rol_lab in usuarios_laboratorio:
            usr = sesion.scalar(select(UsuarioModelo).where(UsuarioModelo.correo == correo_lab))
            if usr is None:
                h_pwd = (
                    hash_contrasena(contrasena)
                    if (correo_lab == correo and contrasena and len(contrasena) >= 14)
                    else hash_lab
                )
                usr = UsuarioModelo(
                    id=nuevo_id(),
                    correo=correo_lab,
                    nombre=nombre_lab,
                    hash_contrasena=h_pwd,
                    activo=True,
                )
                sesion.add(usr)
                sesion.flush()
                sesion.add(UsuarioRolModelo(usuario_id=usr.id, rol_id=roles[rol_lab].id))
                sesion.add(AsignacionUsuarioClienteModelo(usuario_id=usr.id, cliente_id=cliente.id))

        if correo and contrasena and len(contrasena) >= 14:
            usr = sesion.scalar(select(UsuarioModelo).where(UsuarioModelo.correo == correo))
            if usr is None:
                usr = UsuarioModelo(
                    id=nuevo_id(),
                    correo=correo,
                    nombre=os.getenv("TALENTIA_ADMIN_NAME", "Administracion del piloto"),
                    hash_contrasena=hash_contrasena(contrasena),
                    activo=True,
                )
                sesion.add(usr)
                sesion.flush()
                sesion.add(UsuarioRolModelo(usuario_id=usr.id, rol_id=roles[Rol.ADMINISTRADOR].id))
                sesion.add(AsignacionUsuarioClienteModelo(usuario_id=usr.id, cliente_id=cliente.id))

        total_usuarios = sesion.scalar(select(func.count()).select_from(UsuarioModelo)) or 0
        if configuracion.ambiente is Ambiente.PILOTO and total_usuarios == 0:
            raise RuntimeError(
                "El piloto requiere TALENTIA_ADMIN_EMAIL y TALENTIA_ADMIN_PASSWORD iniciales"
            )


def construir_servicio() -> tuple[Configuracion, ServicioTalentIA]:
    configuracion = cargar_configuracion()
    migrar(configuracion)
    motor = crear_motor(configuracion.url_base_datos)
    fabrica_sesiones = FabricaSesiones(motor)
    preparar_acceso(configuracion, fabrica_sesiones)
    fabrica_unidad = cast(FabricaUnidadTrabajo, FabricaUnidadTrabajoSqlalchemy(fabrica_sesiones))
    servicio = ServicioTalentIA(
        fabrica_unidad,
        AlmacenLocal(configuracion.ruta_documentos),
        leer_filas,
        extraer_documento,
        configuracion.tamano_maximo_mb * 1024 * 1024,
    )
    return configuracion, servicio
