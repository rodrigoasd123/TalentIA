from __future__ import annotations

import json
from decimal import Decimal
from urllib.error import HTTPError

import pytest
from sqlalchemy.orm import Session

from talentia.ai.workflows.nodos_evaluacion import ContextoNodosEvaluacion
from talentia.modules.recruitment.domain.modelos import RequisitoPerfil
from talentia.platform.cliente_llm import ClienteLLM, RespuestaLLM
from talentia.platform.observabilidad.mlflow_tracker import TrazaWorkflowMLflow
from talentia.shared.infrastructure.base_datos import crear_motor
from talentia.shared.infrastructure.modelos_orm import ConfiguracionIAModelo


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


def test_panel_es_exclusivo_de_administracion_y_badge_global(cliente_api) -> None:
    cliente, _ = _login_web(cliente_api)
    pagina = cliente.get("/admin/configuracion-ia")
    assert pagina.status_code == 200
    assert "Panel de configuracion y estado de IA" in pagina.text
    assert "Abrir Dashboard de MLflow" in pagina.text
    assert 'href="/admin/configuracion-ia"' in cliente.get("/").text

    token = cliente_api["token_para"](
        "reclutador-ia",
        "reclutador-ia@pruebas.test",
        ["reclutador"],
        [cliente_api["cliente_id"]],
        "csrf-reclutador-ia",
    )
    cliente.cookies.set("talentia_session", token)
    assert cliente.get("/admin/configuracion-ia").status_code == 403
    inicio = cliente.get("/")
    assert "IA: Modo Local / Deterministico" in inicio.text
    assert 'class="estado estado-ia' in inicio.text


def test_guardado_caliente_cifra_clave_y_controla_concurrencia(cliente_api) -> None:
    cliente, csrf = _login_web(cliente_api)
    clave = "clave-openai-sintetica"
    respuesta = cliente.post(
        "/admin/configuracion-ia",
        data={
            "csrf": csrf,
            "proveedor": "openai",
            "modelo": "gpt-4o-mini",
            "temperatura": "0.2",
            "tokens_maximos": "512",
            "api_key": clave,
            "version": "1",
        },
        follow_redirects=False,
    )
    assert respuesta.status_code == 303
    publica = cliente.app.state.gestor_configuracion_ia.obtener_publica()
    interna = cliente.app.state.gestor_configuracion_ia.obtener_interna()
    assert publica.proveedor == "openai"
    assert publica.modelo == "gpt-4o-mini"
    assert publica.clave_configurada
    assert not hasattr(publica, "api_key")
    assert interna.api_key == clave

    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        persistida = sesion.get(ConfiguracionIAModelo, "global")
        assert persistida is not None
        assert persistida.clave_openai_cifrada != clave
        assert clave not in str(persistida.clave_openai_cifrada)

    conflicto = cliente.post(
        "/admin/configuracion-ia",
        data={
            "csrf": csrf,
            "proveedor": "local",
            "modelo": "deterministico-local",
            "temperatura": "0",
            "tokens_maximos": "256",
            "api_key": "",
            "version": "1",
        },
    )
    assert conflicto.status_code == 409
    assert clave not in conflicto.text


def test_diagnostico_htmx_exitoso_y_error_sanitizado(cliente_api, monkeypatch) -> None:
    cliente, csrf = _login_web(cliente_api)
    gestor = cliente.app.state.gestor_configuracion_ia
    gestor.guardar(
        proveedor="openai",
        modelo="gpt-4o-mini",
        temperatura=0,
        tokens_maximos=128,
        api_key="clave-diagnostico-prueba",
        version=1,
    )

    class Respuesta:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limite: int) -> bytes:
            return b'{"output_text":"OK"}'

    monkeypatch.setattr("talentia.platform.configuracion_ia.urlopen", lambda *_a, **_k: Respuesta())
    exito = cliente.post(
        "/admin/configuracion-ia/diagnostico",
        data={"csrf": csrf},
    )
    assert exito.status_code == 200
    assert "ACTIVO Y CONECTADO" in exito.text
    assert "HTTP 200" in exito.text

    def invalida(*_args, **_kwargs):
        raise HTTPError("https://api.openai.com", 401, "no", {}, None)

    monkeypatch.setattr("talentia.platform.configuracion_ia.urlopen", invalida)
    error = cliente.post(
        "/admin/configuracion-ia/diagnostico",
        data={"csrf": csrf},
    )
    assert error.status_code == 200
    assert "ERROR DE CONEXION" in error.text
    assert "API Key invalida" in error.text
    assert "clave-diagnostico" not in error.text


