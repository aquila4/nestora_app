"""add property type

Revision ID: ab177423689f
Revises: 0e726caaf471
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

revision = 'ab177423689f'
down_revision = '0e726caaf471'
branch_labels = None
depends_on = None


def upgrade():
    # already exists in database, nothing to do
    pass


def downgrade():
    # nothing to undo since we didn't apply anything
    pass