"""Merge heads 14a8f2b3c9d7 and e3734758a52e

Revision ID: merge_14a8_e373
Revises: 14a8f2b3c9d7, e3734758a52e
Create Date: 2025-12-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_14a8_e373'
down_revision: Union[str, Sequence[str], None] = ('14a8f2b3c9d7', 'e3734758a52e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration, no changes needed
    pass


def downgrade() -> None:
    # This is a merge migration, no changes needed
    pass

