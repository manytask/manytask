"""Add is_large flag to Task

Revision ID: 49870528e70a
Revises: b608e9f744f4
Create Date: 2025-06-17 17:31:38.981986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49870528e70a'
down_revision: Union[str, None] = 'b608e9f744f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tasks', sa.Column('is_large', sa.Boolean(), server_default='false', nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tasks', 'is_large')
    # ### end Alembic commands ###
