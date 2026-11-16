"""
Côté responsables : réception des PV, relecture, demandes de correction, validation.
"""
import difflib
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.v1.common import get_dossier, livraison_out, bytes_response, DOCX_MIME, AFF_ACTIVES, now
from app.core.deps import DbDep, require_permission
from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.journal import TypeActionEnum
from app.models.refonte import Livraison, DemandeCorrection
from app.models.user import User
from app.services import storage, workflow as wf
from app.services.attribution import charge_reelle
from app.services.docx_check import extraire_paragraphes
from app.services.journal import log_action
from app.services.livraisons import deposer, lire_docx
from app.services.notifications import notifier, compte_prestataire, internes
from app.models.prestataire import Prestataire

router = APIRouter()


class DemandeCorrectionIn(BaseModel):
    message: str = Field(min_length=5, max_length=5000)
    livraison_id: Optional[uuid.UUID] = None
    date_limite: Optional[datetime] = None


class ValidationIn(BaseModel):
    nombre_pages_final: Decimal = Field(gt=0, le=5000)
    livraison_id: uuid.UUID
    derogation_motif: Optional[str] = Field(default=None, max_length=1000)


def _livraison(db, livraison_id: uuid.UUID) -> Livraison:
    l = db.query(Livraison).filter(Livraison.id == livraison_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Version introuvable")
    get_dossier(db, l.dossier_id)
    return l


def _aff_courante(db, dossier_id) -> Optional[Affectation]:
    return db.query(Affectation).filter(Affectation.dossier_id == dossier_id,
                                        Affectation.statut.in_(AFF_ACTIVES)).first()


@router.get("/dossiers/{dossier_id}/livraisons")
def lister(dossier_id: uuid.UUID, db: DbDep, _u: User = Depends(require_permission("dossiers.voir"))):
    get_dossier(db, dossier_id)
    return [livraison_out(l) for l in db.query(Livraison).filter(Livraison.dossier_id == dossier_id)
            .order_by(Livraison.version.desc()).all()]


@router.get("/livraisons/{livraison_id}/fichier")
def telecharger(livraison_id: uuid.UUID, db: DbDep,
                user: User = Depends(require_permission("relecture", "validation", "dossiers.gerer"))):
    l = _livraison(db, livraison_id)
    content = storage.load_pv(db, l.stockage, l.stockage_ref, l.drive_id)
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, dossier_id=l.dossier_id, utilisateur_id=user.id,
               detail={"action": "telechargement_pv", "livraison_id": str(l.id), "version": l.version})
    db.commit()
    return bytes_response(content, l.nom_original if l.nom_original.lower().endswith(".docx")
                          else f"PV_v{l.version}.docx", DOCX_MIME)


@router.get("/livraisons/{a_id}/comparer/{b_id}")
def comparer(a_id: uuid.UUID, b_id: uuid.UUID, db: DbDep,
             _u: User = Depends(require_permission("relecture", "validation"))):
    a, b = _livraison(db, a_id), _livraison(db, b_id)
    if a.dossier_id != b.dossier_id:
        raise HTTPException(status_code=400, detail="Les versions doivent appartenir au même dossier")
    pa = extraire_paragraphes(storage.load_pv(db, a.stockage, a.stockage_ref, a.drive_id))
    pb = extraire_paragraphes(storage.load_pv(db, b.stockage, b.stockage_ref, b.drive_id))
    blocs = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=pa, b=pb, autojunk=False).get_opcodes():
        if tag == "equal":
            blocs.append({"type": "identique", "nombre": i2 - i1})
        else:
            blocs.append({"type": {"replace": "modifie", "delete": "supprime", "insert": "ajoute"}[tag],
                          "avant": pa[i1:i2][:50], "apres": pb[j1:j2][:50]})
    return {"version_a": a.version, "version_b": b.version,
            "paragraphes_a": len(pa), "paragraphes_b": len(pb),
            "modifications": sum(1 for x in blocs if x["type"] != "identique"), "blocs": blocs[:400]}


@router.post("/dossiers/{dossier_id}/relecture/commencer")
def commencer_relecture(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("relecture"))):
    d = get_dossier(db, dossier_id, lock=True)
    wf.changer_production(db, d, wf.A_RELIRE, user.id, "prise en charge de la relecture")
    db.commit()
    return {"statut_production": d.statut_production}


@router.post("/dossiers/{dossier_id}/relecture/terminer")
def terminer_relecture(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("relecture"))):
    d = get_dossier(db, dossier_id, lock=True)
    wf.changer_production(db, d, wf.A_CONTROLER, user.id, "relecture terminée")
    notifier(db, internes(db, "validation"), "pv_a_controler", f"PV à contrôler : {d.reference}",
             "La relecture est terminée, le PV attend la validation finale.",
             lien=f"/dossiers/{d.id}", dossier_id=d.id, exclure=user.id)
    db.commit()
    return {"statut_production": d.statut_production}


