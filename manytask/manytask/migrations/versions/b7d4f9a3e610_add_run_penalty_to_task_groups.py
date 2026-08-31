"""Add run_penalty to task_groups

Revision ID: b7d4f9a3e610
Revises: f4a6c1d0b2e7
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d4f9a3e610'
down_revision: Union[str, None] = 'f4a6c1d0b2e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task_groups', sa.Column('run_penalty', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('task_groups', 'run_penalty')
