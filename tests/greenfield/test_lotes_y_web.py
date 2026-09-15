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
            b"nombres,apellidos,correo\nAna,Importada,ana@test.local\n",
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
    assert confirmado.json()["importadas"] == 1
    candidatos = cliente.get("/api/v1/candidates?q=Ana", headers=cabeceras).json()["items"]
    assert len(candidatos) == 1
    repetido = cliente.post(f"/api/v1/import-batches/{lote_id}/confirm", headers=cabeceras)
    assert repetido.json()["reutilizado"] is True


def test_importa_excolaboradores_sin_persistir_documento_crudo(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    respuesta = cliente.post(
        "/api/v1/former-employees/imports",
        data={
            "cliente_id": cliente_api["cliente_id"],
            "clave_idempotencia": "ex-tcs-1",
        },
        files={
            "archivo": (
                "excolaboradores.csv",
                b"documento,elegible_reingreso\nDNI-87654321,si\n",
                "text/csv",
            )
        },
        headers=cabeceras,
    )
    assert respuesta.status_code == 201
    confirmado = cliente.post(
        f"/api/v1/import-batches/{respuesta.json()['id']}/confirm", headers=cabeceras
    )
    assert confirmado.status_code == 200
    assert confirmado.json()["importadas"] == 1


def test_login_web_y_cabeceras_seguras(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    pagina = cliente.get("/login")
    assert pagina.status_code == 200
    assert "TalentIA" in pagina.text
    assert pagina.headers["x-frame-options"] == "DENY"


def test_alta_web_evidencia_ficha_y_trazabilidad(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    token = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token)
    csrf = cliente.app.state.firmador.leer(token)["csrf"]
    formulario = cliente.get("/candidatos/nuevo")
    assert formulario.status_code == 200
    respuesta = cliente.post(
        "/candidatos/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "nombres": "Lucia",
            "apellidos": "Web",
            "documento": "WEB-123",
            "correo": "lucia@web.test",
            "expectativa_salarial": "5000",
            "ctc_rol": "6000",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert "Lucia Web" in respuesta.text
    assert "Trazabilidad" in respuesta.text
    assert "-16.67" in respuesta.text


def test_sesion_vencida_redirecciona_a_login_en_web(cliente_api) -> None:
    from talentia.platform.security.contrasenas import FirmadorSesion

    cliente = cliente_api["cliente"]
    firmador_vencido = FirmadorSesion("pruebas-talentia-01234567890123456789", minutos=-1)
    token_vencido = firmador_vencido.crear(
        {
            "sub": "usuario-vencido",
            "correo": "vencido@test.local",
            "roles": ["reclutador"],
            "clientes": [],
            "csrf": "csrf-vencido",
            "sv": 1,
        }
    )

    cliente.cookies.clear()
    resp = cliente.get("/candidatos", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

    cliente.cookies.set("talentia_session", token_vencido)
    resp = cliente.get("/candidatos", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    assert "talentia_session" in resp.headers.get("set-cookie", "")

    cliente.cookies.set("talentia_session", token_vencido)
    resp_htmx = cliente.get("/candidatos", headers={"HX-Request": "true"})
    assert resp_htmx.status_code == 200
    assert resp_htmx.headers.get("HX-Redirect") == "/login"

    cliente.cookies.set("talentia_session", token_vencido)
    resp_login = cliente.get("/login", follow_redirects=False)
    assert resp_login.status_code == 200
    assert "TalentIA" in resp_login.text
