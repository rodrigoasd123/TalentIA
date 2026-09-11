"""Base general de candidatos y estado operativo.

Revision ID: b72f13a8c901
Revises: a94109cb367c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b72f13a8c901"
down_revision: str | None = "a94109cb367c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    fields = [
        sa.Column("client", sa.String(160), nullable=False, server_default=""),
        sa.Column(
            "candidate_status",
            sa.String(32),
            nullable=False,
            server_default="pendiente_contacto",
        ),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("recruiter", sa.String(160), nullable=False, server_default=""),
        sa.Column("q", sa.String(80), nullable=False, server_default=""),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("reported_age", sa.Integer(), nullable=True),
        sa.Column("bgc", sa.String(160), nullable=False, server_default=""),
        sa.Column("technical_knowledge", sa.Text(), nullable=False, server_default=""),
        sa.Column("equifax_debt", sa.Float(), nullable=True),
        sa.Column("salary_expectation", sa.Float(), nullable=True),
        sa.Column("requested", sa.String(160), nullable=False, server_default=""),
        sa.Column("role_ctc", sa.Float(), nullable=True),
        sa.Column("ctc_variation_pct", sa.Float(), nullable=True),
        sa.Column("availability", sa.String(160), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    ]
    for field in fields:
        op.add_column("candidates", field)
    op.create_index("ix_candidates_candidate_status", "candidates", ["candidate_status"])


def downgrade() -> None:
    op.drop_index("ix_candidates_candidate_status", table_name="candidates")
    for name in reversed(
        [
            "client",
            "candidate_status",
            "record_date",
            "recruiter",
            "q",
            "birth_date",
            "reported_age",
            "bgc",
            "technical_knowledge",
            "equifax_debt",
            "salary_expectation",
            "requested",
            "role_ctc",
            "ctc_variation_pct",
            "availability",
            "notes",
        ]
    ):
        op.drop_column("candidates", name)
