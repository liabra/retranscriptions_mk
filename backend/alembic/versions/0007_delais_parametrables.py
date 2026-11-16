"""délais de réalisation et paramètres métier administrables ; urgence désactivée par défaut

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16

Schéma : strictement additif (2 tables, 3 colonnes).
Données :
- la configuration initiale des délais et paramètres est créée par seed_parametres.py ;
- majoration d'urgence désactivée tant que la cliente n'a pas confirmé sa règle
  (les calculs déjà enregistrés ne sont pas modifiés).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)

def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("regles_delai"):
        op.create_table(
            "regles_delai",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("libelle", sa.String(200), nullable=False),
            sa.Column("actif", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("priorite", sa.Integer, nullable=False, server_default="100"),
            sa.Column("type_instance", sa.String(20), nullable=True),
            sa.Column("duree_min_minutes", sa.Integer, nullable=True),
            sa.Column("duree_max_minutes", sa.Integer, nullable=True),
            sa.Column("urgence", sa.Boolean, nullable=True),
            sa.Column("prestation", sa.String(20), nullable=True),
            sa.Column("delai_jours", sa.Integer, nullable=False),
            sa.Column("type_jours", sa.String(20), nullable=False, server_default="calendaires"),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("modifie_par_id", UUID, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if not _has_table("parametres"):
        op.create_table(
            "parametres",
            sa.Column("cle", sa.String(80), primary_key=True),
            sa.Column("valeur", postgresql.JSONB(), nullable=True),
            sa.Column("modifie_par_id", UUID, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("dossiers")}
    if "echeance_mode" not in existing:
        # Échéances existantes : saisies à la main jusqu'ici
        op.add_column("dossiers", sa.Column("echeance_mode", sa.String(20), nullable=False, server_default="manuelle"))
    if "echeance_detail" not in existing:
        op.add_column("dossiers", sa.Column("echeance_detail", postgresql.JSONB(), nullable=True))
    if "echeance_figee_le" not in existing:
        op.add_column("dossiers", sa.Column("echeance_figee_le", sa.DateTime(timezone=True), nullable=True))
        # Dossiers déjà attribués : échéance considérée comme figée
        op.execute("""UPDATE dossiers d SET echeance_figee_le = (SELECT min(a.date_attribution) FROM affectations a
                      WHERE a.dossier_id = d.id) WHERE EXISTS (SELECT 1 FROM affectations a WHERE a.dossier_id = d.id)""")

    # Majoration d'urgence : désactivée tant que la règle n'est pas confirmée
    op.execute("UPDATE grilles_tarifaires SET active = false "
               "WHERE lower(type::text) = 'urgence' AND active = true AND brouillon = false")


def downgrade() -> None:
    for col in ("echeance_figee_le", "echeance_detail", "echeance_mode"):
        if col in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("dossiers")}:
            op.drop_column("dossiers", col)
    for t in ("parametres", "regles_delai"):
        if _has_table(t):
            op.drop_table(t)
