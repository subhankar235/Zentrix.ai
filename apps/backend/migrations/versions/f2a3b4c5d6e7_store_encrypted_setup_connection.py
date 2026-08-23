"""Store encrypted setup credentials for monitoring-role repair."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "database_connections",
        sa.Column("encrypted_setup_connection_string", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("database_connections", "encrypted_setup_connection_string")
