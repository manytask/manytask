"""Store every reported submission separately from aggregate grades.

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
"""

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: str = "d2e3f4a5b6c7"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Existing grades cannot reconstruct individual attempts; history starts here.
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_on_course_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(), server_default="OK", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("submit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_on_course_id"],
            ["users_on_courses.id"],
            name=op.f("fk_submissions_user_on_course_id_users_on_courses"),
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_submissions_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index("ix_submissions_user_task_time", "submissions", ["user_on_course_id", "task_id", "submit_time"])
    op.create_index(op.f("ix_submissions_task_id"), "submissions", ["task_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_submissions_task_id"), table_name="submissions")
    op.drop_index("ix_submissions_user_task_time", table_name="submissions")
    op.drop_table("submissions")
