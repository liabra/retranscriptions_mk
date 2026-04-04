import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.dossier import Dossier, StatutDossierEnum
from app.models.client import Client
from app.models.facture import FactureClient, StatutPaiementEnum
from app.models.pricing.calcul import CalculTarifaire
from app.models.user import User
from app.models.journal import TypeActionEnum
from app.schemas.facture import FactureGenerate, FacturePaiementUpdate, FactureOut
from app.services.journal import log_action

router = APIRouter()


def _get_dossier_or_404(dossier_id: uuid.UUID, db) -> Dossier:
    d = db.query(Dossier).filter(Dossier.id == dossier_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return d


def _generate_numero_facture(db) -> str:
    year = datetime.now(timezone.utc).year
    count = (
        db.query(FactureClient)
        .filter(FactureClient.numero_facture.like(f"FAC-{year}-%"))
        .count()
    )
    return f"FAC-{year}-{count + 1:04d}"


@router.post("/dossiers/{dossier_id}/generer-facture", response_model=FactureOut, status_code=201)
def generer_facture(
    dossier_id: uuid.UUID,
    payload: FactureGenerate,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    dossier = _get_dossier_or_404(dossier_id, db)

    existing = db.query(FactureClient).filter(FactureClient.dossier_id == dossier_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Une facture existe déjà pour ce dossier")

    if not dossier.calcul_tarifaire_id:
        raise HTTPException(status_code=400, detail="Aucun calcul tarifaire disponible. Calculez d'abord.")

    calcul = db.query(CalculTarifaire).filter(CalculTarifaire.id == dossier.calcul_tarifaire_id).first()
    if not calcul:
        raise HTTPException(status_code=404, detail="Calcul tarifaire introuvable")

    payeur_id = dossier.payeur_id or dossier.client_id
    montant_ht = calcul.montant_client_final
    taux_tva = Decimal("0.00")
    montant_tva = Decimal("0.00")

    if payload.tva_applicable:
        taux_tva = payload.taux_tva
        montant_tva = (montant_ht * taux_tva / Decimal("100")).quantize(Decimal("0.01"))

    montant_ttc = montant_ht + montant_tva

    facture = FactureClient(
        numero_facture=_generate_numero_facture(db),
        dossier_id=dossier_id,
        payeur_id=payeur_id,
        calcul_tarifaire_id=calcul.id,
        montant_ht=montant_ht,
        tva_applicable=payload.tva_applicable,
        taux_tva=taux_tva,
        montant_tva=montant_tva,
        montant_ttc=montant_ttc,
        date_emission=date.today(),
        date_echeance=payload.date_echeance,
        statut_paiement=StatutPaiementEnum.NON_PAYEE,
    )
    db.add(facture)

    # Auto-transition dossier → FACTURE
    dossier.statut = StatutDossierEnum.FACTURE

    db.flush()
    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "generation_facture",
            "numero_facture": facture.numero_facture,
            "montant_ttc": str(montant_ttc),
        },
    )
    db.commit()
    db.refresh(facture)
    return facture


@router.get("/dossiers/{dossier_id}/facture", response_model=FactureOut)
def get_facture_dossier(dossier_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    _get_dossier_or_404(dossier_id, db)
    facture = db.query(FactureClient).filter(FactureClient.dossier_id == dossier_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Aucune facture pour ce dossier")
    return facture


@router.get("/factures/{facture_id}", response_model=FactureOut)
def get_facture(facture_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return facture


def _build_facture_html(facture: FactureClient, dossier: Dossier, payeur: Client) -> str:
    tva_line = ""
    if facture.tva_applicable:
        tva_line = f"""
        <tr>
            <td>TVA ({facture.taux_tva}%)</td>
            <td style="text-align:right">{float(facture.montant_tva):.2f} €</td>
        </tr>"""
    echeance = facture.date_echeance.strftime("%d/%m/%Y") if facture.date_echeance else "À réception"
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; color: #111; margin: 40px; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .subtitle {{ color: #666; margin-bottom: 24px; }}
  .grid {{ display: flex; gap: 40px; margin-bottom: 24px; }}
  .block {{ flex: 1; }}
  .label {{ color: #666; font-size: 11px; text-transform: uppercase; margin-bottom: 2px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th {{ background: #f4f4f4; padding: 8px; text-align: left; font-size: 11px; text-transform: uppercase; }}
  td {{ padding: 8px; border-bottom: 1px solid #eee; }}
  .total-row td {{ font-weight: bold; font-size: 14px; background: #f9f9f9; }}
  .footer {{ margin-top: 40px; font-size: 11px; color: #999; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; }}
  .badge-green {{ background: #d1fae5; color: #065f46; }}
  .badge-gray {{ background: #f3f4f6; color: #374151; }}
</style>
</head>
<body>
<h1>FACTURE {facture.numero_facture}</h1>
<div class="subtitle">
  Émise le {facture.date_emission.strftime("%d/%m/%Y")} ·
  Dossier {dossier.reference}
</div>

<div class="grid">
  <div class="block">
    <div class="label">Destinataire</div>
    <strong>{payeur.nom}</strong><br>
    {payeur.type if payeur.type else ""}
  </div>
  <div class="block">
    <div class="label">Référence dossier</div>
    <strong>{dossier.reference}</strong><br>
    {dossier.type_instance.value if dossier.type_instance else ""}
    {(" — " + dossier.titre) if dossier.titre else ""}
  </div>
  <div class="block">
    <div class="label">Échéance</div>
    <strong>{echeance}</strong>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Description</th>
      <th style="text-align:right">Montant</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Prestation de retranscription — {dossier.reference}</td>
      <td style="text-align:right">{float(facture.montant_ht):.2f} €</td>
    </tr>
    {tva_line}
    <tr class="total-row">
      <td>TOTAL TTC</td>
      <td style="text-align:right">{float(facture.montant_ttc):.2f} €</td>
    </tr>
  </tbody>
</table>

<div style="margin-top:16px">
  Statut : <span class="badge {'badge-green' if facture.statut_paiement.value == 'soldee' else 'badge-gray'}">
    {'Soldée' if facture.statut_paiement.value == 'soldee' else 'En attente de paiement'}
  </span>
</div>

<div class="footer">
  Document généré automatiquement — Système de gestion des retranscriptions
</div>
</body>
</html>"""


@router.get("/factures/{facture_id}/html", response_class=HTMLResponse)
def get_facture_html(facture_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    dossier = db.query(Dossier).filter(Dossier.id == facture.dossier_id).first()
    payeur = db.query(Client).filter(Client.id == facture.payeur_id).first()
    if not dossier or not payeur:
        raise HTTPException(status_code=500, detail="Données manquantes pour générer la facture")
    return HTMLResponse(content=_build_facture_html(facture, dossier, payeur))


@router.get("/factures/{facture_id}/pdf")
def get_facture_pdf(facture_id: uuid.UUID, db: DbDep, current_user: CurrentUser):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    dossier = db.query(Dossier).filter(Dossier.id == facture.dossier_id).first()
    payeur = db.query(Client).filter(Client.id == facture.payeur_id).first()
    if not dossier or not payeur:
        raise HTTPException(status_code=500, detail="Données manquantes")

    html = _build_facture_html(facture, dossier, payeur)
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{facture.numero_facture}.pdf"'},
        )
    except Exception as e:
        # Fallback HTML si WeasyPrint indisponible (env sans GTK)
        return HTMLResponse(content=html, status_code=200)


@router.delete("/factures/{facture_id}", status_code=204)
def delete_facture(
    facture_id: uuid.UUID,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    if facture.statut_paiement != StatutPaiementEnum.NON_PAYEE:
        raise HTTPException(status_code=400, detail="Seules les factures non payées peuvent être supprimées")
    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=facture.dossier_id,
        utilisateur_id=admin.id,
        detail={"action": "suppression_facture", "numero_facture": facture.numero_facture},
    )
    db.delete(facture)
    db.commit()


@router.patch("/factures/{facture_id}/paiement", response_model=FactureOut)
def update_facture_paiement(
    facture_id: uuid.UUID,
    payload: FacturePaiementUpdate,
    db: DbDep,
    admin: User = Depends(require_admin_or_coordinator),
):
    facture = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not facture:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    try:
        facture.statut_paiement = StatutPaiementEnum(payload.statut_paiement)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Statut invalide: {payload.statut_paiement}")

    # Auto-transition dossier → PAYE_ENTRANT quand facture soldée
    if facture.statut_paiement == StatutPaiementEnum.SOLDEE:
        dossier = db.query(Dossier).filter(Dossier.id == facture.dossier_id).first()
        if dossier and dossier.statut == StatutDossierEnum.FACTURE:
            dossier.statut = StatutDossierEnum.PAYE_ENTRANT

    log_action(
        db, TypeActionEnum.PAIEMENT,
        dossier_id=facture.dossier_id,
        utilisateur_id=admin.id,
        detail={
            "action": "update_statut_facture",
            "facture_id": str(facture_id),
            "statut": payload.statut_paiement,
        },
    )
    db.commit()
    db.refresh(facture)
    return facture
