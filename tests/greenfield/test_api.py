from __future__ import annotations

from sqlalchemy.orm import Session

from talentia.shared.infrastructure.base_datos import crear_motor
from talentia.shared.infrastructure.modelos_orm import CandidatoModelo


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


def test_control_optimista_fusiona_campos_disjuntos(cliente_api) -> None:
    candidato = _alta(cliente_api)
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    ruta = f"/api/v1/candidates/{candidato['id']}"
    assert (
        cliente.patch(
            ruta, headers=cabeceras, json={"version": 1, "cambios": {"ubicacion": "Lima"}}
        ).status_code
        == 200
    )
    fusion = cliente.patch(
        ruta,
        headers=cabeceras,
        json={"version": 1, "cambios": {"disponibilidad": "Inmediata"}},
    )
    assert fusion.status_code == 200
    assert fusion.json()["ubicacion"] == "Lima"
    assert fusion.json()["disponibilidad"] == "Inmediata"
    assert fusion.json()["version"] == 3


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
    assert respuesta.json()["resultado"] == "probable"
    assert respuesta.json()["criterio"] == "telefono_o_nombre: requiere_decision_humana"


def test_telefono_es_probable_y_requiere_confirmacion_humana(cliente_api) -> None:
    _alta(cliente_api)
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    identidad = {
        "cliente_id": cliente_api["cliente_id"],
        "documento": "DNI-OTRA-IDENTIDAD",
        "correo": "otra@sintetico.test",
        "telefono": "+51 900 111 222",
        "nombre_completo": "Otra Persona",
    }
    preflight = cliente.post(
        "/api/v1/candidates/identity-checks", json=identidad, headers=cabeceras
    ).json()
    assert preflight["resultado"] == "probable"
    assert preflight["evidencia"][0]["criterio"] == "telefono"
    datos = {
        "cliente_id": cliente_api["cliente_id"],
        "nombres": "Otra",
        "apellidos": "Persona",
        "documento": "DNI-OTRA-IDENTIDAD",
        "correo": "otra@sintetico.test",
        "telefono": "+51 900 111 222",
        "preflight_id": preflight["preflight_id"],
    }
    assert cliente.post("/api/v1/candidates", json=datos, headers=cabeceras).status_code == 409
    confirmada = cliente.post(
        "/api/v1/candidates",
        json={**datos, "confirmar_posible_duplicado": True},
        headers=cabeceras,
    )
    assert confirmada.status_code == 201


def test_nombre_se_compara_con_toda_la_base_sin_limite_200(cliente_api) -> None:
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        for indice in range(205):
            sesion.add(
                CandidatoModelo(
                    id=f"masivo-{indice:04d}",
                    cliente_id=cliente_api["cliente_id"],
                    nombres="Objetivo" if indice == 204 else "Persona",
                    apellidos="Final" if indice == 204 else f"{indice:04d}",
                    estado="pendiente",
                )
            )
        sesion.commit()
    respuesta = cliente_api["cliente"].post(
        "/api/v1/candidates/identity-checks",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "nombre_completo": "Objetivo Final",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["candidato_ids"] == ["masivo-0204"]


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
