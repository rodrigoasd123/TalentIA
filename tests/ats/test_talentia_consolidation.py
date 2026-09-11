from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.core.config import PROJECT_ROOT, get_settings, reset_settings_cache
from app.infrastructure.database.legacy_adoption import (
    DatabaseAdoptionError,
    adopt_legacy_default_database,
    inspect_database,
)
from app.infrastructure.database.session import init_database, reset_engine


def _database(path: Path, *, rows: int = 1) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('a94109cb367c')")
        connection.execute("CREATE TABLE candidates (id TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO candidates VALUES (?)", [(f"candidate-{i}",) for i in range(rows)]
        )


def test_talentia_environment_has_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERA_DATABASE_URL", "sqlite:///./legacy.db")
    monkeypatch.setenv("TALENTIA_DATABASE_URL", "sqlite:///./official.db")
    reset_settings_cache()
    assert get_settings().database_url == "sqlite:///./official.db"
    reset_settings_cache()


def test_legacy_environment_warns_without_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TALENTIA_DATABASE_URL", raising=False)
    monkeypatch.setenv("VERA_DATABASE_URL", "sqlite:///./secret-path.db")
    reset_settings_cache()
    with pytest.warns(FutureWarning) as captured:
        assert get_settings().database_url.endswith("secret-path.db")
    messages = " ".join(str(item.message) for item in captured)
    assert "VERA_DATABASE_URL" in messages
    assert "secret-path.db" not in messages
    reset_settings_cache()


def test_new_install_targets_talentia_database(tmp_path: Path) -> None:
    assert adopt_legacy_default_database(tmp_path) == tmp_path / "talentia.db"
    assert not (tmp_path / "vera.db").exists()


def test_existing_legacy_database_is_copied_without_data_loss(tmp_path: Path) -> None:
    legacy = tmp_path / "vera.db"
    _database(legacy, rows=3)
    before = inspect_database(legacy)

    target = adopt_legacy_default_database(tmp_path)

    assert target.exists()
    assert legacy.exists()
    assert inspect_database(target) == before
    backups = list((tmp_path / ".talentia-backups").glob("*.db.bak"))
    assert len(backups) == 1
    assert inspect_database(backups[0]) == before
    assert backups[0].with_suffix(backups[0].suffix + ".json").exists()


def test_existing_talentia_database_is_used(tmp_path: Path) -> None:
    target = tmp_path / "talentia.db"
    _database(target)
    assert adopt_legacy_default_database(tmp_path) == target


def test_two_databases_stop_without_modification(tmp_path: Path) -> None:
    legacy = tmp_path / "vera.db"
    target = tmp_path / "talentia.db"
    _database(legacy, rows=1)
    _database(target, rows=2)
    legacy_hash = inspect_database(legacy).sha256
    target_hash = inspect_database(target).sha256
    with pytest.raises(DatabaseAdoptionError, match="ambas bases"):
        adopt_legacy_default_database(tmp_path)
    assert inspect_database(legacy).sha256 == legacy_hash
    assert inspect_database(target).sha256 == target_hash


def test_copy_failure_leaves_source_and_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = tmp_path / "vera.db"
    _database(legacy)

    def fail_copy(*_args, **_kwargs):
        raise OSError("fallo inyectado")

    monkeypatch.setattr("app.infrastructure.database.legacy_adoption.shutil.copy2", fail_copy)
    with pytest.raises(OSError, match="fallo inyectado"):
        adopt_legacy_default_database(tmp_path)
    assert legacy.exists()
    assert not (tmp_path / "talentia.db").exists()


def test_real_alembic_database_is_adopted_and_upgraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = tmp_path / "vera.db"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    monkeypatch.setenv("TALENTIA_DATABASE_URL", f"sqlite:///{legacy.as_posix()}")
    reset_settings_cache()
    command.upgrade(config, "head")
    before = inspect_database(legacy)

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TALENTIA_DATABASE_URL", raising=False)
    monkeypatch.delenv("VERA_DATABASE_URL", raising=False)
    reset_engine()
    reset_settings_cache()
    try:
        init_database()
        target = tmp_path / "talentia.db"
        assert target.exists()
        assert legacy.exists()
        assert inspect_database(target).table_counts == before.table_counts
    finally:
        reset_engine()
        reset_settings_cache()
