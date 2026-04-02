"""fichiers_dossier

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-02 00:00:00.000000

Ajoute la table fichiers_dossier pour la gestion documentaire OneDrive.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    from sqlalchemy import inspect
    return inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _table_exists("fichiers_dossier"):
        op.create_table(
            "fichiers_dossier",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("dossiers.id"), nullable=False),
            sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("users.id"), nullable=True),
            sa.Column("type_document", sa.Text, nullable=False),
            sa.Column("nom_fichier", sa.String(500), nullable=False),
            sa.Column("url_onedrive", sa.Text, nullable=False),
            sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
            sa.Column("statut", sa.Text, nullable=False, server_default="disponible"),
            sa.Column("commentaire", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_fichiers_dossier_id ON fichiers_dossier (dossier_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_fichiers_dossier_id")
    op.drop_table("fichiers_dossier")
