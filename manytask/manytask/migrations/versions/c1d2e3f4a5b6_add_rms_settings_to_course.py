"""Add rms settings (ci_config_path, protected_branches, rms_settings_pending) to courses

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('courses', sa.Column('ci_config_path', sa.String(), nullable=True))
    op.add_column('courses', sa.Column('protected_branches', sa.JSON(), nullable=True))
    op.add_column(
        'courses', sa.Column('rms_settings_pending', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('courses', 'rms_settings_pending')
    op.drop_column('courses', 'protected_branches')
    op.drop_column('courses', 'ci_config_path')
