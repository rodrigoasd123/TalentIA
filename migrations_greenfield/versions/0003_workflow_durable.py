"""agregar lease, correlacion y checkpoint por nodo

Revision ID: 0003_workflow
Revises: 0002_esquema
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_workflow"
down_revision = "0002_esquema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_jobs") as batch:
        batch.add_column(sa.Column("lease_token", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("lease_expira_en", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("correlacion_id", sa.String(length=40), nullable=False, server_default="")
        )
        batch.add_column(
            sa.Column("timeout_segundos", sa.Integer(), nullable=False, server_default="60")
        )
        batch.create_index("ix_agent_jobs_lease_expira_en", ["lease_expira_en"], unique=False)
        batch.create_index("ix_agent_jobs_correlacion_id", ["correlacion_id"], unique=False)
    with op.batch_alter_table("workflow_checkpoints") as batch:
        batch.create_unique_constraint("uq_checkpoint_job_node", ["trabajo_id", "nodo"])


def downgrade() -> None:
    with op.batch_alter_table("workflow_checkpoints") as batch:
        batch.drop_constraint("uq_checkpoint_job_node", type_="unique")
    with op.batch_alter_table("agent_jobs") as batch:
        batch.drop_index("ix_agent_jobs_correlacion_id")
        batch.drop_index("ix_agent_jobs_lease_expira_en")
        batch.drop_column("timeout_segundos")
        batch.drop_column("correlacion_id")
        batch.drop_column("lease_expira_en")
        batch.drop_column("lease_token")
