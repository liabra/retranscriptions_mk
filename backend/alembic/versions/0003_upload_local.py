"""add url_fichier_local to fichiers_dossier

Revision ID: 0003_upload_local
Revises: 0002_fichiers_dossier
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_upload_local'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # url_onedrive est déjà TEXT NOT NULL — on le rend nullable
    # pour permettre les uploads locaux sans URL OneDrive
    op.alter_column('fichiers_dossier', 'url_onedrive',
                    existing_type=sa.Text(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('fichiers_dossier', 'url_onedrive',
                    existing_type=sa.Text(),
                    nullable=False)
