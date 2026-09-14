"""endurecer autenticacion y revocacion de sesiones

Revision ID: 0004_seguridad
Revises: 0003_workflow
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_seguridad"
down_revision = "0003_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("intentos_fallidos", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "contrasena_cambiada_en",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            )
        )
        batch.add_column(
            sa.Column("sesion_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.create_index("ix_users_bloqueado_hasta", ["bloqueado_hasta"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_bloqueado_hasta")
        batch.drop_column("sesion_version")
        batch.drop_column("contrasena_cambiada_en")
        batch.drop_column("bloqueado_hasta")
        batch.drop_column("intentos_fallidos")
