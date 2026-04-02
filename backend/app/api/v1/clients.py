import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import DbDep, CurrentUser, require_admin_or_coordinator
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut

router = APIRouter()


@router.get("/", response_model=List[ClientOut])
def list_clients(
    db: DbDep,
    _user: User = Depends(require_admin_or_coordinator),
    actif_only: bool = True,
):
    q = db.query(Client)
    if actif_only:
        q = q.filter(Client.actif == True)
    return q.order_by(Client.nom).all()


@router.post("/", response_model=ClientOut, status_code=201)
def create_client(
    payload: ClientCreate,
    db: DbDep,
    _user: User = Depends(require_admin_or_coordinator),
):
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: uuid.UUID,
    db: DbDep,
    _user: User = Depends(require_admin_or_coordinator),
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
    _user: User = Depends(require_admin_or_coordinator),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)
