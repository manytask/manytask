"""add_score_and_special_flags

Revision ID: 8c0eb289f000
Revises: bcca2f4efa74
Create Date: 2025-03-04 15:11:53.057083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c0eb289f000'
down_revision: Union[str, None] = 'bcca2f4efa74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    
    # These columns were manually added to the database, documenting them here for migration history
    op.add_column('tasks', sa.Column('score', sa.Integer(), server_default='100', nullable=False))
    op.add_column('tasks', sa.Column('is_special', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('task_groups', sa.Column('is_special', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('courses', sa.Column('unique_course_name', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_admin_token', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_course_group', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_course_public_repo', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_course_students_group', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_default_branch', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_client_id', sa.String(), server_default='', nullable=False))
    op.add_column('courses', sa.Column('gitlab_client_secret', sa.String(), server_default='', nullable=False))
    
    # Make columns non-nullable
    op.alter_column('courses', 'unique_course_name',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_admin_token',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_course_group',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_course_public_repo',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_course_students_group',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_default_branch',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_client_id',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('courses', 'gitlab_client_secret',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.alter_column('task_groups', 'is_special',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
    op.alter_column('tasks', 'is_special',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('false'))
    op.alter_column('tasks', 'score',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('100'))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('tasks', 'score',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=sa.text('100'))
    op.alter_column('tasks', 'is_special',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
    op.alter_column('task_groups', 'is_special',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('false'))
    op.alter_column('courses', 'gitlab_client_secret',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'gitlab_client_id',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'gitlab_default_branch',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'gitlab_course_students_group',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'gitlab_course_public_repo',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'gitlab_course_group',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'gitlab_admin_token',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.alter_column('courses', 'unique_course_name',
               existing_type=sa.VARCHAR(),
               nullable=True)
    
    # Document the manual changes that would need to be reverted
    # op.drop_column('task_groups', 'is_special')
    # op.drop_column('tasks', 'is_special')
    # op.drop_column('tasks', 'score')
    # ### end Alembic commands ###
