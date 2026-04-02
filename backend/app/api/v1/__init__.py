from fastapi import APIRouter

from app.api.v1 import auth, clients, prestataires, dossiers, affectations, fichiers

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(clients.router, prefix="/clients", tags=["clients"])
router.include_router(prestataires.router, prefix="/prestataires", tags=["prestataires"])
router.include_router(dossiers.router, prefix="/dossiers", tags=["dossiers"])
router.include_router(affectations.router, tags=["affectations"])
router.include_router(fichiers.router, tags=["fichiers"])
