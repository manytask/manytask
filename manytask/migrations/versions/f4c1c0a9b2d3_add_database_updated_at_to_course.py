"""Add database_updated_at to course

Revision ID: f4c1c0a9b2d3
Revises: merge_14a8_e373
Create Date: 2025-12-23 13:53:30.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4c1c0a9b2d3"
down_revision: Union[str, None] = "merge_14a8_e373"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "courses",
        sa.Column(
            "database_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("courses", "database_updated_at")