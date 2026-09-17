"""incorporar convocatorias, responsables y seleccion gobernada

Revision ID: 0006_convocatorias
Revises: 0005_configuracion_ia
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0006_convocatorias"
down_revision = "0005_configuracion_ia"
branch_labels = None
depends_on = None

_TERMINALES = {"contratada", "no_apta", "rechazada", "backup", "retirada"}


def _id_compatibilidad(cliente_id: str, version_perfil_id: str) -> str:
    return hashlib.sha256(
        f"convocatoria-compatibilidad:{cliente_id}:{version_perfil_id}".encode()
    ).hexdigest()[:32]


def upgrade() -> None:
    op.create_table(
        "recruitment_campaigns",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("cliente_id", sa.String(length=32), nullable=False),
        sa.Column("version_perfil_id", sa.String(length=32), nullable=False),
        sa.Column("codigo", sa.String(length=80), nullable=False),
        sa.Column("vacantes_total", sa.Integer(), nullable=False),
        sa.Column("fecha_apertura", sa.Date(), nullable=True),
        sa.Column("fecha_objetivo", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(length=32), nullable=False),
        sa.Column("motivo_cierre", sa.Text(), nullable=True),
        sa.Column("es_compatibilidad", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["version_perfil_id"], ["job_profile_versions.id"]),
        sa.UniqueConstraint("cliente_id", "codigo", name="uq_campaign_client_code"),
    )
    op.create_index(
        "ix_campaign_client_status",
        "recruitment_campaigns",
        ["cliente_id", "estado"],
        unique=False,
    )
    op.create_index(
        "ix_campaign_client_profile",
        "recruitment_campaigns",
        ["cliente_id", "version_perfil_id"],
        unique=False,
    )
    op.create_index(
        "ix_recruitment_campaigns_cliente_id",
        "recruitment_campaigns",
        ["cliente_id"],
        unique=False,
    )
    op.create_index(
        "ix_recruitment_campaigns_version_perfil_id",
        "recruitment_campaigns",
        ["version_perfil_id"],
        unique=False,
    )
    op.create_index(
        "ix_recruitment_campaigns_estado",
        "recruitment_campaigns",
        ["estado"],
        unique=False,
    )

    op.create_table(
        "campaign_recruiter_assignments",
        sa.Column("convocatoria_id", sa.String(length=32), nullable=False),
        sa.Column("usuario_id", sa.String(length=32), nullable=False),
        sa.Column("asignado_por", sa.String(length=32), nullable=False),
        sa.Column(
            "asignado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ["convocatoria_id"], ["recruitment_campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asignado_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("convocatoria_id", "usuario_id"),
    )
    op.create_index(
        "ix_campaign_recruiter_user_campaign",
        "campaign_recruiter_assignments",
        ["usuario_id", "convocatoria_id"],
        unique=False,
    )

    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("convocatoria_id", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("reclutador_id", sa.String(length=32), nullable=True))

    conexion = op.get_bind()
    filas = conexion.execute(
        sa.text(
            """
            SELECT cliente_id, version_perfil_id, COUNT(*) AS cantidad,
                   MIN(creado_en) AS primera_fecha
            FROM applications
            GROUP BY cliente_id, version_perfil_id
            """
        )
    ).mappings()
    ahora = datetime.now(UTC)
    for fila in filas:
        cliente_id = str(fila["cliente_id"])
        version_id = str(fila["version_perfil_id"])
        convocatoria_id = _id_compatibilidad(cliente_id, version_id)
        estados = {
            str(valor)
            for valor in conexion.execute(
                sa.text(
                    """
                    SELECT DISTINCT estado FROM applications
                    WHERE cliente_id = :cliente_id AND version_perfil_id = :version_id
                    """
                ),
                {"cliente_id": cliente_id, "version_id": version_id},
            ).scalars()
        }
        cerrada = bool(estados) and estados.issubset(_TERMINALES)
        primera_fecha = fila["primera_fecha"]
        if isinstance(primera_fecha, str):
            fecha_apertura = primera_fecha[:10]
        elif primera_fecha is not None:
            fecha_apertura = primera_fecha.date()
        else:
            fecha_apertura = ahora.date()
        conexion.execute(
            sa.text(
                """
                INSERT INTO recruitment_campaigns (
                    id, cliente_id, version_perfil_id, codigo, vacantes_total,
                    fecha_apertura, fecha_objetivo, estado, motivo_cierre,
                    es_compatibilidad, cerrada_en, creado_en, actualizado_en, version
                ) VALUES (
                    :id, :cliente_id, :version_id, :codigo, :vacantes_total,
                    :fecha_apertura, NULL, :estado, :motivo_cierre,
                    1, :cerrada_en, :creado_en, :actualizado_en, 1
                )
                """
            ),
            {
                "id": convocatoria_id,
                "cliente_id": cliente_id,
                "version_id": version_id,
                "codigo": f"LEGACY-{version_id[:16]}",
                "vacantes_total": max(1, int(fila["cantidad"])),
                "fecha_apertura": fecha_apertura,
                "estado": "cerrada" if cerrada else "abierta",
                "motivo_cierre": "Migracion historica" if cerrada else None,
                "cerrada_en": ahora if cerrada else None,
                "creado_en": ahora,
                "actualizado_en": ahora,
            },
        )
        conexion.execute(
            sa.text(
                """
                UPDATE applications SET convocatoria_id = :convocatoria_id
                WHERE cliente_id = :cliente_id AND version_perfil_id = :version_id
                """
            ),
            {
                "convocatoria_id": convocatoria_id,
                "cliente_id": cliente_id,
                "version_id": version_id,
            },
        )

    pendientes = conexion.execute(
        sa.text("SELECT COUNT(*) FROM applications WHERE convocatoria_id IS NULL")
    ).scalar_one()
    if int(pendientes) != 0:
        raise RuntimeError("No fue posible asociar todas las postulaciones a una convocatoria")

    conexion.execute(
        sa.text(
            """
            UPDATE applications
            SET reclutador_id = (
                SELECT actor_id
                FROM audit_events
                WHERE audit_events.recurso_tipo = 'postulacion'
                  AND audit_events.recurso_id = applications.id
                  AND audit_events.accion = 'postulacion.creada'
                ORDER BY audit_events.ocurrido_en ASC
                LIMIT 1
            )
            WHERE reclutador_id IS NULL
            """
        )
    )

    with op.batch_alter_table("applications") as batch:
        batch.alter_column("convocatoria_id", existing_type=sa.String(length=32), nullable=False)
        batch.create_foreign_key(
            "fk_applications_campaign",
            "recruitment_campaigns",
            ["convocatoria_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_applications_recruiter",
            "users",
            ["reclutador_id"],
            ["id"],
        )
        batch.create_unique_constraint(
            "uq_application_campaign_candidate", ["convocatoria_id", "candidato_id"]
        )
        batch.create_index("ix_applications_convocatoria_id", ["convocatoria_id"], unique=False)
        batch.create_index(
            "ix_application_campaign_status", ["convocatoria_id", "estado"], unique=False
        )
        batch.create_index(
            "ix_application_client_candidate", ["cliente_id", "candidato_id"], unique=False
        )
        batch.create_index("ix_applications_reclutador_id", ["reclutador_id"], unique=False)
        batch.create_index(
            "ix_application_client_recruiter",
            ["cliente_id", "reclutador_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_index("ix_application_client_recruiter")
        batch.drop_index("ix_applications_reclutador_id")
        batch.drop_index("ix_application_client_candidate")
        batch.drop_index("ix_application_campaign_status")
        batch.drop_index("ix_applications_convocatoria_id")
        batch.drop_constraint("uq_application_campaign_candidate", type_="unique")
        batch.drop_constraint("fk_applications_recruiter", type_="foreignkey")
        batch.drop_constraint("fk_applications_campaign", type_="foreignkey")
        batch.drop_column("reclutador_id")
        batch.drop_column("convocatoria_id")

    op.drop_index(
        "ix_campaign_recruiter_user_campaign",
        table_name="campaign_recruiter_assignments",
    )
    op.drop_table("campaign_recruiter_assignments")
    op.drop_index("ix_recruitment_campaigns_estado", table_name="recruitment_campaigns")
    op.drop_index("ix_recruitment_campaigns_version_perfil_id", table_name="recruitment_campaigns")
    op.drop_index("ix_recruitment_campaigns_cliente_id", table_name="recruitment_campaigns")
    op.drop_index("ix_campaign_client_profile", table_name="recruitment_campaigns")
    op.drop_index("ix_campaign_client_status", table_name="recruitment_campaigns")
    op.drop_table("recruitment_campaigns")
