import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.user import RoleEnum


class UserCreate(BaseModel):
    email: EmailStr
    nom: str
    password: str
    role: RoleEnum


class UserUpdate(BaseModel):
    nom: Optional[str] = None
    role: Optional[RoleEnum] = None
    actif: Optional[bool] = None
    password: Optional[str] = None  # reset mot de passe


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    nom: str
    role: RoleEnum
    actif: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
