from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from talentia.main import app


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
        yield {
            "cliente": cliente,
            "cabeceras": {"Authorization": f"Bearer {token}"},
            "cliente_id": sesion["clientes"][0],
            "base": base,
            "documentos": documentos,
        }
