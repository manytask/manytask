"""Add the course permission to preview future tasks.

Revision ID: 7e42f751a901
Revises: a1b2c3d4e5f6
"""

import sqlalchemy as sa
from alembic import op

revision: str = "7e42f751a901"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("allow_future_tasks", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("courses", "allow_future_tasks")
