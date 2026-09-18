from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import func, select

from talentia.platform.jobs.worker import procesar_siguiente
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    DocumentoCandidatoModelo,
    EventoAuditoriaModelo,
    PerfilPuestoModelo,
    PostulacionModelo,
    TrabajoAgenteModelo,
    VersionPerfilPuestoModelo,
)


def _docx(*lineas: str) -> bytes:
    parrafos = "".join(f"<w:p><w:r><w:t>{linea}</w:t></w:r></w:p>" for linea in lineas)
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{parrafos}</w:body></w:document>"
    )
    contenido = BytesIO()
    with ZipFile(contenido, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archivo.writestr("word/document.xml", xml)
    return contenido.getvalue()


def _login_web(cliente_api: dict[str, object]) -> tuple[object, str]:
    cliente = cliente_api["cliente"]
    respuesta = cliente.post(
        "/login",
        data={"correo": "admin@pruebas.test", "contrasena": "Contrasena-Pruebas-2026!"},
    )
    assert respuesta.status_code == 200
    token = cliente.cookies.get("talentia_session")
    assert token is not None
    csrf = str(cliente.app.state.firmador.leer(token)["csrf"])
    return cliente, csrf


def _crear_candidato(cliente_api: dict[str, object], sufijo: str) -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    identidad = cliente.post(
        "/api/v1/candidates/identity-checks",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "documento": f"DNI-F4-{sufijo}",
            "nombre_completo": f"Candidata {sufijo}",
        },
    ).json()
    respuesta = cliente.post(
        "/api/v1/candidates",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "nombres": "Candidata",
            "apellidos": sufijo,
            "documento": f"DNI-F4-{sufijo}",
            "preflight_id": identidad["preflight_id"],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return str(respuesta.json()["id"])


def _crear_perfil_version(cliente_api: dict[str, object], sufijo: str) -> tuple[str, str]:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    perfil = cliente.post(
        "/api/v1/job-profiles",
        headers=cabeceras,
        json={
            "cliente_id": cliente_api["cliente_id"],
            "codigo": f"F4-{sufijo}",
            "titulo": "Ingenieria de software",
        },
    )
    assert perfil.status_code == 201, perfil.text
    version = cliente.post(
        f"/api/v1/job-profiles/{perfil.json()['id']}/versions",
        headers=cabeceras,
        json={
            "requisitos": [
                {
                    "codigo": "PY",
                    "descripcion": "Experiencia Python",
                    "obligatorio": True,
                    "peso": "1",
                }
            ],
            "ctc": "5000",
            "publicado": True,
        },
    )
    assert version.status_code == 201, version.text
    return str(perfil.json()["id"]), str(version.json()["id"])


def _crear_postulacion_api(
    cliente_api: dict[str, object], candidato_id: str, version_id: str
) -> str:
    respuesta = cliente_api["cliente"].post(
        "/api/v1/applications",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "candidato_id": candidato_id,
            "version_perfil_id": version_id,
            "fuente": "portal",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return str(respuesta.json()["id"])


def test_crear_perfil_admite_job_description_manual(cliente_api) -> None:
    cliente, csrf = _login_web(cliente_api)
    respuesta = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "FULLSTACK-MANUAL",
            "titulo": "Desarrollador Fullstack Senior",
            "modo_jd": "manual",
            "descripcion_puesto": (
                "Experiencia tecnica:\n"
                "- Python y FastAPI en sistemas productivos\n"
                "- React y TypeScript\n"
                "Deseable:\n"
                "- Despliegues en AWS"
            ),
        },
        follow_redirects=False,
    )

    assert respuesta.status_code == 303
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    with fabrica.sesion() as sesion:
        perfil = sesion.scalar(
            select(PerfilPuestoModelo).where(PerfilPuestoModelo.codigo == "FULLSTACK-MANUAL")
        )
        assert perfil is not None
        version = sesion.scalar(
            select(VersionPerfilPuestoModelo).where(
                VersionPerfilPuestoModelo.perfil_id == perfil.id
            )
        )
        assert version is not None
        assert version.publicado
        assert len(version.requisitos) == 3
        assert {bool(requisito["obligatorio"]) for requisito in version.requisitos} == {True, False}


