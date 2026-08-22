"""Remove duplicate targets and enforce one connection per owner/target."""

from typing import Sequence, Union

from alembic import op


revision: str = "d4f7b9c2a1e0"
down_revision: Union[str, None] = "c6c36b82a139"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY user_id, lower(host), port,
                                        lower(database_name), lower(username)
                           ORDER BY created_at DESC, id DESC
                       ) AS row_number
                FROM database_connections
            )
            DELETE FROM database_connections
            WHERE id IN (SELECT id FROM ranked WHERE row_number > 1)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_database_connections_owner_target
        ON database_connections (
            user_id,
            lower(host),
            port,
            lower(database_name),
            lower(username)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_database_connections_owner_target")
