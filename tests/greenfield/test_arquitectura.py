from __future__ import annotations

import ast
from pathlib import Path


def _importaciones(ruta: Path) -> set[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    resultado: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            resultado.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            resultado.add(nodo.module)
    return resultado


def test_dominio_no_importa_frameworks() -> None:
    prohibidos = ("fastapi", "sqlalchemy", "langgraph", "jinja2")
    for ruta in Path("src/talentia/modules").glob("*/domain/*.py"):
        assert not any(nombre.startswith(prohibidos) for nombre in _importaciones(ruta)), ruta


def test_aplicacion_no_importa_infraestructura() -> None:
    for ruta in Path("src/talentia").glob("**/application/*.py"):
        assert not any(".infrastructure" in nombre for nombre in _importaciones(ruta)), ruta


def test_api_no_importa_orm() -> None:
    for ruta in Path("src/talentia/web").glob("**/*.py"):
        assert not any("modelos_orm" in nombre for nombre in _importaciones(ruta)), ruta
