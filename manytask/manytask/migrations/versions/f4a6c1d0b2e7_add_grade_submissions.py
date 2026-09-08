"""Add grade_submissions table

Revision ID: f4a6c1d0b2e7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a6c1d0b2e7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('grade_submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('grade_id', sa.Integer(), nullable=False),
    sa.Column('raw_score', sa.Float(), nullable=False),
    sa.Column('submit_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('check_deadline', sa.Boolean(), nullable=False),
    sa.Column('flags', sa.String(), nullable=True),
    sa.Column('commit_sha', sa.String(length=64), nullable=True),
    sa.Column('job_id', sa.BigInteger(), nullable=True),
    sa.Column('ignored', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], name=op.f('fk_grade_submissions_grade_id_grades'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_grade_submissions'))
    )
    op.create_index(op.f('ix_grade_submissions_grade_id'), 'grade_submissions', ['grade_id'], unique=False)
    op.create_index(op.f('ix_grade_submissions_job_id'), 'grade_submissions', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_grade_submissions_job_id'), table_name='grade_submissions')
    op.drop_index(op.f('ix_grade_submissions_grade_id'), table_name='grade_submissions')
    op.drop_table('grade_submissions')
