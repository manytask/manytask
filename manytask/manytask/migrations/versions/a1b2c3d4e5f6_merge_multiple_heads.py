"""Merge multiple heads

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6, 5630538e6ecb
Create Date: 2026-02-26 15:22:29.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = ("f1a2b3c4d5e6", "5630538e6ecb")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
