from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from talentia.shared.infrastructure.modelos_orm import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

url = os.getenv("TALENTIA_GREENFIELD_DATABASE_URL")
if url:
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

target_metadata = Base.metadata


def ejecutar_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def ejecutar_online() -> None:
    motor = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with motor.connect() as conexion:
        if conexion.dialect.name == "sqlite":
            conexion.exec_driver_sql("PRAGMA foreign_keys=ON")
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        if conexion.in_transaction():
            conexion.commit()


if context.is_offline_mode():
    ejecutar_offline()
else:
    ejecutar_online()
