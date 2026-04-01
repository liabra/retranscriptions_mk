import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import RoleEnum


class UserCreate(BaseModel):
    email: EmailStr
    nom: str
    password: str
    role: RoleEnum


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    nom: str
    role: RoleEnum
    actif: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
