from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from talentia.platform.jobs.worker import procesar_siguiente
from talentia.shared.application.errores import ConflictoError
from talentia.shared.domain.modelos import UsuarioActual
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    CorreccionCampoModelo,
    EventoAuditoriaModelo,
    TrabajoAgenteModelo,
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


def _crear_candidato(cliente_api: dict[str, object], sufijo: str = "001") -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    identidad = {
        "cliente_id": cliente_id,
        "documento": f"DNI-EVAL-{sufijo}",
        "nombre_completo": "Eva Evaluacion",
    }
    preflight = cliente.post(
        "/api/v1/candidates/identity-checks", json=identidad, headers=cabeceras
    )
    alta = cliente.post(
        "/api/v1/candidates",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "nombres": "Eva",
            "apellidos": "Evaluacion",
            "documento": f"DNI-EVAL-{sufijo}",
            "preflight_id": preflight.json()["preflight_id"],
        },
    )
    assert alta.status_code == 201, alta.text
    return str(alta.json()["id"])


def _preparar_evaluacion(
    cliente_api: dict[str, object],
    *,
    sufijo: str = "001",
    archivo: tuple[str, bytes, str] | None = None,
) -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    candidato_id = _crear_candidato(cliente_api, sufijo)
    perfil = cliente.post(
        "/api/v1/job-profiles",
        headers=cabeceras,
        json={"cliente_id": cliente_id, "codigo": f"DEV-EVAL-{sufijo}", "titulo": "Backend"},
    )
    assert perfil.status_code == 201, perfil.text
    version = cliente.post(
        f"/api/v1/job-profiles/{perfil.json()['id']}/versions",
        headers=cabeceras,
        json={
            "requisitos": [
                {"codigo": "PY", "descripcion": "Python", "peso": "1.0"},
                {"codigo": "AWS", "descripcion": "AWS", "peso": "1.0"},
            ],
            "publicado": True,
        },
    )
    assert version.status_code == 201, version.text
    documento = cliente.post(
        f"/api/v1/candidates/{candidato_id}/resumes",
        headers=cabeceras,
        files={"archivo": archivo or ("cv.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert documento.status_code == 201, documento.text
    postulacion = cliente.post(
        "/api/v1/applications",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "candidato_id": candidato_id,
            "version_perfil_id": version.json()["id"],
            "fuente": "prueba",
        },
    )
    assert postulacion.status_code == 201, postulacion.text
    trabajo = cliente.post(
        f"/api/v1/applications/{postulacion.json()['id']}/evaluation-jobs",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "documento_id": documento.json()["id"],
            "version_perfil_id": version.json()["id"],
            "clave_idempotencia": f"eval-e2e-{sufijo}",
        },
    )
    assert trabajo.status_code == 202, trabajo.text
    return str(trabajo.json()["id"])


def test_worker_persiste_evaluacion_y_revision_resoluble(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(cliente_api)
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))

    assert procesar_siguiente(fabrica) == trabajo_id

    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    trabajo = cliente.get(f"/api/v1/jobs/{trabajo_id}", headers=cabeceras)
    assert trabajo.status_code == 200
    assert trabajo.json()["estado"] == "completado"
    assert trabajo.json()["resultado"]["evaluacion_id"] == trabajo_id

    evaluacion = cliente.get(f"/api/v1/evaluations/{trabajo_id}", headers=cabeceras)
    assert evaluacion.status_code == 200, evaluacion.text
    assert evaluacion.json()["requiere_revision"] is True
    assert evaluacion.json()["puntaje_documental"] is None
    assert evaluacion.json()["revisiones"][0]["estado"] == "pendiente"

    revision = cliente.post(
        f"/api/v1/evaluations/{trabajo_id}/reviews",
        headers=cabeceras,
        json={
            "decision": "corregida",
            "comentario": "Se valido manualmente la evidencia con la persona candidata.",
            "correcciones": [
                {
                    "campo": "nivel_ingles",
                    "valor_anterior": None,
                    "valor_nuevo": "B2 verificado",
                }
            ],
        },
    )
    assert revision.status_code == 200, revision.text
    assert revision.json()["estado"] == "corregida"
    assert revision.json()["correcciones"] == 1

    repetida = cliente.post(
        f"/api/v1/evaluations/{trabajo_id}/reviews",
        headers=cabeceras,
        json={"decision": "aceptada", "comentario": "Intento repetido"},
    )
    assert repetida.status_code == 409


