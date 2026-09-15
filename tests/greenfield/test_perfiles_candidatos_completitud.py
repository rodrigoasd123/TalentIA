from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import text

from talentia.modules.candidates.domain.modelos import Candidato
from talentia.shared.application.servicio_principal import calcular_completitud_candidato


def _docx(*lineas: str) -> bytes:
    parrafos = "".join(f"<w:p><w:r><w:t>{linea}</w:t></w:r></w:p>" for linea in lineas)
    documento = (
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
        archivo.writestr("word/document.xml", documento)
    return contenido.getvalue()


def _cv(nombre: str, documento: str, correo: str) -> bytes:
    return _docx(
        nombre,
        f"DNI: {documento} | Celular: +51 99{documento[-6:]}0",
        f"Correo: {correo} | Ubicacion: Miraflores, Lima",
        "Convocatoria: DEV-BACK-01 | Expectativa salarial: S/ 8,200.00",
        "Especialidad: Python, FastAPI, Docker, AWS",
        "Disponibilidad: Inmediata",
        "1. Resumen Ejecutivo: Desarrollador Backend Senior",
    )


def _sesion_web(cliente_api: dict[str, object]) -> tuple[object, str]:
    cliente = cliente_api["cliente"]
    token = str(cliente_api["cabeceras"]["Authorization"]).removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token)
    csrf = str(cliente.app.state.firmador.leer(token)["csrf"])
    return cliente, csrf


def test_calcular_completitud_candidato_logica() -> None:
    # 1. Candidato nuevo/vacío: Incompleto
    candidato_vacio = Candidato(nombres="Juan", apellidos="Perez")
    res1 = calcular_completitud_candidato(candidato_vacio)
    assert res1["completo"] is False
    assert res1["porcentaje"] == 0
    assert len(res1["campos_faltantes"]) == 5

    # 2. Candidato con solo algunos campos: Incompleto parcial
    candidato_medio = Candidato(
        nombres="Juan",
        apellidos="Perez",
        reclutador="Diana Torres",
        expectativa_salarial=Decimal("8000.00"),
    )
    res2 = calcular_completitud_candidato(candidato_medio)
    assert res2["completo"] is False
    assert res2["porcentaje"] == 40
    assert "Fecha de nacimiento / Reniec" in res2["campos_faltantes"]
    assert "Validación BGC / Títulos" in res2["campos_faltantes"]

    # 3. Candidato con todos los requisitos de RRHH: Completo (100%)
    candidato_completo = Candidato(
        nombres="Juan",
        apellidos="Perez",
        reclutador="Diana Torres",
        fecha_nacimiento=date(1992, 5, 14),
        ctc_rol=Decimal("8500.00"),
        expectativa_salarial=Decimal("8000.00"),
        etiquetas=["bgc-validado"],
    )
    res3 = calcular_completitud_candidato(candidato_completo)
    assert res3["completo"] is True
    assert res3["porcentaje"] == 100
    assert len(res3["campos_faltantes"]) == 0


def test_perfil_detalle_y_carga_cv_contextual(cliente_api) -> None:
    cliente, csrf = _sesion_web(cliente_api)

    # 1. Crear un perfil de prueba
    resp_perfil = cliente.post(
        "/perfiles/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "DEV-TEST-99",
            "titulo": "Desarrollador Backend de Prueba",
        },
    )
    assert resp_perfil.status_code in {200, 303}

    # Obtener el perfil creado
    with cliente.app.state.servicio._fabrica() as unidad:
        perfil_row = unidad.datos.sesion.execute(
            text("SELECT id FROM job_profiles WHERE codigo = 'DEV-TEST-99'")
        ).first()
        perfil_id = perfil_row[0] if perfil_row else None

    assert perfil_id is not None

    # Publicar versión 1 del perfil con CTC 8,500
    resp_version = cliente.post(
        f"/perfiles/{perfil_id}/versiones/nueva",
        data={
            "csrf": csrf,
            "requisitos_texto": (
                "REQ-1 | Python y FastAPI | obligatorio | 3\nREQ-2 | Docker y AWS | opcional | 2"
            ),
            "ctc": "8500.00",
            "publicado": "si",
        },
    )
    assert resp_version.status_code in {200, 303}

    # 2. Cargar CV directamente en la vacante
    archivos = [
        (
            "archivos",
            (
                "01_cv_backend.docx",
                _cv("Gonzalo Javier Benavides Rivas", "72109845", "gonzalo.b@example.test"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ),
    ]
    resp_carga = cliente.post(
        f"/perfiles/{perfil_id}/importar-cvs",
        data={"csrf": csrf, "fuente": "LinkedIn", "reclutador": "Diana RRHH"},
        files=archivos,
    )
    assert resp_carga.status_code == 200
    assert "Gonzalo Javier Benavides Rivas" in resp_carga.text
    assert "DEV-TEST-99" in resp_carga.text
    assert "INCOMPLETO" in resp_carga.text

    # 3. Consultar vista individual del perfil
    resp_detalle = cliente.get(f"/perfiles/{perfil_id}")
    assert resp_detalle.status_code == 200
    assert "Gonzalo Javier Benavides Rivas" in resp_detalle.text
    assert "72109845" in resp_detalle.text
    assert "S/ 8,200.00" in resp_detalle.text

    # Obtener el id del candidato creado
    with cliente.app.state.servicio._fabrica() as unidad:
        cand_row = unidad.datos.sesion.execute(
            text("SELECT id, version FROM candidates WHERE documento_normalizado = '72109845'")
        ).first()
        cand_id, cand_version = cand_row[0], cand_row[1]

    # 4. Completar validación de RRHH
    resp_completar = cliente.post(
        f"/perfiles/{perfil_id}/candidatos/{cand_id}/completar-rrhh",
        data={
            "csrf": csrf,
            "version": str(cand_version),
            "reclutador": "Diana Torres RRHH",
            "fecha_nacimiento": "1994-08-20",
            "ctc_rol": "8500.00",
            "expectativa_salarial": "8200.00",
            "disponibilidad": "Inmediata",
            "bgc_validado": "on",
            "titulo_verificado": "on",
        },
    )
    assert resp_completar.status_code in {200, 303}

    # 5. Verificar que ahora aparezca COMPLETO (100%)
    resp_detalle_post = cliente.get(f"/perfiles/{perfil_id}")
    assert resp_detalle_post.status_code == 200
    assert "COMPLETO (100%)" in resp_detalle_post.text
