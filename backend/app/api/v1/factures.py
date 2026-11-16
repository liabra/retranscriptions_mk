import html
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.api.v1.common import get_dossier, dossier_resume
from app.core.config import settings
from app.core.deps import DbDep, require_permission
from app.models.affectation import Affectation, StatutAffectationEnum, RoleAffectationEnum
from app.models.client import Client
from app.models.dossier import Dossier
from app.models.facture import FactureClient, StatutPaiementEnum
from app.models.journal import TypeActionEnum
from app.models.paiement import PaiementPrestataire, StatutPaiementPrestaEnum, RolePayeEnum
from app.models.pricing.calcul import CalculTarifaire, StatutCalculEnum
from app.models.refonte import Encaissement
from app.models.user import User
from app.services import workflow as wf
from app.services.journal import log_action
from app.services.notifications import notifier, internes

router = APIRouter()


class FactureGenerate(BaseModel):
    tva_applicable: bool = False
    taux_tva: Decimal = Field(default=Decimal("20.00"), ge=0, le=100)
    date_echeance: Optional[date] = None


class EncaissementIn(BaseModel):
    montant: Decimal = Field(gt=0, le=1_000_000)
    date_encaissement: date
    mode: Optional[str] = Field(default=None, max_length=30)
    reference: Optional[str] = Field(default=None, max_length=100)
    commentaire: Optional[str] = Field(default=None, max_length=1000)


class Annulation(BaseModel):
    motif: str = Field(min_length=3, max_length=1000)


