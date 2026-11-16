"""
Espace retranscripteur.

Chaque route vérifie : compte actif lié à une fiche prestataire (FK), affectation
appartenant à ce prestataire, statut d'affectation autorisant l'action.
Aucune donnée financière, note interne, indicateur ou lien OneDrive n'est renvoyé.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.v1.common import (
    get_dossier, audio_du_dossier, stream_response, bytes_response, DOCX_MIME, livraison_out, correction_out, now,
)
from app.core.deps import DbDep, require_prestataire
from app.models.affectation import Affectation, StatutAffectationEnum
from app.models.client import Client
from app.models.journal import TypeActionEnum
from app.models.refonte import Livraison, DemandeCorrection
from app.models.user import User
from app.services import storage, workflow as wf
from app.services.journal import log_action
from app.services.livraisons import deposer, lire_docx
from app.services.notifications import notifier, internes

router = APIRouter(prefix="/espace-prestataire")

TRAVAIL = (StatutAffectationEnum.EN_ATTENTE, StatutAffectationEnum.EN_COURS, StatutAffectationEnum.LIVRE)

ETAPES = {
    "attribue": ("a_commencer", "À commencer"),
    "en_cours": ("en_cours", "En cours"),
    "livre": ("livre", "Livré — en attente de relecture"),
    "a_relire": ("en_relecture", "En relecture"),
    "a_controler": ("en_relecture", "En relecture"),
    "correction_demandee": ("correction", "Correction demandée"),
    "valide": ("termine", "Validé"),
    "archive": ("termine", "Validé"),
}


def _aff(db, user: User, affectation_id: uuid.UUID) -> Affectation:
    aff = db.query(Affectation).filter(Affectation.id == affectation_id).first()
    # fix S2 : 404 identique que l'affectation n'existe pas ou appartienne à un autre prestataire
    if not aff or aff.prestataire_id != user.prestataire_id or aff.statut == StatutAffectationEnum.REJETE:
        raise HTTPException(status_code=404, detail="Mission introuvable")
    return aff


def _mission(db, aff: Affectation, user: User) -> dict:
    d = get_dossier(db, aff.dossier_id)
    client = db.query(Client).filter(Client.id == d.client_id).first()
    audio = audio_du_dossier(db, d.id)
    etape, etape_label = ETAPES.get(d.statut_production, ("en_attente", "En attente"))
    if aff.statut == StatutAffectationEnum.VALIDE:
        etape, etape_label = "termine", "Validé"
    livs = db.query(Livraison).filter(Livraison.affectation_id == aff.id,
                                      Livraison.type_depot == "depot_prestataire").order_by(Livraison.version.desc()).all()
    corrections = db.query(DemandeCorrection).filter(DemandeCorrection.affectation_id == aff.id) \
        .order_by(DemandeCorrection.created_at.desc()).all()
    ech = aff.date_limite_rendu
    return {
        "affectation_id": str(aff.id),
        "reference": d.reference,
        "titre": d.titre,
        "instance": client.nom if client else None,
        "type_instance": d.type_instance.value,
        "date_seance": d.date_seance,
        "duree_audio_minutes": d.duree_audio_minutes,
        "echeance": ech,
        "urgent": d.est_urgent,
        "en_retard": bool(ech and aff.statut in TRAVAIL and d.statut_production in ("attribue", "en_cours", "correction_demandee")
                          and (ech if ech.tzinfo else ech.replace(tzinfo=now().tzinfo)) < now()),
        "consignes": aff.commentaire,
        "etape": etape,
        "etape_label": etape_label,
        "peut_deposer": aff.statut in TRAVAIL and d.statut_production in ("attribue", "en_cours", "livre", "correction_demandee"),
        "audio": {"disponible": bool(audio and audio.disponible), "nom_fichier": audio.nom_fichier if audio else None,
                  "taille_octets": audio.taille_octets if audio else None} if audio else None,
        # version déposée par le prestataire : rapport de conformité visible pour qu'il corrige lui-même
        "versions": [{k: v for k, v in livraison_out(l).items() if k not in ("depose_par",)} for l in livs],
        "corrections": [{k: v for k, v in correction_out(c).items() if k != "demandee_par"} for c in corrections],
        "attribue_le": aff.date_attribution,
    }


@router.get("/missions")
def mes_missions(db: DbDep, user: User = Depends(require_prestataire), terminees: bool = False):
    q = db.query(Affectation).filter(Affectation.prestataire_id == user.prestataire_id)
    q = q.filter(Affectation.statut == StatutAffectationEnum.VALIDE) if terminees else q.filter(Affectation.statut.in_(TRAVAIL))
    missions = []
    for aff in q.order_by(Affectation.date_limite_rendu.asc().nullslast()).all():
        try:
            missions.append(_mission(db, aff, user))
        except HTTPException:
            continue  # dossier supprimé logiquement
    return missions


@router.get("/missions/{affectation_id}")
def mission(affectation_id: uuid.UUID, db: DbDep, user: User = Depends(require_prestataire)):
    return _mission(db, _aff(db, user, affectation_id), user)


@router.post("/missions/{affectation_id}/commencer")
def commencer(affectation_id: uuid.UUID, db: DbDep, user: User = Depends(require_prestataire)):
    aff = _aff(db, user, affectation_id)
    d = get_dossier(db, aff.dossier_id, lock=True)
    if aff.statut == StatutAffectationEnum.EN_ATTENTE and d.statut_production == wf.ATTRIBUE:
        aff.statut = StatutAffectationEnum.EN_COURS
        wf.changer_production(db, d, wf.EN_COURS, user.id, "début de la retranscription")
        db.commit()
    return _mission(db, aff, user)


@router.get("/missions/{affectation_id}/audio")
def telecharger_audio(affectation_id: uuid.UUID, db: DbDep, user: User = Depends(require_prestataire)):
    aff = _aff(db, user, affectation_id)
    if aff.statut not in TRAVAIL:
        raise HTTPException(status_code=403, detail="L'audio n'est plus accessible pour cette mission")
    d = get_dossier(db, aff.dossier_id, lock=True)
    audio = audio_du_dossier(db, d.id)
    if not audio or not audio.disponible:
        raise HTTPException(status_code=409, detail="L'audio n'est pas encore disponible. La responsable a été informée.")
    chunks = storage.stream_audio(audio)  # proxy : le prestataire ne reçoit jamais de lien OneDrive
    if aff.statut == StatutAffectationEnum.EN_ATTENTE and d.statut_production == wf.ATTRIBUE:
        aff.statut = StatutAffectationEnum.EN_COURS
        wf.changer_production(db, d, wf.EN_COURS, user.id, "premier téléchargement de l'audio")
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "telechargement_audio", "audio_id": str(audio.id), "affectation_id": str(aff.id)})
    db.commit()
    ext = "." + audio.nom_fichier.rsplit(".", 1)[-1] if "." in audio.nom_fichier else ""
    return stream_response(chunks, f"Audio_{d.reference}{ext}", audio.mime_type or "application/octet-stream",
                           audio.taille_octets)


@router.post("/missions/{affectation_id}/livraisons", status_code=201)
async def deposer_pv(affectation_id: uuid.UUID, db: DbDep, user: User = Depends(require_prestataire),
                     file: UploadFile = File(...), commentaire: Optional[str] = Form(default=None)):
    aff = _aff(db, user, affectation_id)
    d = get_dossier(db, aff.dossier_id, lock=True)
    if aff.statut not in TRAVAIL or d.statut_production not in (wf.ATTRIBUE, wf.EN_COURS, wf.LIVRE, wf.CORRECTION_DEMANDEE):
        raise HTTPException(status_code=409, detail="Le dépôt n'est pas possible à cette étape (relecture en cours)")
    content = await lire_docx(file)
    etait_correction = d.statut_production == wf.CORRECTION_DEMANDEE
    liv = deposer(db, d, user, content, file.filename or "", aff, "depot_prestataire", commentaire)
    if d.statut_production == wf.ATTRIBUE:
        wf.changer_production(db, d, wf.EN_COURS, user.id, "dépôt direct")
    wf.changer_production(db, d, wf.LIVRE, user.id, f"dépôt de la version {liv.version}")
    aff.statut = StatutAffectationEnum.LIVRE
    if etait_correction:
        for c in db.query(DemandeCorrection).filter(DemandeCorrection.affectation_id == aff.id,
                                                    DemandeCorrection.resolue_le.is_(None)).all():
            c.resolue_le = now()
            c.resolue_par_livraison_id = liv.id
    titre = (f"Nouvelle version déposée : {d.reference}" if etait_correction or liv.version > 1
             else f"PV livré : {d.reference}")
    alerte = "" if liv.statut_controle in ("conforme", "avertissements") else " ⚠ Contrôle de conformité : non conforme."
    notifier(db, internes(db, "relecture"), "pv_livre", titre,
             f"Version {liv.version} déposée par {user.nom}.{alerte}", lien=f"/dossiers/{d.id}",
             dossier_id=d.id, dedup_key=f"livraison:{liv.id}")
    db.commit()
    return _mission(db, aff, user)


@router.get("/livraisons/{livraison_id}/fichier")
def telecharger_ma_version(livraison_id: uuid.UUID, db: DbDep, user: User = Depends(require_prestataire)):
    l = db.query(Livraison).filter(Livraison.id == livraison_id).first()
    if not l or l.depose_par_id != user.id or l.type_depot != "depot_prestataire":
        raise HTTPException(status_code=404, detail="Version introuvable")
    content = storage.load_pv(db, l.stockage, l.stockage_ref, l.drive_id)
    return bytes_response(content, l.nom_original, DOCX_MIME)
