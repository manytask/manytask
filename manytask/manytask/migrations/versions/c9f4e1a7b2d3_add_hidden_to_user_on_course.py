"""add_hidden_to_user_on_course

Revision ID: c9f4e1a7b2d3
Revises: a1b2c3d4e5f6
Create Date: 2026-08-25 20:24:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f4e1a7b2d3'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users_on_courses',
        sa.Column('hidden', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('users_on_courses', 'hidden')
