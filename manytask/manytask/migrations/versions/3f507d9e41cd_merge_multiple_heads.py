"""merge multiple heads

Revision ID: 3f507d9e41cd
Revises: 725a697ec7b9, merge_14a8_e373
Create Date: 2026-01-09 13:00:11.839505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f507d9e41cd'
down_revision: Union[str, None] = ('725a697ec7b9', 'merge_14a8_e373')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
