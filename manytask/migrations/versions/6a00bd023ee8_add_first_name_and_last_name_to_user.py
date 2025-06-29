"""Add first_name and last_name to User

Revision ID: 6a00bd023ee8
Revises: 49870528e70a
Create Date: 2025-06-24 13:33:47.017795

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a00bd023ee8'
down_revision: Union[str, None] = '49870528e70a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # To avoid nulls in non-nullable colums, we do the following:
    # 1. Add nullable column
    # 2. Set default values ('') for existing rows
    # 3. Set column to be nullable=False

    op.add_column('users', sa.Column('first_name', sa.String(), nullable=True))
    op.execute("UPDATE users SET first_name = '' WHERE first_name IS NULL")
    op.alter_column('users', 'first_name', 
                    existing_type=sa.String(),
                    nullable=False)

    op.add_column('users', sa.Column('last_name', sa.String(), nullable=True))
    op.execute("UPDATE users SET last_name = '' WHERE last_name IS NULL")
    op.alter_column('users', 'last_name', 
                    existing_type=sa.String(),
                    nullable=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    # ### end Alembic commands ###
