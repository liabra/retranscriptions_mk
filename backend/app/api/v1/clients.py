import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, require_permission
from app.core.permissions import has_permission
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut

router = APIRouter()


@router.get("", response_model=List[ClientOut])
def list_clients(
    db: DbDep,
    _user: User = Depends(require_permission("dossiers.voir", "clients.gerer", "finance.voir", "audios.gerer")),
    actif_only: bool = True,
):
    q = db.query(Client)
    if actif_only:
        q = q.filter(Client.actif == True)
    return q.order_by(Client.nom).all()


@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    payload: ClientCreate,
    db: DbDep,
    _user: User = Depends(require_permission("clients.gerer")),
):
    if payload.grille_tarifaire_id and not has_permission(_user, "tarifs.gerer"):
        raise HTTPException(status_code=403, detail="Attribuer un tarif négocié requiert le droit de gérer les tarifs")
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: uuid.UUID,
    db: DbDep,
    _user: User = Depends(require_permission("dossiers.voir", "clients.gerer", "finance.voir")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return ClientOut.model_validate(client)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    db: DbDep,
    _user: User = Depends(require_permission("clients.gerer")),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    if "grille_tarifaire_id" in payload.model_fields_set and payload.grille_tarifaire_id != client.grille_tarifaire_id \
            and not has_permission(_user, "tarifs.gerer"):
        raise HTTPException(status_code=403, detail="Attribuer un tarif négocié requiert le droit de gérer les tarifs")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)
