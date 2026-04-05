"""add client role to roleenum

Revision ID: 0004
Revises: 0003_upload_local
Create Date: 2026-04-05
"""
from alembic import op

revision = '0004'
down_revision = '0003_upload_local'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: ADD VALUE is safe even if already present (IF NOT EXISTS)
    op.execute("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'client'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # Downgrade is a no-op — the value is simply unused if the role is removed from code.
    pass
