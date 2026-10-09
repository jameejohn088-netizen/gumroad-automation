"""add last_error columns to gumroad_accounts

Revision ID: 9f2c4a1b7d3e
Revises: 347ec07a3a73
Create Date: 2026-10-09 15:20:00.000000

Surfaces the last Gumroad API error per account on the dashboard
(requirement: show each account's connection status and API errors).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f2c4a1b7d3e'
down_revision: Union[str, None] = '347ec07a3a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gumroad_accounts',
                  sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('gumroad_accounts',
                  sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('gumroad_accounts', 'last_error_at')
    op.drop_column('gumroad_accounts', 'last_error')