def _facture(db, facture_id: uuid.UUID) -> FactureClient:
    f = db.query(FactureClient).filter(FactureClient.id == facture_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return f


def facture_out(db, f: FactureClient) -> dict:
    payeur = db.query(Client).filter(Client.id == f.payeur_id).first()
    dossier = db.query(Dossier).filter(Dossier.id == f.dossier_id).first()
    return {
        "id": str(f.id), "numero_facture": f.numero_facture, "dossier_id": str(f.dossier_id),
        "dossier_reference": dossier.reference if dossier else None,
        "payeur_id": str(f.payeur_id), "payeur_nom": payeur.nom if payeur else None,
        "calcul_tarifaire_id": str(f.calcul_tarifaire_id),
        "montant_ht": f.montant_ht, "tva_applicable": f.tva_applicable, "taux_tva": f.taux_tva,
        "montant_tva": f.montant_tva, "montant_ttc": f.montant_ttc,
        "montant_encaisse": f.montant_encaisse or Decimal("0.00"),
        "reste_a_encaisser": (f.montant_ttc - (f.montant_encaisse or 0)) if not f.annulee_le else Decimal("0.00"),
        "date_emission": f.date_emission, "date_echeance": f.date_echeance,
        "statut_paiement": f.statut_paiement.value, "annulee_le": f.annulee_le, "motif_annulation": f.motif_annulation,
        "en_retard": bool(not f.annulee_le and f.date_echeance and f.date_echeance < date.today()
                          and f.statut_paiement != StatutPaiementEnum.SOLDEE),
        "encaissements": [{
            "id": str(e.id), "montant": e.montant, "date_encaissement": e.date_encaissement, "mode": e.mode,
            "reference": e.reference, "commentaire": e.commentaire, "created_at": e.created_at,
        } for e in f.encaissements.order_by(Encaissement.date_encaissement).all()],
    }


def _prochain_numero(db) -> str:
    """Numérotation continue sans réutilisation (les factures ne sont jamais supprimées)."""
    year = datetime.now(timezone.utc).year
    numeros = [n for (n,) in db.query(FactureClient.numero_facture)
               .filter(FactureClient.numero_facture.like(f"FAC-{year}-%")).all()]
    maxi = max((int(m.group(1)) for n in numeros if (m := re.match(rf"FAC-{year}-(\d+)$", n))), default=0)
    return f"FAC-{year}-{maxi + 1:04d}"


def _generer_paiements(db, d: Dossier, calcul: CalculTarifaire) -> int:
    nb = 0
    affs = db.query(Affectation).filter(
        Affectation.dossier_id == d.id, Affectation.statut == StatutAffectationEnum.VALIDE,
        Affectation.type_role == RoleAffectationEnum.RETRANSCRIPTEUR,
    ).all()
    for aff in affs:
        if db.query(PaiementPrestataire).filter(PaiementPrestataire.affectation_id == aff.id).first():
            continue
        db.add(PaiementPrestataire(
            affectation_id=aff.id, dossier_id=d.id, prestataire_id=aff.prestataire_id,
            role_paye=RolePayeEnum.RETRANSCRIPTEUR, nombre_pages=calcul.nombre_pages,
            detail_calcul={"calcul_id": str(calcul.id), "version_calcul": calcul.version_calcul},
            montant_brut=calcul.montant_retranscripteur, ajustement_manuel=Decimal("0.00"),
            montant_final=calcul.montant_retranscripteur, statut=StatutPaiementPrestaEnum.A_PAYER,
        ))
        nb += 1
    return nb


@router.get("/factures")
def lister(db: DbDep, _u: User = Depends(require_permission("finance.voir")),
           vue: str = Query(default="attente", pattern="^(a_etablir|attente|reglees|annulees|toutes)$"),
           limit: int = Query(default=100, ge=1, le=500)):
    if vue == "a_etablir":
        rows = db.query(Dossier).filter(Dossier.statut_facturation == wf.F_A_ETABLIR,
                                        Dossier.supprime_le.is_(None)).order_by(Dossier.valide_le).limit(limit).all()
        out = []
        for d in rows:
            item = dossier_resume(db, d)
            calcul = db.query(CalculTarifaire).filter(CalculTarifaire.id == d.calcul_tarifaire_id).first() \
                if d.calcul_tarifaire_id else None
            item["calcul"] = ({"id": str(calcul.id), "statut": calcul.statut.value,
                               "montant_client_final": calcul.montant_client_final} if calcul else None)
            item["nombre_pages_final"] = d.nombre_pages_final
            out.append(item)
        return {"vue": vue, "items": out}
    q = db.query(FactureClient)
    if vue == "attente":
        q = q.filter(FactureClient.annulee_le.is_(None), FactureClient.statut_paiement != StatutPaiementEnum.SOLDEE)
    elif vue == "reglees":
        q = q.filter(FactureClient.annulee_le.is_(None), FactureClient.statut_paiement == StatutPaiementEnum.SOLDEE)
    elif vue == "annulees":
        q = q.filter(FactureClient.annulee_le.isnot(None))
    return {"vue": vue, "items": [facture_out(db, f) for f in
                                  q.order_by(FactureClient.date_emission.desc()).limit(limit).all()]}


@router.post("/dossiers/{dossier_id}/generer-facture", status_code=201)
def generer_facture(dossier_id: uuid.UUID, payload: FactureGenerate, db: DbDep,
                    user: User = Depends(require_permission("finance.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    if d.statut_facturation != wf.F_A_ETABLIR:
        raise HTTPException(status_code=409, detail="Le dossier n'est pas en attente de facturation (PV non validé ?)")
    if db.query(FactureClient).filter(FactureClient.dossier_id == d.id, FactureClient.annulee_le.is_(None)).first():
        raise HTTPException(status_code=409, detail="Une facture existe déjà pour ce dossier")
    calcul = db.query(CalculTarifaire).filter(CalculTarifaire.id == d.calcul_tarifaire_id).first() \
        if d.calcul_tarifaire_id else None
    if not calcul or calcul.statut != StatutCalculEnum.DEFINITIF:
        raise HTTPException(status_code=409, detail="Le calcul tarifaire doit être validé avant la facturation")

    payeur_id = d.payeur_id or d.client_id
    payeur = db.query(Client).filter(Client.id == payeur_id).first()  # fix B1 : payeur défini
    if not payeur:
        raise HTTPException(status_code=400, detail="Payeur introuvable")
    montant_ht = calcul.montant_client_final
    taux = payload.taux_tva if payload.tva_applicable else Decimal("0.00")
    montant_tva = (montant_ht * taux / Decimal("100")).quantize(Decimal("0.01"))
    facture = FactureClient(
        numero_facture=_prochain_numero(db), dossier_id=d.id, payeur_id=payeur.id, calcul_tarifaire_id=calcul.id,
        montant_ht=montant_ht, tva_applicable=payload.tva_applicable, taux_tva=taux, montant_tva=montant_tva,
        montant_ttc=montant_ht + montant_tva, date_emission=date.today(), date_echeance=payload.date_echeance,
        statut_paiement=StatutPaiementEnum.NON_PAYEE, montant_encaisse=Decimal("0.00"),
    )
    db.add(facture)
    db.flush()
    wf.changer_facturation(db, d, wf.F_EMISE, user.id, facture.numero_facture)
    nb = _generer_paiements(db, d, calcul)
    log_action(db, TypeActionEnum.PAIEMENT, dossier_id=d.id, utilisateur_id=user.id, detail={
        "action": "generation_facture", "numero_facture": facture.numero_facture,
        "montant_ttc": str(facture.montant_ttc), "paiements_prestataires_crees": nb,
    })
    notifier(db, internes(db, "finance.voir"), "facture_creee", f"Facture {facture.numero_facture} créée",
             f"{d.reference} — {facture.montant_ttc} € TTC", lien="/finance", dossier_id=d.id,
             exclure=user.id, dedup_key=f"facture:{facture.id}")
    db.commit()
    return facture_out(db, facture)


@router.get("/dossiers/{dossier_id}/facture")
def facture_du_dossier(dossier_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    get_dossier(db, dossier_id)
    f = db.query(FactureClient).filter(FactureClient.dossier_id == dossier_id) \
        .order_by(FactureClient.annulee_le.isnot(None), FactureClient.date_emission.desc()).first()
    if not f:
        raise HTTPException(status_code=404, detail="Aucune facture pour ce dossier")
    return facture_out(db, f)


@router.get("/factures/{facture_id}")
def lire(facture_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    return facture_out(db, _facture(db, facture_id))


@router.post("/factures/{facture_id}/encaissements", status_code=201)
def encaisser(facture_id: uuid.UUID, payload: EncaissementIn, db: DbDep,
              user: User = Depends(require_permission("finance.gerer"))):
    f = _facture(db, facture_id)
    if f.annulee_le:
        raise HTTPException(status_code=409, detail="Facture annulée")
    deja = f.montant_encaisse or Decimal("0.00")
    if deja + payload.montant > f.montant_ttc:
        raise HTTPException(status_code=400, detail=f"Montant supérieur au reste à encaisser ({f.montant_ttc - deja} €)")
    d = get_dossier(db, f.dossier_id, lock=True)
    db.add(Encaissement(facture_id=f.id, montant=payload.montant, date_encaissement=payload.date_encaissement,
                        mode=payload.mode, reference=payload.reference, commentaire=payload.commentaire,
                        saisi_par_id=user.id))
    f.montant_encaisse = deja + payload.montant
    solde = f.montant_encaisse >= f.montant_ttc
    f.statut_paiement = StatutPaiementEnum.SOLDEE if solde else StatutPaiementEnum.PARTIELLEMENT
    wf.changer_facturation(db, d, wf.F_REGLEE if solde else wf.F_PARTIELLE, user.id,
                           f"encaissement {payload.montant} €")
    notifier(db, internes(db, "finance.voir"), "encaissement_recu",
             f"Encaissement reçu : {f.numero_facture}", f"{payload.montant} € reçus"
             + (" — facture soldée." if solde else "."), lien="/finance", dossier_id=d.id, exclure=user.id)
    db.commit()
    return facture_out(db, f)


@router.post("/factures/{facture_id}/annuler")
def annuler(facture_id: uuid.UUID, payload: Annulation, db: DbDep,
            user: User = Depends(require_permission("finance.gerer"))):
    """Remplace l'ancienne suppression : la facture et son numéro sont conservés."""
    f = _facture(db, facture_id)
    if f.annulee_le:
        raise HTTPException(status_code=409, detail="Facture déjà annulée")
    if (f.montant_encaisse or 0) > 0:
        raise HTTPException(status_code=409, detail="Facture partiellement réglée : établissez un avoir comptable")
    d = get_dossier(db, f.dossier_id, lock=True)
    f.annulee_le = datetime.now(timezone.utc)
    f.motif_annulation = payload.motif
    wf.changer_facturation(db, d, wf.F_A_ETABLIR, user.id, f"annulation {f.numero_facture} : {payload.motif}")
    db.commit()
    return facture_out(db, f)


def _facture_html(f: FactureClient, dossier: Dossier, payeur: Client) -> str:
    e = lambda v: html.escape(str(v or ""))  # fix S10 : échappement systématique  # noqa: E731
    tva = (f'<tr><td>TVA ({e(f.taux_tva)} %)</td><td class="r">{float(f.montant_tva):.2f} €</td></tr>'
           if f.tva_applicable else "")
    echeance = f.date_echeance.strftime("%d/%m/%Y") if f.date_echeance else "À réception"
    annulee = '<p class="ann">FACTURE ANNULÉE</p>' if f.annulee_le else ""
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><title>{e(f.numero_facture)}</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#1f2937;margin:40px}}
h1{{font-size:22px;margin:0 0 4px;color:#4338ca}} .muted{{color:#6b7280}}
.grid{{display:flex;gap:40px;margin:28px 0}} .b{{flex:1}} .l{{color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;margin-top:12px}} th{{background:#eef2ff;text-align:left;padding:8px;font-size:11px}}
td{{padding:8px;border-bottom:1px solid #e5e7eb}} .r{{text-align:right}} .t td{{font-weight:bold;font-size:14px}}
.ann{{color:#b91c1c;font-weight:bold;font-size:16px}}
</style></head><body>
<h1>Facture {e(f.numero_facture)}</h1>
<div class="muted">{e(settings.APP_NAME)} · émise le {f.date_emission.strftime("%d/%m/%Y")}</div>{annulee}
<div class="grid">
<div class="b"><div class="l">Destinataire</div><strong>{e(payeur.nom)}</strong><br>{e(payeur.adresse)}</div>
<div class="b"><div class="l">Dossier</div><strong>{e(dossier.reference)}</strong><br>{e(dossier.type_instance.value)} {e(dossier.titre)}</div>
<div class="b"><div class="l">Échéance</div><strong>{e(echeance)}</strong></div>
</div>
<table><thead><tr><th>Désignation</th><th class="r">Montant</th></tr></thead><tbody>
<tr><td>Retranscription — dossier {e(dossier.reference)}</td><td class="r">{float(f.montant_ht):.2f} €</td></tr>
{tva}<tr class="t"><td>Total TTC</td><td class="r">{float(f.montant_ttc):.2f} €</td></tr>
</tbody></table>
<p class="muted" style="margin-top:32px">Document généré par la plateforme {e(settings.APP_NAME)}.</p>
</body></html>"""


def _deny_fetch(url, *args, **kwargs):
    raise ValueError("Ressource externe interdite")  # fix S10 : aucun accès réseau/fichier à la génération PDF


@router.get("/factures/{facture_id}/html", response_class=HTMLResponse)
def facture_html(facture_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    f = _facture(db, facture_id)
    dossier = db.query(Dossier).filter(Dossier.id == f.dossier_id).first()
    payeur = db.query(Client).filter(Client.id == f.payeur_id).first()
    return HTMLResponse(_facture_html(f, dossier, payeur),
                        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})


@router.get("/factures/{facture_id}/pdf")
def facture_pdf(facture_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("finance.voir"))):
    f = _facture(db, facture_id)
    dossier = db.query(Dossier).filter(Dossier.id == f.dossier_id).first()
    payeur = db.query(Client).filter(Client.id == f.payeur_id).first()
    try:
        from weasyprint import HTML
        pdf = HTML(string=_facture_html(f, dossier, payeur), url_fetcher=_deny_fetch).write_pdf()
    except Exception:
        raise HTTPException(status_code=503, detail="Génération PDF indisponible sur ce serveur : utilisez la version HTML")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{f.numero_facture}.pdf"'})
