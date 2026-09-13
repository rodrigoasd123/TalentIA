from __future__ import annotations

from talentia.platform.jobs.worker import procesar_siguiente
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor


def _crear_candidato(cliente_api: dict[str, object]) -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    identidad = {
        "cliente_id": cliente_id,
        "documento": "DNI-EVAL-001",
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
            "documento": "DNI-EVAL-001",
            "preflight_id": preflight.json()["preflight_id"],
        },
    )
    assert alta.status_code == 201, alta.text
    return str(alta.json()["id"])


def _preparar_evaluacion(cliente_api: dict[str, object]) -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    candidato_id = _crear_candidato(cliente_api)
    perfil = cliente.post(
        "/api/v1/job-profiles",
        headers=cabeceras,
        json={"cliente_id": cliente_id, "codigo": "DEV-EVAL", "titulo": "Backend"},
    )
    assert perfil.status_code == 201, perfil.text
    version = cliente.post(
        f"/api/v1/job-profiles/{perfil.json()['id']}/versions",
        headers=cabeceras,
        json={
            "requisitos": [{"codigo": "PY", "descripcion": "Python", "peso": "1.0"}],
            "publicado": True,
        },
    )
    assert version.status_code == 201, version.text
    documento = cliente.post(
        f"/api/v1/candidates/{candidato_id}/resumes",
        headers=cabeceras,
        files={"archivo": ("cv.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
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
            "clave_idempotencia": "eval-e2e-001",
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
