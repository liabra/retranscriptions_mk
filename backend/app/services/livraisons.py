"""Dépôt d'une version de PV (prestataire ou correction interne)."""
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.affectation import Affectation
from app.models.client import Client
from app.models.dossier import Dossier
from app.models.journal import TypeActionEnum
from app.models.refonte import Livraison
from app.models.user import User
from app.services import storage
from app.services.docx_check import controler_docx, DocxInvalide
from app.services.journal import log_action


async def lire_docx(file: UploadFile) -> bytes:
    max_bytes = settings.MAX_DOCX_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (maximum {settings.MAX_DOCX_MB} Mo)")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")
    return content


def deposer(
    db: Session, dossier: Dossier, user: User, content: bytes, filename: str,
    affectation: Optional[Affectation], type_depot: str, commentaire: Optional[str],
) -> Livraison:
    try:
        rapport = controler_docx(content, filename)
    except DocxInvalide as exc:
        log_action(db, TypeActionEnum.ACCES_DOCUMENT, dossier_id=dossier.id, utilisateur_id=user.id,
                   detail={"action": "depot_refuse", "raison": str(exc)[:300]})
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))
    version = (db.query(func.max(Livraison.version)).filter(Livraison.dossier_id == dossier.id).scalar() or 0) + 1
    client = db.query(Client).filter(Client.id == dossier.client_id).first()
    suffixe = "corrige_interne" if type_depot == "correction_interne" else "retranscription"
    nom_stockage = f"PV_{dossier.reference}_v{version}_{suffixe}.docx"
    stockage_type, ref, drive_id = storage.save_pv(
        db, content, storage.dossier_folder(client.nom if client else None, dossier.reference), nom_stockage)
    liv = Livraison(
        dossier_id=dossier.id, affectation_id=affectation.id if affectation else None, version=version,
        type_depot=type_depot, nom_original=(filename or nom_stockage)[:500], taille_octets=len(content),
        sha256=storage.sha256(content), stockage=stockage_type, stockage_ref=ref, drive_id=drive_id,
        statut_controle=rapport.statut, rapport_controle=rapport.to_dict(),
        pages_declarees=rapport.pages_declarees, commentaire=(commentaire or None) and commentaire[:2000],
        depose_par_id=user.id,
    )
    db.add(liv)
    db.flush()
    log_action(db, TypeActionEnum.ACCES_DOCUMENT, dossier_id=dossier.id, utilisateur_id=user.id, detail={
        "action": "depot_pv", "livraison_id": str(liv.id), "version": version, "type": type_depot,
        "controle": rapport.statut, "sha256": liv.sha256, "stockage": stockage_type,
    })
    return liv
