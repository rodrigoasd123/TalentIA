"""Backup y restauracion segura de SQLite mediante su API nativa."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


class OperacionBaseDatosError(RuntimeError):
    """La operacion no puede garantizar integridad o no sobreescritura."""


def verificar_integridad(ruta: Path) -> None:
    if not ruta.is_file():
        raise OperacionBaseDatosError(f"No existe la base: {ruta}")
    try:
        with sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True) as conexion:
            resultado = conexion.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as error:
        raise OperacionBaseDatosError("La base SQLite no es valida") from error
    if not resultado or resultado[0] != "ok":
        raise OperacionBaseDatosError("La base SQLite no supera integrity_check")


def crear_respaldo(origen: Path, destino: Path) -> Path:
    verificar_integridad(origen)
    if destino.exists():
        raise OperacionBaseDatosError("El destino ya existe; no se sobrescribe")
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(origen) as fuente, sqlite3.connect(destino) as copia:
            fuente.backup(copia)
    except Exception:
        destino.unlink(missing_ok=True)
        raise
    verificar_integridad(destino)
    return destino


def restaurar_respaldo(origen: Path, destino: Path) -> Path:
    return crear_respaldo(origen, destino)


def main() -> None:
    analizador = argparse.ArgumentParser()
    subcomandos = analizador.add_subparsers(dest="operacion", required=True)
    for nombre in ("respaldar", "restaurar"):
        comando = subcomandos.add_parser(nombre)
        comando.add_argument("origen", type=Path)
        comando.add_argument("destino", type=Path)
    argumentos = analizador.parse_args()
    funcion = crear_respaldo if argumentos.operacion == "respaldar" else restaurar_respaldo
    print(funcion(argumentos.origen, argumentos.destino))


if __name__ == "__main__":
    main()
