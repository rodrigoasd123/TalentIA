def test_lote_tiene_staging_y_confirmacion_idempotente(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    datos = {
        "cliente_id": cliente_api["cliente_id"],
        "tipo": "candidatos",
        "clave_idempotencia": "lote-prueba-1",
    }
    archivos = {
        "archivo": (
            "candidatos.csv",
            b"nombres,correo\nAna,ana@test.local\n",
            "text/csv",
        )
    }
    lote = cliente.post("/api/v1/import-batches", data=datos, files=archivos, headers=cabeceras)
    assert lote.status_code == 201
    lote_id = lote.json()["id"]
    detalle = cliente.get(f"/api/v1/import-batches/{lote_id}", headers=cabeceras)
    assert detalle.json()["estado"] == "staging"
    confirmado = cliente.post(f"/api/v1/import-batches/{lote_id}/confirm", headers=cabeceras)
    assert confirmado.json()["estado"] == "confirmado"


def test_login_web_y_cabeceras_seguras(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    pagina = cliente.get("/login")
    assert pagina.status_code == 200
    assert "TalentIA" in pagina.text
    assert pagina.headers["x-frame-options"] == "DENY"
