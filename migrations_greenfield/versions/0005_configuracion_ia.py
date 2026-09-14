"""agregar configuracion runtime de IA

Revision ID: 0005_configuracion_ia
Revises: 0004_seguridad
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_configuracion_ia"
down_revision = "0004_seguridad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_runtime_settings",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("proveedor", sa.String(length=30), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("temperatura", sa.Numeric(3, 2), nullable=False),
        sa.Column("tokens_maximos", sa.Integer(), nullable=False),
        sa.Column("clave_openai_cifrada", sa.Text(), nullable=True),
        sa.Column("clave_gemini_cifrada", sa.Text(), nullable=True),
        sa.Column("estado_conexion", sa.String(length=30), nullable=False),
        sa.Column("detalle_conexion", sa.String(length=160), nullable=False),
        sa.Column("latencia_ms", sa.Numeric(12, 3), nullable=True),
        sa.Column("ultima_verificacion_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_exito_en", sa.DateTime(timezone=True), nullable=True),
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
    )


def downgrade() -> None:
    op.drop_table("ai_runtime_settings")
