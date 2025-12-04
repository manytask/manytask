"""add student role to useronnamespace

Revision ID: 14a8f2b3c9d7
Revises: 6f154d0905ec
Create Date: 2025-11-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14a8f2b3c9d7'
down_revision: Union[str, None] = '6f154d0905ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'STUDENT' value to user_on_namespace_role enum
    op.execute("ALTER TYPE user_on_namespace_role ADD VALUE IF NOT EXISTS 'STUDENT'")


def downgrade() -> None:
    # Downgrading enum types is complex and typically not recommended
    # You would need to create a new type, migrate data, and drop the old type
    # For simplicity, we'll leave this as a no-op
    pass
