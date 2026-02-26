"""add_auth_id_to_users

Revision ID: 5630538e6ecb
Revises: 3f507d9e41cd
Create Date: 2026-02-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5630538e6ecb"
down_revision: Union[str, None] = "3f507d9e41cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_id", sa.BigInteger(), nullable=True))
    # Convert rms_id to integer for auth_id (rms_id might be integer or string at this point)
    # For string rms_id values, cast to integer
    op.execute(
        "UPDATE users SET auth_id = CAST(rms_id AS BIGINT) WHERE rms_id IS NOT NULL AND CAST(rms_id AS TEXT) ~ '^[0-9]+$'"
    )
    # For non-numeric rms_id values or NULL values, use a default value
    op.execute("UPDATE users SET auth_id = -1 WHERE auth_id IS NULL")
    op.alter_column("users", "auth_id", nullable=False)
    op.create_unique_constraint(op.f("uq_users_auth_id"), "users", ["auth_id"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_users_auth_id"), "users", type_="unique")
    op.drop_column("users", "auth_id")
