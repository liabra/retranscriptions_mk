"""add client role to roleenum

Revision ID: 0004
Revises: 0003_upload_local
Create Date: 2026-04-05

fix (audit B10) : la migration 0001 crée `users.role` en TEXT ; le type `roleenum` n'existe
que si le schéma a été créé par SQLAlchemy (create_all). L'ajout de valeur est donc
conditionnel. SQLAlchemy enregistre le NOM du membre (« CLIENT ») : les deux graphies
sont ajoutées pour couvrir les deux modes de création. Sans effet si déjà appliquée.
"""
from alembic import op

revision = '0004'
down_revision = '0003_upload_local'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'roleenum') THEN
                ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'CLIENT';
                ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'client';
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    # PostgreSQL ne permet pas de retirer une valeur d'enum : sans effet.
    pass
