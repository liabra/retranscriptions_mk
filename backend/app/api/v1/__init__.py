from fastapi import APIRouter

from app.api.v1 import (
    auth, clients, prestataires, dossiers, affectations, grilles, calculs, factures, paiements,
    journal_api, audios, livraisons, espace_prestataire, espace_client, notifications_api, dashboard, tarifs, parametres,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(dashboard.router, tags=["dashboard"])
router.include_router(clients.router, prefix="/clients", tags=["clients"])
router.include_router(prestataires.router, prefix="/prestataires", tags=["prestataires"])
router.include_router(dossiers.router, prefix="/dossiers", tags=["dossiers"])
router.include_router(audios.router, tags=["audios"])
router.include_router(affectations.router, tags=["attribution"])
router.include_router(livraisons.router, tags=["livraisons"])
router.include_router(espace_prestataire.router, tags=["espace prestataire"])
router.include_router(espace_client.router, tags=["espace client"])
router.include_router(grilles.router, tags=["grilles"])
router.include_router(tarifs.router, tags=["tarifs"])
router.include_router(parametres.router, tags=["paramètres"])
router.include_router(calculs.router, tags=["calculs"])
router.include_router(factures.router, tags=["factures"])
router.include_router(paiements.router, tags=["paiements"])
router.include_router(journal_api.router, tags=["journal"])
router.include_router(notifications_api.router, tags=["notifications"])
