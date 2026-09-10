"""Seguridad de la API: autenticación, RBAC y protección de secretos.

Estas pruebas bloquean el merge. Verifican propiedades que, de romperse, dejarían
el sistema abierto sin que nada más lo delate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Environment, get_settings, reset_settings_cache
from app.domain.enums import ROLE_PERMISSIONS, Permission, Role
from app.infrastructure.security.passwords import (
    PasswordPolicyError,
    hash_password,
    needs_rehash,
    validate_password,
    verify_password,
)
from app.infrastructure.security.tokens import TOKEN_REGISTRY, TokenService

pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def _clean_registry():
    TOKEN_REGISTRY.clear()
    yield
    TOKEN_REGISTRY.clear()


# ── Contraseñas ──────────────────────────────────────────────────────────────


def test_la_contraseña_se_almacena_con_argon2id() -> None:
    resultado = hash_password("Contraseña-Segura-2026!")
    assert resultado.startswith("$argon2id$")
    assert "Contraseña-Segura-2026!" not in resultado


def test_dos_hashes_de_la_misma_contraseña_difieren() -> None:
    """La sal aleatoria impide deducir que dos cuentas comparten contraseña."""
    a = hash_password("Contraseña-Segura-2026!")
    b = hash_password("Contraseña-Segura-2026!")
    assert a != b
    assert verify_password("Contraseña-Segura-2026!", a)
    assert verify_password("Contraseña-Segura-2026!", b)


@pytest.mark.parametrize(
    "password",
    ["corta1!", "sinmayusculasni digitos", "12345678901234", "password", "PASSWORD123"],
)
def test_la_politica_rechaza_contraseñas_debiles(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        validate_password(password)


def test_un_hash_vacio_no_valida_nada() -> None:
    """Un usuario sin contraseña no puede autenticarse por descuido."""
    assert not verify_password("cualquier-cosa", "")


def test_un_hash_corrupto_no_revienta() -> None:
    assert not verify_password("cualquier-cosa", "no-es-un-hash")
    assert needs_rehash("no-es-un-hash")


# ── Tokens ───────────────────────────────────────────────────────────────────


def test_el_token_de_acceso_lleva_los_permisos_del_rol() -> None:
    service = TokenService()
    pair = service.issue_pair(user_id="u1", email="a@example.test", role=Role.AUDITOR)
    claims = service.decode(pair.access_token)

    assert claims.role is Role.AUDITOR
    esperados = {p.value for p in ROLE_PERMISSIONS[Role.AUDITOR]}
    assert claims.permissions == esperados


def test_el_token_de_refresco_no_lleva_permisos() -> None:
    """Solo sirve para obtener un token de acceso; no autoriza nada por sí mismo."""
    service = TokenService()
    pair = service.issue_pair(user_id="u1", email="a@example.test", role=Role.ADMIN)
    claims = service.decode(pair.refresh_token, expected_type="refresh")
    assert claims.permissions == frozenset()


def test_un_token_de_refresco_no_sirve_como_token_de_acceso() -> None:
    from app.core.exceptions import AuthenticationError

    service = TokenService()
    pair = service.issue_pair(user_id="u1", email="a@example.test", role=Role.ADMIN)
    with pytest.raises(AuthenticationError):
        service.decode(pair.refresh_token, expected_type="access")


def test_un_token_manipulado_se_rechaza() -> None:
    from app.core.exceptions import AuthenticationError

    service = TokenService()
    pair = service.issue_pair(user_id="u1", email="a@example.test", role=Role.RECRUITER)
    cabecera, carga, firma = pair.access_token.split(".")
    manipulado = f"{cabecera}.{carga}.{'x' * len(firma)}"

    with pytest.raises(AuthenticationError):
        service.decode(manipulado)


def test_un_token_sin_firma_se_rechaza() -> None:
    """Defensa contra el ataque clásico de algoritmo «none».

    El decodificador fija el algoritmo esperado en lugar de aceptar el que
    declara la cabecera del propio token.
    """
    import base64
    import json

    from app.core.exceptions import AuthenticationError

    cabecera = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).decode().rstrip("=")
    carga = base64.urlsafe_b64encode(
        json.dumps(
            {"sub": "atacante", "type": "access", "jti": "x", "exp": 9999999999,
             "role": "admin", "perms": ["settings:write"]}
        ).encode()
    ).decode().rstrip("=")

    with pytest.raises(AuthenticationError):
        TokenService().decode(f"{cabecera}.{carga}.")


def test_reutilizar_un_refresco_revoca_la_familia_entera() -> None:
    """Un refresco consumido que reaparece es señal de robo.

    Se asume lo peor y se invalida la sesión completa: es preferible obligar a
    iniciar sesión de nuevo que mantener viva una sesión comprometida.
    """
    from app.core.exceptions import AuthenticationError

    service = TokenService()
    original = service.issue_pair(user_id="u1", email="a@example.test", role=Role.RECRUITER)
    nuevo = service.rotate(original.refresh_token)

    with pytest.raises(AuthenticationError):
        service.rotate(original.refresh_token)

    # El token nuevo, legítimo hasta ese momento, también queda invalidado.
    with pytest.raises(AuthenticationError):
        service.decode(nuevo.access_token)


def test_el_cierre_de_sesion_invalida_la_familia() -> None:
    from app.core.exceptions import AuthenticationError

    service = TokenService()
    pair = service.issue_pair(user_id="u1", email="a@example.test", role=Role.RECRUITER)
    service.revoke_session(pair.refresh_token)

    with pytest.raises(AuthenticationError):
        service.decode(pair.access_token)


# ── Matriz de permisos ───────────────────────────────────────────────────────


def test_ningun_rol_salvo_admin_modifica_la_configuracion() -> None:
    for rol, permisos in ROLE_PERMISSIONS.items():
        if rol is not Role.ADMIN:
            assert Permission.SETTINGS_WRITE not in permisos


def test_el_entrevistador_no_accede_a_datos_personales_completos() -> None:
    permisos = ROLE_PERMISSIONS[Role.INTERVIEWER]
    assert Permission.CANDIDATE_PII_READ not in permisos
    assert Permission.EVALUATION_OVERRIDE not in permisos


def test_ningun_rol_puede_escribir_en_la_auditoria() -> None:
    """No existe un permiso de escritura de auditoría, y no debe existir."""
    assert not hasattr(Permission, "AUDIT_WRITE")
    for permisos in ROLE_PERMISSIONS.values():
        assert not any("audit" in p.value and "read" not in p.value for p in permisos)


# ── Modo de laboratorio ──────────────────────────────────────────────────────


def test_la_sesion_de_laboratorio_solo_existe_en_desarrollo(monkeypatch) -> None:
    """La puerta abierta del laboratorio debe cerrarse sola fuera de él.

    Es exactamente el tipo de atajo que acaba llegando a producción si nadie lo
    comprueba automáticamente.
    """
    from fastapi import Request

    from app.api.dependencies import get_current_user
    from app.core.exceptions import AuthenticationError

    peticion = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)})

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", Environment.DEVELOPMENT)
    usuario = get_current_user(peticion, authorization=None)
    assert usuario.is_lab_session

    for entorno in (Environment.PRODUCTION, Environment.STAGING, Environment.TESTING):
        monkeypatch.setattr(settings, "environment", entorno)
        with pytest.raises(AuthenticationError):
            get_current_user(peticion, authorization=None)


# ── Endpoints ────────────────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("VERA_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("VERA_ENVIRONMENT", "development")
    reset_settings_cache()

    from app.infrastructure.database.session import reset_engine

    reset_engine()
    from app.api.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    reset_settings_cache()


def test_las_credenciales_invalidas_no_revelan_si_el_usuario_existe(
    client: TestClient,
) -> None:
    """El mensaje debe ser idéntico en ambos casos.

    Si difiriera, se podría enumerar qué correos están registrados.
    """
    inexistente = client.post(
        "/api/v1/auth/login", json={"email": "nadie@ejemplo.test", "password": "x" * 14}
    )
    assert inexistente.status_code == 401
    assert inexistente.json()["error"]["message"] == "Credenciales inválidas"


def test_la_api_nunca_devuelve_un_secreto_en_claro(client: TestClient) -> None:
    """No existe ningún endpoint que exponga una API key completa."""
    clave = "clave-gemini-ficticia-para-prueba-1234567890"
    client.patch("/api/v1/config/settings", json={"values": {"llm.api_key": clave}})

    respuesta = client.get("/api/v1/config/settings")
    assert clave not in respuesta.text

    item = next(
        i for i in respuesta.json()["settings"] if i["key"] == "llm.api_key"
    )
    assert item["is_set"] is True
    assert "•" in item["value"]


def test_una_clave_de_configuracion_desconocida_se_ignora(client: TestClient) -> None:
    """La tabla de configuración no admite claves arbitrarias."""
    respuesta = client.patch(
        "/api/v1/config/settings", json={"values": {"clave.inventada": "valor"}}
    )
    assert respuesta.status_code == 200
    claves = {i["key"] for i in respuesta.json()["settings"]}
    assert "clave.inventada" not in claves


def test_las_cabeceras_de_seguridad_estan_presentes(client: TestClient) -> None:
    respuesta = client.get("/health/live")
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert respuesta.headers["Referrer-Policy"] == "no-referrer"
    assert respuesta.headers["X-Trace-Id"]


def test_el_error_no_filtra_detalles_internos(client: TestClient) -> None:
    """Un fallo no debe exponer rutas, trazas de pila ni SQL."""
    respuesta = client.post(
        "/api/v1/evaluations/run",
        json={"job_code": "NO-EXISTE", "resume_code": "NO-EXISTE"},
    )
    assert respuesta.status_code == 404
    cuerpo = respuesta.text.lower()
    for filtracion in ("traceback", "sqlalchemy", "site-packages", ".py\", line"):
        assert filtracion not in cuerpo
    assert respuesta.json()["error"]["trace_id"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/jobs"),
        ("get", "/api/v1/dashboard/summary"),
        ("get", "/api/v1/config/settings"),
        ("post", "/api/v1/jobs"),
    ],
)
def test_las_rutas_de_negocio_exigen_autenticacion_fuera_del_laboratorio(
    client: TestClient, monkeypatch, method: str, path: str
) -> None:
    monkeypatch.setattr(get_settings(), "environment", Environment.STAGING)
    response = client.post(path, json={}) if method == "post" else client.get(path)
    assert response.status_code == 401