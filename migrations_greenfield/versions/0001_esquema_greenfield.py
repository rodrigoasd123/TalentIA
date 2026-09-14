"""Marca base del esquema greenfield.

Revision ID: 0001_greenfield
"""

revision = "0001_greenfield"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Establece la marca base antes de crear el esquema explicito."""


def downgrade() -> None:
    """Retira la marca base despues de desmontar el esquema."""
