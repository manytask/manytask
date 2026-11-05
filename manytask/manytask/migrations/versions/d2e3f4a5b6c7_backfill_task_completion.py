"""Initialize completion flags for scores already meeting min_score.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str = "c1d2e3f4a5b6"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute(
        "UPDATE grades SET is_solved = true FROM tasks "
        "WHERE grades.task_id = tasks.id AND grades.score >= tasks.min_score AND NOT grades.is_solved"
    )


def downgrade() -> None:
    # Completion flags also contain manual decisions, which must survive a downgrade.
    pass