def test_formularios_crean_perfil_y_version_y_conservan_datos(cliente_api) -> None:
    cliente, csrf = _login_web(cliente_api)
    alta = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "WEB-F4",
            "titulo": "Backend Senior",
        },
        follow_redirects=False,
    )
    assert alta.status_code == 303
    ruta_perfil = alta.headers["location"]
    assert ruta_perfil.startswith("/perfiles/")
    ruta_version = f"{ruta_perfil}/versiones/nueva"

    invalida = cliente.post(
        ruta_version,
        data={
            "csrf": csrf,
            "requisitos_texto": "FORMATO SIN SEPARADORES",
            "ctc": "6200",
            "publicado": "si",
        },
    )
    assert invalida.status_code == 422
    assert "FORMATO SIN SEPARADORES" in invalida.text
    assert 'value="6200"' in invalida.text
    assert "checked" in invalida.text

    creada = cliente.post(
        ruta_version,
        data={
            "csrf": csrf,
            "requisitos_texto": (
                "PY | Experiencia Python | obligatorio | 1\nAWS | Experiencia AWS | opcional | 0.5"
            ),
            "ctc": "6200",
            "publicado": "si",
        },
        follow_redirects=False,
    )
    assert creada.status_code == 303
    assert creada.headers["location"].startswith(("/modulo/perfiles", "/perfiles/"))

    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    with fabrica.sesion() as sesion:
        perfil = sesion.scalar(
            select(PerfilPuestoModelo).where(PerfilPuestoModelo.codigo == "WEB-F4")
        )
        assert perfil is not None
        version = sesion.scalar(
            select(VersionPerfilPuestoModelo)
            .where(VersionPerfilPuestoModelo.perfil_id == perfil.id)
            .order_by(VersionPerfilPuestoModelo.numero.desc())
        )
        assert version is not None
        assert version.publicado
        assert len(version.requisitos) == 2

    duplicado = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "WEB-F4",
            "titulo": "Titulo conservado",
        },
    )
    assert duplicado.status_code == 409
    assert "Titulo conservado" in duplicado.text
    assert "Ya existe un perfil" in duplicado.text

    token_otro_cliente = cliente_api["token_para"](
        "gestor-otro-f4",
        "gestor@otro.test",
        ["gestor_contratacion"],
        ["cliente-fuera-de-alcance"],
        "csrf-gestor-otro",
    )
    cliente.cookies.set("talentia_session", token_otro_cliente)
    assert cliente.get(ruta_version).status_code == 403


def test_postulacion_web_es_idempotente_y_valida_rbac_idor(cliente_api) -> None:
    candidato_id = _crear_candidato(cliente_api, "APP")
    _, version_id = _crear_perfil_version(cliente_api, "APP")
    cliente, csrf = _login_web(cliente_api)
    datos = {
        "csrf": csrf,
        "cliente_id": cliente_api["cliente_id"],
        "candidato_id": candidato_id,
        "version_perfil_id": version_id,
        "fuente": "LinkedIn",
    }
    primera = cliente.post("/postulaciones/nueva", data=datos, follow_redirects=False)
    segunda = cliente.post("/postulaciones/nueva", data=datos, follow_redirects=False)
    assert primera.status_code == 303
    assert segunda.status_code == 303
    assert primera.headers["location"] == segunda.headers["location"]

    listado = cliente.get("/modulo/postulaciones")
    formulario_lote = cliente.get("/lotes/nuevo")
    formulario_candidato = cliente.get("/candidatos/nuevo")
    assert listado.status_code == 200
    assert f">{primera.headers['location'].split('=', 1)[-1]}<" not in listado.text
    assert "Persona candidata" in listado.text
    assert "Vacante" in listado.text
    assert "TCS · TCS" in listado.text
    assert f">{cliente_api['cliente_id']}</option>" not in formulario_lote.text
    assert f">{cliente_api['cliente_id']}</option>" not in formulario_candidato.text
    assert ">TCS · TCS</option>" in formulario_lote.text
    assert ">TCS · TCS</option>" in formulario_candidato.text

    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    with fabrica.sesion() as sesion:
        assert sesion.scalar(select(func.count()).select_from(PostulacionModelo)) == 1
        eventos = sesion.scalar(
            select(func.count())
            .select_from(EventoAuditoriaModelo)
            .where(EventoAuditoriaModelo.accion == "postulacion.creada")
        )
        assert eventos == 1

    token_sin_permiso = cliente_api["token_para"](
        "entrevistador-f4",
        "entrevistador@pruebas.test",
        ["entrevistador"],
        [cliente_api["cliente_id"]],
        "csrf-entrevistador",
    )
    cliente.cookies.set("talentia_session", token_sin_permiso)
    assert cliente.get("/postulaciones/nueva").status_code == 403

    token_otro_cliente = cliente_api["token_para"](
        "reclutador-otro-f4",
        "reclutador@otro.test",
        ["reclutador"],
        ["cliente-fuera-de-alcance"],
        "csrf-otro",
    )
    cliente.cookies.set("talentia_session", token_otro_cliente)
    idor = cliente.post(
        "/postulaciones/nueva",
        data={**datos, "csrf": "csrf-otro"},
    )
    assert idor.status_code == 403

    token_admin = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token_admin)
    csrf_admin = cliente.app.state.firmador.leer(token_admin)["csrf"]
    assert (
        cliente.post(
            "/postulaciones/nueva", data={**datos, "csrf": f"{csrf_admin}-incorrecto"}
        ).status_code
        == 401
    )


