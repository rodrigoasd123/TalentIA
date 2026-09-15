from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PLANTILLAS = RAIZ / "src" / "talentia" / "web" / "templates"
ESTILOS = RAIZ / "src" / "talentia" / "web" / "static" / "css" / "aplicacion.css"
LOGO_TCS = RAIZ / "src" / "talentia" / "web" / "static" / "img" / "tcs-wordmark.svg"


def test_sistema_visual_es_local_centralizado_y_responsive() -> None:
    css = ESTILOS.read_text(encoding="utf-8")

    for token in (
        "--color-primary-950",
        "--color-accent-500",
        "--color-neutral-200",
        "--font-sans",
        "--radius-md",
        "--shadow-sm",
        "--focus-ring",
    ):
        assert token in css
    assert "@media (max-width: 820px)" in css
    assert "@media (max-width: 600px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@import" not in css
    assert "http://" not in css
    assert "https://" not in css


def test_plantillas_no_incorporan_recursos_remotos() -> None:
    contenido = "\n".join(
        archivo.read_text(encoding="utf-8") for archivo in PLANTILLAS.rglob("*.html")
    )

    assert 'src="http://' not in contenido
    assert 'src="https://' not in contenido
    assert 'href="http://' not in contenido
    assert 'href="https://' not in contenido


def test_shell_marca_navegacion_activa_y_accesibilidad(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cliente.post(
        "/login",
        data={
            "correo": "admin@pruebas.test",
            "contrasena": "Contrasena-Pruebas-2026!",
        },
    )

    pagina = cliente.get("/candidatos")

    assert pagina.status_code == 200
    assert 'href="#contenido-principal"' in pagina.text
    assert 'id="contenido-principal"' in pagina.text
    assert 'href="/candidatos" class="activo" aria-current="page"' in pagina.text
    assert "Talent acquisition workspace" in pagina.text
    assert 'src="/static/img/tcs-wordmark.svg"' in pagina.text
    assert 'alt="Tata Consultancy Services"' in pagina.text
    assert LOGO_TCS.read_text(encoding="utf-8").lstrip().startswith("<svg")
    assert 'action="/logout"' in pagina.text


def test_dashboard_usa_datos_reales_y_conserva_accesos(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cliente.post(
        "/login",
        data={
            "correo": "admin@pruebas.test",
            "contrasena": "Contrasena-Pruebas-2026!",
        },
    )

    pagina = cliente.get("/")

    assert pagina.status_code == 200
    assert "Candidatos recientes" in pagina.text
    assert "Proveedor IA" in pagina.text
    assert "Decision final" in pagina.text
    assert 'href="/candidatos/nuevo"' in pagina.text
    assert 'href="/evaluaciones/nueva"' in pagina.text


def test_contratos_criticos_de_formularios_y_htmx_se_conservan() -> None:
    candidatos = (PLANTILLAS / "candidatos.html").read_text(encoding="utf-8")
    evaluacion = (PLANTILLAS / "nueva_evaluacion.html").read_text(encoding="utf-8")
    progreso = (PLANTILLAS / "fragmentos" / "estado_trabajo.html").read_text(encoding="utf-8")

    assert 'hx-get="/fragmentos/candidatos"' in candidatos
    assert 'hx-target="#tabla-candidatos"' in candidatos
    assert 'name="q"' in candidatos
    assert 'name="postulacion_id"' in evaluacion
    assert 'name="clave_idempotencia"' in evaluacion
    assert 'name="archivo"' in evaluacion
    assert 'hx-get="/fragmentos/trabajos/{{ trabajo.id }}"' in progreso
