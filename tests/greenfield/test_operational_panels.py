from __future__ import annotations

import pytest


def test_panel_perfiles_muestra_datos_persistidos(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    perfil = cliente.post(
        "/api/v1/job-profiles",
        headers=cabeceras,
        json={"cliente_id": cliente_id, "codigo": "QA-001", "titulo": "QA Automation"},
    )
    assert perfil.status_code == 201
    acceso = cliente.post(
        "/login",
        data={
            "correo": "admin@pruebas.test",
            "contrasena": "Contrasena-Pruebas-2026!",
        },
    )
    assert acceso.status_code == 200

    pagina = cliente.get("/modulo/perfiles")

    assert pagina.status_code == 200
    assert "Registros actuales" in pagina.text
    assert "QA-001" in pagina.text
    assert "QA Automation" in pagina.text
    assert "Sin actividad" not in pagina.text


def test_modulo_desconocido_devuelve_404_controlado(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cliente.post(
        "/login",
        data={
            "correo": "admin@pruebas.test",
            "contrasena": "Contrasena-Pruebas-2026!",
        },
    )

    respuesta = cliente.get("/modulo/no-existe")

    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    "modulo",
    [
        "clientes",
        "perfiles",
        "postulaciones",
        "documentos",
        "evaluaciones",
        "revisiones",
        "lotes",
        "excolaboradores",
        "exclusiones",
        "trabajos",
        "metricas",
    ],
)
def test_paneles_operativos_responden_sin_datos_simulados(cliente_api, modulo: str) -> None:
    cliente = cliente_api["cliente"]
    cliente.post(
        "/login",
        data={
            "correo": "admin@pruebas.test",
            "contrasena": "Contrasena-Pruebas-2026!",
        },
    )

    respuesta = cliente.get(f"/modulo/{modulo}")

    assert respuesta.status_code == 200
    assert "Registros actuales" in respuesta.text