def test_carga_cv_crea_un_trabajo_y_reutiliza_documento_y_job(cliente_api) -> None:
    candidato_id = _crear_candidato(cliente_api, "CV")
    _, version_id = _crear_perfil_version(cliente_api, "CV")
    postulacion_id = _crear_postulacion_api(cliente_api, candidato_id, version_id)
    cliente, csrf = _login_web(cliente_api)
    clave = "web-f4-cv-idempotente"
    archivo = (
        "cv.docx",
        _docx(
            "Habilidades: Python, SQL",
            "Experiencia: Cinco anos con Python",
            "Educacion: Ingenieria",
            "Empresa reciente: TCS",
        ),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    primera = cliente.post(
        "/evaluaciones/nueva",
        data={"csrf": csrf, "postulacion_id": postulacion_id, "clave_idempotencia": clave},
        files={"archivo": archivo},
        follow_redirects=False,
    )
    segunda = cliente.post(
        "/evaluaciones/nueva",
        data={"csrf": csrf, "postulacion_id": postulacion_id, "clave_idempotencia": clave},
        files={"archivo": archivo},
        follow_redirects=False,
    )
    assert primera.status_code == 303
    assert segunda.status_code == 303
    assert primera.headers["location"] == segunda.headers["location"]
    progreso = cliente.get(primera.headers["location"])
    assert progreso.status_code == 200
    assert "Pendiente" in progreso.text

    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    with fabrica.sesion() as sesion:
        assert sesion.scalar(select(func.count()).select_from(DocumentoCandidatoModelo)) == 1
        assert sesion.scalar(select(func.count()).select_from(TrabajoAgenteModelo)) == 1
    archivos = [item for item in Path(cliente_api["documentos"]).iterdir() if item.is_file()]
    assert len(archivos) == 1

    trabajo_id = primera.headers["location"].rsplit("/", 1)[-1]
    assert procesar_siguiente(fabrica) == trabajo_id
    completado = cliente.get(f"/trabajos/{trabajo_id}")
    assert "Revision humana requerida" in completado.text
    assert f"/evaluaciones/{trabajo_id}" in completado.text

    invalida = cliente.post(
        "/evaluaciones/nueva",
        data={
            "csrf": csrf,
            "postulacion_id": postulacion_id,
            "clave_idempotencia": "clave-conservada-error",
        },
        files={"archivo": ("cv.txt", b"contenido", "text/plain")},
    )
    assert invalida.status_code == 422
    assert f'value="{postulacion_id}" selected' in invalida.text
    assert 'value="clave-conservada-error"' in invalida.text
    assert "seleccione nuevamente el archivo" in invalida.text


def test_formularios_de_fase_4_rechazan_csrf_y_postulacion_fuera_de_alcance(
    cliente_api,
) -> None:
    candidato_id = _crear_candidato(cliente_api, "SEC")
    _, version_id = _crear_perfil_version(cliente_api, "SEC")
    postulacion_id = _crear_postulacion_api(cliente_api, candidato_id, version_id)
    cliente, _ = _login_web(cliente_api)
    sin_csrf = cliente.post(
        "/evaluaciones/nueva",
        data={
            "csrf": "incorrecto",
            "postulacion_id": postulacion_id,
            "clave_idempotencia": "csrf-f4",
        },
        files={"archivo": ("cv.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert sin_csrf.status_code == 401

    token_otro_cliente = cliente_api["token_para"](
        "reclutador-otro-cv-f4",
        "reclutador-cv@otro.test",
        ["reclutador"],
        ["cliente-fuera-de-alcance"],
        "csrf-otro-cv",
    )
    cliente.cookies.set("talentia_session", token_otro_cliente)
    idor = cliente.post(
        "/evaluaciones/nueva",
        data={
            "csrf": "csrf-otro-cv",
            "postulacion_id": postulacion_id,
            "clave_idempotencia": "idor-f4",
        },
        files={"archivo": ("cv.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert idor.status_code == 403