def test_cliente_llm_registra_uso_sin_enviar_pii_cruda(cliente_api, monkeypatch) -> None:
    gestor = cliente_api["cliente"].app.state.gestor_configuracion_ia
    gestor.guardar(
        proveedor="gemini",
        modelo="gemini-1.5-flash",
        temperatura=0,
        tokens_maximos=128,
        api_key="gemini-clave-prueba",
        version=1,
    )
    solicitudes = []

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limite: int) -> bytes:
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "requisitos": [
                                                    {
                                                        "codigo": "PY",
                                                        "veredicto": "coincide",
                                                        "evidencia": "Python",
                                                    }
                                                ]
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 23, "candidatesTokenCount": 7},
                }
            ).encode()

    def responder(solicitud, **_kwargs):
        solicitudes.append(solicitud)
        if len(solicitudes) == 1:
            raise HTTPError("https://generativelanguage.googleapis.com", 503, "no", {}, None)
        return Respuesta()

    monkeypatch.setattr("talentia.platform.cliente_llm.urlopen", responder)
    monkeypatch.setattr("talentia.platform.cliente_llm.time.sleep", lambda _segundos: None)
    resultado = ClienteLLM(gestor).evaluar(
        "Experiencia con Python. [CORREO_RETIRADO]",
        (("PY", "Experiencia Python"),),
    )
    assert resultado is not None
    assert resultado.prompt_tokens == 23
    assert resultado.completion_tokens == 7
    assert len(solicitudes) == 2
    cuerpo = solicitudes[0].data.decode()
    assert "persona@ejemplo.test" not in cuerpo
    assert "gemini-clave-prueba" not in cuerpo


def test_configuracion_rechaza_csrf_y_modelo_de_otro_proveedor(cliente_api) -> None:
    cliente, csrf = _login_web(cliente_api)
    invalido = cliente.post(
        "/admin/configuracion-ia",
        data={
            "csrf": csrf,
            "proveedor": "gemini",
            "modelo": "gpt-4o-mini",
            "temperatura": "0",
            "tokens_maximos": "128",
            "version": "1",
        },
    )
    assert invalido.status_code == 422
    sin_csrf = cliente.post(
        "/admin/configuracion-ia/diagnostico",
        data={"csrf": "incorrecto"},
    )
    assert sin_csrf.status_code == 403


def test_sugerencia_llm_exige_evidencia_original_y_conserva_tokens() -> None:
    requisito = RequisitoPerfil("PY", "Experiencia Python", True, Decimal("1"))
    valida = ContextoNodosEvaluacion._resultado_llm(
        {"documento_id": "doc-1"},
        "Experiencia comprobable con Python en proyectos.",
        (requisito,),
        RespuestaLLM(
            "openai",
            "gpt-4o-mini",
            ({"codigo": "PY", "veredicto": "coincide", "evidencia": "Python"},),
            31,
            9,
        ),
    )
    assert valida["resultados_requisitos"][0]["veredicto"] == "coincide"
    assert valida["resultados_requisitos"][0]["evidencia"][0]["fragmento"] == "Python"
    assert valida["prompt_tokens"] == 31
    assert valida["completion_tokens"] == 9

    inventada = ContextoNodosEvaluacion._resultado_llm(
        {"documento_id": "doc-1"},
        "Experiencia comprobable con Python en proyectos.",
        (requisito,),
        RespuestaLLM(
            "gemini",
            "gemini-1.5-flash",
            ({"codigo": "PY", "veredicto": "coincide", "evidencia": "Java"},),
            20,
            5,
        ),
    )
    assert inventada["resultados_requisitos"][0]["veredicto"] == "revision_manual"
    assert inventada["revision_requerida"] is True


def test_mlflow_registra_padre_nodo_tokens_y_latencia_sin_contenido(tmp_path) -> None:
    mlflow = pytest.importorskip("mlflow")
    tracking_uri = f"sqlite:///{(tmp_path / 'traces.db').as_posix()}"
    traza = TrazaWorkflowMLflow(
        tracking_uri,
        "trabajo-seguro",
        "correlacion-segura",
        "openai",
        "gpt-4o-mini",
    )
    traza.iniciar()
    traza.registrar_nodo(
        "evaluar_requisitos",
        secuencia=6,
        duracion_ms=42.5,
        prompt_tokens=120,
        completion_tokens=30,
    )
    traza.finalizar(estado="completado", prompt_tokens=120, completion_tokens=30)

    mlflow.set_tracking_uri(tracking_uri)
    experimento = mlflow.MlflowClient().get_experiment_by_name("talentia-workflows")
    assert experimento is not None
    corridas = mlflow.MlflowClient().search_runs([experimento.experiment_id])
    assert len(corridas) == 2
    nodo = next(
        item for item in corridas if item.data.tags.get("talentia.tipo") == "nodo_langgraph"
    )
    assert nodo.data.metrics["prompt_tokens"] == 120
    assert nodo.data.metrics["completion_tokens"] == 30
    assert nodo.data.metrics["total_tokens"] == 150
    serializado = json.dumps(
        [{"tags": item.data.tags, "metrics": item.data.metrics} for item in corridas]
    )
    assert "contenido del CV" not in serializado
    assert "api_key" not in serializado
