"""Mark telemetry rows by their collection source."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e8a1c7d4f203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("query_metrics", "table_metrics", "plan_metrics"):
        op.add_column(table, sa.Column("capture_source", sa.String(length=50), nullable=True))
        op.create_index(
            f"ix_{table}_capture_source",
            table,
            ["capture_source"],
            unique=False,
        )


def downgrade() -> None:
    for table in ("plan_metrics", "table_metrics", "query_metrics"):
        op.drop_index(f"ix_{table}_capture_source", table_name=table)
        op.drop_column(table, "capture_source")
