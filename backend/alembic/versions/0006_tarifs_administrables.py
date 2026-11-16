"""tarifs administrables : familles de versions, brouillons, majorations paramétrables

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16

Migration STRICTEMENT ADDITIVE. Reprise :
- chaque grille existante devient la première version de sa propre famille ;
- majorations « sans prise de notes » et « prestation particulière » : appliquées au client
  uniquement (comportement actuel du calcul) ; urgence : client et retranscripteur (comportement actuel).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLS = [
    sa.Column("famille_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("brouillon", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("type_instance", sa.String(20), nullable=True),
    sa.Column("applique_client", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("applique_retranscripteur", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("conditions", postgresql.JSONB(), nullable=True),
]


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("grilles_tarifaires")}
    for col in COLS:
        if col.name not in existing:
            op.add_column("grilles_tarifaires", col)
    op.execute("CREATE INDEX IF NOT EXISTS ix_grilles_famille_id ON grilles_tarifaires (famille_id)")
    op.execute("UPDATE grilles_tarifaires SET famille_id = id WHERE famille_id IS NULL")
    op.execute("UPDATE grilles_tarifaires SET applique_retranscripteur = false "
               "WHERE lower(type::text) IN ('snp', 'special')")
    op.execute("""UPDATE grilles_tarifaires SET conditions =
                  '{"case_cochee": true, "dossier_signale_urgent": true, "delai_max_jours": null}'::jsonb
                  WHERE lower(type::text) = 'urgence' AND conditions IS NULL""")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_grilles_famille_id")
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("grilles_tarifaires")}
    for col in reversed(COLS):
        if col.name in existing:
            op.drop_column("grilles_tarifaires", col.name)
