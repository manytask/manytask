"""Init migration

Revision ID: a7c68744b7a5
Revises: 
Create Date: 2025-01-31 03:31:29.653859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c68744b7a5'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('gitlab_instance_host', sa.String(), nullable=False),
    sa.Column('registration_secret', sa.String(), nullable=False),
    sa.Column('show_allscores', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('deadlines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('gitlab_instance_host', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username', 'gitlab_instance_host', name='_username_gitlab_instance_uc')
    )
    op.create_table('task_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('deadline_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['deadline_id'], ['deadlines.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users_on_courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('repo_name', sa.String(), nullable=False),
    sa.Column('join_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_course_admin', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'course_id', name='_user_course_uc')
    )
    op.create_table('tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('is_bonus', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['task_groups.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('grades',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_on_course_id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('last_submit_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.ForeignKeyConstraint(['user_on_course_id'], ['users_on_courses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_on_course_id', 'task_id', name='_user_on_course_task_uc')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('grades')
    op.drop_table('tasks')
    op.drop_table('users_on_courses')
    op.drop_table('task_groups')
    op.drop_table('users')
    op.drop_table('deadlines')
    op.drop_table('courses')
    # ### end Alembic commands ###