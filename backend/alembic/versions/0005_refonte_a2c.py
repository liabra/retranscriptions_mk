"""refonte A2C : trois suivis de statut, audios, livraisons PV, notifications, encaissements

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16

Migration STRICTEMENT ADDITIVE : aucune table ni colonne existante n'est supprimée ou modifiée.
Les statuts sont stockés en texte (pas d'enum PostgreSQL natif) pour fonctionner quel que soit
le mode de création initial du schéma.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column) -> None:
    if not _has_column(table, column.name):
        op.add_column(table, column)


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────
    _add("users", sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()))
    _add("users", sa.Column("token_version", sa.Integer, nullable=False, server_default="0"))
    _add("users", sa.Column("permissions", JSONB, nullable=True))
    _add("users", sa.Column("notif_email", sa.Boolean, nullable=False, server_default=sa.true()))
    _add("users", sa.Column("prestataire_id", UUID, sa.ForeignKey("prestataires.id"), nullable=True))
    _add("users", sa.Column("client_id", UUID, sa.ForeignKey("clients.id"), nullable=True))
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_prestataire_id ON users (prestataire_id) "
               "WHERE prestataire_id IS NOT NULL")

    # ── dossiers ──────────────────────────────────────────────────────────
    _add("dossiers", sa.Column("statut_production", sa.String(30), nullable=False, server_default="a_qualifier"))
    _add("dossiers", sa.Column("statut_facturation", sa.String(30), nullable=False, server_default="non_applicable"))
    _add("dossiers", sa.Column("statut_avant_blocage", sa.String(30), nullable=True))
    _add("dossiers", sa.Column("motif_blocage", sa.Text, nullable=True))
    _add("dossiers", sa.Column("supprime_le", sa.DateTime(timezone=True), nullable=True))
    _add("dossiers", sa.Column("valide_le", sa.DateTime(timezone=True), nullable=True))
    op.execute("CREATE INDEX IF NOT EXISTS ix_dossiers_statut_production ON dossiers (statut_production)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dossiers_statut_facturation ON dossiers (statut_facturation)")

    # ── prestataires / factures ──────────────────────────────────────────
    _add("prestataires", sa.Column("specialites", JSONB, nullable=True))
    _add("prestataires", sa.Column("notes_internes", sa.Text, nullable=True))
    _add("factures_clients", sa.Column("montant_encaisse", sa.Numeric(10, 2), nullable=False, server_default="0"))
    _add("factures_clients", sa.Column("annulee_le", sa.DateTime(timezone=True), nullable=True))
    _add("factures_clients", sa.Column("motif_annulation", sa.Text, nullable=True))

    # ── nouvelles tables ─────────────────────────────────────────────────
    if not _has_table("stockage_fichiers"):
        op.create_table(
            "stockage_fichiers",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("contenu", sa.LargeBinary, nullable=False),
            sa.Column("taille_octets", sa.BigInteger, nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if not _has_table("audios"):
        op.create_table(
            "audios",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("dossier_id", UUID, sa.ForeignKey("dossiers.id"), nullable=True, index=True),
            sa.Column("client_id", UUID, sa.ForeignKey("clients.id"), nullable=True),
            sa.Column("nom_fichier", sa.String(500), nullable=False),
            sa.Column("taille_octets", sa.BigInteger, nullable=True),
            sa.Column("mime_type", sa.String(100), nullable=True),
            sa.Column("duree_minutes", sa.Integer, nullable=True),
            sa.Column("origine", sa.String(30), nullable=False),
            sa.Column("stockage", sa.String(20), nullable=False, server_default="onedrive"),
            sa.Column("drive_id", sa.String(200), nullable=True),
            sa.Column("item_id", sa.String(200), nullable=True),
            sa.Column("chemin_local", sa.Text, nullable=True),
            sa.Column("lien_prive_chiffre", sa.Text, nullable=True),
            sa.Column("etag", sa.String(200), nullable=True),
            sa.Column("statut", sa.String(20), nullable=False, server_default="a_traiter", index=True),
            sa.Column("disponible", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("verifie_le", sa.DateTime(timezone=True), nullable=True),
            sa.Column("message_verification", sa.Text, nullable=True),
            sa.Column("ajoute_par_id", UUID, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("drive_id", "item_id", name="uq_audios_drive_item"),
        )
    if not _has_table("livraisons"):
        op.create_table(
            "livraisons",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("dossier_id", UUID, sa.ForeignKey("dossiers.id"), nullable=False, index=True),
            sa.Column("affectation_id", UUID, sa.ForeignKey("affectations.id"), nullable=True, index=True),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("type_depot", sa.String(30), nullable=False, server_default="depot_prestataire"),
            sa.Column("nom_original", sa.String(500), nullable=False),
            sa.Column("taille_octets", sa.BigInteger, nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("stockage", sa.String(20), nullable=False),
            sa.Column("stockage_ref", sa.String(300), nullable=False),
            sa.Column("drive_id", sa.String(200), nullable=True),
            sa.Column("statut_controle", sa.String(20), nullable=False),
            sa.Column("rapport_controle", JSONB, nullable=True),
            sa.Column("pages_declarees", sa.Integer, nullable=True),
            sa.Column("commentaire", sa.Text, nullable=True),
            sa.Column("depose_par_id", UUID, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("depose_le", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("dossier_id", "version", name="uq_livraisons_dossier_version"),
        )
    if not _has_table("demandes_correction"):
        op.create_table(
            "demandes_correction",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("dossier_id", UUID, sa.ForeignKey("dossiers.id"), nullable=False, index=True),
            sa.Column("affectation_id", UUID, sa.ForeignKey("affectations.id"), nullable=True),
            sa.Column("livraison_id", UUID, sa.ForeignKey("livraisons.id"), nullable=True),
            sa.Column("message", sa.Text, nullable=False),
            sa.Column("date_limite", sa.DateTime(timezone=True), nullable=True),
            sa.Column("demandee_par_id", UUID, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("resolue_par_livraison_id", UUID, sa.ForeignKey("livraisons.id"), nullable=True),
            sa.Column("resolue_le", sa.DateTime(timezone=True), nullable=True),
        )
    if not _has_table("encaissements"):
        op.create_table(
            "encaissements",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("facture_id", UUID, sa.ForeignKey("factures_clients.id"), nullable=False, index=True),
            sa.Column("montant", sa.Numeric(10, 2), nullable=False),
            sa.Column("date_encaissement", sa.Date, nullable=False),
            sa.Column("mode", sa.String(30), nullable=True),
            sa.Column("reference", sa.String(100), nullable=True),
            sa.Column("commentaire", sa.Text, nullable=True),
            sa.Column("saisi_par_id", UUID, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if not _has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("titre", sa.String(300), nullable=False),
            sa.Column("message", sa.Text, nullable=True),
            sa.Column("lien", sa.String(300), nullable=True),
            sa.Column("dossier_id", UUID, sa.ForeignKey("dossiers.id"), nullable=True),
            sa.Column("dedup_key", sa.String(200), nullable=True),
            sa.Column("email_statut", sa.String(20), nullable=False, server_default="non_demande"),
            sa.Column("lu_le", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
            sa.UniqueConstraint("user_id", "dedup_key", name="uq_notifications_dedup"),
        )
    if not _has_table("graph_sync_state"):
        op.create_table(
            "graph_sync_state",
            sa.Column("id", sa.String(50), primary_key=True),
            sa.Column("delta_link", sa.Text, nullable=True),
            sa.Column("derniere_execution", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dernier_succes", sa.DateTime(timezone=True), nullable=True),
            sa.Column("derniere_erreur", sa.Text, nullable=True),
            sa.Column("echecs_consecutifs", sa.Integer, nullable=False, server_default="0"),
            sa.Column("nouveaux_detectes", sa.Integer, nullable=False, server_default="0"),
        )

    # ── reprise des données existantes (aucune perte : l'ancien statut est conservé) ──
    op.execute("""
        UPDATE dossiers SET statut_production = CASE lower(statut::text)
            WHEN 'recu' THEN 'a_qualifier' WHEN 'en_qualification' THEN 'a_qualifier'
            WHEN 'incomplet' THEN 'a_qualifier'
            WHEN 'estime' THEN 'a_attribuer' WHEN 'a_attribuer' THEN 'a_attribuer'
            WHEN 'en_retranscription' THEN 'en_cours'
            WHEN 'a_corriger' THEN 'livre'
            WHEN 'en_correction' THEN 'a_relire' WHEN 'en_mise_en_forme' THEN 'a_relire'
            WHEN 'calcul_en_cours' THEN 'a_controler' WHEN 'a_valider' THEN 'a_controler'
            WHEN 'envoye' THEN 'valide' WHEN 'facture' THEN 'valide'
            WHEN 'paye_entrant' THEN 'valide' WHEN 'prestataires_payes' THEN 'valide'
            WHEN 'archive' THEN 'archive' WHEN 'bloque' THEN 'bloque'
            ELSE 'a_qualifier' END,
        statut_facturation = CASE lower(statut::text)
            WHEN 'envoye' THEN 'a_etablir' WHEN 'facture' THEN 'emise'
            WHEN 'paye_entrant' THEN 'reglee' WHEN 'prestataires_payes' THEN 'reglee'
            ELSE 'non_applicable' END
    """)
    op.execute("UPDATE factures_clients SET montant_encaisse = montant_ttc WHERE lower(statut_paiement::text) = 'soldee'")
    # Liaison explicite compte ↔ fiche, uniquement si l'email est sans ambiguïté
    op.execute("""
        UPDATE users u SET prestataire_id = p.id FROM prestataires p
        WHERE lower(u.role::text) IN ('retranscripteur', 'correcteur') AND u.prestataire_id IS NULL
          AND lower(p.email) = lower(u.email)
          AND (SELECT count(*) FROM prestataires p2 WHERE lower(p2.email) = lower(u.email)) = 1
    """)
    op.execute("""
        UPDATE users u SET client_id = c.id FROM clients c
        WHERE lower(u.role::text) = 'client' AND u.client_id IS NULL
          AND lower(c.email_contact) = lower(u.email)
          AND (SELECT count(*) FROM clients c2 WHERE lower(c2.email_contact) = lower(u.email)) = 1
    """)


def downgrade() -> None:
    for table in ("graph_sync_state", "notifications", "encaissements", "demandes_correction",
                  "livraisons", "audios", "stockage_fichiers"):
        if _has_table(table):
            op.drop_table(table)
    op.execute("DROP INDEX IF EXISTS uq_users_prestataire_id")
    op.execute("DROP INDEX IF EXISTS ix_dossiers_statut_production")
    op.execute("DROP INDEX IF EXISTS ix_dossiers_statut_facturation")
    for table, cols in (
        ("factures_clients", ("motif_annulation", "annulee_le", "montant_encaisse")),
        ("prestataires", ("notes_internes", "specialites")),
        ("dossiers", ("valide_le", "supprime_le", "motif_blocage", "statut_avant_blocage",
                      "statut_facturation", "statut_production")),
        ("users", ("client_id", "prestataire_id", "notif_email", "permissions", "token_version",
                   "must_change_password")),
    ):
        for col in cols:
            if _has_column(table, col):
                op.drop_column(table, col)
