def test_trabajo_rechaza_referencias_inexistentes(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    solicitud = cliente.post(
        "/api/v1/applications/post-1/evaluation-jobs",
        headers=cabeceras,
        json={
            "cliente_id": cliente_api["cliente_id"],
            "documento_id": "doc-1",
            "version_perfil_id": "perfil-1",
            "clave_idempotencia": "trabajo-prueba-1",
        },
    )
    assert solicitud.status_code == 422
    assert solicitud.json()["error"]["codigo"] == "entrada_invalida"
