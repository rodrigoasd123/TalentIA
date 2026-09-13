"""Motor SQLite, sesiones y unidad de trabajo del nuevo runtime."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def crear_motor(url: str) -> Engine:
    argumentos: dict[str, object] = {"future": True}
    if url.startswith("sqlite"):
        argumentos["connect_args"] = {"check_same_thread": False}
    motor = create_engine(url, **argumentos)
    if url.startswith("sqlite"):

        @event.listens_for(motor, "connect")
        def configurar_sqlite(conexion: Any, _registro: Any) -> None:
            cursor = conexion.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return motor


class FabricaSesiones:
    def __init__(self, motor: Engine) -> None:
        self._fabrica = sessionmaker(
            bind=motor, expire_on_commit=False, autoflush=False, future=True
        )

    @contextmanager
    def sesion(self) -> Iterator[Session]:
        sesion = self._fabrica()
        try:
            yield sesion
            sesion.commit()
        except Exception:
            sesion.rollback()
            raise
        finally:
            sesion.close()

    def nueva(self) -> Session:
        return self._fabrica()
