"""AI admin catalog, workflow node traces and benchmark history.

Revision ID: c310b61d28a4
Revises: f747b450b57a
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c310b61d28a4"
down_revision: str | None = "f747b450b57a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_providers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("adapter_type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("encrypted_credential", sa.Text(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_providers_is_enabled", "ai_providers", ["is_enabled"])
    op.create_table(
        "ai_models",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("input_price_per_million", sa.Float(), nullable=True),
        sa.Column("output_price_per_million", sa.Float(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id"),
    )
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    op.create_index("ix_ai_models_model_id", "ai_models", ["model_id"], unique=True)
    op.create_index("ix_ai_models_is_enabled", "ai_models", ["is_enabled"])
    with op.batch_alter_table("workflow_runs") as batch:
        batch.add_column(sa.Column("node_runs", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(
            sa.Column("mlflow_run_id", sa.String(length=64), nullable=False, server_default="")
        )
    op.create_table(
        "model_benchmark_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("started_by", sa.String(length=64), nullable=False),
        sa.Column("suite_version", sa.String(length=64), nullable=False),
        sa.Column("suite_hash", sa.String(length=64), nullable=False),
        sa.Column("graph_name", sa.String(length=64), nullable=False),
        sa.Column("graph_version", sa.String(length=32), nullable=False),
        sa.Column("baseline_model", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("ranking", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("mlflow_run_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_benchmark_started_by", "model_benchmark_runs", ["started_by"])
    op.create_index("ix_benchmark_suite", "model_benchmark_runs", ["suite_version"])
    op.create_index("ix_benchmark_baseline", "model_benchmark_runs", ["baseline_model"])
    op.create_index("ix_benchmark_status", "model_benchmark_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_benchmark_status", table_name="model_benchmark_runs")
    op.drop_index("ix_benchmark_baseline", table_name="model_benchmark_runs")
    op.drop_index("ix_benchmark_suite", table_name="model_benchmark_runs")
    op.drop_index("ix_benchmark_started_by", table_name="model_benchmark_runs")
    op.drop_table("model_benchmark_runs")
    with op.batch_alter_table("workflow_runs") as batch:
        batch.drop_column("mlflow_run_id")
        batch.drop_column("node_runs")
    op.drop_index("ix_ai_models_is_enabled", table_name="ai_models")
    op.drop_index("ix_ai_models_model_id", table_name="ai_models")
    op.drop_index("ix_ai_models_provider_id", table_name="ai_models")
    op.drop_table("ai_models")
    op.drop_index("ix_ai_providers_is_enabled", table_name="ai_providers")
    op.drop_table("ai_providers")
