import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_

from app.api.v1.common import get_dossier, dossier_resume, audio_public, livraison_out, correction_out, now
from app.core.deps import DbDep, require_permission, client_ip
from app.core.permissions import has_permission
from app.models.affectation import Affectation
from app.models.client import Client
from app.models.dossier import Dossier, TypeInstanceEnum, NiveauConfidentialiteEnum
from app.models.facture import FactureClient
from app.models.journal import TypeActionEnum
from app.models.prestataire import Prestataire
from app.models.refonte import AudioSource, Livraison, DemandeCorrection
from app.models.user import User
from app.services import workflow as wf
from app.services import delais
from app.services.dossier import generate_reference
from app.services.journal import log_action

router = APIRouter()


class CriteresTarif(BaseModel):
    urgence: bool = False
    sans_prise_de_note: bool = False
    prestation_speciale: bool = False
    type_prestation_speciale: Optional[str] = Field(default=None, max_length=200)
    volume_estime_pages: Optional[Decimal] = Field(default=None, ge=0, le=5000)


class DossierCreate(BaseModel):
    type_instance: TypeInstanceEnum
    client_id: uuid.UUID
    payeur_id: Optional[uuid.UUID] = None
    titre: Optional[str] = Field(default=None, max_length=500)
    date_seance: Optional[date] = None
    date_reception_audio: Optional[datetime] = None
    date_limite: Optional[date] = None
    duree_audio_minutes: Optional[int] = Field(default=None, ge=0, le=6000)
    niveau_confidentialite: NiveauConfidentialiteEnum = NiveauConfidentialiteEnum.STANDARD
    notes_internes: Optional[str] = Field(default=None, max_length=10000)
    audio_id: Optional[uuid.UUID] = None
    criteres_tarif: Optional[CriteresTarif] = None
    qualifier: bool = False  # True = qualification immédiate (passe « à attribuer »)


class DossierUpdate(BaseModel):
    titre: Optional[str] = Field(default=None, max_length=500)
    notes_internes: Optional[str] = Field(default=None, max_length=10000)
    date_seance: Optional[date] = None
    date_limite: Optional[date] = None
    niveau_confidentialite: Optional[NiveauConfidentialiteEnum] = None
    duree_audio_minutes: Optional[int] = Field(default=None, ge=0, le=6000)
    type_instance: Optional[TypeInstanceEnum] = None
    client_id: Optional[uuid.UUID] = None
    payeur_id: Optional[uuid.UUID] = None


class Qualification(BaseModel):
    criteres_tarif: CriteresTarif
    date_limite: Optional[date] = None
    duree_audio_minutes: Optional[int] = Field(default=None, ge=0, le=6000)


class Motif(BaseModel):
    motif: str = Field(min_length=3, max_length=1000)


class Urgence(BaseModel):
    urgent: bool


# Étapes où l'échéance calculée suit encore les caractéristiques du dossier (non engagé)
_AVANT_ATTRIBUTION = (wf.A_QUALIFIER, wf.A_ATTRIBUER)


def _urgent(db, d: Dossier) -> bool:
    return delais.est_urgent(db, d.date_limite) or bool((d.criteres_tarif or {}).get("urgence"))


def _client_or_400(db, client_id):
    c = db.query(Client).filter(Client.id == client_id, Client.actif == True).first()  # noqa: E712
    if not c:
        raise HTTPException(status_code=400, detail="Client introuvable ou inactif")
    return c


