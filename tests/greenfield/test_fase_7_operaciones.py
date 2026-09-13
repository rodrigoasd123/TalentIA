from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from talentia.platform.operaciones.base_datos import (
    OperacionBaseDatosError,
    crear_respaldo,
    restaurar_respaldo,
)
from talentia.shared.infrastructure.base_datos import crear_motor


def _configuracion_alembic(base: Path) -> Config:
    configuracion = Config("alembic_greenfield.ini")
    configuracion.set_main_option("script_location", "migrations_greenfield")
    configuracion.set_main_option("sqlalchemy.url", f"sqlite:///{base.as_posix()}")
    return configuracion


def test_migraciones_son_reversibles_revision_por_revision(tmp_path) -> None:
    base = tmp_path / "migraciones.db"
    configuracion = _configuracion_alembic(base)
    command.upgrade(configuracion, "0001_greenfield")
    command.upgrade(configuracion, "0002_esquema")
    command.upgrade(configuracion, "0003_workflow")
    motor = crear_motor(f"sqlite:///{base.as_posix()}")
    assert "lease_token" in {
        columna["name"] for columna in inspect(motor).get_columns("agent_jobs")
    }
    command.downgrade(configuracion, "0002_esquema")
    assert "lease_token" not in {
        columna["name"] for columna in inspect(motor).get_columns("agent_jobs")
    }
    motor.dispose()
    command.downgrade(configuracion, "0001_greenfield")
    command.downgrade(configuracion, "base")
    command.upgrade(configuracion, "head")
    motor = crear_motor(f"sqlite:///{base.as_posix()}")
    assert {"candidates", "agent_jobs", "pilot_metric_events"} <= set(
        inspect(motor).get_table_names()
    )
    motor.dispose()


def test_backup_y_restauracion_conservan_integridad_y_datos(tmp_path) -> None:
    origen = tmp_path / "origen.db"
    respaldo = tmp_path / "respaldos" / "talentia.db"
    restaurada = tmp_path / "restaurada.db"
    with sqlite3.connect(origen) as conexion:
        conexion.execute("CREATE TABLE evidencia (id INTEGER PRIMARY KEY, valor TEXT)")
        conexion.execute("INSERT INTO evidencia(valor) VALUES ('dato sintetico')")
    crear_respaldo(origen, respaldo)
    restaurar_respaldo(respaldo, restaurada)
    with sqlite3.connect(restaurada) as conexion:
        assert conexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conexion.execute("SELECT valor FROM evidencia").fetchone()[0] == "dato sintetico"
    with pytest.raises(OperacionBaseDatosError, match="no se sobrescribe"):
        restaurar_respaldo(respaldo, restaurada)


def test_backup_rechaza_archivo_corrupto(tmp_path) -> None:
    corrupta = tmp_path / "corrupta.db"
    corrupta.write_bytes(b"esto no es sqlite")
    with pytest.raises(OperacionBaseDatosError, match="SQLite no es valida"):
        crear_respaldo(corrupta, tmp_path / "copia.db")
