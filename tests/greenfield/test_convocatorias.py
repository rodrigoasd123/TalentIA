from __future__ import annotations

import os
import re
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from talentia.modules.recruitment.domain.modelos import (
    Convocatoria,
    EstadoPostulacion,
    TransicionPostulacionInvalidaError,
    validar_transicion_postulacion,
)
from talentia.platform.cliente_llm import ClienteLLM
from talentia.shared.application.errores import ConflictoError
from talentia.shared.domain.modelos import nuevo_id
from talentia.shared.infrastructure.base_datos import crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    EventoAuditoriaModelo,
    PostulacionModelo,
)
from talentia.shared.infrastructure.repositorio_sqlalchemy import RepositorioSqlalchemy


def _crear_candidato(cliente_api: dict[str, object], indice: int) -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    cliente_id = cliente_api["cliente_id"]
    correo = f"candidato-{indice}@sintetico.test"
    documento = f"DNI-{indice:08d}"
    identidad = {
        "cliente_id": cliente_id,
        "documento": documento,
        "correo": correo,
        "nombre_completo": f"Candidato Sintetico {indice}",
    }
    preflight = cliente.post(
        "/api/v1/candidates/identity-checks", json=identidad, headers=cabeceras
    )
    assert preflight.status_code == 200
    respuesta = cliente.post(
        "/api/v1/candidates",
        headers=cabeceras,
        json={
            "cliente_id": cliente_id,
            "nombres": "Candidato",
            "apellidos": f"Sintetico {indice}",
            "tipo_documento": "DNI",
            "documento": documento,
            "correo": correo,
            "preflight_id": preflight.json()["preflight_id"],
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return str(respuesta.json()["id"])


def _crear_version_publicada(cliente_api: dict[str, object]) -> str:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    perfil = cliente.post(
        "/api/v1/job-profiles",
        headers=cabeceras,
        json={
            "cliente_id": cliente_api["cliente_id"],
            "codigo": "FULLSTACK-SPEC037",
            "titulo": "Full Stack Senior",
        },
    )
    assert perfil.status_code == 201, perfil.text
    version = cliente.post(
        f"/api/v1/job-profiles/{perfil.json()['id']}/versions",
        headers=cabeceras,
        json={
            "publicado": True,
            "requisitos": [
                {
                    "codigo": "PYTHON",
                    "descripcion": "Python senior",
                    "obligatorio": True,
                    "peso": "1",
                }
            ],
        },
    )
    assert version.status_code == 201, version.text
    return str(version.json()["id"])


def _crear_convocatoria(
    cliente_api: dict[str, object],
    version_id: str,
    *,
    codigo: str = "CONV-SPEC037",
    vacantes: int = 1,
) -> dict[str, object]:
    respuesta = cliente_api["cliente"].post(
        "/api/v1/campaigns",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "version_perfil_id": version_id,
            "codigo": codigo,
            "vacantes_total": vacantes,
            "estado": "abierta",
            "fecha_apertura": "2026-09-16",
            "fecha_objetivo": "2026-10-16",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _crear_postulacion(
    cliente_api: dict[str, object], candidato_id: str, version_id: str, convocatoria_id: str
) -> dict[str, object]:
    respuesta = cliente_api["cliente"].post(
        "/api/v1/applications",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "candidato_id": candidato_id,
            "version_perfil_id": version_id,
            "convocatoria_id": convocatoria_id,
            "fuente": "portal_tcs",
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _transicionar(
    cliente_api: dict[str, object],
    postulacion: dict[str, object],
    destino: str,
    motivo: str | None = None,
) -> dict[str, object]:
    if destino == "finalista" and motivo is None:
        motivo = "Seleccion humana para cubrir la convocatoria"
    respuesta = cliente_api["cliente"].post(
        f"/api/v1/applications/{postulacion['id']}/transitions",
        headers=cliente_api["cabeceras"],
        json={"destino": destino, "version": postulacion["version"], "motivo": motivo},
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_maquina_estados_exige_motivo_y_separa_aptitud_de_finalista() -> None:
    validar_transicion_postulacion(EstadoPostulacion.REVISION_HUMANA, EstadoPostulacion.APTA)
    try:
        validar_transicion_postulacion(EstadoPostulacion.APTA, EstadoPostulacion.FINALISTA)
    except TransicionPostulacionInvalidaError as error:
        assert "motivo" in str(error)
    else:
        raise AssertionError("La seleccion final sin justificacion debio rechazarse")
    validar_transicion_postulacion(
        EstadoPostulacion.APTA,
        EstadoPostulacion.FINALISTA,
        "Seleccion humana para cubrir la convocatoria",
    )
    try:
        validar_transicion_postulacion(EstadoPostulacion.REVISION_HUMANA, EstadoPostulacion.NO_APTA)
    except TransicionPostulacionInvalidaError as error:
        assert "motivo" in str(error)
    else:
        raise AssertionError("El descarte sin motivo debio rechazarse")
    assert EstadoPostulacion.APTA is not EstadoPostulacion.FINALISTA


def test_convocatoria_valida_cupos_y_fechas() -> None:
    convocatoria = Convocatoria(
        cliente_id="cliente",
        version_perfil_id="version",
        codigo="CONV-001",
        vacantes_total=2,
        fecha_apertura=date(2026, 9, 16),
        fecha_objetivo=date(2026, 10, 16),
    )
    convocatoria.validar()
    convocatoria.vacantes_total = 0
    try:
        convocatoria.validar()
    except ValueError as error:
        assert "vacante" in str(error)
    else:
        raise AssertionError("Una convocatoria sin vacantes debio rechazarse")


def test_un_perfil_admite_convocatorias_independientes(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    primera = _crear_convocatoria(cliente_api, version_id, codigo="CONV-SPEC037-A", vacantes=2)
    segunda = _crear_convocatoria(cliente_api, version_id, codigo="CONV-SPEC037-B", vacantes=3)

    assert primera["version_perfil_id"] == segunda["version_perfil_id"] == version_id
    assert primera["id"] != segunda["id"]
    assert primera["vacantes_total"] == 2
    assert segunda["vacantes_total"] == 3
    pagina_1 = (
        cliente_api["cliente"]
        .get(
            "/api/v1/campaigns",
            headers=cliente_api["cabeceras"],
            params={"cliente_id": cliente_api["cliente_id"], "limit": 1},
        )
        .json()
    )
    pagina_2 = (
        cliente_api["cliente"]
        .get(
            "/api/v1/campaigns",
            headers=cliente_api["cabeceras"],
            params={
                "cliente_id": cliente_api["cliente_id"],
                "limit": 1,
                "cursor": pagina_1[0]["id"],
            },
        )
        .json()
    )
    assert len(pagina_1) == len(pagina_2) == 1
    assert pagina_1[0]["id"] != pagina_2[0]["id"]


def test_flujo_humano_cierra_y_convierte_aptas_en_backup(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id)
    primera = _crear_postulacion(
        cliente_api, _crear_candidato(cliente_api, 101), version_id, str(convocatoria["id"])
    )
    segunda = _crear_postulacion(
        cliente_api, _crear_candidato(cliente_api, 102), version_id, str(convocatoria["id"])
    )
    for destino in (
        "contactada",
        "cv_recibido",
        "en_evaluacion",
        "revision_humana",
        "apta",
        "finalista",
        "entrevista",
        "oferta",
        "contratada",
    ):
        primera = _transicionar(cliente_api, primera, destino)
    for destino in (
        "contactada",
        "cv_recibido",
        "en_evaluacion",
        "revision_humana",
        "apta",
    ):
        segunda = _transicionar(cliente_api, segunda, destino)

    previa = cliente_api["cliente"].get(
        f"/api/v1/campaigns/{convocatoria['id']}/close-preview",
        headers=cliente_api["cabeceras"],
    )
    assert previa.status_code == 200, previa.text
    assert previa.json()["puede_cerrar"] is True
    assert previa.json()["aptas_para_backup"] == 1
    cierre = cliente_api["cliente"].post(
        f"/api/v1/campaigns/{convocatoria['id']}/close",
        headers=cliente_api["cabeceras"],
        json={"version": convocatoria["version"], "motivo": "Vacante cubierta"},
    )
    assert cierre.status_code == 200, cierre.text
    assert cierre.json()["estado"] == "cerrada"
    assert cierre.json()["backups_generados"] == 1
    candidato_tardio = _crear_candidato(cliente_api, 103)
    alta_tardia = cliente_api["cliente"].post(
        "/api/v1/applications",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "candidato_id": candidato_tardio,
            "version_perfil_id": version_id,
            "convocatoria_id": convocatoria["id"],
            "fuente": "portal_tcs",
        },
    )
    assert alta_tardia.status_code == 409


def test_transicion_rechaza_version_obsoleta(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id)
    postulacion = _crear_postulacion(
        cliente_api, _crear_candidato(cliente_api, 201), version_id, str(convocatoria["id"])
    )
    original = dict(postulacion)
    _transicionar(cliente_api, postulacion, "contactada")
    conflicto = cliente_api["cliente"].post(
        f"/api/v1/applications/{postulacion['id']}/transitions",
        headers=cliente_api["cabeceras"],
        json={"destino": "contactada", "version": original["version"], "motivo": None},
    )
    assert conflicto.status_code == 409
    assert "version actual" in conflicto.json()["error"]["mensaje"]


def test_identidad_exacta_muestra_antecedente_de_la_misma_cuenta(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id)
    candidato_id = _crear_candidato(cliente_api, 301)
    _crear_postulacion(cliente_api, candidato_id, version_id, str(convocatoria["id"]))

    respuesta = cliente_api["cliente"].post(
        "/api/v1/candidates/identity-checks",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "documento": "DNI-00000301",
            "correo": "candidato-301@sintetico.test",
            "nombre_completo": "Candidato Sintetico 301",
        },
    )

    assert respuesta.status_code == 200
    resultado = respuesta.json()
    assert resultado["resultado"] == "exacta"
    assert resultado["evidencia"][0]["antecedentes"][0]["proceso"] == "CONV-SPEC037"
    assert resultado["evidencia"][0]["antecedentes"][0]["fecha"]
    assert resultado["evidencia"][0]["antecedentes"][0]["reclutador"] == "Administracion del piloto"


def test_identidad_y_url_no_filtran_otra_cuenta(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    otra_cuenta = nuevo_id()
    token_otro = cliente_api["token_para"](
        nuevo_id(),
        "reclutador-bbva@pruebas.test",
        ["reclutador"],
        [otra_cuenta],
        "csrf-bbva",
    )
    cabeceras_otro = {"Authorization": f"Bearer {token_otro}"}
    identidad = {
        "cliente_id": otra_cuenta,
        "documento": "DNI-AISLADO-037",
        "correo": "persona-aislada@pruebas.test",
        "nombre_completo": "Persona Aislada",
    }
    preflight = cliente.post(
        "/api/v1/candidates/identity-checks", json=identidad, headers=cabeceras_otro
    )
    creado = cliente.post(
        "/api/v1/candidates",
        headers=cabeceras_otro,
        json={
            "cliente_id": otra_cuenta,
            "nombres": "Persona",
            "apellidos": "Aislada",
            "tipo_documento": "DNI",
            "documento": identidad["documento"],
            "correo": identidad["correo"],
            "preflight_id": preflight.json()["preflight_id"],
        },
    )
    assert creado.status_code == 201

    token_bcp = cliente_api["token_para"](
        nuevo_id(),
        "reclutador-bcp@pruebas.test",
        ["reclutador"],
        [str(cliente_api["cliente_id"])],
        "csrf-bcp",
    )
    cabeceras_bcp = {"Authorization": f"Bearer {token_bcp}"}
    busqueda = cliente.post(
        "/api/v1/candidates/identity-checks",
        headers=cabeceras_bcp,
        json={**identidad, "cliente_id": cliente_api["cliente_id"]},
    )
    directa = cliente.get(f"/api/v1/candidates/{creado.json()['id']}", headers=cabeceras_bcp)
    assert busqueda.status_code == 200
    assert busqueda.json()["resultado"] == "ninguna"
    assert busqueda.json()["evidencia"] == []
    assert directa.status_code == 404
    assert "Aislada" not in directa.text
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        evento = sesion.scalar(
            select(EventoAuditoriaModelo).where(
                EventoAuditoriaModelo.accion == "seguridad.idor_bloqueado",
                EventoAuditoriaModelo.recurso_id == creado.json()["id"],
            )
        )
    assert evento is not None
    assert evento.detalle == {"motivo": "recurso_fuera_de_alcance"}


def test_hiring_manager_asigna_alcance_y_responsabilidad_con_auditoria(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cliente_id = str(cliente_api["cliente_id"])
    manager_id = nuevo_id()
    reclutador_id = nuevo_id()
    token_manager = cliente_api["token_para"](
        manager_id,
        "manager-spec037@pruebas.test",
        ["gestor_contratacion"],
        [cliente_id],
        "csrf-manager",
    )
    token_reclutador_obsoleto = cliente_api["token_para"](
        reclutador_id,
        "reclutador-spec037@pruebas.test",
        ["reclutador"],
        [],
        "csrf-reclutador",
    )
    cabeceras_manager = {"Authorization": f"Bearer {token_manager}"}
    alcance = cliente.post(
        f"/api/v1/users/{reclutador_id}/client-assignments",
        headers=cabeceras_manager,
        json={"cliente_id": cliente_id, "asignar": True},
    )
    assert alcance.status_code == 200, alcance.text
    sesion_anterior = cliente.get(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token_reclutador_obsoleto}"},
    )
    assert sesion_anterior.status_code == 401

    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id)
    responsable = cliente.post(
        f"/api/v1/campaigns/{convocatoria['id']}/recruiters",
        headers=cabeceras_manager,
        json={"usuario_id": reclutador_id, "asignar": True},
    )
    assert responsable.status_code == 200, responsable.text
    detalle = cliente.get(
        f"/api/v1/campaigns/{convocatoria['id']}", headers=cabeceras_manager
    ).json()
    assert [item["id"] for item in detalle["responsables"]] == [reclutador_id]

    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        acciones = list(
            sesion.scalars(
                select(EventoAuditoriaModelo.accion).where(
                    EventoAuditoriaModelo.actor_id == manager_id
                )
            )
        )
    assert "acceso.cliente_asignado" in acciones
    assert "convocatoria.reclutador_asignado" in acciones

    cliente.cookies.set("talentia_session", token_manager)
    pagina_asignaciones = cliente.get("/modulo/usuarios")
    assert pagina_asignaciones.status_code == 200
    assert "Alcance de mis cuentas" in pagina_asignaciones.text
    assert "reclutador-spec037@pruebas.test" in pagina_asignaciones.text
    assert "Modificar rol" not in pagina_asignaciones.text


def test_espacio_web_expone_jerarquia_y_funciona_sin_llm(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id)
    _crear_postulacion(
        cliente_api,
        _crear_candidato(cliente_api, 350),
        version_id,
        str(convocatoria["id"]),
    )
    token = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente_api["cliente"].cookies.set("talentia_session", token)

    cuentas = cliente_api["cliente"].get("/cuentas")
    lista = cliente_api["cliente"].get(f"/cuentas/{cliente_api['cliente_id']}/convocatorias")
    detalle = cliente_api["cliente"].get(f"/convocatorias/{convocatoria['id']}")

    assert cuentas.status_code == 200
    assert "Cuenta" in cuentas.text
    assert lista.status_code == 200
    assert "Cuenta → perfil publicado → convocatoria → responsables → candidaturas" in lista.text
    assert detalle.status_code == 200
    assert "Responsables" in detalle.text
    assert "Full Stack Senior" in detalle.text
    assert "Cantidades por estado" in detalle.text
    assert "Nueva: 1" in detalle.text
    assert "Cierre bajo confirmación humana" in detalle.text


def test_cupo_finalistas_se_revalida_en_la_transicion(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id, codigo="CONV-CUPOS-037", vacantes=2)
    aptas: list[dict[str, object]] = []
    for indice in (401, 402, 403):
        postulacion = _crear_postulacion(
            cliente_api,
            _crear_candidato(cliente_api, indice),
            version_id,
            str(convocatoria["id"]),
        )
        for destino in (
            "contactada",
            "cv_recibido",
            "en_evaluacion",
            "revision_humana",
            "apta",
        ):
            postulacion = _transicionar(cliente_api, postulacion, destino)
        aptas.append(postulacion)

    _transicionar(cliente_api, aptas[0], "finalista")
    _transicionar(cliente_api, aptas[1], "finalista")
    excedente = cliente_api["cliente"].post(
        f"/api/v1/applications/{aptas[2]['id']}/transitions",
        headers=cliente_api["cabeceras"],
        json={
            "destino": "finalista",
            "version": aptas[2]["version"],
            "motivo": "Selección humana excedente",
        },
    )
    assert excedente.status_code == 409
    assert "cupo" in excedente.json()["error"]["mensaje"].lower()


def test_convocatoria_ordinaria_exige_ambas_fechas(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    respuesta = cliente_api["cliente"].post(
        "/api/v1/campaigns",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "version_perfil_id": version_id,
            "codigo": "CONV-SIN-FECHAS-037",
            "vacantes_total": 1,
            "estado": "abierta",
        },
    )
    assert respuesta.status_code == 422


def test_finalista_exige_justificacion_y_la_audita(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id, codigo="CONV-MOTIVO-037")
    postulacion = _crear_postulacion(
        cliente_api,
        _crear_candidato(cliente_api, 501),
        version_id,
        str(convocatoria["id"]),
    )
    for destino in (
        "contactada",
        "cv_recibido",
        "en_evaluacion",
        "revision_humana",
        "apta",
    ):
        postulacion = _transicionar(cliente_api, postulacion, destino)
    sin_motivo = cliente_api["cliente"].post(
        f"/api/v1/applications/{postulacion['id']}/transitions",
        headers=cliente_api["cabeceras"],
        json={"destino": "finalista", "version": postulacion["version"], "motivo": None},
    )
    assert sin_motivo.status_code == 422
    justificacion = "Seleccionada por decisión humana para entrevista"
    finalista = _transicionar(cliente_api, postulacion, "finalista", justificacion)
    assert finalista["estado"] == "finalista"

    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        evento = sesion.scalar(
            select(EventoAuditoriaModelo)
            .where(
                EventoAuditoriaModelo.accion == "postulacion.estado_cambiado",
                EventoAuditoriaModelo.recurso_id == postulacion["id"],
            )
            .order_by(EventoAuditoriaModelo.ocurrido_en.desc())
        )
    assert evento is not None
    assert evento.detalle["estado_anterior"] == "apta"
    assert evento.detalle["estado_nuevo"] == "finalista"
    assert evento.detalle["motivo"] == justificacion


def test_compare_and_swap_rechaza_dos_sesiones_con_la_misma_version(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id, codigo="CONV-CAS-037")
    postulacion = _crear_postulacion(
        cliente_api,
        _crear_candidato(cliente_api, 502),
        version_id,
        str(convocatoria["id"]),
    )
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as primera, Session(motor) as segunda:
        assert primera.get(PostulacionModelo, postulacion["id"]) is not None
        assert segunda.get(PostulacionModelo, postulacion["id"]) is not None
        repo_primero = RepositorioSqlalchemy(primera)
        repo_segundo = RepositorioSqlalchemy(segunda)
        actualizado = repo_primero.transicionar_postulacion(
            str(postulacion["id"]), "contactada", None, int(postulacion["version"])
        )
        primera.commit()
        assert actualizado["version"] == int(postulacion["version"]) + 1
        with pytest.raises(ConflictoError, match="version actual"):
            repo_segundo.transicionar_postulacion(
                str(postulacion["id"]), "contactada", None, int(postulacion["version"])
            )
        segunda.rollback()


def test_conflicto_web_conserva_destino_y_comentario(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id, codigo="CONV-UI-409-037")
    postulacion = _crear_postulacion(
        cliente_api,
        _crear_candidato(cliente_api, 503),
        version_id,
        str(convocatoria["id"]),
    )
    version_obsoleta = int(postulacion["version"])
    _transicionar(cliente_api, postulacion, "contactada")
    token = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente_api["cliente"].cookies.set("talentia_session", token)
    detalle = cliente_api["cliente"].get(f"/convocatorias/{convocatoria['id']}")
    coincidencia_csrf = re.search(r'name="csrf" value="([^"]+)"', detalle.text)
    assert coincidencia_csrf is not None
    comentario = "Comentario que no debe perderse después del conflicto"
    respuesta = cliente_api["cliente"].post(
        f"/convocatorias/{convocatoria['id']}/candidaturas/{postulacion['id']}/transicion",
        data={
            "csrf": coincidencia_csrf.group(1),
            "destino": "contactada",
            "version": version_obsoleta,
            "motivo": comentario,
        },
    )
    assert respuesta.status_code == 409
    assert "Cambio no aplicado" in respuesta.text
    assert "Contactada" in respuesta.text
    assert comentario in respuesta.text


def test_flujo_completo_no_invoca_proveedores_llm(cliente_api, monkeypatch) -> None:
    def llamada_prohibida(*args: object, **kwargs: object) -> object:
        raise AssertionError("La SPEC-037 no debe invocar un proveedor LLM")

    monkeypatch.setattr(ClienteLLM, "evaluar", llamada_prohibida)
    assert "OPENAI_API_KEY" not in os.environ
    assert "GEMINI_API_KEY" not in os.environ

    reclutador_id = nuevo_id()
    cliente_api["token_para"](
        reclutador_id,
        "reclutador-sin-llm@pruebas.test",
        ["reclutador"],
        [str(cliente_api["cliente_id"])],
        "csrf-sin-llm",
    )
    version_id = _crear_version_publicada(cliente_api)
    convocatoria = _crear_convocatoria(cliente_api, version_id, codigo="CONV-SIN-LLM-037")
    asignacion = cliente_api["cliente"].post(
        f"/api/v1/campaigns/{convocatoria['id']}/recruiters",
        headers=cliente_api["cabeceras"],
        json={"usuario_id": reclutador_id, "asignar": True},
    )
    assert asignacion.status_code == 200
    postulacion = _crear_postulacion(
        cliente_api,
        _crear_candidato(cliente_api, 504),
        version_id,
        str(convocatoria["id"]),
    )
    for destino in (
        "contactada",
        "cv_recibido",
        "en_evaluacion",
        "revision_humana",
        "apta",
        "finalista",
        "entrevista",
        "oferta",
        "contratada",
    ):
        postulacion = _transicionar(cliente_api, postulacion, destino)
    cierre = cliente_api["cliente"].post(
        f"/api/v1/campaigns/{convocatoria['id']}/close",
        headers=cliente_api["cabeceras"],
        json={"version": convocatoria["version"], "motivo": "Cupo cubierto sin IA"},
    )
    assert cierre.status_code == 200
    assert cierre.json()["estado"] == "cerrada"


def test_candidato_solo_puede_estar_en_una_convocatoria_activa(cliente_api) -> None:
    version_id = _crear_version_publicada(cliente_api)
    convocatoria_1 = _crear_convocatoria(cliente_api, version_id, codigo="CONV-UNICA-001")
    convocatoria_2 = _crear_convocatoria(cliente_api, version_id, codigo="CONV-UNICA-002")
    candidato_id = _crear_candidato(cliente_api, 901)

    # 1. Postular a primera convocatoria debe tener éxito
    primera = _crear_postulacion(cliente_api, candidato_id, version_id, str(convocatoria_1["id"]))
    assert primera["id"]

    # 2. Reintento idempotente con misma convocatoria debe funcionar
    reintento = cliente_api["cliente"].post(
        "/api/v1/applications",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "candidato_id": candidato_id,
            "version_perfil_id": version_id,
            "convocatoria_id": str(convocatoria_1["id"]),
            "fuente": "portal_tcs",
        },
    )
    assert reintento.status_code == 201
    assert reintento.json()["id"] == primera["id"]

    # 3. Intentar postular a una segunda convocatoria activa debe ser rechazado con 409
    segunda_intento = cliente_api["cliente"].post(
        "/api/v1/applications",
        headers=cliente_api["cabeceras"],
        json={
            "cliente_id": cliente_api["cliente_id"],
            "candidato_id": candidato_id,
            "version_perfil_id": version_id,
            "convocatoria_id": str(convocatoria_2["id"]),
            "fuente": "portal_tcs",
        },
    )
    assert segunda_intento.status_code == 409
    assert "ya se encuentra en un proceso activo" in segunda_intento.text
    assert "CONV-UNICA-001" in segunda_intento.text

    # 4. Si la primera postulación es descartada (rechazada), el candidato queda libre
    post_contactada = _transicionar(cliente_api, primera, "contactada")
    post_rechazada = _transicionar(
        cliente_api, post_contactada, "rechazada", motivo="No cumple expectativas salariales"
    )
    assert post_rechazada["estado"] == "rechazada"

    # 5. Ahora sí debe permitirse postular a la segunda convocatoria
    segunda_valida = _crear_postulacion(cliente_api, candidato_id, version_id, str(convocatoria_2["id"]))
    assert segunda_valida["id"]
    assert segunda_valida["convocatoria_id"] == str(convocatoria_2["id"])