def test_worker_no_duplica_evaluacion_al_reconsultar(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(cliente_api)
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    assert procesar_siguiente(fabrica) == trabajo_id
    assert procesar_siguiente(fabrica) is None

    evaluacion = cliente_api["cliente"].get(
        f"/api/v1/evaluations/{trabajo_id}", headers=cliente_api["cabeceras"]
    )
    assert len(evaluacion.json()["revisiones"]) == 1


def test_web_muestra_evidencia_y_registra_ingles_verificado(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(
        cliente_api,
        sufijo="WEB",
        archivo=(
            "cv.docx",
            _docx(
                "Habilidades: Python, SQL",
                "Experiencia: Cinco anos con Python en backend",
                "Educacion: Ingenieria de Sistemas",
                "Empresa reciente: TCS",
            ),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    )
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    assert procesar_siguiente(fabrica) == trabajo_id
    cliente = cliente_api["cliente"]
    acceso = cliente.post(
        "/login",
        data={"correo": "admin@pruebas.test", "contrasena": "Contrasena-Pruebas-2026!"},
    )
    assert acceso.status_code == 200

    listado = cliente.get("/modulo/evaluaciones")
    detalle = cliente.get(f"/evaluaciones/{trabajo_id}")
    assert listado.status_code == 200
    assert f"/evaluaciones/{trabajo_id}" in listado.text
    assert detalle.status_code == 200
    assert "Requisitos y evidencia" in detalle.text
    assert "Python" in detalle.text
    assert "posiciones" in detalle.text
    assert "Sin evidencia suficiente" in detalle.text
    assert "Guardar decision auditada" in detalle.text

    token = cliente.cookies.get("talentia_session")
    assert token is not None
    csrf = cliente.app.state.firmador.leer(token)["csrf"]
    sin_justificacion = cliente.post(
        f"/evaluaciones/{trabajo_id}/revision",
        data={"csrf": csrf, "decision": "aceptada", "comentario": "x"},
    )
    assert sin_justificacion.status_code == 422
    assert "justificacion es obligatoria" in sin_justificacion.text
    invalida = cliente.post(
        f"/evaluaciones/{trabajo_id}/revision",
        data={
            "csrf": csrf,
            "decision": "corregida",
            "comentario": "Se verifico el nivel durante la entrevista.",
        },
    )
    assert invalida.status_code == 422
    assert "requiere al menos una correccion" in invalida.text
    assert "Se verifico el nivel" in invalida.text

    resuelta = cliente.post(
        f"/evaluaciones/{trabajo_id}/revision",
        data={
            "csrf": csrf,
            "decision": "corregida",
            "comentario": "Se verifico el nivel durante la entrevista.",
            "campo_correccion": "nivel_ingles",
            "valor_anterior": "Sin evidencia",
            "valor_nuevo": "B2 verificado",
        },
        follow_redirects=False,
    )
    assert resuelta.status_code == 303
    final = cliente.get(f"/evaluaciones/{trabajo_id}")
    assert "Revision completada" in final.text
    assert "nivel_ingles" in final.text
    assert "B2 verificado" in final.text
    assert "Guardar decision auditada" not in final.text

    with fabrica.sesion() as sesion:
        assert sesion.scalar(select(func.count()).select_from(CorreccionCampoModelo)) == 1
        eventos = sesion.scalar(
            select(func.count())
            .select_from(EventoAuditoriaModelo)
            .where(EventoAuditoriaModelo.accion == "evaluacion.revision_resuelta")
        )
        assert eventos == 1


def test_web_revision_exige_csrf_rbac_y_alcance_de_cliente(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(cliente_api, sufijo="SEC")
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    assert procesar_siguiente(fabrica) == trabajo_id
    cliente = cliente_api["cliente"]

    token_reclutador = cliente_api["token_para"](
        "reclutador-web",
        "reclutador@pruebas.test",
        ["reclutador"],
        [cliente_api["cliente_id"]],
        "csrf-reclutador",
    )
    cliente.cookies.set("talentia_session", token_reclutador)
    lectura = cliente.get(f"/evaluaciones/{trabajo_id}")
    assert lectura.status_code == 200
    assert "Guardar decision auditada" not in lectura.text
    sin_permiso = cliente.post(
        f"/evaluaciones/{trabajo_id}/revision",
        data={
            "csrf": "csrf-reclutador",
            "decision": "aceptada",
            "comentario": "Revision sin permisos",
        },
    )
    assert sin_permiso.status_code == 403

    token_otro_cliente = cliente_api["token_para"](
        "revisor-otro-cliente",
        "revisor@otro.test",
        ["entrevistador"],
        ["cliente-fuera-de-alcance"],
        "csrf-otro",
    )
    cliente.cookies.set("talentia_session", token_otro_cliente)
    assert cliente.get(f"/evaluaciones/{trabajo_id}").status_code == 403

    token_admin = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token_admin)
    csrf_admin = cliente.app.state.firmador.leer(token_admin)["csrf"]
    sin_csrf = cliente.post(
        f"/evaluaciones/{trabajo_id}/revision",
        data={
            "csrf": "incorrecto",
            "decision": "aceptada",
            "comentario": "Revision con CSRF incorrecto",
        },
    )
    assert sin_csrf.status_code == 401
    correcta = cliente.post(
        f"/evaluaciones/{trabajo_id}/revision",
        data={
            "csrf": csrf_admin,
            "decision": "aceptada",
            "comentario": "Revision valida del administrador",
        },
    )
    assert correcta.status_code == 200


def test_web_trabajo_muestra_pendiente_revision_y_error(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(cliente_api, sufijo="JOB")
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    cliente = cliente_api["cliente"]
    token_admin = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token_admin)

    pendiente = cliente.get(f"/trabajos/{trabajo_id}")
    assert pendiente.status_code == 200
    assert "Pendiente" in pendiente.text
    assert f'hx-get="/fragmentos/trabajos/{trabajo_id}"' in pendiente.text
    assert "Actualizando progreso" in pendiente.text

    with fabrica.sesion() as sesion:
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(TrabajoAgenteModelo.id == trabajo_id)
            .values(estado="reservado")
        )
    reservado = cliente.get(f"/fragmentos/trabajos/{trabajo_id}")
    assert "Procesando" in reservado.text
    with fabrica.sesion() as sesion:
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(TrabajoAgenteModelo.id == trabajo_id)
            .values(estado="pendiente", disponible_en=datetime.now(UTC))
        )
    assert procesar_siguiente(fabrica) == trabajo_id
    completado = cliente.get(f"/fragmentos/trabajos/{trabajo_id}")
    assert completado.status_code == 200
    assert "Revision humana requerida" in completado.text
    assert f"/evaluaciones/{trabajo_id}" in completado.text

    with fabrica.sesion() as sesion:
        sesion.execute(
            update(TrabajoAgenteModelo)
            .where(TrabajoAgenteModelo.id == trabajo_id)
            .values(estado="fallido", resultado=None, error="WorkflowTimeoutError")
        )
    fallido = cliente.get(f"/fragmentos/trabajos/{trabajo_id}")
    assert fallido.status_code == 200
    assert "Error" in fallido.text
    assert "WorkflowTimeoutError" in fallido.text


def test_dos_revisores_concurrentes_producen_una_decision_y_un_evento(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(cliente_api, sufijo="RACE")
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    assert procesar_siguiente(fabrica) == trabajo_id
    token = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    datos_usuario = cliente_api["cliente"].app.state.firmador.leer(token)
    usuario = UsuarioActual(
        id=str(datos_usuario["sub"]),
        correo=str(datos_usuario["correo"]),
        roles=frozenset(str(item) for item in datos_usuario["roles"]),
        clientes=frozenset(str(item) for item in datos_usuario["clientes"]),
    )
    barrera = threading.Barrier(2)

    def resolver(indice: int) -> str:
        barrera.wait()
        try:
            cliente_api["cliente"].app.state.servicio.registrar_revision(
                usuario,
                trabajo_id,
                {
                    "decision": "aceptada",
                    "comentario": f"Decision concurrente numero {indice}",
                    "correcciones": [],
                },
                f"corr-race-{indice}",
            )
        except ConflictoError:
            return "conflicto"
        return "aceptada"

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = list(ejecutor.map(resolver, (1, 2)))
    assert sorted(resultados) == ["aceptada", "conflicto"]

    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        eventos = sesion.scalar(
            select(func.count())
            .select_from(EventoAuditoriaModelo)
            .where(EventoAuditoriaModelo.accion == "evaluacion.revision_resuelta")
        )
        assert eventos == 1


def test_revision_puede_rechazar_sugerencia_con_justificacion(cliente_api) -> None:
    trabajo_id = _preparar_evaluacion(cliente_api, sufijo="REJECT")
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    assert procesar_siguiente(fabrica) == trabajo_id
    respuesta = cliente_api["cliente"].post(
        f"/api/v1/evaluations/{trabajo_id}/reviews",
        headers=cliente_api["cabeceras"],
        json={
            "decision": "rechazada",
            "comentario": "La evidencia fue revisada y la sugerencia no corresponde.",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "rechazada"
