"""add_student_token_to_user_on_course

Revision ID: c7f0a91d4b28
Revises: a1b2c3d4e5f6
Create Date: 2026-08-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7f0a91d4b28'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users_on_courses', sa.Column('token', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_on_courses_token', 'users_on_courses', ['token'])


def downgrade() -> None:
    op.drop_constraint('uq_users_on_courses_token', 'users_on_courses', type_='unique')
    op.drop_column('users_on_courses', 'token')
