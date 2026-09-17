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


def test_migraciones_son_reversibles_revision_por_revision(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TALENTIA_GREENFIELD_DATABASE_URL", raising=False)
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


def test_migracion_convocatorias_preserva_postulacion_y_evidencia(tmp_path) -> None:
    base = tmp_path / "convocatorias-historicas.db"
    configuracion = _configuracion_alembic(base)
    command.upgrade(configuracion, "0005_configuracion_ia")
    ahora = "2026-09-16 12:00:00"
    with sqlite3.connect(base) as conexion:
        conexion.execute(
            """
            INSERT INTO clients(id, codigo, nombre, activo, creado_en, actualizado_en, version)
            VALUES ('cliente-historico', 'HIST', 'Cuenta historica', 1, ?, ?, 1)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO candidates(
                id, cliente_id, nombres, apellidos, estado, etiquetas,
                creado_en, actualizado_en, version
            ) VALUES ('candidato-historico', 'cliente-historico', 'Ana', 'Historia',
                      'en_proceso', '[]', ?, ?, 1)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO job_profiles(
                id, cliente_id, codigo, titulo, activo, creado_en, actualizado_en, version
            ) VALUES ('perfil-historico', 'cliente-historico', 'PER-HIST',
                      'Perfil historico', 1, ?, ?, 1)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO job_profile_versions(
                id, perfil_id, numero, requisitos, publicado, creado_en, actualizado_en, version
            ) VALUES ('version-historica', 'perfil-historico', 1, '[]', 1, ?, ?, 1)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO applications(
                id, cliente_id, candidato_id, version_perfil_id, fuente, estado,
                clave_idempotencia, creado_en, actualizado_en, version
            ) VALUES ('postulacion-historica', 'cliente-historico', 'candidato-historico',
                      'version-historica', 'adecco', 'revision_humana', 'idem-historica',
                      ?, ?, 3)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO candidate_documents(
                id, cliente_id, candidato_id, nombre_original, tipo_mime, hash_sha256,
                ruta_almacenamiento, tamano_bytes, creado_en, actualizado_en, version
            ) VALUES ('documento-historico', 'cliente-historico', 'candidato-historico',
                      'cv.pdf', 'application/pdf', 'hash-historico', 'storage/cv.pdf', 10,
                      ?, ?, 1)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO evaluations(
                id, cliente_id, postulacion_id, documento_id, version_perfil_id,
                puntaje_documental, requiere_revision, simulada,
                creado_en, actualizado_en, version
            ) VALUES ('evaluacion-historica', 'cliente-historico', 'postulacion-historica',
                      'documento-historico', 'version-historica', 75, 1, 0, ?, ?, 1)
            """,
            (ahora, ahora),
        )
        conexion.execute(
            """
            INSERT INTO human_reviews(
                id, evaluacion_id, estado, comentario, creado_en, actualizado_en, version
            ) VALUES ('revision-historica', 'evaluacion-historica', 'pendiente',
                      'Conservar evidencia', ?, ?, 1)
            """,
            (ahora, ahora),
        )

    command.upgrade(configuracion, "0006_convocatorias")
    with sqlite3.connect(base) as conexion:
        columnas_postulacion = {
            fila[1] for fila in conexion.execute("PRAGMA table_info(applications)").fetchall()
        }
        assert "reclutador_id" in columnas_postulacion
        indices_responsables = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA index_list(campaign_recruiter_assignments)"
            ).fetchall()
        }
        assert "ix_campaign_recruiter_user_campaign" in indices_responsables
        postulacion = conexion.execute(
            """
            SELECT cliente_id, candidato_id, version_perfil_id, estado, fuente,
                   convocatoria_id, version
            FROM applications WHERE id = 'postulacion-historica'
            """
        ).fetchone()
        assert postulacion is not None
        assert postulacion[:5] == (
            "cliente-historico",
            "candidato-historico",
            "version-historica",
            "revision_humana",
            "adecco",
        )
        assert postulacion[5]
        assert postulacion[6] == 3
        assert (
            conexion.execute(
                "SELECT COUNT(*) FROM evaluations WHERE id = 'evaluacion-historica'"
            ).fetchone()[0]
            == 1
        )
        assert (
            conexion.execute(
                "SELECT COUNT(*) FROM human_reviews WHERE id = 'revision-historica'"
            ).fetchone()[0]
            == 1
        )
        convocatoria = conexion.execute(
            """
            SELECT cliente_id, version_perfil_id, es_compatibilidad
            FROM recruitment_campaigns WHERE id = ?
            """,
            (postulacion[5],),
        ).fetchone()
        assert convocatoria == ("cliente-historico", "version-historica", 1)

    command.downgrade(configuracion, "0005_configuracion_ia")
    with sqlite3.connect(base) as conexion:
        columnas = {
            fila[1] for fila in conexion.execute("PRAGMA table_info(applications)").fetchall()
        }
        assert "convocatoria_id" not in columnas
        assert "reclutador_id" not in columnas
        assert (
            conexion.execute(
                "SELECT estado FROM applications WHERE id = 'postulacion-historica'"
            ).fetchone()[0]
            == "revision_humana"
        )
        assert (
            conexion.execute(
                "SELECT COUNT(*) FROM evaluations WHERE id = 'evaluacion-historica'"
            ).fetchone()[0]
            == 1
        )
