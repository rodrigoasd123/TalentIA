from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from talentia.main import app
from talentia.platform.security.contrasenas import hash_contrasena
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    AsignacionUsuarioClienteModelo,
    ClienteModelo,
    RolModelo,
    UsuarioModelo,
    UsuarioRolModelo,
)


@pytest.fixture
def cliente_api(tmp_path, monkeypatch) -> Iterator[dict[str, object]]:
    base = tmp_path / "talentia-pruebas.db"
    documentos = tmp_path / "documentos"
    monkeypatch.setenv("TALENTIA_ENV", "pruebas")
    monkeypatch.setenv("TALENTIA_GREENFIELD_DATABASE_URL", f"sqlite:///{base.as_posix()}")
    monkeypatch.setenv("TALENTIA_SESSION_SECRET", "pruebas-talentia-01234567890123456789")
    monkeypatch.setenv("TALENTIA_ADMIN_EMAIL", "admin@pruebas.test")
    monkeypatch.setenv("TALENTIA_ADMIN_PASSWORD", "Contrasena-Pruebas-2026!")
    monkeypatch.setenv("TALENTIA_DOCUMENT_STORAGE", str(documentos))
    with TestClient(app) as cliente:
        acceso = cliente.post(
            "/api/v1/auth/login",
            json={
                "correo": "admin@pruebas.test",
                "contrasena": "Contrasena-Pruebas-2026!",
            },
        )
        assert acceso.status_code == 200
        token = acceso.json()["access_token"]
        sesion = app.state.firmador.leer(token)

        def token_para(
            usuario_id: str,
            correo: str,
            roles: list[str],
            clientes: list[str],
            csrf: str,
        ) -> str:
            motor = crear_motor(f"sqlite:///{base.as_posix()}")
            with Session(motor) as db:
                usuario = UsuarioModelo(
                    id=usuario_id,
                    correo=correo,
                    nombre="Usuario autorizado de prueba",
                    hash_contrasena=hash_contrasena("Acceso-Pruebas-2026!"),
                    activo=True,
                )
                db.add(usuario)
                db.flush()
                for codigo in roles:
                    rol = db.scalar(select(RolModelo).where(RolModelo.codigo == codigo))
                    assert rol is not None
                    db.add(UsuarioRolModelo(usuario_id=usuario_id, rol_id=rol.id))
                for cliente_id in clientes:
                    if db.get(ClienteModelo, cliente_id) is None:
                        db.add(
                            ClienteModelo(
                                id=cliente_id,
                                codigo=f"TEST-{nuevo_id()[:8]}",
                                nombre="Cliente de aislamiento",
                                activo=True,
                            )
                        )
                        db.flush()
                    db.add(
                        AsignacionUsuarioClienteModelo(usuario_id=usuario_id, cliente_id=cliente_id)
                    )
                db.commit()
            return app.state.firmador.crear(
                {
                    "sub": usuario_id,
                    "correo": correo,
                    "roles": roles,
                    "clientes": clientes,
                    "csrf": csrf,
                    "sv": 1,
                }
            )

        yield {
            "cliente": cliente,
            "cabeceras": {"Authorization": f"Bearer {token}"},
            "cliente_id": sesion["clientes"][0],
            "base": base,
            "documentos": documentos,
            "token_para": token_para,
        }
