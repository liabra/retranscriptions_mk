"""
Espace client (conservé, périmètre volontairement réduit) :
suivi de ses propres dossiers et dépôt d'un audio. Aucune donnée interne ou financière.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.v1.audios import enregistrer_fichier_audio
from app.core.deps import DbDep, require_client
from app.core.config import settings
from app.models.dossier import Dossier
from app.models.refonte import AudioSource
from app.models.user import User
from app.services.notifications import notifier, internes

router = APIRouter(prefix="/espace-client")

_ETAPES_CLIENT = {
    "a_qualifier": "Reçu", "a_attribuer": "En préparation", "attribue": "En cours de retranscription",
    "en_cours": "En cours de retranscription", "livre": "En relecture", "a_relire": "En relecture",
    "correction_demandee": "En relecture", "a_controler": "En relecture", "valide": "Terminé",
    "archive": "Terminé", "bloque": "En attente",
}


@router.get("/dossiers")
def mes_dossiers(db: DbDep, user: User = Depends(require_client)):
    # fix S5 : uniquement les dossiers du client lié au compte (FK), jamais par identifiant libre
    rows = db.query(Dossier).filter(Dossier.client_id == user.client_id, Dossier.supprime_le.is_(None)) \
        .order_by(Dossier.created_at.desc()).limit(200).all()
    return [{"reference": d.reference, "titre": d.titre, "type_instance": d.type_instance.value,
             "date_seance": d.date_seance, "etape": _ETAPES_CLIENT.get(d.statut_production, "En cours"),
             "created_at": d.created_at} for d in rows]


@router.get("/audios")
def mes_depots(db: DbDep, user: User = Depends(require_client)):
    rows = db.query(AudioSource).filter(AudioSource.client_id == user.client_id,
                                        AudioSource.ajoute_par_id == user.id) \
        .order_by(AudioSource.created_at.desc()).limit(100).all()
    return [{"id": str(a.id), "nom_fichier": a.nom_fichier, "taille_octets": a.taille_octets,
             "created_at": a.created_at, "pris_en_charge": a.statut == "associe"} for a in rows]


@router.post("/audios", status_code=201)
async def deposer_audio(db: DbDep, user: User = Depends(require_client), file: UploadFile = File(...),
                        commentaire: Optional[str] = Form(default=None)):
    a = await enregistrer_fichier_audio(db, user, file, user.client_id, None, "depot_client")
    notifier(db, internes(db, "audios.gerer"), "nouvel_audio", f"Audio déposé par {user.nom}",
             (commentaire or "")[:500] or None, lien="/audios")
    db.commit()
    return {"id": str(a.id), "nom_fichier": a.nom_fichier, "created_at": a.created_at,
            "taille_max_mo": settings.MAX_AUDIO_MB}
