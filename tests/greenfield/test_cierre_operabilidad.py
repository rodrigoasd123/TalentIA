from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from talentia.platform.observabilidad.rendimiento import (
    ResultadoSolicitud,
    ejecutar_medicion,
    resumir_resultados,
    validar_parametros,
)


@contextmanager
def servidor_local(codigo: int) -> Iterator[str]:
    class Manejador(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(codigo)
            self.end_headers()
            self.wfile.write(b"persona@ejemplo.test contenido que no debe registrarse")

        def log_message(self, formato: str, *argumentos: object) -> None:
            del formato, argumentos

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    hilo = Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}/health"
    finally:
        servidor.shutdown()
        hilo.join(timeout=2)
        servidor.server_close()


def test_docker_resuelve_src_y_ci_usa_acciones_node24() -> None:
    dockerfile = Path("Dockerfile").read_text("utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text("utf-8")
    assert "PYTHONPATH=/app/src" in dockerfile
    assert "talentia.main:app" in dockerfile
    assert "actions/checkout@v5" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "python -m pytest -q tests/greenfield" in workflow


def test_resumen_calcula_conteos_y_percentiles_sin_datos_de_respuesta() -> None:
    resumen = resumir_resultados(
        [
            ResultadoSolicitud(True, 10.0),
            ResultadoSolicitud(True, 20.0),
            ResultadoSolicitud(False, 100.0, "http_500"),
        ]
    )
    assert resumen.solicitudes == 3
    assert resumen.exitos == 2
    assert resumen.errores == 1
    assert resumen.promedio_ms == pytest.approx(43.333, abs=0.001)
    assert resumen.p50_ms == 20.0
    assert resumen.p95_ms == 100.0
    assert resumen.errores_por_tipo == {"http_500": 1}
    assert "persona@" not in str(resumen.como_dict())


def test_medicion_http_local_reporta_exito_y_error_sin_cuerpo() -> None:
    with servidor_local(200) as url_saludable:
        saludable = ejecutar_medicion(url_saludable, solicitudes=4, concurrencia=2, timeout=2)
    assert saludable.exitos == 4
    assert saludable.errores == 0

    with servidor_local(500) as url_fallida:
        fallida = ejecutar_medicion(url_fallida, solicitudes=3, concurrencia=1, timeout=2)
    assert fallida.exitos == 0
    assert fallida.errores == 3
    assert fallida.errores_por_tipo == {"http_500": 3}
    assert "persona@ejemplo.test" not in str(fallida.como_dict())


@pytest.mark.parametrize(
    ("url", "solicitudes", "concurrencia", "timeout"),
    [
        ("file:///tmp/test", 1, 1, 1.0),
        ("http://127.0.0.1", 0, 1, 1.0),
        ("http://127.0.0.1", 1, 2, 1.0),
        ("http://127.0.0.1", 1, 1, 0.0),
    ],
)
def test_medicion_rechaza_parametros_no_acotados(
    url: str, solicitudes: int, concurrencia: int, timeout: float
) -> None:
    with pytest.raises(ValueError):
        validar_parametros(url, solicitudes, concurrencia, timeout)
