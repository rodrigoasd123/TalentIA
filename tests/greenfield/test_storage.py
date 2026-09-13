from __future__ import annotations

from pathlib import Path

import pytest

from talentia.platform.document_store.local import AlmacenLocal


def test_almacen_local_guarda_en_directorio_privado(tmp_path: Path) -> None:
    almacen = AlmacenLocal(tmp_path / "documentos")

    ruta = Path(almacen.guardar("cv-prueba.pdf", b"%PDF-contenido-sintetico"))

    assert ruta.parent == (tmp_path / "documentos").resolve()
    assert ruta.read_bytes() == b"%PDF-contenido-sintetico"


@pytest.mark.parametrize("nombre", ["../escape.pdf", "subdir/cv.pdf", "", ".", ".."])
def test_almacen_local_rechaza_escape_de_ruta(tmp_path: Path, nombre: str) -> None:
    almacen = AlmacenLocal(tmp_path / "documentos")

    with pytest.raises(ValueError):
        almacen.guardar(nombre, b"contenido")