@router.post("/dossiers/{dossier_id}/corrections", status_code=201)
def demander_correction(dossier_id: uuid.UUID, payload: DemandeCorrectionIn, db: DbDep,
                        user: User = Depends(require_permission("relecture"))):
    d = get_dossier(db, dossier_id, lock=True)
    aff = _aff_courante(db, d.id)
    if not aff:
        raise HTTPException(status_code=409, detail="Aucun retranscripteur actif sur ce dossier")
    if payload.livraison_id:
        l = _livraison(db, payload.livraison_id)
        if l.dossier_id != d.id:
            raise HTTPException(status_code=400, detail="Version d'un autre dossier")
    wf.changer_production(db, d, wf.CORRECTION_DEMANDEE, user.id, payload.message[:200])
    aff.statut = StatutAffectationEnum.EN_COURS
    if payload.date_limite:
        aff.date_limite_rendu = payload.date_limite
    c = DemandeCorrection(dossier_id=d.id, affectation_id=aff.id, livraison_id=payload.livraison_id,
                          message=payload.message, date_limite=payload.date_limite, demandee_par_id=user.id)
    db.add(c)
    db.flush()
    log_action(db, TypeActionEnum.NOTE, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "demande_correction", "correction_id": str(c.id)})
    notifier(db, compte_prestataire(db, aff.prestataire_id), "correction_demandee",
             f"Correction demandée : {d.reference}", payload.message[:500],
             lien="/mes-missions", dossier_id=d.id, dedup_key=f"correction:{c.id}")
    db.commit()
    return {"id": str(c.id), "statut_production": d.statut_production}


@router.post("/dossiers/{dossier_id}/livraisons", status_code=201)
async def deposer_correction_interne(
    dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("relecture")),
    file: UploadFile = File(...), commentaire: Optional[str] = Form(default=None),
):
    """Version corrigée par une responsable (relecture interne). Ne change pas l'étape de production."""
    d = get_dossier(db, dossier_id, lock=True)
    if d.statut_production not in (wf.LIVRE, wf.A_RELIRE, wf.A_CONTROLER):
        raise HTTPException(status_code=409, detail="Dépôt interne possible uniquement pendant la relecture")
    content = await lire_docx(file)
    liv = deposer(db, d, user, content, file.filename or "", _aff_courante(db, d.id), "correction_interne", commentaire)
    db.commit()
    return livraison_out(liv)


@router.post("/dossiers/{dossier_id}/valider")
def valider(dossier_id: uuid.UUID, payload: ValidationIn, db: DbDep,
            user: User = Depends(require_permission("validation"))):
    d = get_dossier(db, dossier_id, lock=True)
    l = _livraison(db, payload.livraison_id)
    if l.dossier_id != d.id:
        raise HTTPException(status_code=400, detail="Version d'un autre dossier")
    if l.statut_controle == "non_conforme" and not (payload.derogation_motif or "").strip():
        raise HTTPException(status_code=409, detail="Version non conforme : indiquez le motif de dérogation pour valider")
    wf.changer_production(db, d, wf.VALIDE, user.id, "validation du PV", {
        "livraison_id": str(l.id), "version": l.version, "derogation": payload.derogation_motif,
    })
    d.valide_le = now()
    d.nombre_pages_final = payload.nombre_pages_final
    if d.statut_facturation == wf.F_NON_APPLICABLE:
        wf.changer_facturation(db, d, wf.F_A_ETABLIR, user.id, "PV validé")
    aff = db.query(Affectation).filter(Affectation.dossier_id == d.id,
                                       Affectation.statut.in_(AFF_ACTIVES)).first()
    if aff:
        aff.statut = StatutAffectationEnum.VALIDE
        if not aff.date_rendu_effectif:
            premiere = db.query(Livraison).filter(Livraison.affectation_id == aff.id,
                                                  Livraison.type_depot == "depot_prestataire") \
                .order_by(Livraison.version).first()
            aff.date_rendu_effectif = premiere.depose_le if premiere else now()
        presta = db.query(Prestataire).filter(Prestataire.id == aff.prestataire_id).first()
        if presta:
            db.flush()
            presta.charge_actuelle = charge_reelle(db, presta.id)
        notifier(db, compte_prestataire(db, aff.prestataire_id), "pv_valide", f"PV validé : {d.reference}",
                 "Merci ! Votre retranscription a été validée.", lien="/mes-missions", dossier_id=d.id,
                 dedup_key=f"validation:{d.id}")
    notifier(db, internes(db, "finance.gerer"), "facture_a_etablir", f"Facture à établir : {d.reference}",
             "Le PV est validé, la facturation peut être préparée.", lien=f"/dossiers/{d.id}",
             dossier_id=d.id, dedup_key=f"a_facturer:{d.id}", exclure=user.id)
    db.commit()
    return {"statut_production": d.statut_production, "statut_facturation": d.statut_facturation}
