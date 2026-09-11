"""Adopción segura de la base SQLite predeterminada heredada.

No modifica el esquema: Alembic conserva esa responsabilidad. Este módulo solo
copia una base íntegra a su nombre oficial antes de crear el motor SQLAlchemy.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


class DatabaseAdoptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    sha256: str
    alembic_revision: str
    table_counts: dict[str, int]


CRITICAL_TABLES = (
    "candidates", "jobs", "applications", "candidate_documents", "evaluations",
    "human_reviews", "audit_events",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_database(path: Path) -> DatabaseSnapshot:
    absolute = path.resolve(strict=True)
    uri = f"file:{absolute.as_posix()}?mode=ro"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(uri, uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise DatabaseAdoptionError("La verificación de integridad SQLite falló.")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "alembic_version" not in tables:
                raise DatabaseAdoptionError(
                    "La base heredada no contiene revisión Alembic; requiere revisión manual."
                )
            revision_row = connection.execute(
                "SELECT version_num FROM alembic_version LIMIT 1"
            ).fetchone()
            if not revision_row or not revision_row[0]:
                raise DatabaseAdoptionError("La revisión Alembic está vacía.")
            counts = {
                table: connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'  # noqa: S608 - catálogo interno cerrado
                ).fetchone()[0]
                for table in CRITICAL_TABLES
                if table in tables
            }
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise DatabaseAdoptionError("No se pudo verificar la base SQLite heredada.") from exc
    return DatabaseSnapshot(_sha256(absolute), str(revision_row[0]), counts)


def adopt_legacy_default_database(root: Path) -> Path:
    root = root.resolve()
    legacy = (root / "vera.db").resolve()
    target = (root / "talentia.db").resolve()
    if legacy.parent != root or target.parent != root:
        raise DatabaseAdoptionError("Las rutas de base predeterminadas no son seguras.")
    if legacy.exists() and target.exists():
        raise DatabaseAdoptionError(
            f"Existen ambas bases: {legacy} y {target}. Ninguna fue modificada. "
            "Respalda y selecciona manualmente una mediante TALENTIA_DATABASE_URL."
        )
    if target.exists() or not legacy.exists():
        return target

    before = inspect_database(legacy)
    backup_dir = (root / ".talentia-backups").resolve()
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"vera-{stamp}-{before.sha256[:12]}.db.bak"
    temporary = root / f".talentia.db.{os.getpid()}.tmp"
    if backup.exists() or temporary.exists():
        raise DatabaseAdoptionError("Existe un archivo de adopción previo; revisa el directorio.")
    try:
        shutil.copy2(legacy, backup)
        if inspect_database(backup) != before:
            raise DatabaseAdoptionError("El respaldo verificable no coincide con el origen.")
        shutil.copy2(legacy, temporary)
        with temporary.open("r+b") as copied:
            os.fsync(copied.fileno())
        if inspect_database(temporary) != before:
            raise DatabaseAdoptionError("La copia temporal no coincide con el origen.")
        os.replace(temporary, target)
        if inspect_database(target) != before:
            raise DatabaseAdoptionError("La base adoptada no coincide con el origen.")
        manifest = {
            "source_name": legacy.name, "target_name": target.name,
            "backup_name": backup.name, "sha256": before.sha256,
            "alembic_revision": before.alembic_revision,
            "table_counts": before.table_counts, "created_at": datetime.now(UTC).isoformat(),
        }
        (backup.with_suffix(backup.suffix + ".json")).write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception:
        if temporary.exists() and temporary.parent == root:
            temporary.unlink()
        raise
    return target


__all__ = [
    "DatabaseAdoptionError", "DatabaseSnapshot", "adopt_legacy_default_database",
    "inspect_database",
]
