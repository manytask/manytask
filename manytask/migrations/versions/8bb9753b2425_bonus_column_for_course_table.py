"""bonus column for course table

Revision ID: 8bb9753b2425
Revises: 2226e9ac60f3
Create Date: 2025-09-08 17:34:49.511803

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from manytask.models import Course, Deadline, Task, TaskGroup

# revision identifiers, used by Alembic.
revision: str = "8bb9753b2425"
down_revision: Union[str, None] = "2226e9ac60f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    for course in session.query(Course).all():
        bonus_group = (
            session.query(TaskGroup).filter(TaskGroup.course_id == course.id, TaskGroup.name == "Bonus group").first()
        )
        if not bonus_group:
            deadline = Deadline()
            bonus_group = TaskGroup(
                name="Bonus group",
                course_id=course.id,
                deadline=deadline,
                position=9999,
            )
            session.add(bonus_group)
            session.flush()

        bonus_task = session.query(Task).filter(Task.group_id == bonus_group.id, Task.name == "bonus_score").first()
        if not bonus_task:
            bonus_task = Task(
                name="bonus_score",
                group_id=bonus_group.id,
                score=0,
                enabled=False,
                position=0,
            )
            session.add(bonus_task)

    session.commit()


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)

    tasks = session.query(Task).filter(Task.name == "bonus_score").all()
    for task in tasks:
        session.delete(task)

    groups = session.query(TaskGroup).filter(TaskGroup.name == "Bonus group").all()
    for group in groups:
        session.delete(group)

    session.commit()