@router.get("")
def list_dossiers(
    db: DbDep,
    _u: User = Depends(require_permission("dossiers.voir")),
    production: Optional[str] = Query(default=None, description="statuts séparés par des virgules"),
    facturation: Optional[str] = None,
    retard: bool = False,
    urgent: bool = False,
    client_id: Optional[uuid.UUID] = None,
    prestataire_id: Optional[uuid.UUID] = None,
    q: Optional[str] = Query(default=None, max_length=100),
    archives: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(Dossier).filter(Dossier.supprime_le.is_(None))
    if production:
        statuts = [s for s in production.split(",") if s in wf.PRODUCTION_LABELS]
        query = query.filter(Dossier.statut_production.in_(statuts))
    elif not archives:
        query = query.filter(Dossier.statut_production != wf.ARCHIVE)
    if facturation:
        statuts = [s for s in facturation.split(",") if s in wf.FACTURATION_LABELS]
        query = query.filter(Dossier.statut_facturation.in_(statuts))
    if urgent:
        query = query.filter(Dossier.est_urgent == True)  # noqa: E712
    if client_id:
        query = query.filter(Dossier.client_id == client_id)
    if prestataire_id:
        sub = db.query(Affectation.dossier_id).filter(Affectation.prestataire_id == prestataire_id)
        query = query.filter(Dossier.id.in_(sub))
    if q:
        like = f"%{q.strip()}%"  # paramètre lié, pas de concaténation SQL
        query = query.filter(or_(Dossier.reference.ilike(like), Dossier.titre.ilike(like)))
    query = query.order_by(Dossier.est_urgent.desc(), Dossier.date_limite.asc().nullslast(),
                           Dossier.created_at.desc())
    if retard:
        items = [dossier_resume(db, d) for d in query.all()]
        items = [i for i in items if i["en_retard"]]
        return {"total": len(items), "items": items[offset:offset + limit]}
    total = query.count()
    return {"total": total, "items": [dossier_resume(db, d) for d in query.offset(offset).limit(limit).all()]}


@router.post("", status_code=201)
def create_dossier(payload: DossierCreate, request: Request, db: DbDep,
                   user: User = Depends(require_permission("dossiers.gerer"))):
    _client_or_400(db, payload.client_id)
    if payload.payeur_id:
        _client_or_400(db, payload.payeur_id)
    audio = None
    if payload.audio_id:
        audio = db.query(AudioSource).filter(AudioSource.id == payload.audio_id).with_for_update().first()
        if not audio or audio.dossier_id or audio.statut == "ignore":
            raise HTTPException(status_code=400, detail="Audio introuvable ou déjà associé à un dossier")
    if payload.qualifier and not payload.criteres_tarif:
        raise HTTPException(status_code=400, detail="Les critères de tarification sont requis pour qualifier")
    dossier = Dossier(
        reference=generate_reference(db, payload.type_instance),
        type_instance=payload.type_instance,
        client_id=payload.client_id,
        payeur_id=payload.payeur_id or payload.client_id,
        titre=payload.titre,
        date_seance=payload.date_seance,
        date_reception_audio=payload.date_reception_audio or (audio.created_at if audio else now()),
        date_limite=payload.date_limite,
        duree_audio_minutes=payload.duree_audio_minutes or (audio.duree_minutes if audio else None),
        niveau_confidentialite=payload.niveau_confidentialite,
        notes_internes=payload.notes_internes,
        criteres_tarif=payload.criteres_tarif.model_dump(mode="json") if payload.criteres_tarif else None,
        echeance_mode="manuelle" if payload.date_limite else "calculee",
        statut_production=wf.A_QUALIFIER,
        statut_facturation=wf.F_NON_APPLICABLE,
    )
    dossier.statut = wf._LEGACY[wf.A_QUALIFIER]
    if not payload.date_limite:
        delais.appliquer_echeance(db, dossier)  # réception de l'audio + délai paramétré
    dossier.est_urgent = _urgent(db, dossier)
    db.add(dossier)
    db.flush()
    log_action(db, TypeActionEnum.CREATION, dossier_id=dossier.id, utilisateur_id=user.id,
               ip_source=client_ip(request),
               detail={"reference": dossier.reference, "type_instance": payload.type_instance.value,
                       "audio_id": str(audio.id) if audio else None})
    delais.tracer(db, dossier, user.id, "echeance_initiale", None, None,
                  "saisie à la création" if payload.date_limite else "calculée à réception de l'audio")
    if audio:
        audio.dossier_id = dossier.id
        audio.client_id = payload.client_id
        audio.statut = "associe"
    if payload.qualifier:
        wf.changer_production(db, dossier, wf.A_ATTRIBUER, user.id, "qualification à la création")
    db.commit()
    return detail(dossier.id, db, user)


@router.get("/{dossier_id}")
def detail(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("dossiers.voir"))):
    d = get_dossier(db, dossier_id)
    out = dossier_resume(db, d)
    affs = db.query(Affectation).filter(Affectation.dossier_id == d.id).order_by(Affectation.date_attribution).all()
    prestas = {p.id: p.nom for p in db.query(Prestataire).filter(
        Prestataire.id.in_([a.prestataire_id for a in affs])).all()} if affs else {}
    payeur = db.query(Client).filter(Client.id == d.payeur_id).first() if d.payeur_id else None
    out.update({
        "payeur_id": str(d.payeur_id) if d.payeur_id else None,
        "payeur_nom": payeur.nom if payeur else None,
        "date_reception_audio": d.date_reception_audio,
        "niveau_confidentialite": d.niveau_confidentialite.value,
        "notes_internes": d.notes_internes,
        "criteres_tarif": d.criteres_tarif,
        "nombre_pages_final": d.nombre_pages_final,
        "motif_blocage": d.motif_blocage,
        "statut_avant_blocage": d.statut_avant_blocage,
        "valide_le": d.valide_le,
        "echeance_mode": d.echeance_mode,
        "echeance_figee_le": d.echeance_figee_le,
        "echeance_detail": d.echeance_detail,
        "transitions_possibles": sorted(wf.PRODUCTION_TRANSITIONS.get(d.statut_production, set())),
        "audio": audio_public(db.query(AudioSource).filter(AudioSource.dossier_id == d.id)
                              .order_by(AudioSource.created_at.desc()).first()),
        "affectations": [{
            "id": str(a.id), "prestataire_id": str(a.prestataire_id),
            "prestataire_nom": prestas.get(a.prestataire_id), "statut": a.statut.value,
            "type_role": a.type_role.value, "date_attribution": a.date_attribution,
            "date_limite_rendu": a.date_limite_rendu, "date_rendu_effectif": a.date_rendu_effectif,
            "commentaire": a.commentaire,
        } for a in affs],
        "livraisons": [livraison_out(l) for l in db.query(Livraison).filter(Livraison.dossier_id == d.id)
                       .order_by(Livraison.version.desc()).all()],
        "corrections": [correction_out(c) for c in db.query(DemandeCorrection).filter(
            DemandeCorrection.dossier_id == d.id).order_by(DemandeCorrection.created_at.desc()).all()],
        "acces_finance": has_permission(user, "finance.voir"),
    })
    return out


