"""Motor y sesiones de base de datos.

SQLite necesita un par de ajustes para comportarse como un motor decente, y
conviene aplicarlos desde el principio para que el laboratorio se parezca lo
más posible a producción:

* ``foreign_keys=ON``: SQLite ignora las claves foráneas por defecto. Sin esto,
  el laboratorio permite datos huérfanos que PostgreSQL rechazaría, y el fallo
  aparece en el despliegue en vez de en el desarrollo.
* ``journal_mode=WAL``: permite lecturas concurrentes con una escritura.
* ``busy_timeout``: en lugar de fallar de inmediato ante un bloqueo, espera.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import PROJECT_ROOT, Environment, get_settings
from app.core.logging import get_logger
from app.infrastructure.database.models import Base

logger = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_engine() -> Engine:
    """Motor único de la aplicación."""
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    kwargs: dict[str, object] = {"echo": settings.database_echo, "future": True}

    if settings.is_sqlite:
        # ``check_same_thread=False`` es necesario porque FastAPI atiende
        # peticiones síncronas en un pool de hilos.
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)

    _engine = create_engine(settings.database_url, **kwargs)
    if settings.is_sqlite:
        _configure_sqlite(_engine)

    logger.info(
        "Motor de base de datos inicializado",
        dialect=_engine.dialect.name,
        sqlite=settings.is_sqlite,
    )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Unidad de trabajo: confirma al salir bien, revierte al fallar.

    Que el ``rollback`` sea automático evita el escenario clásico de una
    excepción a mitad de un caso de uso que deja la mitad de los cambios
    aplicados.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """Dependencia para FastAPI."""
    with session_scope() as session:
        yield session


def init_database(*, drop_all: bool = False) -> None:
    """Actualiza el esquema mediante Alembic.

    Las pruebas en memoria son la única excepción: una conexión SQLite en
    memoria no se comparte con el motor temporal que abriría Alembic.
    """
    engine = get_engine()
    settings = get_settings()
    if settings.environment is Environment.TESTING:
        if drop_all:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        return

    from alembic import command
    from alembic.config import Config

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    if drop_all:
        logger.warning("Reiniciando el esquema local mediante migraciones Alembic")
        command.downgrade(config, "base")
    command.upgrade(config, "head")
    logger.info("Esquema de base de datos migrado", revision="head")


def reset_engine() -> None:
    """Solo para tests: fuerza un motor nuevo."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


__all__ = [
    "get_engine", "get_session", "get_session_factory", "init_database",
    "reset_engine", "session_scope",
]
