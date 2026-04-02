"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

Schéma complet v2.0 :
  - users, clients, prestataires
  - grilles_tarifaires, regles_tarifaires, calculs_tarifaires (moteur tarifaire)
  - dossiers, affectations
  - journal_activites, incidents_qualite
  - factures_clients, paiements_prestataires
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    from sqlalchemy import inspect
    bind = op.get_bind()
    return inspect(bind).has_table(table_name)


def upgrade() -> None:
    # ── ENUMS ──────────────────────────────────────────────────────────────
    # IF NOT EXISTS : idempotent si la migration est rejouée après un crash partiel
    op.execute("CREATE TYPE IF NOT EXISTS roleenum AS ENUM ('administratrice','coordinatrice','retranscripteur','correcteur','comptabilite','lecture_seule')")
    op.execute("CREATE TYPE IF NOT EXISTS typeclientenum AS ENUM ('CE','CMAS','CSSCT','Syndicat','Autre')")
    op.execute("CREATE TYPE IF NOT EXISTS roleprestaenum AS ENUM ('retranscripteur','correcteur','les_deux')")
    op.execute("CREATE TYPE IF NOT EXISTS statutdossierenum AS ENUM ('recu','en_qualification','estime','a_attribuer','en_retranscription','a_corriger','en_correction','en_mise_en_forme','calcul_en_cours','a_valider','envoye','facture','paye_entrant','prestataires_payes','archive','bloque','incomplet')")
    op.execute("CREATE TYPE IF NOT EXISTS typeinstanceenum AS ENUM ('CE','CMAS','CSSCT','Autre')")
    op.execute("CREATE TYPE IF NOT EXISTS niveauconfidentialiteenum AS ENUM ('standard','renforce','absolu')")
    op.execute("CREATE TYPE IF NOT EXISTS statutaffectationenum AS ENUM ('en_attente','en_cours','livre','valide','rejete')")
    op.execute("CREATE TYPE IF NOT EXISTS roleaffectationenum AS ENUM ('retranscripteur','correcteur')")
    op.execute("CREATE TYPE IF NOT EXISTS typeactionenum AS ENUM ('creation','statut','affectation','envoi','paiement','ajustement_tarifaire','note','config_grille','calcul_tarifaire','incident','archivage','auth','acces_document')")
    op.execute("CREATE TYPE IF NOT EXISTS graviteenum AS ENUM ('mineur','majeur','bloquant')")
    op.execute("CREATE TYPE IF NOT EXISTS statutincidentenum AS ENUM ('ouvert','en_cours','resolu')")
    op.execute("CREATE TYPE IF NOT EXISTS statutpaiementenum AS ENUM ('non_payee','partiellement','soldee')")
    op.execute("CREATE TYPE IF NOT EXISTS statutpaiementprestaenum AS ENUM ('a_payer','valide','paye')")
    op.execute("CREATE TYPE IF NOT EXISTS rolepayeenum AS ENUM ('retranscripteur','correcteur')")
    op.execute("CREATE TYPE IF NOT EXISTS typegrilleenum AS ENUM ('client','retranscripteur','correcteur','urgence','snp','special','prise_de_note')")
    op.execute("CREATE TYPE IF NOT EXISTS ciblegrilleenum AS ENUM ('global','client_specifique','prestataire_specifique')")
    op.execute("CREATE TYPE IF NOT EXISTS typerègleenum AS ENUM ('base','majoration','remise','forfait','plancher','plafond')")
    op.execute("CREATE TYPE IF NOT EXISTS conditiontypeenum AS ENUM ('toujours','si_type_instance','si_urgence','si_snp','si_special','si_duree','si_volume','si_client','combinee')")
    op.execute("CREATE TYPE IF NOT EXISTS modecalculenum AS ENUM ('par_page','forfait_fixe','pourcentage_base','pourcentage_total','multiplicateur')")
    op.execute("CREATE TYPE IF NOT EXISTS statutcalculenum AS ENUM ('estimatif','definitif','ajuste')")

    # ── USERS ──────────────────────────────────────────────────────────────
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("nom", sa.String(255), nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("role", sa.Enum("administratrice","coordinatrice","retranscripteur","correcteur","comptabilite","lecture_seule", name="roleenum", create_type=False), nullable=False),
            sa.Column("actif", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # ── GRILLES_TARIFAIRES (avant clients/prestataires car FK) ─────────────
    if not _table_exists("grilles_tarifaires"):
        op.create_table(
            "grilles_tarifaires",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("nom", sa.String(255), nullable=False),
            sa.Column("type", sa.Text, nullable=False),
            sa.Column("cible", sa.Text, nullable=False, server_default="global"),
            sa.Column("cible_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
            sa.Column("date_debut", sa.Date, nullable=False),
            sa.Column("date_fin", sa.Date, nullable=True),
            sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("creee_par_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("date_creation", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_grilles_type ON grilles_tarifaires (type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_grilles_cible_id ON grilles_tarifaires (cible_id)")

    # ── REGLES_TARIFAIRES ─────────────────────────────────────────────────
    if not _table_exists("regles_tarifaires"):
        op.create_table(
            "regles_tarifaires",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("grille_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grilles_tarifaires.id", ondelete="CASCADE"), nullable=False),
            sa.Column("libelle", sa.String(255), nullable=False),
            sa.Column("type_regle", sa.Text, nullable=False),
            sa.Column("condition_type", sa.Text, nullable=False, server_default="toujours"),
            sa.Column("condition_valeur", postgresql.JSONB, nullable=True),
            sa.Column("mode_calcul", sa.Text, nullable=False),
            sa.Column("valeur", sa.Numeric(10, 4), nullable=False),
            sa.Column("unite", sa.String(50), nullable=True),
            sa.Column("priorite", sa.Integer, nullable=False, server_default="100"),
            sa.Column("cumulable", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("plafond_montant", sa.Numeric(10, 2), nullable=True),
            sa.Column("actif", sa.Boolean, nullable=False, server_default="true"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_regles_grille_id ON regles_tarifaires (grille_id)")

    # ── CLIENTS ───────────────────────────────────────────────────────────
    if not _table_exists("clients"):
        op.create_table(
            "clients",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("nom", sa.String(255), nullable=False),
            sa.Column("type", sa.Text, nullable=False),
            sa.Column("entreprise_mere", sa.String(255), nullable=True),
            sa.Column("contact_principal", sa.String(255), nullable=True),
            sa.Column("email_contact", sa.String(255), nullable=True),
            sa.Column("telephone", sa.String(50), nullable=True),
            sa.Column("adresse", sa.Text, nullable=True),
            sa.Column("conditions_paiement", sa.String(100), nullable=True),
            sa.Column("grille_tarifaire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grilles_tarifaires.id"), nullable=True),
            sa.Column("actif", sa.Boolean, nullable=False, server_default="true"),
        )

    # ── PRESTATAIRES ──────────────────────────────────────────────────────
    if not _table_exists("prestataires"):
        op.create_table(
            "prestataires",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("nom", sa.String(255), nullable=False),
            sa.Column("role", sa.Text, nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("telephone", sa.String(50), nullable=True),
            sa.Column("disponible", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("charge_actuelle", sa.Integer, nullable=False, server_default="0"),
            sa.Column("note_qualite", sa.Numeric(3, 2), nullable=False, server_default="1.00"),
            sa.Column("actif", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("iban_chiffre", sa.Text, nullable=True),
            sa.Column("grille_tarifaire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("grilles_tarifaires.id"), nullable=True),
        )

    # ── CALCULS_TARIFAIRES (avant dossiers car FK bidirectionnel) ──────────
    if not _table_exists("calculs_tarifaires"):
        op.create_table(
            "calculs_tarifaires",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_calcul", sa.Integer, nullable=False, server_default="1"),
            sa.Column("date_calcul", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("declenche_par_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("nombre_pages", sa.Numeric(10, 4), nullable=False),
            sa.Column("criteres_appliques", postgresql.JSONB, nullable=True),
            sa.Column("regles_appliquees", postgresql.JSONB, nullable=True),
            sa.Column("montant_client_brut", sa.Numeric(10, 2), nullable=False),
            sa.Column("ajustement_client", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("motif_ajustement_client", sa.Text, nullable=True),
            sa.Column("montant_client_final", sa.Numeric(10, 2), nullable=False),
            sa.Column("montant_retranscripteur", sa.Numeric(10, 2), nullable=False),
            sa.Column("montant_correcteur", sa.Numeric(10, 2), nullable=False),
            sa.Column("montant_prestataires_total", sa.Numeric(10, 2), nullable=False),
            sa.Column("marge_brute", sa.Numeric(10, 2), nullable=False),
            sa.Column("grilles_version_snap", postgresql.JSONB, nullable=True),
            sa.Column("statut", sa.Text, nullable=False, server_default="estimatif"),
            sa.Column("valide_par_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_calculs_dossier_id ON calculs_tarifaires (dossier_id)")

    # ── DOSSIERS ──────────────────────────────────────────────────────────
    if not _table_exists("dossiers"):
        op.create_table(
            "dossiers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("reference", sa.String(50), nullable=False, unique=True),
            sa.Column("titre", sa.String(500), nullable=True),
            sa.Column("statut", sa.Text, nullable=False, server_default="recu"),
            sa.Column("type_instance", sa.Text, nullable=False),
            sa.Column("date_seance", sa.Date, nullable=True),
            sa.Column("date_reception_audio", sa.DateTime(timezone=True), nullable=False),
            sa.Column("date_limite", sa.Date, nullable=True),
            sa.Column("date_envoi_client", sa.DateTime(timezone=True), nullable=True),
            sa.Column("est_urgent", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("urgence_forcee", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("payeur_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
            sa.Column("duree_audio_minutes", sa.Integer, nullable=True),
            sa.Column("nombre_pages_final", sa.Numeric(10, 4), nullable=True),
            sa.Column("criteres_tarif", postgresql.JSONB, nullable=True),
            sa.Column("calcul_tarifaire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calculs_tarifaires.id"), nullable=True),
            sa.Column("niveau_confidentialite", sa.Text, nullable=False, server_default="standard"),
            sa.Column("notes_internes", sa.Text, nullable=True),
            sa.Column("archive_snapshot", postgresql.JSONB, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_dossiers_reference ON dossiers (reference)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dossiers_statut ON dossiers (statut)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dossiers_client_id ON dossiers (client_id)")

    # FK de calculs_tarifaires vers dossiers (ajout post-création, ignorée si déjà présente)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'fk_calculs_dossier_id'
            ) THEN
                ALTER TABLE calculs_tarifaires
                ADD CONSTRAINT fk_calculs_dossier_id
                FOREIGN KEY (dossier_id) REFERENCES dossiers(id);
            END IF;
        END $$;
    """)

    # ── AFFECTATIONS ──────────────────────────────────────────────────────
    if not _table_exists("affectations"):
        op.create_table(
            "affectations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dossiers.id"), nullable=False),
            sa.Column("prestataire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prestataires.id"), nullable=False),
            sa.Column("type_role", sa.Text, nullable=False),
            sa.Column("date_attribution", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("date_limite_rendu", sa.DateTime(timezone=True), nullable=True),
            sa.Column("date_rendu_effectif", sa.DateTime(timezone=True), nullable=True),
            sa.Column("statut", sa.Text, nullable=False, server_default="en_attente"),
            sa.Column("grille_snap", postgresql.JSONB, nullable=True),
            sa.Column("montant_calcule", sa.Numeric(10, 2), nullable=True),
            sa.Column("commentaire", sa.Text, nullable=True),
        )

    # ── JOURNAL_ACTIVITES ─────────────────────────────────────────────────
    if not _table_exists("journal_activites"):
        op.create_table(
            "journal_activites",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dossiers.id", ondelete="SET NULL"), nullable=True),
            sa.Column("utilisateur_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("type_action", sa.Text, nullable=False),
            sa.Column("detail", postgresql.JSONB, nullable=True),
            sa.Column("ip_source", sa.String(45), nullable=True),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_journal_timestamp ON journal_activites (timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_journal_dossier_id ON journal_activites (dossier_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_journal_type_action ON journal_activites (type_action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_journal_detail_gin ON journal_activites USING gin(detail)")

    # ── INCIDENTS_QUALITE ─────────────────────────────────────────────────
    if not _table_exists("incidents_qualite"):
        op.create_table(
            "incidents_qualite",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dossiers.id"), nullable=False),
            sa.Column("signale_par_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("prestataire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prestataires.id"), nullable=True),
            sa.Column("description", sa.Text, nullable=False),
            sa.Column("gravite", sa.Text, nullable=False),
            sa.Column("statut", sa.Text, nullable=False, server_default="ouvert"),
            sa.Column("impact_tarifaire", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("montant_impact", sa.Numeric(10, 2), nullable=True),
            sa.Column("resolution", sa.Text, nullable=True),
        )

    # ── FACTURES_CLIENTS ──────────────────────────────────────────────────
    if not _table_exists("factures_clients"):
        op.create_table(
            "factures_clients",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("numero_facture", sa.String(50), nullable=False, unique=True),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dossiers.id"), nullable=False),
            sa.Column("payeur_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("calcul_tarifaire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calculs_tarifaires.id"), nullable=False),
            sa.Column("montant_ht", sa.Numeric(10, 2), nullable=False),
            sa.Column("tva_applicable", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("taux_tva", sa.Numeric(5, 2), nullable=False, server_default="0"),
            sa.Column("montant_tva", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("montant_ttc", sa.Numeric(10, 2), nullable=False),
            sa.Column("date_emission", sa.Date, nullable=False),
            sa.Column("date_echeance", sa.Date, nullable=True),
            sa.Column("statut_paiement", sa.Text, nullable=False, server_default="non_payee"),
        )

    # ── PAIEMENTS_PRESTATAIRES ────────────────────────────────────────────
    if not _table_exists("paiements_prestataires"):
        op.create_table(
            "paiements_prestataires",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("affectation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("affectations.id"), nullable=False),
            sa.Column("dossier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dossiers.id"), nullable=False),
            sa.Column("prestataire_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prestataires.id"), nullable=False),
            sa.Column("role_paye", sa.Text, nullable=False),
            sa.Column("nombre_pages", sa.Numeric(10, 4), nullable=False),
            sa.Column("detail_calcul", postgresql.JSONB, nullable=True),
            sa.Column("montant_brut", sa.Numeric(10, 2), nullable=False),
            sa.Column("ajustement_manuel", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("motif_ajustement", sa.Text, nullable=True),
            sa.Column("montant_final", sa.Numeric(10, 2), nullable=False),
            sa.Column("statut", sa.Text, nullable=False, server_default="a_payer"),
            sa.Column("date_virement", sa.Date, nullable=True),
            sa.Column("reference_virement", sa.String(100), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("paiements_prestataires")
    op.drop_table("factures_clients")
    op.drop_table("incidents_qualite")
    op.execute("DROP INDEX IF EXISTS ix_journal_detail_gin")
    op.drop_table("journal_activites")
    op.drop_table("affectations")
    op.drop_constraint("fk_calculs_dossier_id", "calculs_tarifaires", type_="foreignkey")
    op.drop_table("dossiers")
    op.drop_table("calculs_tarifaires")
    op.drop_table("prestataires")
    op.drop_table("clients")
    op.drop_table("regles_tarifaires")
    op.drop_table("grilles_tarifaires")
    op.drop_table("users")

    for enum_name in ["roleenum","typeclientenum","roleprestaenum","statutdossierenum",
                      "typeinstanceenum","niveauconfidentialiteenum","statutaffectationenum",
                      "roleaffectationenum","typeactionenum","graviteenum","statutincidentenum",
                      "statutpaiementenum","statutpaiementprestaenum","rolepayeenum",
                      "typegrilleenum","ciblegrilleenum","typeregleenum","conditiontypeenum",
                      "modecalculenum","statutcalculenum"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