@router.patch("/{dossier_id}")
def update_dossier(dossier_id: uuid.UUID, payload: DossierUpdate, db: DbDep,
                   user: User = Depends(require_permission("dossiers.gerer"))):
    d = get_dossier(db, dossier_id)
    if d.statut_production == wf.ARCHIVE:
        raise HTTPException(status_code=409, detail="Un dossier archivé n'est plus modifiable")
    changes = payload.model_dump(exclude_unset=True)
    facture = db.query(FactureClient).filter(FactureClient.dossier_id == d.id,
                                             FactureClient.annulee_le.is_(None)).first()
    if facture and {"client_id", "payeur_id", "type_instance"} & set(changes):
        raise HTTPException(status_code=409, detail="Client, payeur et instance sont figés après facturation")
    for key in ("client_id", "payeur_id"):
        if changes.get(key):
            _client_or_400(db, changes[key])
    if "date_limite" in changes and not changes["date_limite"] and d.echeance_figee_le:
        raise HTTPException(status_code=409, detail="Échéance figée depuis l'attribution : saisissez une nouvelle date")
    ancienne, mode_avant = d.date_limite, d.echeance_mode
    for field, value in changes.items():
        setattr(d, field, value)
    if "date_limite" in changes:
        if changes["date_limite"]:
            d.echeance_mode, d.echeance_detail = "manuelle", None
            delais.tracer(db, d, user.id, "echeance_modifiee", ancienne, mode_avant, "modification manuelle")
        else:
            delais.appliquer_echeance(db, d)  # échéance effacée : retour au calcul automatique
            delais.tracer(db, d, user.id, "echeance_recalculee", ancienne, mode_avant, "retour au calcul automatique")
    elif delais.recalculable(d) and {"duree_audio_minutes", "type_instance"} & set(changes):
        delais.appliquer_echeance(db, d)
        delais.tracer(db, d, user.id, "echeance_recalculee", ancienne, mode_avant, "caractéristiques du dossier modifiées")
    if not d.urgence_forcee:
        d.est_urgent = _urgent(db, d)
    log_action(db, TypeActionEnum.NOTE, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "modification", "champs": sorted(changes)})
    db.commit()
    return detail(d.id, db, user)


