from __future__ import annotations


def _alta(cliente_api: dict[str, object]) -> dict[str, object]:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    identidad = {
        "cliente_id": cliente_id,
        "documento": "DNI-12345678",
        "correo": "ana@sintetico.test",
        "telefono": "+51 900 111 222",
        "nombre_completo": "Ana Sintetica",
    }
    preflight = cliente.post(
        "/api/v1/candidates/identity-checks", json=identidad, headers=cabeceras
    )
    assert preflight.status_code == 200
    alta = cliente.post(
        "/api/v1/candidates",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "nombres": "Ana",
            "apellidos": "Sintetica",
            "tipo_documento": "DNI",
            "documento": "DNI-12345678",
            "correo": "ana@sintetico.test",
            "telefono": "+51 900 111 222",
            "perfil_solicitado": "Desarrollo backend",
            "preflight_id": preflight.json()["preflight_id"],
        },
    )
    assert alta.status_code == 201, alta.text
    return alta.json()


def test_auth_preflight_alta_busqueda_y_traza(cliente_api) -> None:
    candidato = _alta(cliente_api)
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    listado = cliente.get("/api/v1/candidates?q=Ana", headers=cabeceras)
    assert listado.status_code == 200
    assert len(listado.json()["items"]) == 1
    traza = cliente.get(f"/api/v1/candidates/{candidato['id']}/trace", headers=cabeceras)
    assert traza.status_code == 200
    assert "Ana Sintetica" in traza.json()["resumen"]


def test_control_optimista_detecta_conflicto(cliente_api) -> None:
    candidato = _alta(cliente_api)
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    ruta = f"/api/v1/candidates/{candidato['id']}"
    primera = cliente.patch(
        ruta,
        headers=cabeceras,
        json={"version": 1, "cambios": {"ubicacion": "Lima"}},
    )
    assert primera.status_code == 200
    segunda = cliente.patch(
        ruta,
        headers=cabeceras,
        json={"version": 1, "cambios": {"ubicacion": "Cusco"}},
    )
    assert segunda.status_code == 409


def test_identidad_normaliza_tildes_en_todas_las_capas(cliente_api) -> None:
    _alta(cliente_api)
    respuesta = cliente_api["cliente"].post(
        "/api/v1/candidates/identity-checks",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "nombre_completo": "\u00c1na Sint\u00e9tica",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["resultado"] == "bloqueada"
    assert respuesta.json()["criterio"] == "nombre: BIZ-004 pendiente"


def test_bgc_equifax_permanecen_bloqueados(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    identidad = {
        "cliente_id": cliente_id,
        "documento": "99999999",
        "nombre_completo": "Persona Bloqueada",
    }
    preflight = cliente.post(
        "/api/v1/candidates/identity-checks", json=identidad, headers=cabeceras
    ).json()
    respuesta = cliente.post(
        "/api/v1/candidates",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "nombres": "Persona",
            "apellidos": "Bloqueada",
            "documento": "99999999",
            "bgc": "dato",
            "preflight_id": preflight["preflight_id"],
        },
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["codigo"] == "decision_negocio_pendiente"


def test_sin_token_no_hay_acceso(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    assert cliente.get("/api/v1/candidates").status_code == 401