@router.post("/{dossier_id}/qualifier")
def qualifier(dossier_id: uuid.UUID, payload: Qualification, db: DbDep,
              user: User = Depends(require_permission("dossiers.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    if d.statut_production not in (wf.A_QUALIFIER, wf.A_ATTRIBUER):
        raise HTTPException(status_code=409, detail="La qualification n'est possible qu'avant l'attribution")
    d.criteres_tarif = payload.criteres_tarif.model_dump(mode="json")
    if payload.duree_audio_minutes is not None:
        d.duree_audio_minutes = payload.duree_audio_minutes
    ancienne, mode_avant = d.date_limite, d.echeance_mode
    if payload.date_limite:
        d.date_limite, d.echeance_mode, d.echeance_detail = payload.date_limite, "manuelle", None
        delais.tracer(db, d, user.id, "echeance_modifiee", ancienne, mode_avant, "saisie à la qualification")
    elif delais.recalculable(d):
        delais.appliquer_echeance(db, d)
        delais.tracer(db, d, user.id, "echeance_recalculee", ancienne, mode_avant, "qualification")
    if not d.urgence_forcee:
        d.est_urgent = _urgent(db, d)
    if d.statut_production == wf.A_QUALIFIER:
        wf.changer_production(db, d, wf.A_ATTRIBUER, user.id, "qualification",
                              {"criteres": d.criteres_tarif})
    else:
        log_action(db, TypeActionEnum.NOTE, dossier_id=d.id, utilisateur_id=user.id,
                   detail={"action": "requalification", "criteres": d.criteres_tarif})
    db.commit()
    return detail(d.id, db, user)


@router.post("/{dossier_id}/echeance/recalculer")
def recalculer_echeance(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("dossiers.gerer"))):
    """Remplace une échéance saisie à la main par l'échéance calculée — uniquement avant attribution."""
    d = get_dossier(db, dossier_id, lock=True)
    if d.echeance_figee_le or d.statut_production not in _AVANT_ATTRIBUTION:
        raise HTTPException(status_code=409, detail="Échéance figée depuis l'attribution : seule une modification "
                                                    "manuelle est possible")
    ancienne, mode_avant = d.date_limite, d.echeance_mode
    if not delais.appliquer_echeance(db, d):
        raise HTTPException(status_code=409, detail="Aucune règle de délai ne correspond à ce dossier : "
                                                    "complétez les délais dans les paramètres ou saisissez l'échéance")
    if not d.urgence_forcee:
        d.est_urgent = _urgent(db, d)
    delais.tracer(db, d, user.id, "echeance_recalculee", ancienne, mode_avant, "retour au calcul automatique")
    db.commit()
    return detail(d.id, db, user)


@router.post("/{dossier_id}/urgence")
def urgence(dossier_id: uuid.UUID, payload: Urgence, db: DbDep,
            user: User = Depends(require_permission("dossiers.gerer"))):
    d = get_dossier(db, dossier_id)
    d.est_urgent = payload.urgent
    d.urgence_forcee = payload.urgent
    log_action(db, TypeActionEnum.STATUT, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "urgence", "valeur": payload.urgent})
    db.commit()
    return detail(d.id, db, user)


@router.post("/{dossier_id}/bloquer")
def bloquer(dossier_id: uuid.UUID, payload: Motif, db: DbDep,
            user: User = Depends(require_permission("dossiers.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    wf.bloquer(db, d, user.id, payload.motif)
    db.commit()
    return detail(d.id, db, user)


@router.post("/{dossier_id}/debloquer")
def debloquer(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("dossiers.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    wf.debloquer(db, d, user.id)
    db.commit()
    return detail(d.id, db, user)


@router.post("/{dossier_id}/archiver")
def archiver(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("dossiers.gerer"))):
    d = get_dossier(db, dossier_id, lock=True)
    resume = dossier_resume(db, d)
    wf.changer_production(db, d, wf.ARCHIVE, user.id, "archivage")
    d.archive_snapshot = {
        "archive_le": now().isoformat(), "par": str(user.id),
        "reference": d.reference, "client": resume["client_nom"], "type_instance": resume["type_instance"],
        "retranscripteur": resume["retranscripteur"], "statut_facturation": d.statut_facturation,
        "nombre_pages_final": str(d.nombre_pages_final) if d.nombre_pages_final is not None else None,
        "livraisons": [{"version": l.version, "sha256": l.sha256, "depose_le": l.depose_le.isoformat()}
                       for l in db.query(Livraison).filter(Livraison.dossier_id == d.id).all()],
    }
    log_action(db, TypeActionEnum.ARCHIVAGE, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "archivage"})
    db.commit()
    return detail(d.id, db, user)


@router.delete("/{dossier_id}", status_code=204)
def supprimer(dossier_id: uuid.UUID, db: DbDep, user: User = Depends(require_permission("dossiers.gerer"))):
    """fix B3 : suppression LOGIQUE ; le journal et l'historique sont conservés."""
    d = get_dossier(db, dossier_id, lock=True)
    if d.statut_production not in (wf.A_QUALIFIER, wf.A_ATTRIBUER, wf.BLOQUE):
        raise HTTPException(status_code=409, detail="Seul un dossier non attribué peut être supprimé")
    if db.query(FactureClient).filter(FactureClient.dossier_id == d.id).first():
        raise HTTPException(status_code=409, detail="Un dossier facturé ne peut pas être supprimé")
    d.supprime_le = now()
    for audio in db.query(AudioSource).filter(AudioSource.dossier_id == d.id).all():
        audio.dossier_id = None
        audio.statut = "a_traiter"
    log_action(db, TypeActionEnum.ARCHIVAGE, dossier_id=d.id, utilisateur_id=user.id,
               detail={"action": "suppression_logique", "reference": d.reference})
    db.commit()
